"""Fase 4: modalidad externa (Tusdatos) de punta a punta sobre PostgreSQL.

HTTP con JWT firmado, admisión, trabajador por etapas con reloj controlado, custodia local
y Tusdatos simulado con las respuestas grabadas del sandbox. Sin red.
"""
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from api import dependencias_listas
from api.middleware import autenticacion
from api.routers import consultas_listas
from infrastructure.config.configuracion import KeycloakConfig, SagrilaftListasConfig
from infrastructure.listas.custodia import CustodiaLocalListas
from infrastructure.listas.tusdatos.cliente import ClienteTusdatos
from infrastructure.listas.tusdatos.configuracion import ConfiguracionTusdatos
from infrastructure.persistencia.models import Formulario
from infrastructure.persistencia.modelos_listas import (
    ConsultaLista, EventoConsulta, EvidenciaConsulta, ProgresoConsultaExterna, TrabajoConsulta,
)
from services.listas import modalidades
from services.listas.modalidad_externa import ModalidadExterna
from services.listas.politica_v2 import PoliticaListasV2
from services.listas.trabajador import TrabajadorListas

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "contracts"))
from soporte_tusdatos import PDF_MINIMO, SimuladorTusdatos  # noqa: E402

JOB_CON_ERROR = "485e9823-df75-4b1e-9f64-58916a82dfd7"
JOB_CON_HALLAZGO = "6460fc34-4154-43db-9438-8c5a059304c0"
REPORTE_CC = "651c2ede72476080772781f5"
REPORTE_CON_ERROR = "d9530d51473cf57e73945088"


@pytest.fixture
def externo(sesiones, tmp_path, monkeypatch):
    configuracion = SagrilaftListasConfig(proveedor=None, implementacion="externo")
    keycloak = KeycloakConfig(url="http://identidad.local", realm="pruebas", client_id="portal")
    clave = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(clave.public_key()))
    jwk.update(kid="clave-local", use="sig", alg="RS256")

    async def claves_locales(_):
        return {"keys": [jwk]}
    monkeypatch.setattr(autenticacion, "_obtener_jwks", claves_locales)
    monkeypatch.setattr(autenticacion, "_AUTH_DESHABILITADA", False)
    simulador = SimuladorTusdatos()
    sandbox = ConfiguracionTusdatos(url_base="http://docs.tusdatos.co", usuario="pruebas", clave="password")
    modalidad = ModalidadExterna(fabrica_cliente=lambda _entorno: ClienteTusdatos(
        sandbox, transporte=simulador.transporte, dormir=lambda _s: None, metricas=lambda *_: None))
    monkeypatch.setitem(modalidades.MODALIDADES, "externo", modalidad)
    aplicacion = FastAPI()
    aplicacion.state.config = SimpleNamespace(keycloak=keycloak, listas_cautela=configuracion, entorno="development")
    aplicacion.include_router(consultas_listas.enrutador)
    custodia = CustodiaLocalListas(tmp_path / "custodia")
    aplicacion.dependency_overrides[dependencias_listas.sesiones_listas] = lambda: sesiones
    aplicacion.dependency_overrides[dependencias_listas.custodia_listas] = lambda: custodia
    expediente_id, otro_id = str(uuid4()), str(uuid4())
    with sesiones.begin() as sesion:
        for identificador in (expediente_id, otro_id):
            sesion.add(Formulario(id=identificador, tipo_contraparte="cliente", estado="enviado", tipo_persona="juridica",
                razon_social="EMPRESA DE PRUEBAS S A S", numero_identificacion="900000152", tipo_identificacion="NIT",
                nombre_representante="MIGUEL FERNANDO PEREZ GOMEZ", numero_doc_representante="111", tipo_doc_representante="CC"))

    def token(*roles):
        return jwt.encode({"sub": "persona-local", "iss": keycloak.issuer, "aud": "portal", "azp": "portal",
                           "exp": datetime.now(timezone.utc) + timedelta(minutes=30),
                           "realm_access": {"roles": ["acceso_clientes", *(roles or ("listas_revisor",))]}},
                          clave, algorithm="RS256", headers={"kid": "clave-local"})
    cliente = TestClient(aplicacion)
    cliente.headers["Authorization"] = f"Bearer {token()}"
    reloj = [datetime.now(timezone.utc)]
    trabajador = TrabajadorListas(sesiones, PoliticaListasV2(configuracion, "development"), custodia, reloj=lambda: reloj[0])
    yield SimpleNamespace(cliente=cliente, sesiones=sesiones, custodia=custodia, simulador=simulador,
                          expediente=expediente_id, otro=otro_id, trabajador=trabajador, reloj=reloj, token=token)
    cliente.close()


def crear(e, tipo="CC", valor="112", clave=None, expediente=None, forzar=False, roles=None, **criterio):
    cuerpo = {"criterio": {"tipo_sujeto": "PERSONA", "identificadores": [{"tipo": tipo, "valor": valor}], **criterio},
              **({"forzar_actualizacion": True} if forzar else {})}
    encabezados = {"Idempotency-Key": clave or str(uuid4())}
    if roles:
        encabezados["Authorization"] = f"Bearer {e.token(*roles)}"
    respuesta = e.cliente.post(f"/api/expedientes/{expediente or e.expediente}/consultas-listas", json=cuerpo,
                               headers=encabezados)
    alinear_reloj(e)
    return respuesta


def alinear_reloj(e):
    # La admisión usa la hora real; el reloj del trabajador nunca debe quedar por detrás.
    e.reloj[0] = max(e.reloj[0], datetime.now(timezone.utc))


def detalle(e, consulta_id):
    respuesta = e.cliente.get(f"/api/consultas-listas/{consulta_id}")
    assert respuesta.status_code == 200, respuesta.text
    return respuesta.json()["consulta"]


def lanzamientos(e):
    return [p for p in e.simulador.peticiones if p.method == "POST" and p.url.path == "/api/launch"]


def procesar(e, paso=20, maximo=100):
    """Ejecuta el trabajador avanzando el reloj, como lo harían las pasadas reales."""
    for _ in range(maximo):
        if not e.trabajador.ejecutar_uno():
            with e.sesiones() as sesion:
                pendientes = sesion.scalar(select(TrabajoConsulta.id).where(TrabajoConsulta.fase != "FINALIZADA").limit(1))
            if pendientes is None:
                return
            e.reloj[0] += timedelta(seconds=paso)
    pytest.fail("El trabajador no terminó")


def progreso(e, consulta_id):
    with e.sesiones() as sesion:
        return sesion.scalar(select(ProgresoConsultaExterna).where(ProgresoConsultaExterna.consulta_id == UUID(consulta_id)))


def eventos(e, consulta_id):
    with e.sesiones() as sesion:
        return [ev.tipo for ev in sesion.scalars(select(EventoConsulta).where(EventoConsulta.consulta_id == UUID(consulta_id))
                                                  .order_by(EventoConsulta.creado_en))]


def error_trabajo(e, consulta_id):
    with e.sesiones() as sesion:
        return sesion.scalar(select(TrabajoConsulta.error).where(TrabajoConsulta.consulta_id == UUID(consulta_id)))


# ── Flujo normal ─────────────────────────────────────────────────────────────

def test_disponibilidad_anuncia_externo_con_contrato_20(externo):
    datos = externo.cliente.get("/api/listas/disponibilidad").json()
    assert datos["consultar"] and datos["implementacion"] == "externo" and datos["version_contrato"] == "2.0"


def test_cc_con_hallazgos_completa_y_solo_guarda_lo_aprobado(externo):
    respuesta = crear(externo, valor="111", fecha_expedicion="2014-12-01")
    assert respuesta.status_code == 202, respuesta.text
    consulta_id = respuesta.json()["consulta_id"]
    procesar(externo)
    consulta = detalle(externo, consulta_id)
    assert consulta["estado_ejecucion"] == "COMPLETADA" and consulta["conclusion_busqueda"] == "CON_CANDIDATOS"
    assert consulta["proveedor"] == "tusdatos" and len(consulta["cobertura"]) == 11
    assert {c["motivos"][0]["campo"] for c in consulta["candidatos"]} >= {"ofac", "peps", "procuraduria"}
    assert [e["tipo"] for e in consulta["evidencias"]] == ["INFORME_INTERNO"]
    # Un solo lanzamiento, con el documento limpio y sin fecha (solo CE la exige).
    assert len(lanzamientos(externo)) == 1
    assert json.loads(lanzamientos(externo)[0].content) == {"doc": "111", "typedoc": "CC", "force": False,
                                                            "webhook_reference": consulta_id}
    guardado = progreso(externo, consulta_id)
    assert guardado.etapa == "TERMINADA" and guardado.reporte_id == REPORTE_CC and len(guardado.huella_respuesta) == 64
    texto = json.dumps(guardado.respuesta_filtrada).casefold()
    assert all(f'"{c}"' not in texto for c in ("sisben", "ruaf", "fosyga", "delitos_sexuales", "simit"))
    # El sandbox no entrega PDF reales: se cierra igual y queda constancia.
    assert "PDF_PROVEEDOR_NO_DISPONIBLE" in eventos(externo, consulta_id)


def test_pdf_del_proveedor_se_custodia_como_evidencia(externo):
    externo.simulador.extras[("GET", f"/api/v2/report_pdf/{REPORTE_CC}")] = [
        httpx.Response(202, json={"status": "processing"}, headers={"Retry-After": "10"}),
        httpx.Response(200, content=PDF_MINIMO, headers={"content-type": "application/pdf"})]
    consulta_id = crear(externo, valor="111").json()["consulta_id"]
    procesar(externo)
    evidencias = {e["tipo"]: e for e in detalle(externo, consulta_id)["evidencias"]}
    assert set(evidencias) == {"INFORME_INTERNO", "PDF_PROVEEDOR"}
    with externo.sesiones() as sesion:
        pdf = sesion.scalar(select(EvidenciaConsulta).where(EvidenciaConsulta.tipo == "PDF_PROVEEDOR"))
    assert externo.custodia.leer(pdf.clave, pdf.huella, pdf.tamano_bytes) == PDF_MINIMO
    assert "PDF_PROVEEDOR_CUSTODIADO" in eventos(externo, consulta_id)


def test_cc_sin_hallazgos_concluye_sin_candidatos(externo):
    consulta_id = crear(externo, valor="112").json()["consulta_id"]
    procesar(externo)
    consulta = detalle(externo, consulta_id)
    assert consulta["estado_ejecucion"] == "COMPLETADA" and consulta["conclusion_busqueda"] == "SIN_CANDIDATOS"


def test_grupo_empresa_y_representante_respeta_turno_de_5_segundos(externo):
    respuesta = externo.cliente.post(f"/api/expedientes/{externo.expediente}/consultas-listas/grupos",
                                     headers={"Idempotency-Key": "grupo-1"})
    assert respuesta.status_code == 202, respuesta.text
    alinear_reloj(externo)
    consultas = {c["sujeto_rol"]: c["consulta_id"] for c in respuesta.json()["consultas"]}
    assert set(consultas) == {"CONTRAPARTE", "REPRESENTANTE"}
    assert externo.trabajador.ejecutar_uno() and externo.trabajador.ejecutar_uno()
    assert len(lanzamientos(externo)) == 1  # el segundo esperó su turno
    externo.reloj[0] += timedelta(seconds=6)
    procesar(externo)
    assert len(lanzamientos(externo)) == 2
    empresa, persona = detalle(externo, consultas["CONTRAPARTE"]), detalle(externo, consultas["REPRESENTANTE"])
    assert empresa["estado_ejecucion"] == "COMPLETADA" and len(empresa["cobertura"]) == 6
    assert persona["conclusion_busqueda"] == "CON_CANDIDATOS"


def test_recarga_gratuita_de_fuentes_con_error(externo):
    externo.simulador.extras[("POST", "/api/launch")] = httpx.Response(200, json={"jobid": JOB_CON_ERROR, "validado": True})
    externo.simulador.extras[("GET", f"/api/retry/{REPORTE_CON_ERROR}")] = httpx.Response(200, json={"jobid": JOB_CON_HALLAZGO})
    consulta_id = crear(externo, valor="113").json()["consulta_id"]
    procesar(externo)
    assert detalle(externo, consulta_id)["estado_ejecucion"] == "COMPLETADA"
    assert progreso(externo, consulta_id).recargas == 1
    assert "RECARGA_FUENTES_EXTERNAS" in eventos(externo, consulta_id) and len(lanzamientos(externo)) == 1


# ── Respuestas sin reporte ───────────────────────────────────────────────────

@pytest.mark.parametrize("valor,codigo", [("128", "TITULAR_NO_AUTORIZA"), ("126", "RESULTADO_EN_CACHE_SIN_REFERENCIA")])
def test_respuestas_sin_reporte_cierran_con_constancia(externo, valor, codigo):
    consulta_id = crear(externo, valor=valor).json()["consulta_id"]
    procesar(externo)
    consulta = detalle(externo, consulta_id)
    assert consulta["estado_ejecucion"] == "FALLIDA" and consulta["conclusion_busqueda"] == "NO_CONCLUYENTE"
    assert codigo in {a["codigo"] for a in consulta["advertencias"]}
    assert [e["tipo"] for e in consulta["evidencias"]] == ["INFORME_INTERNO"]


# ── Fallas: nunca se relanza sola una consulta que pudo gastar crédito ───────

def test_sin_respuesta_tras_enviar_queda_indeterminada_sin_relanzar(externo):
    externo.simulador.extras[("POST", "/api/launch")] = httpx.ReadTimeout("sin respuesta")
    consulta_id = crear(externo).json()["consulta_id"]
    procesar(externo)
    assert detalle(externo, consulta_id)["estado_ejecucion"] == "INDETERMINADA"
    assert error_trabajo(externo, consulta_id) == "EFECTO_EXTERNO_DESCONOCIDO" and len(lanzamientos(externo)) == 1


def test_trabajador_que_cae_mientras_lanza_no_relanza(externo):
    def caida(_peticion):
        raise RuntimeError("el proceso murió durante el lanzamiento")
    externo.simulador.extras[("POST", "/api/launch")] = caida
    consulta_id = crear(externo).json()["consulta_id"]
    with pytest.raises(RuntimeError):
        externo.trabajador.ejecutar_uno()
    assert progreso(externo, consulta_id).etapa == "LANZANDO"
    externo.simulador.extras.clear()
    externo.reloj[0] += timedelta(minutes=6)  # vence la concesión de la pasada caída
    procesar(externo)
    assert detalle(externo, consulta_id)["estado_ejecucion"] == "INDETERMINADA"
    assert error_trabajo(externo, consulta_id) == "EFECTO_EXTERNO_DESCONOCIDO" and len(lanzamientos(externo)) == 1


def test_sin_conexion_antes_de_enviar_se_reintenta_mas_tarde(externo):
    externo.simulador.extras[("POST", "/api/launch")] = httpx.ConnectError("sin red")
    consulta_id = crear(externo).json()["consulta_id"]
    assert externo.trabajador.ejecutar_uno()
    assert progreso(externo, consulta_id).etapa == "POR_LANZAR"
    externo.simulador.extras.clear()
    procesar(externo)
    assert detalle(externo, consulta_id)["estado_ejecucion"] == "COMPLETADA"


def test_plazo_de_15_minutos_cierra_no_concluyente(externo):
    externo.simulador.extras[("GET", "/api/results/5c6c80c0-4dd3-41c9-9648-46871a7176ad")] = httpx.Response(
        207, json={"estado": "procesando"})
    consulta_id = crear(externo).json()["consulta_id"]
    procesar(externo, paso=60)
    consulta = detalle(externo, consulta_id)
    assert consulta["estado_ejecucion"] == "INDETERMINADA" and consulta["conclusion_busqueda"] == "NO_CONCLUYENTE"
    assert error_trabajo(externo, consulta_id) == "TIEMPO_AGOTADO_PROVEEDOR" and len(lanzamientos(externo)) == 1


# ── Admisión ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("cuerpo", [dict(tipo="CE", valor="960696"), dict(tipo="PAS", valor="381310014"),
                                    dict(tipo="TI", valor="123")])
def test_admision_rechaza_lo_que_tusdatos_no_puede_consultar(externo, cuerpo):
    assert crear(externo, **cuerpo).status_code == 422
    assert externo.simulador.peticiones == []
    with externo.sesiones() as sesion:
        assert sesion.scalar(select(ConsultaLista.id).limit(1)) is None


def test_ce_con_fecha_y_pasaporte_con_nombre_se_admiten(externo):
    assert crear(externo, tipo="CE", valor="960696", fecha_expedicion="2001-11-01").status_code == 202
    assert crear(externo, tipo="PAS", valor="381310014", nombre="JUAN PEREZ PEREZ").status_code == 202


# ── Fase 5: bloquear y reutilizar, forzar actualización y PDF del proveedor ──

def test_misma_cedula_en_6_horas_reutiliza_la_consulta_y_no_gasta_credito(externo):
    primera = crear(externo, valor="1.12")  # el documento se compara sin separadores
    assert primera.status_code == 202 and primera.json()["reutilizada"] is False
    segunda = crear(externo, valor="112")
    assert segunda.status_code == 202 and segunda.json() == {**primera.json(), "reutilizada": True}
    procesar(externo)
    assert crear(externo, valor="112").json() == {**primera.json(), "reutilizada": True}  # también ya terminada
    assert len(lanzamientos(externo)) == 1


def test_reintento_con_la_misma_clave_no_se_informa_como_reutilizada(externo):
    primera = crear(externo, clave="clave-fija").json()
    assert crear(externo, clave="clave-fija").json() == primera and primera["reutilizada"] is False


def test_otro_expediente_no_reutiliza_la_consulta(externo):
    primera = crear(externo).json()["consulta_id"]
    otra = crear(externo, expediente=externo.otro).json()
    assert otra["consulta_id"] != primera and otra["reutilizada"] is False


def test_consulta_fallida_o_fuera_de_ventana_no_se_reutiliza(externo, monkeypatch):
    titular = crear(externo, valor="128").json()["consulta_id"]
    procesar(externo)
    assert crear(externo, valor="128").json()["consulta_id"] != titular
    from services.listas import modalidad_externa
    primera = crear(externo).json()["consulta_id"]
    monkeypatch.setattr(modalidad_externa, "VENTANA_REUTILIZACION", timedelta(0))
    assert crear(externo).json()["consulta_id"] != primera


def test_grupo_reutiliza_la_consulta_reciente_del_representante(externo):
    individual = crear(externo, valor="111").json()["consulta_id"]
    respuesta = externo.cliente.post(f"/api/expedientes/{externo.expediente}/consultas-listas/grupos",
                                     headers={"Idempotency-Key": "grupo-reutiliza"}).json()
    alinear_reloj(externo)
    por_rol = {c["sujeto_rol"]: c for c in respuesta["consultas"]}
    assert por_rol["REPRESENTANTE"] == {"consulta_id": individual, "sujeto_rol": "REPRESENTANTE", "reutilizada": True}
    assert por_rol["CONTRAPARTE"]["reutilizada"] is False
    procesar(externo)
    assert len(lanzamientos(externo)) == 2  # NIT nuevo + la cédula una sola vez


def test_forzar_actualizacion_lanza_con_force_y_queda_en_el_manifiesto(externo):
    primera = crear(externo).json()["consulta_id"]
    forzada = crear(externo, forzar=True).json()
    assert forzada["consulta_id"] != primera and forzada["reutilizada"] is False
    procesar(externo)
    cuerpos = [json.loads(p.content) for p in lanzamientos(externo)]
    assert [c["force"] for c in cuerpos] == [False, True]
    with externo.sesiones() as sesion:
        assert sesion.get(ConsultaLista, UUID(forzada["consulta_id"])).manifiesto["forzar"] is True


def test_forzar_exige_el_permiso_del_equipo_revisor(externo):
    assert crear(externo, forzar=True, roles=("listas_operador",)).status_code == 403
    assert externo.cliente.get("/api/listas/disponibilidad").json()["forzar"] is True
    operador = externo.cliente.get("/api/listas/disponibilidad",
                                   headers={"Authorization": f"Bearer {externo.token('listas_operador')}"}).json()
    assert operador["forzar"] is False and operador["ver_pdf_proveedor"] is False


def test_pdf_del_proveedor_solo_para_el_equipo_revisor_y_queda_auditado(externo):
    externo.simulador.extras[("GET", f"/api/v2/report_pdf/{REPORTE_CC}")] = httpx.Response(
        200, content=PDF_MINIMO, headers={"content-type": "application/pdf"})
    consulta_id = crear(externo, valor="111").json()["consulta_id"]
    procesar(externo)
    pdf = next(e for e in detalle(externo, consulta_id)["evidencias"] if e["tipo"] == "PDF_PROVEEDOR")
    ruta = f"/api/consultas-listas/{consulta_id}/evidencias/{pdf['id']}"
    respuesta = externo.cliente.get(ruta)
    assert respuesta.status_code == 200 and respuesta.content == PDF_MINIMO
    assert f'filename="proveedor_{consulta_id}.pdf"' in respuesta.headers["content-disposition"]
    operador = {"Authorization": f"Bearer {externo.token('listas_operador')}"}
    assert externo.cliente.get(ruta, headers=operador).status_code == 403
    with externo.sesiones() as sesion:
        lecturas = [ev.detalle for ev in sesion.scalars(select(EventoConsulta).where(
            EventoConsulta.consulta_id == UUID(consulta_id), EventoConsulta.tipo == "EVIDENCIA_LEIDA"))]
    assert lecturas == [{"tipo": "PDF_PROVEEDOR", "evidencia_id": pdf["id"]}]
