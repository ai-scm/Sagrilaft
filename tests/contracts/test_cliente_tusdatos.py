"""Cliente HTTP de Tusdatos contra respuestas grabadas del sandbox. Sin red salvo la prueba opcional final."""
import base64
import os
from datetime import date

import httpx
import pytest

from domain.listas.puertos import ListasNoDisponibles
from infrastructure.listas.tusdatos.cliente import (
    ClienteTusdatos, DocumentoPdf, Interruptor, PdfPendiente, limpiar_documento,
)
from infrastructure.listas.tusdatos.configuracion import ConfiguracionTusdatos
from infrastructure.listas.tusdatos.errores import (
    ConsultaFallida, CredencialesRechazadas, EfectoDesconocido, ProveedorNoDisponible,
    RespuestaInesperada, SolicitudRechazada, TitularNoAutoriza, TrabajoVencido,
)
from soporte_tusdatos import PDF_MINIMO, SimuladorTusdatos

SANDBOX = "http://docs.tusdatos.co"
JOB_CON_HALLAZGO = "6460fc34-4154-43db-9438-8c5a059304c0"
REPORTE_CC = "651c2ede72476080772781f5"
REPORTE_NIT = "5d9e05963817a56d989523c0"


def configuracion(**cambios):
    datos = {"url_base": SANDBOX, "usuario": "pruebas", "clave": "password", **cambios}
    return ConfiguracionTusdatos(**datos)


def cliente(simulador=None, metricas=None, **opciones):
    simulador = simulador or SimuladorTusdatos()
    registradas = [] if metricas is None else metricas
    return ClienteTusdatos(opciones.pop("config", configuracion()), transporte=simulador.transporte,
        dormir=lambda _s: None, metricas=lambda *a: registradas.append(a), **opciones), simulador


# ── Configuración ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("cambios", [
    {"url_base": "http://dash-board.tusdatos.co"},             # HTTP fuera del sandbox
    {"url_base": "https://dash-board.tusdatos.co/api"},        # con ruta
    {"url_base": "ftp://docs.tusdatos.co"},
    {"token": "api_td_x"},                                     # token y usuario a la vez
    {"usuario": "", "clave": ""},                              # sin credenciales
    {"usuario": "pruebas", "clave": ""},
    {"tiempo_lectura": 0},
])
def test_configuracion_invalida_no_arranca(cambios):
    with pytest.raises(ListasNoDisponibles):
        configuracion(**cambios)


def test_produccion_exige_https_real_y_token():
    with pytest.raises(ListasNoDisponibles, match="sandbox"):
        configuracion().validar_entorno("production")
    with pytest.raises(ListasNoDisponibles, match="Token"):
        configuracion(url_base="https://dash-board.tusdatos.co").validar_entorno("production")
    ConfiguracionTusdatos(url_base="https://dash-board.tusdatos.co", token="api_td_x").validar_entorno("production")


def test_secretos_no_aparecen_en_repr():
    texto = repr(ConfiguracionTusdatos(url_base="https://dash-board.tusdatos.co", token="api_td_secreto"))
    assert "api_td_secreto" not in texto and "password" not in repr(configuracion())


def test_configuracion_desde_entorno(monkeypatch):
    monkeypatch.setenv("LISTAS_TUSDATOS_URL", "https://dash-board.tusdatos.co/")
    monkeypatch.setenv("LISTAS_TUSDATOS_TOKEN", "api_td_x")
    monkeypatch.setenv("LISTAS_TUSDATOS_TIEMPO_LECTURA", "30")
    leida = ConfiguracionTusdatos.desde_entorno("production")
    assert leida.url_base == "https://dash-board.tusdatos.co" and leida.tiempo_lectura == 30
    monkeypatch.delenv("LISTAS_TUSDATOS_URL")
    with pytest.raises(ListasNoDisponibles):
        ConfiguracionTusdatos.desde_entorno("development")


def test_autenticacion_basica_en_sandbox_y_bearer_con_token():
    basico, simulador = cliente()
    basico.estado(JOB_CON_HALLAZGO)
    esperado = "Basic " + base64.b64encode(b"pruebas:password").decode()
    assert simulador.peticiones[-1].headers["authorization"] == esperado
    token, simulador = cliente(config=ConfiguracionTusdatos(url_base="https://dash-board.tusdatos.co", token="api_td_x"))
    token.estado(JOB_CON_HALLAZGO)
    assert simulador.peticiones[-1].headers["authorization"] == "Bearer api_td_x"


# ── Lanzamiento ──────────────────────────────────────────────────────────────

def test_lanzar_cc_envia_formato_del_proveedor():
    c, simulador = cliente()
    lanzado = c.lanzar("CC", "111", fecha_expedicion=date(2014, 12, 1), referencia="consulta-1")
    assert lanzado.jobid == JOB_CON_HALLAZGO and not lanzado.en_cache and lanzado.validado is True
    assert simulador.cuerpos()[-1] == {"doc": "111", "typedoc": "CC", "force": False, "fechaE": "01/12/2014",
                                       "webhook_reference": "consulta-1"}


def test_lanzar_forzado_y_pasaporte_con_nombre():
    c, simulador = cliente()
    assert c.lanzar("CC", "127", fecha_expedicion=date(2015, 1, 5), forzar=True).jobid
    assert simulador.cuerpos()[-1]["force"] is True
    assert c.lanzar("PP", "381310014", nombre=" JUAN PEREZ PEREZ ").jobid
    assert simulador.cuerpos()[-1]["name"] == "JUAN PEREZ PEREZ"


def test_cc_en_cache_del_proveedor_no_trae_jobid():
    c, _ = cliente()
    assert c.lanzar("CC", "126").en_cache


@pytest.mark.parametrize("argumentos", [
    dict(tipo_documento="INT", numero="XY4322211000", nombre="EZRA WHITE EFYGH"),  # fuera de alcance
    dict(tipo_documento="CE", numero="960696"),                                    # CE sin fecha
    dict(tipo_documento="PP", numero="381310014"),                                 # PP sin nombre
    dict(tipo_documento="NIT", numero="ABC"),
    dict(tipo_documento="CC", numero=" - "),
])
def test_validaciones_previas_no_gastan_creditos(argumentos):
    c, simulador = cliente()
    with pytest.raises(ValueError):
        c.lanzar(**argumentos)
    assert simulador.peticiones == []


def test_documento_sin_separadores():
    assert limpiar_documento("1.234.567-8") == "12345678" and limpiar_documento("900 000,152") == "900000152"


def test_titular_que_no_autoriza_no_expone_datos():
    c, _ = cliente()
    with pytest.raises(TitularNoAutoriza) as error:
        c.lanzar("CC", "128", fecha_expedicion=date(2007, 6, 8))
    assert "128" not in str(error.value) and "instruccion" not in str(error.value)
    assert not error.value.reintentable


def test_solicitud_rechazada_y_credenciales():
    simulador = SimuladorTusdatos({("POST", "/api/launch"): httpx.Response(422, json={"detail": "x"})})
    c, _ = cliente(simulador)
    with pytest.raises(SolicitudRechazada):
        c.lanzar("CC", "999")
    c, _ = cliente(SimuladorTusdatos({("GET", f"/api/results/{JOB_CON_HALLAZGO}"): httpx.Response(401, json={})}))
    with pytest.raises(CredencialesRechazadas):
        c.estado(JOB_CON_HALLAZGO)


@pytest.mark.parametrize("falla,esperado", [
    (httpx.ReadTimeout("lento"), EfectoDesconocido),          # pudo llegar: no repetir
    (httpx.RemoteProtocolError("cortado"), EfectoDesconocido),
    (httpx.Response(502, json={}), EfectoDesconocido),
    (httpx.ConnectError("sin red"), ProveedorNoDisponible),   # no llegó: repetir es seguro
])
def test_lanzar_nunca_se_reintenta_solo(falla, esperado):
    c, simulador = cliente(SimuladorTusdatos({("POST", "/api/launch"): falla}))
    with pytest.raises(esperado) as error:
        c.lanzar("CC", "111")
    assert len(simulador.peticiones) == 1
    assert error.value.reintentable is (esperado is ProveedorNoDisponible)


# ── Estado del trabajo ───────────────────────────────────────────────────────

def test_estados_del_trabajo():
    c, _ = cliente()
    assert not c.estado("6769d210-3476-4c82-a044-045e9d5bc157").finalizado
    final = c.estado(JOB_CON_HALLAZGO)
    assert final.finalizado and final.reporte_id == REPORTE_CC and final.hallazgo and final.errores == ()
    assert final.validado is True
    con_error = c.estado("485e9823-df75-4b1e-9f64-58916a82dfd7")
    assert {"ofac", "lista_onu", "policia"} <= set(con_error.errores)
    nit = c.estado("e7451a5e-97ca-498e-a7f0-a352658cbc26")
    assert nit.reporte_id == REPORTE_NIT and nit.validado is None


def test_trabajo_vencido_y_consulta_fallida_no_se_reintentan():
    c, _ = cliente()
    with pytest.raises(TrabajoVencido):
        c.estado("00000000-0000-0000-0000-000000000000")
    fallido = SimuladorTusdatos({("GET", f"/api/results/{JOB_CON_HALLAZGO}"): httpx.Response(500, json={"estado": "error, consulta fallida"})})
    c, simulador = cliente(fallido)
    with pytest.raises(ConsultaFallida):
        c.estado(JOB_CON_HALLAZGO)
    assert len(simulador.peticiones) == 1


def test_identificadores_del_proveedor_no_permiten_cambiar_la_ruta():
    c, simulador = cliente()
    with pytest.raises(RespuestaInesperada):
        c.estado("../api/plans")
    assert simulador.peticiones == []


# ── Reporte, PDF y lecturas ──────────────────────────────────────────────────

def test_reporte_conserva_bytes_originales_para_la_huella():
    c, _ = cliente()
    reporte = c.reporte(REPORTE_CC)
    assert reporte.datos["ofac"] and len(reporte.sha256) == 64
    assert reporte.datos == httpx.Response(200, content=reporte.contenido).json()
    assert c.reporte(REPORTE_NIT).datos["ofac"] is False


def test_lecturas_se_reintentan_ante_caidas():
    ruta = ("GET", f"/api/report_json/{REPORTE_CC}")
    c, simulador = cliente(SimuladorTusdatos({ruta: [httpx.Response(503), httpx.ConnectError("x"),
                                                    httpx.Response(200, json={"ofac": False})]}))
    assert c.reporte(REPORTE_CC).datos == {"ofac": False} and len(simulador.peticiones) == 3
    c, simulador = cliente(SimuladorTusdatos({ruta: httpx.Response(503)}))
    with pytest.raises(ProveedorNoDisponible):
        c.reporte(REPORTE_CC)
    assert len(simulador.peticiones) == 3


def test_pdf_listo_en_preparacion_y_ruta_de_nit():
    persona = ("GET", f"/api/v2/report_pdf/{REPORTE_CC}")
    c, simulador = cliente(SimuladorTusdatos({persona: [
        httpx.Response(202, json={"status": "processing"}, headers={"Retry-After": "10"}),
        httpx.Response(200, content=PDF_MINIMO, headers={"content-type": "application/pdf"})]}))
    assert c.pdf(REPORTE_CC, es_nit=False) == PdfPendiente(reintentar_en=10)
    listo = c.pdf(REPORTE_CC, es_nit=False)
    assert isinstance(listo, DocumentoPdf) and listo.contenido == PDF_MINIMO
    assert simulador.peticiones[-1].url.params["async"] == "true"
    nit = ("GET", f"/api/v2/report_nit_pdf/{REPORTE_NIT}")
    c, simulador = cliente(SimuladorTusdatos({nit: httpx.Response(200, content=PDF_MINIMO)}))
    assert isinstance(c.pdf(REPORTE_NIT, es_nit=True), DocumentoPdf)


def test_pdf_del_sandbox_no_es_pdf_y_se_rechaza():
    c, _ = cliente()
    with pytest.raises(RespuestaInesperada, match="PDF"):
        c.pdf("5d9e00483800a5071688a101", es_nit=False)  # id de ejemplo de su documentación
    with pytest.raises(RespuestaInesperada, match="PDF"):
        c.pdf(REPORTE_NIT, es_nit=True)


def test_recarga_de_fuentes_con_error():
    ruta = ("GET", f"/api/retry/{REPORTE_CC}")
    c, simulador = cliente(SimuladorTusdatos({ruta: httpx.Response(200, json={"doc": 111, "jobid": JOB_CON_HALLAZGO})}))
    assert c.reintentar_fuentes(REPORTE_CC, "CC") == JOB_CON_HALLAZGO
    assert simulador.peticiones[-1].url.params["typedoc"] == "CC"
    c, simulador = cliente(SimuladorTusdatos({("GET", f"/api/retry_nit/{REPORTE_NIT}"): httpx.Response(200, json={"jobid": JOB_CON_HALLAZGO})}))
    assert c.reintentar_fuentes(REPORTE_NIT, "NIT") == JOB_CON_HALLAZGO


def test_salud_y_creditos():
    c, _ = cliente()
    fuentes = {f.codigo: f.estado for f in c.estado_fuentes()}
    assert fuentes["policia"] == "operational" and fuentes["procuraduria"] == "under_maintenance"
    assert c.creditos_restantes() == 0


# ── Interruptor y métricas ───────────────────────────────────────────────────

def test_interruptor_corta_tras_fallas_seguidas_y_se_recupera():
    instante = [0.0]
    interruptor = Interruptor(umbral=2, enfriamiento=30, reloj=lambda: instante[0])
    ruta = ("GET", f"/api/results/{JOB_CON_HALLAZGO}")
    c, simulador = cliente(SimuladorTusdatos({ruta: httpx.ConnectError("x")}), interruptor=interruptor, reintentos_lectura=0)
    for _ in range(2):
        with pytest.raises(ProveedorNoDisponible):
            c.estado(JOB_CON_HALLAZGO)
    with pytest.raises(ProveedorNoDisponible, match="Interruptor"):
        c.estado(JOB_CON_HALLAZGO)
    assert len(simulador.peticiones) == 2
    instante[0] = 31
    simulador.extras.clear()
    assert c.estado(JOB_CON_HALLAZGO).finalizado


def test_metricas_sin_datos_personales():
    metricas = []
    c, _ = cliente(metricas=metricas)
    c.lanzar("CC", "111", fecha_expedicion=date(2014, 12, 1))
    namespace, dimensiones, valores = metricas[-1]
    assert namespace == "Sagrilaft/Listas" and dimensiones == {"Proveedor": "Tusdatos", "Operacion": "lanzar"}
    assert "111" not in repr(metricas) and valores["TusdatosExito"] == 1


# ── Sandbox real (opcional) ──────────────────────────────────────────────────

@pytest.mark.skipif(os.getenv("LISTAS_TUSDATOS_SANDBOX") != "1", reason="Definir LISTAS_TUSDATOS_SANDBOX=1 para usar la red")
def test_flujo_completo_contra_el_sandbox_real():
    with ClienteTusdatos(configuracion(), dormir=lambda _s: None, metricas=lambda *a: None) as real:
        lanzado = real.lanzar("CC", "111", fecha_expedicion=date(2014, 12, 1))
        estado = real.estado(lanzado.jobid)
        assert estado.finalizado and real.reporte(estado.reporte_id).datos
