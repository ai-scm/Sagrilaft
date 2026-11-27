"""F1: contratos, límites de confianza y selección. Sin bases de datos ni red."""
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from domain.listas.contratos import (
    ConsultaV2, CrearConsultaV2, ResultadoProveedorV2, SolicitudIdempotente,
)
from domain.listas.puertos import ListasNoDisponibles, SolicitudProveedorV2
from infrastructure.config.configuracion import SagrilaftListasConfig
from infrastructure.listas.fabrica import crear_consultor_v2
from infrastructure.listas.simulado import SimuladorListasV2
from services.listas.consulta_v2 import EjecutorConsultaV2
from services.listas.politica_v2 import ActorListas, PoliticaListasV2, AccesoListasDenegado


@pytest.fixture(autouse=True)
def entorno_limpio(monkeypatch):
    for variable in ("LISTAS_IMPLEMENTACION", "PROVEEDOR_LISTAS_CAUTELA", "LISTAS_SIMULACION_ESCENARIO",
                     "LISTAS_ADMIN_HABILITADA", "LISTAS_BUSQUEDA_INDEPENDIENTE_HABILITADA"):
        monkeypatch.delenv(variable, raising=False)


def solicitud(**criterio):
    return CrearConsultaV2.model_validate({
        "version_contrato": "2.0",
        "contexto": {"tipo": "EXPEDIENTE", "expediente_id": "exp-1", "sujeto_rol": "CONTRAPARTE"},
        "criterio": {"tipo_sujeto": "PERSONA", "nombre": "Persona ficticia", **criterio},
    })


def config(**kwargs):
    return SagrilaftListasConfig(implementacion="simulado", escenario="sin_coincidencias_v1", **kwargs)


def actor(*permisos, sub="persona-1"):
    return ActorListas("emisor-prueba", sub, frozenset(permisos))


def entrada_proveedor(**criterio):
    return SolicitudProveedorV2(
        consulta_id=uuid4(), correlacion_id=uuid4(), criterio=solicitud(**criterio).criterio,
        implementacion="simulado", proveedor="simulador", adaptador_version="simulado-v1",
        algoritmo_version="fixture-v1", parametros={}, admitida_en=datetime.now(timezone.utc),
        huella_configuracion="a" * 64,
    )


def resultado(escenario="sin_coincidencias_v1", **criterio):
    entrada = entrada_proveedor(**criterio)
    return SimuladorListasV2(escenario).consultar(entrada)


@pytest.mark.parametrize("cambio", [
    {"nombre": " "}, {"nombre": None}, {"nombre": "a" * 501},
    {"identificadores": [{"tipo": "CC", "valor": 123}]},
    {"identificadores": [{"tipo": "CC", "valor": " "}]},
    {"fecha_nacimiento": "2026-99-40"}, {"nacionalidades": ["Colombia"]},
    {"nombres_adicionales": ["x"] * 11}, {"riesgo": "ALTO"},
])
def test_criterios_invalidos(cambio):
    with pytest.raises(ValidationError):
        solicitud(**cambio)


def test_documentos_preservan_ceros_y_no_confunden_fechas():
    s = solicitud(nombre=None, identificadores=[{"tipo": "CC", "valor": "0000123"}], fecha_expedicion="2020-01-02")
    assert s.criterio.identificadores[0].valor == "0000123"
    assert s.criterio.fecha_nacimiento is None


@pytest.mark.parametrize("campo", ["actor", "proveedor", "version_id", "algoritmo", "riesgo"])
def test_cliente_no_impone_contexto_interno(campo):
    cuerpo = solicitud().model_dump()
    cuerpo[campo] = "inyectado"
    with pytest.raises(ValidationError):
        CrearConsultaV2.model_validate(cuerpo)


def test_contextos_no_se_mezclan_y_motivo_obligatorio():
    cuerpo = solicitud().model_dump()
    cuerpo["contexto"] = {"tipo": "INDEPENDIENTE"}
    with pytest.raises(ValidationError):
        CrearConsultaV2.model_validate(cuerpo)
    cuerpo["contexto"]["motivo"] = "Consulta autorizada de prueba"
    assert CrearConsultaV2.model_validate(cuerpo).contexto.tipo == "INDEPENDIENTE"
    cuerpo["contexto"]["expediente_id"] = "exp-1"
    with pytest.raises(ValidationError):
        CrearConsultaV2.model_validate(cuerpo)


def test_idempotencia_canonica_sin_promesa_de_reserva_en_memoria():
    primero = SolicitudIdempotente(clave="peticion-1", solicitud=solicitud())
    cuerpo = primero.solicitud.model_dump(mode="json")
    segundo = SolicitudIdempotente(clave="peticion-2", solicitud=dict(reversed(list(cuerpo.items()))))
    assert primero.hash_cuerpo == segundo.hash_cuerpo
    assert primero.hash_cuerpo != SolicitudIdempotente(clave="peticion-1", solicitud=solicitud(nombre="Otra persona")).hash_cuerpo
    with pytest.raises(ValidationError):
        SolicitudIdempotente(clave=" ", solicitud=solicitud())


@pytest.mark.parametrize("escenario,estado,conclusion", [
    ("sin_coincidencias_v1", "COMPLETADA", "SIN_CANDIDATOS"),
    ("coincidencia_v1", "COMPLETADA", "CON_CANDIDATOS"),
    ("parcial_v1", "PARCIAL", "NO_CONCLUYENTE"),
    ("error_v1", "FALLIDA", "NO_CONCLUYENTE"),
])
def test_escenarios_no_producen_riesgo_ni_sancion(escenario, estado, conclusion):
    r = resultado(escenario)
    assert r.estado_ejecucion == estado
    assert r.conclusion_busqueda == conclusion
    assert any(a.codigo == "SIMULADO" for a in r.advertencias)
    assert "riesgo" not in r.model_dump_json().lower()
    assert all(c.version_id is None for c in r.cobertura)
    assert ResultadoProveedorV2.model_validate_json(r.model_dump_json()) == r


def test_ids_deterministas_por_consulta_y_distintos_entre_consultas():
    s = entrada_proveedor()
    sim = SimuladorListasV2("coincidencia_v1")
    assert sim.consultar(s).candidatos == sim.consultar(s).candidatos
    assert sim.consultar(s).candidatos[0].id != resultado("coincidencia_v1").candidatos[0].id
    with pytest.raises(ListasNoDisponibles):
        sim.obtener_evidencia(uuid4())


def test_contexto_no_aplicado_se_declara():
    r = resultado(fecha_expedicion="2020-01-01")
    assert r.criterios_no_aplicados[0].descripcion == "fecha_expedicion"


@pytest.mark.parametrize("cambio", [
    {"conclusion_busqueda": "CON_CANDIDATOS"},
    {"estado_ejecucion": "FALLIDA"}, {"fecha_fin": None},
    {"cobertura": []}, {"advertencias": []}, {"nivel_riesgo": "ALTO"},
    {"fecha_inicio": "2026-01-01T00:00:00"},
])
def test_rechaza_resultados_contradictorios(cambio):
    datos = resultado().model_dump()
    datos.update(cambio)
    with pytest.raises(ValidationError):
        ResultadoProveedorV2.model_validate(datos)


def test_no_se_puede_ocultar_cobertura_parcial():
    datos = resultado("parcial_v1").model_dump()
    datos.update(estado_ejecucion="COMPLETADA", conclusion_busqueda="CON_CANDIDATOS")
    with pytest.raises(ValidationError):
        ResultadoProveedorV2.model_validate(datos)


def test_no_se_aceptan_candidatos_de_otra_cobertura():
    datos = resultado("coincidencia_v1").model_dump()
    datos["candidatos"][0]["cobertura_id"] = uuid4()
    with pytest.raises(ValidationError):
        ResultadoProveedorV2.model_validate(datos)


def test_archivos_no_puede_omitir_version_y_hash():
    datos = resultado().model_dump()
    datos["implementacion"] = "archivos"
    with pytest.raises(ValidationError):
        ResultadoProveedorV2.model_validate(datos)


def test_contrato_publico_exige_evidencia_sin_fabricarla_en_f1():
    s = solicitud()
    datos = resultado().model_dump()
    datos.update(contexto=s.contexto, criterio=s.criterio, fase="CERRANDO")
    with pytest.raises(ValidationError, match="informe interno"):
        ConsultaV2.model_validate(datos)
    datos["evidencias"] = [{"id": uuid4(), "tipo": "INFORME_INTERNO", "estado": "DISPONIBLE",
                             "sha256": "a" * 64, "creada_en": datetime.now(timezone.utc)}]
    assert ConsultaV2.model_validate(datos).evidencias[0].sha256 == "a" * 64


@pytest.mark.parametrize("anterior,nuevo", [("dummy", "simulado"), ("sagrilaft", "externo"), ("deshabilitado", "deshabilitado")])
def test_equivalencias_explicitas(anterior, nuevo):
    c = SagrilaftListasConfig(proveedor=anterior)
    assert c.implementacion == nuevo


def test_sin_configuracion_permanece_deshabilitado():
    assert SagrilaftListasConfig().implementacion == "deshabilitado"


@pytest.mark.parametrize("kwargs", [
    {"proveedor": "typo"}, {"implementacion": "typo"},
    {"proveedor": "dummy", "implementacion": "archivos"},
    {"implementacion": "simulado"}, {"proveedor": ""},
])
def test_falla_configuracion_invalida(kwargs):
    with pytest.raises(RuntimeError):
        SagrilaftListasConfig(**kwargs)


@pytest.mark.parametrize("modo", ["archivos", "externo", "deshabilitado"])
def test_fabrica_no_sustituye_por_simulador(modo):
    c = SagrilaftListasConfig(implementacion=modo)
    with pytest.raises(ListasNoDisponibles):
        crear_consultor_v2(c, "staging")
    if modo == "archivos":
        assert c.proveedor == "deshabilitado"


@pytest.mark.parametrize("modo", ["simulado", "archivos"])
def test_produccion_bloquea_simulador_y_archivos(modo):
    c = SagrilaftListasConfig(implementacion=modo, escenario="sin_coincidencias_v1")
    with pytest.raises(RuntimeError, match="producción"):
        crear_consultor_v2(c, "production")


def test_produccion_admite_tusdatos():
    SagrilaftListasConfig(implementacion="externo").validar_entorno("production")
    SagrilaftListasConfig(implementacion="deshabilitado").validar_entorno("production")


def test_produccion_no_admite_administracion():
    with pytest.raises(RuntimeError):
        PoliticaListasV2(SagrilaftListasConfig(admin_habilitada=True), "production")


def test_flags_mal_escritos_no_se_interpretan_como_true(monkeypatch):
    monkeypatch.setenv("LISTAS_ADMIN_HABILITADA", "tru")
    with pytest.raises(RuntimeError):
        SagrilaftListasConfig()


@pytest.mark.parametrize("usuario,acceso", [(actor(), True), (actor("listas.consultar", sub=""), True),
                                            (actor("listas.consultar"), False)])
def test_control_en_servicio_impide_invocar_adaptador(usuario, acceso):
    class NoDebeConsultarse:
        def capacidades(self):
            pytest.fail("El control debe preceder al adaptador")
    ejecutor = EjecutorConsultaV2(PoliticaListasV2(config(), "staging"), NoDebeConsultarse(), lambda *_: acceso)
    with pytest.raises(AccesoListasDenegado):
        ejecutor.consultar(usuario, solicitud(), uuid4(), uuid4())


def test_servicio_compartido_con_simulador():
    c = config()
    ejecutor = EjecutorConsultaV2(PoliticaListasV2(c, "staging"), crear_consultor_v2(c, "staging"), lambda *_: True)
    r = ejecutor.consultar(actor("listas.consultar"), solicitud(), uuid4(), uuid4())
    assert r.conclusion_busqueda == "SIN_CANDIDATOS"
    with pytest.raises(ValueError, match="identificador"):
        ejecutor.consultar(actor("listas.consultar"), solicitud(identificadores=[{"tipo": "OTRO", "valor": "1"}]), uuid4(), uuid4())


def test_contrato_admite_proveedor_externo_sin_version_inventada():
    class ExternoDePrueba:
        def capacidades(self):
            return SimuladorListasV2("sin_coincidencias_v1").capacidades().model_copy(update={"proveedor": "doble-externo"})
        def consultar(self, s):
            datos = SimuladorListasV2("sin_coincidencias_v1").consultar(s).model_dump()
            datos.update(implementacion="externo", proveedor="doble-externo", advertencias=[])
            datos["cobertura"][0].update(version_declarada=None, nombre_origen="Cobertura declarada por el doble")
            return ResultadoProveedorV2.model_validate(datos)
    c = SagrilaftListasConfig(implementacion="externo")
    r = EjecutorConsultaV2(PoliticaListasV2(c, "staging"), ExternoDePrueba(), lambda *_: True).consultar(
        actor("listas.consultar"), solicitud(), uuid4(), uuid4())
    assert r.cobertura[0].version_id is None
    assert r.cobertura[0].version_declarada is None


def test_descarga_historica_no_depende_flag_pero_si_permiso():
    p = PoliticaListasV2(SagrilaftListasConfig(), "staging")
    p.evidencia(actor("listas.ver_evidencias"), "e1", lambda *_: True)
    with pytest.raises(AccesoListasDenegado):
        p.evidencia(actor("listas.ver_evidencias"), "e1", lambda *_: False)
    with pytest.raises(ListasNoDisponibles):
        p.consulta(actor("listas.consultar"), solicitud(), lambda *_: True)


def test_independiente_necesita_flag_y_permiso():
    s = CrearConsultaV2(version_contrato="2.0", contexto={"tipo": "INDEPENDIENTE", "motivo": "Prueba con permiso explícito"}, criterio=solicitud().criterio)
    with pytest.raises(ListasNoDisponibles):
        PoliticaListasV2(config(), "staging").consulta(actor("listas.consultar_independiente"), s, lambda *_: True)
    p = PoliticaListasV2(config(independiente_habilitada=True), "staging")
    with pytest.raises(AccesoListasDenegado):
        p.consulta(actor("listas.consultar"), s, lambda *_: True)
    p.consulta(actor("listas.consultar_independiente"), s, lambda *_: False)


@pytest.mark.parametrize("operacion", ["activar", "revertir"])
def test_cargar_no_implica_permiso_de_activacion(operacion):
    p = PoliticaListasV2(config(admin_habilitada=True), "staging")
    with pytest.raises(AccesoListasDenegado):
        p.administracion(actor("listas.importar"), operacion)
    p.administracion(actor("listas.activar_version"), operacion)


def test_mismo_usuario_aprueba_sin_omitir_flag():
    a = actor("listas.importar", "listas.aprobar_version", "listas.activar_version")
    p = PoliticaListasV2(config(admin_habilitada=True), "staging")
    p.aprobar(a, a)
    p.aprobar(actor("listas.aprobar_version", sub="persona-2"), a)
    with pytest.raises(ListasNoDisponibles):
        PoliticaListasV2(config(), "staging").aprobar(actor("listas.aprobar_version", sub="persona-2"), a)


def test_roles_del_portal_dan_listas_de_expediente_pero_no_administracion():
    """Desde el 2026-11-27 acceso_clientes / acceso_proveedores bastan para listas sobre expedientes."""
    for rol in ("acceso_clientes", "acceso_proveedores"):
        a = ActorListas.desde_identidad_validada("issuer", "sub", (rol,))
        assert a.permisos == frozenset({"listas.consultar", "listas.ver_evidencias", "listas.revisar",
                                        "listas.ver_pdf_proveedor", "listas.forzar_actualizacion"})
        assert not {"listas.importar", "listas.activar_version", "listas.consultar_independiente"} & a.permisos
    assert ActorListas.desde_identidad_validada("issuer", "sub", ("administrador",)).permisos == frozenset()
    cargador = ActorListas.desde_identidad_validada("issuer", "sub", ("listas_cargador",))
    assert "listas.importar" in cargador.permisos
    assert "listas.activar_version" not in cargador.permisos
    operador = ActorListas.desde_identidad_validada("issuer", "sub", ("listas_operador",))
    assert operador.permisos == frozenset({"listas.consultar", "listas.ver_evidencias"})


def test_servicio_rechaza_respuesta_de_otra_consulta():
    class RespuestaAjena:
        def capacidades(self):
            return SimuladorListasV2("sin_coincidencias_v1").capacidades()
        def consultar(self, s):
            return resultado()
    ejecutor = EjecutorConsultaV2(PoliticaListasV2(config(), "staging"), RespuestaAjena(), lambda *_: True)
    with pytest.raises(ValueError, match="otra consulta"):
        ejecutor.consultar(actor("listas.consultar"), solicitud(), uuid4(), uuid4())


def test_proveedor_no_puede_fingir_resultado_completo_deshabilitado():
    datos = resultado().model_dump()
    datos["implementacion"] = "deshabilitado"
    with pytest.raises(ValidationError):
        ResultadoProveedorV2.model_validate(datos)


def test_dos_selectores_equivalentes_son_validos(monkeypatch):
    monkeypatch.setenv("LISTAS_IMPLEMENTACION", "simulado")
    monkeypatch.setenv("PROVEEDOR_LISTAS_CAUTELA", "dummy")
    monkeypatch.setenv("LISTAS_SIMULACION_ESCENARIO", "parcial_v1")
    c = SagrilaftListasConfig()
    assert c.implementacion == "simulado"
    assert c.escenario == "parcial_v1"


def test_archivos_no_llega_al_dummy_heredado():
    from infrastructure.servicios_externos.sagrilaft.fabrica import obtener_consultor_listas
    from infrastructure.servicios_externos.sagrilaft.deshabilitado import ConsultorListasCautelaDeshabilitado
    c = SagrilaftListasConfig(implementacion="archivos")
    assert isinstance(obtener_consultor_listas(c), ConsultorListasCautelaDeshabilitado)
