"""Registro único de modalidades: selección, no sustitución y extensión sin tocar el servicio común."""
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from api.routers.consultas_listas import disponibilidad
from domain.listas.contratos import CrearConsultaV2
from domain.listas.puertos import ListasNoDisponibles
from infrastructure.config.configuracion import SagrilaftListasConfig
from services.listas import modalidades
from services.listas.modalidades import (
    ConsultaAdmitida, ModalidadArchivos, ModalidadExterna, ModalidadSimulada,
    modalidad_de_consulta, modalidad_disponible, modalidad_vigente,
)
from services.listas.politica_v2 import ActorListas, PoliticaListasV2
from services.listas.servicio_comun import ServicioComunListas


@pytest.fixture(autouse=True)
def entorno_limpio(monkeypatch):
    for variable in ("LISTAS_IMPLEMENTACION", "PROVEEDOR_LISTAS_CAUTELA", "LISTAS_SIMULACION_ESCENARIO",
                     "LISTAS_ADMIN_HABILITADA", "LISTAS_BUSQUEDA_INDEPENDIENTE_HABILITADA",
                     "LISTAS_ARCHIVOS_LOCAL_HABILITADA", "LISTAS_ARCHIVOS_FUENTES", "LISTAS_ARCHIVOS_POLITICA_ID"):
        monkeypatch.delenv(variable, raising=False)


def configuracion(modo, **extra):
    return SagrilaftListasConfig(implementacion=modo, **({"escenario": "sin_coincidencias_v1"} if modo == "simulado" else {}), **extra)


def admitida(implementacion, version="2.0", **manifiesto):
    return ConsultaAdmitida(id=uuid4(), implementacion=implementacion, version_contrato=version,
        manifiesto=manifiesto, criterio={}, admitida_en=datetime.now(timezone.utc), tiene_borrador=False)


def servicio(modo, permisos=("listas.consultar",)):
    actor = ActorListas("emisor-prueba", "persona-1", frozenset(permisos))
    comun = ServicioComunListas(None, PoliticaListasV2(configuracion(modo), "development"), None, actor, ("cliente",))
    comun.puede_acceder_expediente = lambda *_: True
    return comun


def solicitud_20():
    return CrearConsultaV2.model_validate({"version_contrato": "2.0",
        "contexto": {"tipo": "EXPEDIENTE", "expediente_id": "exp-1", "sujeto_rol": "CONTRAPARTE"},
        "criterio": {"tipo_sujeto": "PERSONA", "nombre": "Persona ficticia"}})


@pytest.mark.parametrize("modo,clase,contrato", [("simulado", ModalidadSimulada, "2.0"), ("archivos", ModalidadArchivos, "2.1"),
                                                 ("externo", ModalidadExterna, "2.0")])
def test_cada_implementacion_tiene_su_modalidad(modo, clase, contrato):
    modalidad = modalidad_vigente(configuracion(modo))
    assert isinstance(modalidad, clase) and modalidad.version_contrato == contrato


def test_deshabilitado_nunca_se_sustituye():
    with pytest.raises(ListasNoDisponibles):
        modalidad_vigente(configuracion("deshabilitado"))
    assert modalidad_disponible(configuracion("deshabilitado"), "development") is None


def test_externo_sin_configuracion_de_tusdatos_no_esta_disponible(monkeypatch):
    for variable in ("LISTAS_TUSDATOS_URL", "LISTAS_TUSDATOS_TOKEN", "LISTAS_TUSDATOS_USUARIO", "LISTAS_TUSDATOS_CLAVE"):
        monkeypatch.delenv(variable, raising=False)
    assert modalidad_disponible(configuracion("externo"), "development") is None
    monkeypatch.setenv("LISTAS_TUSDATOS_URL", "http://docs.tusdatos.co")
    monkeypatch.setenv("LISTAS_TUSDATOS_USUARIO", "pruebas")
    monkeypatch.setenv("LISTAS_TUSDATOS_CLAVE", "password")
    assert isinstance(modalidad_disponible(configuracion("externo"), "development"), ModalidadExterna)
    assert modalidad_disponible(configuracion("externo"), "production") is None  # producción rechaza el sandbox


def test_manifiesto_simulado_conserva_su_forma_y_huella():
    """Las consultas ya admitidas y sus huellas dependen de esta forma exacta."""
    assert ModalidadSimulada().manifiesto(configuracion("simulado")) == {
        "implementacion": "simulado", "proveedor": "simulador", "adaptador": "simulado-v1",
        "algoritmo": "fixture-v1", "escenario": "sin_coincidencias_v1"}


def test_archivos_sin_habilitacion_local_no_esta_disponible():
    assert modalidad_disponible(configuracion("archivos"), "development") is None


@pytest.mark.parametrize("consulta,esperada", [
    (admitida("simulado", adaptador="simulado-v1", algoritmo="fixture-v1"), ModalidadSimulada),
    (admitida("archivos", "2.1"), ModalidadArchivos),
    (admitida("simulado", adaptador="otro", algoritmo="fixture-v1"), None),
    (admitida("archivos", "2.0"), None),
    (admitida("externo"), None),
])
def test_trabajador_ejecuta_con_la_modalidad_que_admitio(consulta, esperada):
    modalidad = modalidad_de_consulta(consulta)
    assert modalidad is None if esperada is None else isinstance(modalidad, esperada)


def test_contrato_distinto_al_de_la_modalidad_vigente_se_rechaza():
    with pytest.raises(ListasNoDisponibles, match="2.1"):
        servicio("archivos").crear("exp-1", solicitud_20(), "clave-1")


class ModalidadDePrueba:
    """Simula una modalidad nueva: solo se registra, no se toca el servicio común."""
    implementacion = "externo"
    version_contrato = "2.0"
    admite_forzar = False

    def __init__(self):
        self.creadas = []

    def disponible(self, entorno):
        return True

    def recuperar_reintento(self, servicio, solicitud, clave):
        return None

    def crear(self, servicio, solicitud, clave):
        self.creadas.append(clave)
        return "id-externo"

    def crear_grupo(self, servicio, expediente_id, clave, sesion):
        return {"grupo": clave}

    def reconoce(self, consulta):
        return consulta.implementacion == self.implementacion

    def ejecutar(self, trabajador, concesion, consulta):
        pass


def test_modalidad_nueva_se_conecta_solo_registrandola(monkeypatch):
    nueva = ModalidadDePrueba()
    monkeypatch.setitem(modalidades.MODALIDADES, "externo", nueva)
    comun = servicio("externo")
    assert comun.crear("exp-1", solicitud_20(), "clave-1").consulta_id == "id-externo" and nueva.creadas == ["clave-1"]
    assert disponibilidad(comun) == {"consultar": True, "historial": False, "revisar": False,
                                     "implementacion": "externo", "version_contrato": "2.0",
                                     "forzar": False, "ver_pdf_proveedor": False}
    assert modalidad_de_consulta(admitida("externo")) is nueva


def test_disponibilidad_sin_modalidad_no_ofrece_consultar(monkeypatch):
    monkeypatch.delenv("LISTAS_TUSDATOS_URL", raising=False)
    comun = SimpleNamespace(actor=ActorListas("e", "s", frozenset({"listas.consultar"})),
                            politica=SimpleNamespace(config=configuracion("externo")), entorno="development")
    assert disponibilidad(comun)["consultar"] is False and disponibilidad(comun)["version_contrato"] is None


# ── Forzar actualización y permisos del equipo revisor ───────────────────────

def test_revisor_abre_pdf_del_proveedor_y_fuerza_consultas():
    revisor = ActorListas.desde_identidad_validada("e", "s", ("listas_revisor",))
    operador = ActorListas.desde_identidad_validada("e", "s", ("listas_operador",))
    assert {"listas.ver_pdf_proveedor", "listas.forzar_actualizacion"} <= revisor.permisos
    assert not {"listas.ver_pdf_proveedor", "listas.forzar_actualizacion"} & operador.permisos


def test_forzar_exige_permiso_antes_de_tocar_la_modalidad():
    with pytest.raises(PermissionError):
        servicio("simulado").crear("exp-1", solicitud_20(), "clave-1", forzar=True)


def test_forzar_solo_aplica_a_la_modalidad_externa():
    comun = servicio("simulado", permisos=("listas.consultar", "listas.forzar_actualizacion"))
    with pytest.raises(ValueError, match="externa"):
        comun.crear("exp-1", solicitud_20(), "clave-1", forzar=True)
