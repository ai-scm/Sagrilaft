"""Fase 4: modalidad externa (Tusdatos) de punta a punta sobre PostgreSQL.

HTTP con JWT firmado, admisión, trabajador por etapas con reloj controlado, custodia local
y Tusdatos simulado con las respuestas grabadas del sandbox. Sin red.
"""
import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from api import dependencias_listas
from api.middleware import autenticacion
from api.routers import consultas_listas
from infrastructure.config.configuracion import KeycloakConfig, SagrilaftListasConfig
from infrastructure.listas.custodia import CustodiaLocalListas
from infrastructure.listas.tusdatos.cliente import ClienteTusdatos
from infrastructure.listas.tusdatos.configuracion import ConfiguracionTusdatos
from infrastructure.persistencia.models import Formulario
from infrastructure.persistencia.modelos_listas import (
    CoincidenciaLista, ConsultaLista, EventoConsulta, EvidenciaConsulta, ProgresoConsultaExterna, TrabajoConsulta,
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
    assert consulta["proveedor"] == "tusdatos" and consulta["version_contrato"] == "tusdatos-1"
    assert len(consulta["fuentes"]) == 12  # 12 fuentes para cédula
    assert {f["codigo"] for f in consulta["fuentes"] if f["estado"] == "CON_REGISTRO"} >= {
        "ofac", "peps", "procuraduria", "peps_funcion_publica", "lista_onu", "policia"}
    with externo.sesiones() as sesion:  # cada registro es una coincidencia revisable, también ONU y Policía
        registros = sum(len(f["registros"]) for f in consulta["fuentes"])
        assert sesion.scalar(select(func.count()).select_from(CoincidenciaLista)
                             .where(CoincidenciaLista.consulta_id == UUID(consulta_id))) == registros
    assert [e["tipo"] for e in consulta["evidencias"]] == ["INFORME_INTERNO"]
    # Un solo lanzamiento, con el documento limpio y la fecha de expedición (opcional en CC).
    assert len(lanzamientos(externo)) == 1
    assert json.loads(lanzamientos(externo)[0].content) == {"doc": "111", "typedoc": "CC", "force": False,
                                                            "fechaE": "01/12/2014", "webhook_reference": consulta_id}
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
    assert empresa["estado_ejecucion"] == "COMPLETADA" and len(empresa["fuentes"]) == 6
    assert persona["conclusion_busqueda"] == "CON_CANDIDATOS"


def test_recarga_gratuita_de_fuentes_con_error(externo):
    externo.simulador.extras[("POST", "/api/launch")] = httpx.Response(200, json={"jobid": JOB_CON_ERROR, "validado": True})
    externo.simulador.extras[("GET", f"/api/retry/{REPORTE_CON_ERROR}")] = httpx.Response(200, json={"jobid": JOB_CON_HALLAZGO})
    consulta_id = crear(externo, valor="113").json()["consulta_id"]
    procesar(externo)
    assert detalle(externo, consulta_id)["estado_ejecucion"] == "COMPLETADA"
    assert progreso(externo, consulta_id).recargas == 1
    assert "RECARGA_FUENTES_EXTERNAS" in eventos(externo, consulta_id) and len(lanzamientos(externo)) == 1


def test_cada_registro_de_tusdatos_se_revisa_por_separado(externo):
    """ONU y Policía antes quedaban como «hallazgo sin estructura» y no admitían revisión individual."""
    consulta_id = crear(externo, valor="111", fecha_expedicion="2014-12-01").json()["consulta_id"]
    procesar(externo)
    consulta = detalle(externo, consulta_id)
    onu = next(f for f in consulta["fuentes"] if f["codigo"] == "lista_onu")["registros"][0]
    assert onu["sin_detalle"] is True
    respuesta = externo.cliente.post(f"/api/consultas-listas/{consulta_id}/revisiones", json={
        "resultado": "DESCARTADA", "justificacion": "Homónimo: otra fecha de nacimiento", "coincidencia_id": onu["id"]},
        headers={"Authorization": f"Bearer {externo.token('listas_revisor')}"})
    assert respuesta.status_code == 201, respuesta.text
    revisiones = externo.cliente.get(f"/api/consultas-listas/{consulta_id}").json()["revisiones"]
    assert [r["coincidencia_id"] for r in revisiones] == [onu["id"]]


def test_consulta_pendiente_del_adaptador_anterior_se_cierra_sin_lanzar(externo, monkeypatch):
    from infrastructure.listas.tusdatos import adaptador
    from services.listas import modalidad_externa
    with monkeypatch.context() as cambio:  # admitida antes del cambio de contrato (la base no deja alterarla después)
        cambio.setattr(adaptador, "ADAPTADOR_VERSION", "tusdatos-v1")
        cambio.setattr(modalidad_externa, "VERSION_CONTRATO_TUSDATOS", "2.0")
        consulta_id = crear(externo, valor="112").json()["consulta_id"]
    procesar(externo)
    assert lanzamientos(externo) == []
    with externo.sesiones() as sesion:
        trabajo = sesion.scalar(select(TrabajoConsulta).where(TrabajoConsulta.consulta_id == UUID(consulta_id)))
        assert trabajo.error == "ADAPTADOR_RETIRADO"


# ── Respuestas sin reporte ───────────────────────────────────────────────────

@pytest.mark.parametrize("valor,codigo", [("128", "TITULAR_NO_AUTORIZA"), ("126", "RESULTADO_EN_CACHE_SIN_REFERENCIA")])
def test_respuestas_sin_reporte_cierran_con_constancia(externo, valor, codigo):
    consulta_id = crear(externo, valor=valor).json()["consulta_id"]
    procesar(externo)
    consulta = detalle(externo, consulta_id)
    assert consulta["estado_ejecucion"] == "FALLIDA" and consulta["conclusion_busqueda"] == "NO_CONCLUYENTE"
    assert consulta["error"]["codigo"] == codigo
    assert {f["estado"] for f in consulta["fuentes"]} == {"NO_CONSULTADA"}
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


def test_documento_que_tusdatos_no_valida_queda_advertido(externo):
    externo.simulador.extras[("GET", "/api/results/5c6c80c0-4dd3-41c9-9648-46871a7176ad")] = httpx.Response(200, json={
        "estado": "finalizado", "id": "8188f7e8aa70102bf2053f32", "hallazgo": False, "errores": [], "validado": False})
    consulta_id = crear(externo).json()["consulta_id"]
    procesar(externo)
    consulta = detalle(externo, consulta_id)
    assert consulta["estado_ejecucion"] == "COMPLETADA"
    assert "DOCUMENTO_NO_VALIDADO" in {a["codigo"] for a in consulta["avisos"]}


# ── Documento inexistente y revisión previa de fuentes y créditos ────────────

def test_nit_inexistente_se_cierra_con_un_mensaje_claro(externo):
    externo.simulador.extras[("POST", "/api/launch")] = httpx.Response(400, json={"error": "Nit no encontrado"})
    consulta_id = crear(externo, tipo="NIT", valor="900.123.456-7").json()["consulta_id"]
    procesar(externo)
    consulta = detalle(externo, consulta_id)
    assert consulta["estado_ejecucion"] == "FALLIDA" and consulta["error"]["codigo"] == "DOCUMENTO_NO_ENCONTRADO"
    assert "registro mercantil" in consulta["error"]["mensaje"]
    assert [e["tipo"] for e in consulta["evidencias"]] == ["INFORME_INTERNO"]
    assert json.loads(lanzamientos(externo)[0].content)["doc"] == "900123456"  # sin dígito de verificación


def test_el_sandbox_no_revisa_fuentes_ni_creditos(externo):
    crear(externo)
    procesar(externo)
    rutas = {p.url.path for p in externo.simulador.peticiones}
    assert "/api/v1/sources/status" not in rutas and "/api/plans" not in rutas


def estado_fuentes(**estados):
    return httpx.Response(200, json={"sources": [{"code": c, "status": s} for c, s in estados.items()]})


@pytest.fixture
def produccion(externo, monkeypatch):
    """Misma base y simulador, pero con la configuración de producción: activa la revisión previa."""
    metricas = []
    configuracion = ConfiguracionTusdatos(url_base="https://dash-board.tusdatos.co", token="api_td_pruebas", alerta_creditos=50)
    modalidad = ModalidadExterna(fabrica_cliente=lambda _entorno: ClienteTusdatos(
        configuracion, transporte=externo.simulador.transporte, dormir=lambda _s: None,
        metricas=lambda *argumentos: metricas.append(argumentos)),
        monotonic=lambda: externo.reloj[0].timestamp())  # la caché del estado sigue el reloj de la prueba
    monkeypatch.setitem(modalidades.MODALIDADES, "externo", modalidad)
    externo.simulador.extras[("GET", "/api/v1/sources/status")] = estado_fuentes(policia="operational", procuraduria="operational")
    externo.simulador.extras[("GET", "/api/plans")] = httpx.Response(200, json={"amount": 500, "purchase_amount": 1000})
    externo.metricas = metricas
    return externo


def test_fuente_obligatoria_caida_no_gasta_credito(produccion):
    produccion.simulador.extras[("GET", "/api/v1/sources/status")] = estado_fuentes(procuraduria="under_maintenance", rut="source_down")
    consulta_id = crear(produccion).json()["consulta_id"]
    procesar(produccion)
    consulta = detalle(produccion, consulta_id)
    assert consulta["estado_ejecucion"] == "FALLIDA" and consulta["error"]["codigo"] == "FUENTES_CAIDAS_PROVEEDOR"
    assert "Procuraduría General de la Nación" in consulta["error"]["mensaje"] and "RUT" not in consulta["error"]["mensaje"]
    assert lanzamientos(produccion) == [] and "FUENTES_CAIDAS_PROVEEDOR" in eventos(produccion, consulta_id)


def test_forzar_consulta_aunque_haya_fuentes_caidas(produccion):
    produccion.simulador.extras[("GET", "/api/v1/sources/status")] = estado_fuentes(policia="source_down")
    consulta_id = crear(produccion, forzar=True).json()["consulta_id"]
    procesar(produccion)
    assert detalle(produccion, consulta_id)["estado_ejecucion"] == "COMPLETADA"
    assert len(lanzamientos(produccion)) == 1


@pytest.mark.parametrize("estado", [
    estado_fuentes(peps_funcion_publica="source_down", rut="source_down"),  # no deciden el resultado
    httpx.Response(503),                                                    # sin estado no se bloquea
])
def test_caidas_que_no_bloquean(produccion, estado):
    produccion.simulador.extras[("GET", "/api/v1/sources/status")] = estado
    consulta_id = crear(produccion).json()["consulta_id"]
    procesar(produccion)
    assert detalle(produccion, consulta_id)["estado_ejecucion"] == "COMPLETADA" and len(lanzamientos(produccion)) == 1


def test_empresa_no_se_bloquea_por_fuentes_solo_de_personas(produccion):
    produccion.simulador.extras[("GET", "/api/v1/sources/status")] = estado_fuentes(policia="source_down", interpol="source_down")
    consulta_id = crear(produccion, tipo="NIT", valor="900000152").json()["consulta_id"]
    procesar(produccion)
    assert detalle(produccion, consulta_id)["estado_ejecucion"] == "COMPLETADA"


@pytest.mark.parametrize("restantes,aviso", [(500, False), (12, True)])
def test_creditos_se_publican_y_avisan_cuando_quedan_pocos(produccion, caplog, monkeypatch, restantes, aviso):
    # El fileConfig de Alembic (migración de la sesión de pruebas) desactiva los loggers ya creados.
    import logging
    monkeypatch.setattr(logging.getLogger("services.listas.modalidad_externa"), "disabled", False)
    produccion.simulador.extras[("GET", "/api/plans")] = httpx.Response(200, json={"amount": restantes, "purchase_amount": 1000})
    with caplog.at_level("WARNING", logger="services.listas.modalidad_externa"):
        crear(produccion)
        procesar(produccion)
    assert any(m[2] == {"TusdatosCreditosRestantes": restantes} for m in produccion.metricas)
    assert ("quedan 12 créditos" in caplog.text) is aviso
    assert len(lanzamientos(produccion)) == 1  # los créditos nunca bloquean la consulta



# ── Recarga según el estado de las fuentes ───────────────────────────────────

def recargas_pedidas(e):
    return [p for p in e.simulador.peticiones if p.url.path.startswith("/api/retry")]


def preparar_consulta_con_errores(e, *estados):
    e.simulador.extras[("POST", "/api/launch")] = httpx.Response(200, json={"jobid": JOB_CON_ERROR, "validado": True})
    e.simulador.extras[("GET", f"/api/retry/{REPORTE_CON_ERROR}")] = httpx.Response(200, json={"jobid": JOB_CON_HALLAZGO})
    e.simulador.extras[("GET", "/api/v1/sources/status")] = list(estados)


def test_recarga_espera_a_que_vuelva_la_fuente_caida(produccion):
    operativa = estado_fuentes(procuraduria="operational", policia="operational")
    caida = estado_fuentes(procuraduria="under_maintenance", policia="operational")
    preparar_consulta_con_errores(produccion, operativa, caida, caida, operativa)
    consulta_id = crear(produccion, valor="113").json()["consulta_id"]
    procesar(produccion)
    assert detalle(produccion, consulta_id)["estado_ejecucion"] == "COMPLETADA"
    assert len(recargas_pedidas(produccion)) == 1 and len(lanzamientos(produccion)) == 1
    consultas_estado = [p for p in produccion.simulador.peticiones if p.url.path == "/api/v1/sources/status"]
    assert len(consultas_estado) == 4  # antes de lanzar, dos veces caída, y la recarga solo al volver
    assert "RECARGA_FUENTES_EXTERNAS" in eventos(produccion, consulta_id)


def test_si_la_fuente_no_vuelve_a_tiempo_no_gasta_la_recarga_y_dice_por_que(produccion):
    preparar_consulta_con_errores(produccion, estado_fuentes(procuraduria="operational"),
                                  estado_fuentes(procuraduria="source_down"))
    consulta_id = crear(produccion, valor="113").json()["consulta_id"]
    procesar(produccion)
    consulta = detalle(produccion, consulta_id)
    # El sandbox con error falla en todas las fuentes: sin ninguna consultada, la consulta queda FALLIDA.
    assert consulta["estado_ejecucion"] == "FALLIDA" and consulta["conclusion_busqueda"] == "NO_CONCLUYENTE"
    procuraduria = next(f for f in consulta["fuentes"] if f["codigo"] == "procuraduria")
    assert "caída o en mantenimiento" in procuraduria["motivo"]
    assert recargas_pedidas(produccion) == [] and "RECARGA_OMITIDA_FUENTES_CAIDAS" in eventos(produccion, consulta_id)


def test_en_el_sandbox_la_recarga_no_espera(externo):
    preparar_consulta_con_errores(externo, estado_fuentes(procuraduria="source_down"))
    consulta_id = crear(externo, valor="113").json()["consulta_id"]
    procesar(externo)
    assert detalle(externo, consulta_id)["estado_ejecucion"] == "COMPLETADA" and len(recargas_pedidas(externo)) == 1


def test_avisa_una_vez_las_fuentes_que_tusdatos_no_informa(produccion, caplog, monkeypatch):
    import logging
    monkeypatch.setattr(logging.getLogger("services.listas.modalidad_externa"), "disabled", False)
    with caplog.at_level("WARNING", logger="services.listas.modalidad_externa"):
        crear(produccion)
        crear(produccion, valor="111")
        procesar(produccion)
    avisos = [r.getMessage() for r in caplog.records if "no informa" in r.getMessage()]
    assert len(avisos) == 1 and "ofac" in avisos[0] and "procuraduria" not in avisos[0].split(".")[0]


# ── CC en la caché de Tusdatos: recuperación por el historial ────────────────

REPORTE_SIN_HALLAZGO = "8188f7e8aa70102bf2053f32"


def fila_historial(e, reporte_id, hace=timedelta(hours=1), documento="126"):
    creada = (e.reloj[0] - hace).isoformat()
    return {"check_id": reporte_id, "document_type": "CC", "document_number": documento, "created_at": creada,
            "url": f"https://dash-board.tusdatos.co/api/report_json/{reporte_id}"}


def test_cc_en_cache_se_recupera_del_historial_sin_gastar_credito(externo):
    externo.simulador.extras[("GET", "/api/v1/checks")] = lambda _p: httpx.Response(200, json={"data": [
        fila_historial(externo, REPORTE_CC, hace=timedelta(hours=5)),
        fila_historial(externo, REPORTE_SIN_HALLAZGO, hace=timedelta(hours=1))]})
    consulta_id = crear(externo, valor="126").json()["consulta_id"]
    procesar(externo)
    consulta = detalle(externo, consulta_id)
    assert consulta["estado_ejecucion"] == "COMPLETADA" and consulta["conclusion_busqueda"] == "SIN_CANDIDATOS"
    assert progreso(externo, consulta_id).reporte_id == REPORTE_SIN_HALLAZGO  # la más reciente
    assert "REPORTE_RECUPERADO_DE_HISTORIAL" in eventos(externo, consulta_id) and len(lanzamientos(externo)) == 1
    consulta_historial = next(p for p in externo.simulador.peticiones if p.url.path == "/api/v1/checks")
    assert consulta_historial.url.params["document_number"] == "126"


def test_cc_recuperada_con_fuentes_fallidas_usa_la_recarga(externo):
    externo.simulador.extras[("GET", "/api/v1/checks")] = lambda _p: httpx.Response(200, json={"data": [
        fila_historial(externo, REPORTE_CON_ERROR)]})
    externo.simulador.extras[("GET", f"/api/retry/{REPORTE_CON_ERROR}")] = httpx.Response(200, json={"jobid": JOB_CON_HALLAZGO})
    consulta_id = crear(externo, valor="126").json()["consulta_id"]
    procesar(externo)
    assert detalle(externo, consulta_id)["estado_ejecucion"] == "COMPLETADA"
    assert progreso(externo, consulta_id).recargas == 1 and len(lanzamientos(externo)) == 1


@pytest.mark.parametrize("filas", [
    lambda e: [fila_historial(e, REPORTE_CC, hace=timedelta(hours=7))],             # fuera de la ventana de 6 h
    lambda e: [fila_historial(e, REPORTE_CC, documento="999")],                    # de otro documento
    lambda e: [{**fila_historial(e, REPORTE_CC), "created_at": "2026-11-13"}],       # sin hora: no se adivina
    lambda e: [],
])
def test_si_el_historial_no_sirve_se_cierra_como_antes(externo, filas):
    externo.simulador.extras[("GET", "/api/v1/checks")] = lambda _p: httpx.Response(200, json={"data": filas(externo)})
    consulta_id = crear(externo, valor="126").json()["consulta_id"]
    procesar(externo)
    consulta = detalle(externo, consulta_id)
    assert consulta["estado_ejecucion"] == "FALLIDA"
    assert consulta["error"]["codigo"] == "RESULTADO_EN_CACHE_SIN_REFERENCIA"
    assert not any(p.url.path.startswith("/api/report_json") for p in externo.simulador.peticiones)


# ── Sin verificación previa (verify/nit y verify/ce retirados el 2026-11-25) ──

@pytest.mark.parametrize("tipo,numero,extra", [("NIT", "900000152", {}),
                                               ("CE", "960696", {"fecha_expedicion": "2001-11-01"})])
def test_nit_y_ce_se_lanzan_sin_verificar_antes(externo, tipo, numero, extra):
    respuesta = crear(externo, tipo=tipo, valor=numero, **extra)
    assert respuesta.status_code == 202, respuesta.text
    consulta_id = respuesta.json()["consulta_id"]
    procesar(externo)
    rutas = [p.url.path for p in externo.simulador.peticiones]
    assert not [r for r in rutas if "/verify/" in r]
    assert len(lanzamientos(externo)) == 1
    assert progreso(externo, consulta_id).verificacion_documento is None


def test_cc_envia_la_fecha_de_expedicion_si_se_informa(externo):
    assert crear(externo, valor="111", fecha_expedicion="2014-12-01").status_code == 202
    assert crear(externo, valor="112").status_code == 202
    procesar(externo)
    cuerpos = {c["doc"]: c for c in (json.loads(p.content) for p in lanzamientos(externo))}
    assert cuerpos["111"]["fechaE"] == "01/12/2014" and "fechaE" not in cuerpos["112"]


def test_grupo_usa_la_fecha_del_paso_3_solo_para_el_representante(externo):
    # La fecha del expediente es la del documento del representante legal (paso 3 del formulario).
    with externo.sesiones.begin() as sesion:
        sesion.get(Formulario, externo.expediente).fecha_expedicion = date(2014, 12, 1)
    respuesta = externo.cliente.post(f"/api/expedientes/{externo.expediente}/consultas-listas/grupos",
                                     headers={"Idempotency-Key": "grupo-fecha"})
    assert respuesta.status_code == 202, respuesta.text
    alinear_reloj(externo)
    for _ in range(3):
        procesar(externo)
        externo.reloj[0] += timedelta(seconds=6)
    cuerpos = {c["typedoc"]: c for c in (json.loads(p.content) for p in lanzamientos(externo))}
    assert cuerpos["CC"]["fechaE"] == "01/12/2014"   # representante
    assert "fechaE" not in cuerpos["NIT"]              # la empresa no lleva fecha


# ── Capturas de pantalla por fuente ──────────────────────────────────────────

JPEG = b"\xff\xd8\xff\xe0captura-de-prueba"
DEST_CC = "/static/img/63776b99-4f26-4f11-b426-dcbbb124dfb8"


def capturas(e):
    return [p for p in e.simulador.peticiones if p.url.host == "static.tusdatos.co"]


def test_capturas_de_las_fuentes_quedan_como_evidencia_restringida(externo):
    externo.simulador.extras[("GET", f"{DEST_CC}/ofac.jpg")] = httpx.Response(200, content=JPEG + b"ofac")
    externo.simulador.extras[("GET", f"{DEST_CC}/onu.jpg")] = httpx.Response(200, content=JPEG + b"onu")
    consulta_id = crear(externo, valor="111").json()["consulta_id"]
    procesar(externo)
    evidencias = [e for e in detalle(externo, consulta_id)["evidencias"] if e["tipo"] == "CAPTURA_PROVEEDOR"]
    assert sorted(e["fuente_codigo"] for e in evidencias) == ["lista_onu", "ofac"]
    # Se piden solo las fuentes de la consulta que generan captura, sin credenciales.
    pedidas = {p.url.path.rsplit("/", 1)[-1] for p in capturas(externo)}
    assert pedidas == {"ofac.jpg", "ofac_nombre.jpg", "onu.jpg", "interpol.jpg", "europol.jpg", "cidob.jpg",
                       "procuraduria.jpg", "policia.jpg"}
    assert all("authorization" not in p.headers for p in capturas(externo))
    assert "CAPTURAS_PROVEEDOR_CUSTODIADAS" in eventos(externo, consulta_id)
    ofac = next(e for e in evidencias if e["fuente_codigo"] == "ofac")
    ruta = f"/api/consultas-listas/{consulta_id}/evidencias/{ofac['id']}"
    respuesta = externo.cliente.get(ruta)
    assert respuesta.status_code == 200 and respuesta.content == JPEG + b"ofac"
    assert respuesta.headers["content-type"] == "image/jpeg"
    assert f'filename="captura_ofac_{consulta_id}.jpg"' in respuesta.headers["content-disposition"]
    assert externo.cliente.get(ruta, headers={"Authorization": f"Bearer {externo.token('listas_operador')}"}).status_code == 403


def test_la_misma_imagen_en_dos_consultas_no_rompe_el_cierre(externo):
    externo.simulador.extras[("GET", f"{DEST_CC}/ofac.jpg")] = httpx.Response(200, content=JPEG)
    primera = crear(externo, valor="111").json()["consulta_id"]
    procesar(externo)
    segunda = crear(externo, valor="111", forzar=True).json()["consulta_id"]
    procesar(externo)
    assert detalle(externo, segunda)["estado_ejecucion"] == "COMPLETADA"
    assert [e["fuente_codigo"] for e in detalle(externo, primera)["evidencias"] if e["tipo"] == "CAPTURA_PROVEEDOR"] == ["ofac"]


def test_sin_capturas_o_apagadas_la_consulta_cierra_igual(externo, monkeypatch):
    consulta_id = crear(externo, valor="111").json()["consulta_id"]
    procesar(externo)
    assert detalle(externo, consulta_id)["estado_ejecucion"] == "COMPLETADA"
    assert "CAPTURAS_PROVEEDOR_NO_DISPONIBLES" in eventos(externo, consulta_id)
    apagadas = ConfiguracionTusdatos(url_base="http://docs.tusdatos.co", usuario="pruebas", clave="password", capturas=False)
    monkeypatch.setitem(modalidades.MODALIDADES, "externo", ModalidadExterna(fabrica_cliente=lambda _e: ClienteTusdatos(
        apagadas, transporte=externo.simulador.transporte, dormir=lambda _s: None, metricas=lambda *_: None)))
    antes = len(capturas(externo))
    otra = crear(externo, valor="112").json()["consulta_id"]
    procesar(externo)
    assert len(capturas(externo)) == antes and "CAPTURAS_PROVEEDOR_OMITIDAS" in eventos(externo, otra)


# ── Recuperación después del cierre (gratis) ─────────────────────────────────

def revisar(e, minutos):
    """Avanza el reloj y corre la revisión de consultas cerradas, como la haría el trabajador."""
    e.reloj[0] += timedelta(minutes=minutos)
    e.trabajador.revisar_pendientes()


def recargas_de(e, consulta_id):
    with e.sesiones() as sesion:
        return [str(c) for c in sesion.scalars(select(ConsultaLista.id).where(ConsultaLista.consulta_previa_id == UUID(consulta_id)))]


def cerrar_con_fuentes_fallidas(e, *recargas):
    """Consulta cuyas fuentes fallan también en la recarga del cierre; `recargas` responde las siguientes."""
    e.simulador.extras[("POST", "/api/launch")] = httpx.Response(200, json={"jobid": JOB_CON_ERROR, "validado": True})
    e.simulador.extras[("GET", f"/api/retry/{REPORTE_CON_ERROR}")] = [
        httpx.Response(200, json={"jobid": JOB_CON_ERROR}), *recargas]
    consulta_id = crear(e, valor="113").json()["consulta_id"]
    procesar(e)
    assert detalle(e, consulta_id)["estado_ejecucion"] == "FALLIDA" and len(recargas_pedidas(e)) == 1
    return consulta_id


def test_fuentes_fallidas_se_recargan_solas_despues_del_cierre_sin_gastar_credito(externo):
    original = cerrar_con_fuentes_fallidas(externo, httpx.Response(200, json={"jobid": JOB_CON_HALLAZGO}))
    revisar(externo, 5)
    assert recargas_de(externo, original) == []  # la primera recarga espera 10 minutos
    revisar(externo, 6)
    [recarga] = recargas_de(externo, original)
    procesar(externo)
    consulta = detalle(externo, recarga)
    assert consulta["estado_ejecucion"] == "COMPLETADA" and consulta["contexto"]["sujeto_rol"] == "CONTRAPARTE"
    aviso = next(a for a in consulta["avisos"] if a["codigo"] == "RECUPERACION_AUTOMATICA")
    assert original in aviso["descripcion"] and "intento 1 de 3" in aviso["descripcion"]
    assert len(lanzamientos(externo)) == 1 and len(recargas_pedidas(externo)) == 2
    assert "RECUPERACION_PROGRAMADA" in eventos(externo, original)
    # La original no cambia y las dos quedan en el historial del expediente.
    assert detalle(externo, original)["estado_ejecucion"] == "FALLIDA"
    historial = externo.cliente.get(f"/api/expedientes/{externo.expediente}/consultas-listas").json()["consultas"]
    assert {c["consulta_id"]: c.get("recupera") for c in historial} == {original: None, recarga: original}
    revisar(externo, 120)
    assert recargas_de(externo, recarga) == []  # completa: no hay nada más que recargar


def test_la_recarga_automatica_se_detiene_a_las_tres(externo):
    original = cerrar_con_fuentes_fallidas(externo)  # Tusdatos sigue respondiendo con error
    cadena = [original]
    for _ in range(4):
        revisar(externo, 5 * 60)
        cadena += recargas_de(externo, cadena[-1])
        procesar(externo)
    assert len(cadena) == 4 and len(recargas_pedidas(externo)) == 4 and len(lanzamientos(externo)) == 1
    assert "intento 3 de 3" in next(a["descripcion"] for a in detalle(externo, cadena[-1])["avisos"]
                                     if a["codigo"] == "RECUPERACION_AUTOMATICA")


def test_no_recarga_si_el_usuario_ya_volvio_a_consultar(externo):
    original = cerrar_con_fuentes_fallidas(externo)
    externo.simulador.extras[("POST", "/api/launch")] = httpx.Response(200, json={"jobid": JOB_CON_HALLAZGO, "validado": True})
    crear(externo, valor="113", forzar=True)
    procesar(externo)
    revisar(externo, 11)
    assert recargas_de(externo, original) == []


def test_si_tusdatos_no_admite_la_recarga_se_deja_de_insistir(externo):
    original = cerrar_con_fuentes_fallidas(externo, httpx.Response(400, json={"Error": "Message"}))
    revisar(externo, 11)
    [recarga] = recargas_de(externo, original)
    procesar(externo)
    assert detalle(externo, recarga)["error"]["codigo"] == "RECARGA_NO_ADMITIDA_PROVEEDOR"
    revisar(externo, 120)
    assert recargas_de(externo, recarga) == [] and len(recargas_pedidas(externo)) == 2


def test_con_la_fuente_aun_caida_la_recarga_espera(produccion):
    original = cerrar_con_fuentes_fallidas(produccion, httpx.Response(200, json={"jobid": JOB_CON_HALLAZGO}))
    produccion.simulador.extras[("GET", "/api/v1/sources/status")] = [
        estado_fuentes(procuraduria="source_down"), estado_fuentes(procuraduria="operational")]
    revisar(produccion, 11)
    assert recargas_de(produccion, original) == []
    revisar(produccion, 1)
    assert len(recargas_de(produccion, original)) == 1


def test_recuperacion_apagada_no_hace_nada(externo, monkeypatch):
    original = cerrar_con_fuentes_fallidas(externo)
    apagada = ConfiguracionTusdatos(url_base="http://docs.tusdatos.co", usuario="pruebas", clave="password", recuperar=False)
    monkeypatch.setitem(modalidades.MODALIDADES, "externo", ModalidadExterna(fabrica_cliente=lambda _e: ClienteTusdatos(
        apagada, transporte=externo.simulador.transporte, dormir=lambda _s: None, metricas=lambda *_: None)))
    antes = len(externo.simulador.peticiones)
    revisar(externo, 11)
    assert recargas_de(externo, original) == [] and len(externo.simulador.peticiones) == antes


def test_el_pdf_que_no_llego_se_suma_despues_a_la_misma_consulta(externo):
    ruta_pdf = f"/api/v2/report_pdf/{REPORTE_CC}"
    externo.simulador.extras[("GET", ruta_pdf)] = [
        httpx.Response(404), httpx.Response(404),
        httpx.Response(200, content=PDF_MINIMO, headers={"content-type": "application/pdf"})]
    consulta_id = crear(externo, valor="111").json()["consulta_id"]
    procesar(externo)
    assert "PDF_PROVEEDOR_NO_DISPONIBLE" in eventos(externo, consulta_id)
    revisar(externo, 11)  # sigue sin llegar
    assert "PDF_PROVEEDOR" not in {e["tipo"] for e in detalle(externo, consulta_id)["evidencias"]}
    revisar(externo, 30)
    assert "PDF_PROVEEDOR" not in {e["tipo"] for e in detalle(externo, consulta_id)["evidencias"]}  # aún no toca
    revisar(externo, 30)
    assert "PDF_PROVEEDOR" in {e["tipo"] for e in detalle(externo, consulta_id)["evidencias"]}
    assert "EVIDENCIA_PROVEEDOR_RECUPERADA" in eventos(externo, consulta_id)
    assert detalle(externo, consulta_id)["estado_ejecucion"] == "COMPLETADA"
    pedidas = len([p for p in externo.simulador.peticiones if p.url.path == ruta_pdf])
    revisar(externo, 5 * 60)
    assert len([p for p in externo.simulador.peticiones if p.url.path == ruta_pdf]) == pedidas  # ya está


def test_el_pdf_se_pide_como_maximo_tres_veces_despues_del_cierre(externo):
    consulta_id = crear(externo, valor="111").json()["consulta_id"]
    procesar(externo)
    ruta_pdf = f"/api/v2/report_pdf/{REPORTE_CC}"
    antes = len([p for p in externo.simulador.peticiones if p.url.path == ruta_pdf])
    for _ in range(5):
        revisar(externo, 5 * 60)
    assert len([p for p in externo.simulador.peticiones if p.url.path == ruta_pdf]) == antes + 3
    assert eventos(externo, consulta_id).count("EVIDENCIA_PROVEEDOR_REINTENTADA") == 3


def test_capturas_que_no_alcanzaron_a_pedirse_se_recuperan(externo):
    listo = {"pdf": False}

    def pdf(_peticion):
        if listo["pdf"]:
            return httpx.Response(200, content=PDF_MINIMO, headers={"content-type": "application/pdf"})
        return httpx.Response(202, json={"status": "processing"}, headers={"Retry-After": "10"})
    externo.simulador.extras[("GET", f"/api/v2/report_pdf/{REPORTE_CC}")] = pdf
    externo.simulador.extras[("GET", f"{DEST_CC}/ofac.jpg")] = httpx.Response(200, content=JPEG + b"ofac")
    consulta_id = crear(externo, valor="111").json()["consulta_id"]
    procesar(externo)  # el PDF no termina antes del plazo: no hay tiempo para las capturas
    assert "CAPTURAS_PROVEEDOR_OMITIDAS" in eventos(externo, consulta_id) and capturas(externo) == []
    listo["pdf"] = True
    revisar(externo, 11)
    evidencias = detalle(externo, consulta_id)["evidencias"]
    assert {e["tipo"] for e in evidencias} == {"INFORME_INTERNO", "PDF_PROVEEDOR", "CAPTURA_PROVEEDOR"}
    assert [e["fuente_codigo"] for e in evidencias if e["tipo"] == "CAPTURA_PROVEEDOR"] == ["ofac"]
