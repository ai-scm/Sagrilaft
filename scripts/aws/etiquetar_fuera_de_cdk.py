#!/usr/bin/env python3
"""Etiqueta los recursos de SAGRILAFT que viven fuera de CDK.

Aplica el criterio de docs/produccion/configuracion/ETIQUETADO_AWS.md a lo que el
despliegue de CDK no puede etiquetar:

  - alarmas TargetTracking-* del autoescalado del backend  -> backend / autoescalado
  - secreto zoho_credentials importado (solo si no es de CDK) -> secretos / manual
  - parámetros SSM creados a mano (p. ej. PORTAL_URL)        -> configuracion / manual
  - snapshots manuales de RDS de la base del ambiente         -> base-datos / manual
  - logs de Container Insights del cluster                    -> plataforma-contenedores
  - zona privada sagrilaft-<ambiente>.local de Cloud Map      -> plataforma-contenedores

Qué hace y qué no:
  - Solo AGREGA o corrige las claves Project, Environment, Component y ManagedBy.
    No borra etiquetas, no modifica ni elimina recursos.
  - Nunca toca recursos que CloudFormation administra (eso lo hace CDK), salvo los
    snapshots, que solo llevan copia de las etiquetas de la base.
  - Se puede repetir: lo que ya está bien se salta. Conviene correrlo después de
    cada despliegue, porque AWS recrea las alarmas del autoescalado.

Modo por defecto: simulación (solo lee AWS y muestra qué haría).
Para escribir: --apply --expected-account <cuenta>. En prod además --confirmo-prod.

Ejemplo:
  python3 scripts/aws/etiquetar_fuera_de_cdk.py --env staging \\
    --profile PS-PowerUserAccess-874641912777
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable

import boto3

REGION = "us-east-1"
CLAVES = ("Project", "Environment", "Component", "ManagedBy")
MARCA_CFN = "aws:cloudformation:stack-name"


@dataclass
class Recurso:
    tipo: str
    nombre: str
    actuales: dict[str, str]
    deseadas: dict[str, str]
    aplicar: Callable[[dict[str, str]], None] = field(repr=False)

    def faltantes(self) -> dict[str, str]:
        return {k: v for k, v in self.deseadas.items() if self.actuales.get(k) != v}


def etiquetas(env: str, componente: str, administrado: str | None) -> dict[str, str]:
    t = {"Project": "sagrilaft", "Environment": env, "Component": componente}
    if administrado:
        t["ManagedBy"] = administrado
    return t


def a_lista(t: dict[str, str]) -> list[dict[str, str]]:
    return [{"Key": k, "Value": v} for k, v in t.items()]


def de_lista(tags: list[dict[str, str]]) -> dict[str, str]:
    return {x["Key"]: x["Value"] for x in tags}


def alarmas(s, env: str) -> list[Recurso]:
    cw = s.client("cloudwatch")
    prefijo = f"TargetTracking-service/sagrilaft-{env}/SagrilaftStack-{env}-"
    salida = []
    for pagina in cw.get_paginator("describe_alarms").paginate(AlarmNamePrefix=prefijo):
        for a in pagina["MetricAlarms"]:
            arn = a["AlarmArn"]
            actuales = de_lista(cw.list_tags_for_resource(ResourceARN=arn)["Tags"])
            salida.append(Recurso(
                "alarma autoescalado", a["AlarmName"], actuales,
                etiquetas(env, "backend", "autoescalado"),
                lambda t, arn=arn: cw.tag_resource(ResourceARN=arn, Tags=a_lista(t)),
            ))
    return salida


def secretos(s, env: str) -> list[Recurso]:
    sm = s.client("secretsmanager")
    nombre = f"sagrilaft/{env}/zoho_credentials"
    try:
        d = sm.describe_secret(SecretId=nombre)
    except sm.exceptions.ResourceNotFoundException:
        return []
    actuales = de_lista(d.get("Tags", []))
    if MARCA_CFN in actuales:  # lo crea CDK (staging): ya está etiquetado allá
        return []
    return [Recurso(
        "secreto", nombre, actuales, etiquetas(env, "secretos", "manual"),
        lambda t: sm.tag_resource(SecretId=d["ARN"], Tags=a_lista(t)),
    )]


def parametros(s, env: str) -> list[Recurso]:
    ssm = s.client("ssm")
    filtro = [{"Key": "Name", "Option": "BeginsWith", "Values": [f"/sagrilaft/{env}/"]}]
    salida = []
    for pagina in ssm.get_paginator("describe_parameters").paginate(ParameterFilters=filtro):
        for p in pagina["Parameters"]:
            nombre = p["Name"]
            actuales = de_lista(ssm.list_tags_for_resource(
                ResourceType="Parameter", ResourceId=nombre)["TagList"])
            if MARCA_CFN in actuales:
                continue
            salida.append(Recurso(
                "parámetro SSM", nombre, actuales, etiquetas(env, "configuracion", "manual"),
                lambda t, n=nombre: ssm.add_tags_to_resource(
                    ResourceType="Parameter", ResourceId=n, Tags=a_lista(t)),
            ))
    return salida


def snapshots(s, env: str) -> list[Recurso]:
    rds = s.client("rds")
    # Doble condición: la cuenta tiene snapshots de otros proyectos.
    nombre_snapshot = f"sagrilaft-{env}-"
    instancia_del_stack = f"sagrilaftstack-{env}-"
    salida = []
    for pagina in rds.get_paginator("describe_db_snapshots").paginate(SnapshotType="manual"):
        for sn in pagina["DBSnapshots"]:
            if not (sn["DBSnapshotIdentifier"].startswith(nombre_snapshot)
                    and sn["DBInstanceIdentifier"].startswith(instancia_del_stack)):
                continue
            arn = sn["DBSnapshotArn"]
            salida.append(Recurso(
                "snapshot manual RDS", sn["DBSnapshotIdentifier"], de_lista(sn.get("TagList", [])),
                etiquetas(env, "base-datos", "manual"),
                lambda t, arn=arn: rds.add_tags_to_resource(ResourceName=arn, Tags=a_lista(t)),
            ))
    return salida


def logs_container_insights(s, env: str) -> list[Recurso]:
    logs = s.client("logs")
    salida = []
    prefijo = f"/aws/ecs/containerinsights/sagrilaft-{env}/"
    for pagina in logs.get_paginator("describe_log_groups").paginate(logGroupNamePrefix=prefijo):
        for g in pagina["logGroups"]:
            arn = g["arn"].removesuffix(":*")
            actuales = logs.list_tags_for_resource(resourceArn=arn)["tags"]
            if MARCA_CFN in actuales:
                continue
            # Lo crea ECS: sin ManagedBy (ver tabla "Recursos fuera de CDK").
            salida.append(Recurso(
                "logs Container Insights", g["logGroupName"], actuales,
                etiquetas(env, "plataforma-contenedores", None),
                lambda t, arn=arn: logs.tag_resource(resourceArn=arn, tags=t),
            ))
    return salida


def zona_cloud_map(s, env: str) -> list[Recurso]:
    r53 = s.client("route53")
    nombre = f"sagrilaft-{env}.local."
    salida = []
    for z in r53.list_hosted_zones_by_name(DNSName=nombre)["HostedZones"]:
        if z["Name"] != nombre or not z["Config"].get("PrivateZone"):
            continue
        zid = z["Id"].split("/")[-1]
        actuales = de_lista(r53.list_tags_for_resource(
            ResourceType="hostedzone", ResourceId=zid)["ResourceTagSet"]["Tags"])
        # La crea Cloud Map al crear el espacio de nombres: sin ManagedBy.
        salida.append(Recurso(
            "zona privada Cloud Map", f"{nombre} ({zid})", actuales,
            etiquetas(env, "plataforma-contenedores", None),
            lambda t, zid=zid: r53.change_tags_for_resource(
                ResourceType="hostedzone", ResourceId=zid, AddTags=a_lista(t)),
        ))
    return salida


BUSQUEDAS = (alarmas, secretos, parametros, snapshots, logs_container_insights, zona_cloud_map)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--env", required=True, choices=["staging", "prod"])
    ap.add_argument("--profile", help="perfil de AWS CLI")
    ap.add_argument("--apply", action="store_true", help="escribe las etiquetas (sin esto, simula)")
    ap.add_argument("--expected-account", help="obligatorio con --apply")
    ap.add_argument("--confirmo-prod", action="store_true", help="obligatorio con --apply en prod")
    ap.add_argument("--registro", help="archivo JSON con el antes y el después")
    args = ap.parse_args()

    if args.apply and not args.expected_account:
        ap.error("--apply exige --expected-account")
    if args.apply and args.env == "prod" and not args.confirmo_prod:
        ap.error("--apply en prod exige --confirmo-prod")

    s = boto3.Session(profile_name=args.profile, region_name=REGION)
    cuenta = s.client("sts").get_caller_identity()["Account"]
    if args.apply and cuenta != args.expected_account:
        print(f"Cuenta {cuenta} distinta de la esperada {args.expected_account}. No se hace nada.")
        return 2

    recursos = [r for buscar in BUSQUEDAS for r in buscar(s, args.env)]
    modo = "APLICANDO" if args.apply else "SIMULACIÓN (no se escribe nada)"
    print(f"{modo} — cuenta {cuenta}, ambiente {args.env}, {len(recursos)} recursos encontrados\n")

    registro, pendientes = [], 0
    for r in recursos:
        faltan = r.faltantes()
        estado = "ya está bien" if not faltan else ("etiquetado" if args.apply else "se etiquetaría")
        print(f"[{estado}] {r.tipo}: {r.nombre}")
        if faltan:
            pendientes += 1
            for k, v in faltan.items():
                print(f"    {k}: {r.actuales.get(k, '—')} -> {v}")
            if args.apply:
                r.aplicar(faltan)
        registro.append({"tipo": r.tipo, "nombre": r.nombre,
                         "antes": {k: r.actuales.get(k) for k in CLAVES}, "agregadas": faltan})

    print(f"\n{pendientes} de {len(recursos)} recursos {'etiquetados' if args.apply else 'por etiquetar'}.")
    if args.registro:
        with open(args.registro, "w", encoding="utf-8") as f:
            json.dump({"fecha": datetime.now(timezone.utc).isoformat(), "cuenta": cuenta,
                       "ambiente": args.env, "aplicado": args.apply, "recursos": registro},
                      f, indent=1, ensure_ascii=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
