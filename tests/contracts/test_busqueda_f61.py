"""Contratos y preparación F6.1: sin buscador, red, ORM ni bases de datos."""
from datetime import date, datetime, timezone
import json
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from domain.listas.catalogos_busqueda import (
    CatalogoPreparacion, DefinicionIdentificador, EquivalenciaPais, IDENTIFICADORES_INICIALES,
)
from domain.listas.contratos import CrearConsultaV2, Criterio, SolicitudIdempotente
from domain.listas.contratos_busqueda import (
    CandidatoClasificado, CapacidadesBusqueda, ConsultaBusquedaF6, CrearConsultaBusqueda,
    CriterioBusqueda, ManifiestoBusqueda, MotivoClasificacion, ResultadoBusquedaF6,
    SolicitudBusquedaInterna, SolicitudIdempotenteBusqueda, VersionBusquedaFijada,
)
from domain.listas.datos_busqueda import FechaDato, ReferenciaDato, RegistroBusqueda
from infrastructure.listas.catalogos_ofac import CALIDADES_OFAC_ADVANCED
from services.listas.preparacion_criterios import DatosExpedienteBusqueda, preparar_expediente


@pytest.fixture
def catalogo():
    return CatalogoPreparacion(version="criterios-pruebas-v1", identificadores=IDENTIFICADORES_INICIALES,
        paises=(EquivalenciaPais(declarado="CO", codigo="CO"),
                EquivalenciaPais(declarado="Colombia", codigo="CO")))


def preparar(catalogo, **cambios):
    datos = {"expediente_id": "exp-1", "tipo_persona": "juridica",
             "razon_social": "Empresa ficticia", **cambios}
    return preparar_expediente(DatosExpedienteBusqueda(**datos), catalogo)


def referencia(**cambios):
    return ReferenciaDato(fuente_codigo="lista_prueba", version_id=uuid4(), registro_id=uuid4(),
                         campo_original="sujeto/nombre", **cambios)


def cuerpo_candidato():
    ref = referencia()
    return dict(id=uuid4(), cobertura_id=uuid4(), registro_id=ref.registro_id,
        tipo_sujeto="PERSONA", nombre_principal="Persona de prueba", nivel="MEDIA",
        regla_codigo="NOMBRE_COMPLETO", regla_version="reglas-v1",
        explicacion="Coincide el nombre; falta documento para corroborar.",
        algoritmo_version="algoritmo-prueba-v1",
        motivos=[dict(campo="nombre", resultado="COINCIDE", metodo="NOMBRE_EXACTO",
            explicacion="Mismo nombre completo.", valor_consultado="Persona de prueba",
            valor_fuente="Persona de prueba", referencia=ref)])


def resultado_archivos():
    candidato = CandidatoClasificado(**cuerpo_candidato())
    ref = candidato.motivos[0].referencia
    ahora = datetime.now(timezone.utc)
    return ResultadoBusquedaF6(consulta_id=uuid4(), implementacion="archivos", proveedor="archivos",
        estado_ejecucion="COMPLETADA", conclusion_busqueda="CON_CANDIDATOS",
        cobertura=[dict(id=candidato.cobertura_id, fuente_codigo=ref.fuente_codigo,
            nombre_origen="Lista de prueba", version_id=ref.version_id,
            hash_contenido="a"*64, revision_activa=1, estado="CONSULTADA")],
        candidatos=[candidato], fecha_inicio=ahora, fecha_fin=ahora)


def version(**cambios):
    return VersionBusquedaFijada(**dict(fuente_codigo="lista_prueba", version_id=uuid4(),
        revision_activa=1, hash_contenido="a"*64, generacion_id=uuid4(), generacion_hash="b"*64,
        version_adaptador="adaptador-v1", version_normalizacion="conservacion-v1", **cambios))


def manifiesto(*fuentes):
    return ManifiestoBusqueda(politica_version="politica-v1", reglas_version="reglas-v1",
        algoritmo_version="algoritmo-prueba-v1", catalogos_hash="c"*64,
        parametros_internos_hash="d"*64, fuentes=fuentes or [version()])


@pytest.mark.parametrize("nivel", ["ALTA", "MEDIA", "BAJA"])
def test_candidato_exige_nivel_y_explicacion(nivel):
    datos = cuerpo_candidato()
    datos["nivel"] = nivel
    candidato = CandidatoClasificado(**datos)
    assert candidato.nivel == nivel
    assert candidato.explicacion and candidato.regla_codigo


@pytest.mark.parametrize("nivel", ["ALTO", "MEDIO", "BAJO", "SIN_NIVEL", None, "97"])
def test_no_hay_cuarta_categoria(nivel):
    datos = cuerpo_candidato()
    datos["nivel"] = nivel
    with pytest.raises(ValidationError):
        CandidatoClasificado(**datos)


@pytest.mark.parametrize("campo", ["puntaje", "porcentaje", "escala_puntaje", "riesgo"])
def test_sin_puntajes_o_decisiones_en_candidato_publico(campo):
    with pytest.raises(ValidationError):
        CandidatoClasificado(**cuerpo_candidato(), **{campo: 97})


def test_resultado_publico_no_declara_campos_tecnicos_de_similitud():
    esquema = json.dumps(ConsultaBusquedaF6.model_json_schema())
    assert '"puntaje"' not in esquema and '"escala_puntaje"' not in esquema
    resultado = resultado_archivos()
    assert ResultadoBusquedaF6.model_validate_json(resultado.model_dump_json()) == resultado


@pytest.mark.parametrize("campo", ["explicacion", "regla_codigo", "regla_version", "motivos"])
def test_no_se_admite_categoria_sin_justificacion(campo):
    datos = cuerpo_candidato()
    datos.pop(campo)
    with pytest.raises(ValidationError):
        CandidatoClasificado(**datos)


def test_diferencia_no_se_presenta_como_ausencia():
    datos = cuerpo_candidato()["motivos"][0]
    datos["resultado"] = "AUSENTE"
    with pytest.raises(ValidationError):
        MotivoClasificacion(**datos)


def test_no_se_fabrica_candidato_solo_con_contradicciones():
    datos = cuerpo_candidato()
    datos["motivos"][0]["resultado"] = "DIFERENTE"
    with pytest.raises(ValidationError):
        CandidatoClasificado(**datos)


@pytest.mark.parametrize("campo", ["version_id", "registro_id", "fuente_codigo"])
def test_rechaza_motivos_de_otro_origen(campo):
    datos = resultado_archivos().model_dump()
    datos["candidatos"][0]["motivos"][0]["referencia"][campo] = (
        "otra_fuente" if campo == "fuente_codigo" else uuid4())
    with pytest.raises(ValidationError):
        ResultadoBusquedaF6.model_validate(datos)


def test_consulta_necesita_informe_interno_y_conserva_control_f3():
    datos = resultado_archivos().model_dump()
    datos.update(contexto=dict(tipo="EXPEDIENTE", expediente_id="exp-1", sujeto_rol="CONTRAPARTE"),
        criterio=dict(tipo_sujeto="PERSONA", nombre="Persona prueba"), fase="FINALIZADA")
    with pytest.raises(ValidationError):
        ConsultaBusquedaF6(**datos)
    datos["evidencias"] = [dict(id=uuid4(), tipo="INFORME_INTERNO", estado="DISPONIBLE",
        sha256="e"*64, creada_en=datetime.now(timezone.utc))]
    assert ConsultaBusquedaF6(**datos).evidencias[0].estado == "DISPONIBLE"


@pytest.mark.parametrize("datos,precision", [
    ({"precision":"ANIO","valor":{"anio":1980}}, "ANIO"),
    ({"precision":"MES","valor":{"anio":1980,"mes":2}}, "MES"),
    ({"precision":"DIA","valor":{"anio":1980,"mes":2,"dia":29}}, "DIA"),
    ({"precision":"RANGO","desde":{"anio":1979},"hasta":{"anio":1981}}, "RANGO"),
    ({"precision":"NO_INTERPRETADA"}, "NO_INTERPRETADA"),
])
def test_fecha_no_inventa_precision(datos, precision):
    fecha = FechaDato(original="Valor de prueba", calendario="GREGORIANO", **datos)
    assert fecha.precision == precision
    if precision == "ANIO":
        assert fecha.valor.mes is None and fecha.valor.dia is None
    if precision == "RANGO":
        assert fecha.desde.mes is None and fecha.hasta.dia is None


@pytest.mark.parametrize("datos", [
    {"precision":"DIA","valor":{"anio":1981,"mes":2,"dia":29}},
    {"precision":"ANIO","valor":{"anio":1980,"mes":1}},
    {"precision":"DIA","valor":{"anio":1980,"dia":1}},
    {"precision":"NO_INTERPRETADA","valor":{"anio":1980}},
    {"precision":"RANGO","desde":{"anio":1981},"hasta":{"anio":1979}},
    {"precision":"RANGO","desde":{"anio":1980}},
])
def test_fecha_inconsistente_se_rechaza(datos):
    with pytest.raises(ValidationError):
        FechaDato(original="Valor de prueba", calendario="GREGORIANO", **datos)


def test_calendario_desconocido_no_se_convierte_a_gregoriano():
    with pytest.raises(ValidationError):
        FechaDato(original="Otra fecha", calendario="OTRO", precision="DIA",
                  valor={"anio": 1980, "mes": 1, "dia": 1})
    fecha = FechaDato(original="Otra fecha", calendario="OTRO", precision="NO_INTERPRETADA")
    assert fecha.valor is None and fecha.original == "Otra fecha"


def test_identificadores_largos_no_se_truncan_ni_modifican_20():
    valor = "0" + "X" * 199
    nuevo = CriterioBusqueda(tipo_sujeto="PERSONA", identificadores=[{"tipo": "CC", "valor": valor}])
    assert nuevo.identificadores[0].valor == valor
    with pytest.raises(ValidationError):
        Criterio(tipo_sujeto="PERSONA", identificadores=[{"tipo": "CC", "valor": valor}])


def test_calidad_ofac_no_se_inventa():
    assert CALIDADES_OFAC_ADVANCED.resolver("1560") == "CONFIRMADO"
    assert CALIDADES_OFAC_ADVANCED.resolver("1561") == "FALSO"
    assert CALIDADES_OFAC_ADVANCED.resolver("91479") == "REPORTADO"
    assert CALIDADES_OFAC_ADVANCED.resolver("1") == "DESCONOCIDO"
    assert CALIDADES_OFAC_ADVANCED.resolver(None) == "DESCONOCIDO"
    assert CALIDADES_OFAC_ADVANCED.resolver("futuro") == "DESCONOCIDO"


def test_registro_no_mezcla_hechos_de_otras_versiones():
    ref = referencia()
    with pytest.raises(ValidationError):
        RegistroBusqueda(tipo_sujeto="PERSONA", referencia=ref,
            nombres=[dict(valor="Persona", tipo="PRINCIPAL", referencia=referencia())])


def test_proveedor_puede_referir_respuesta_sin_inventar_version():
    ref = ReferenciaDato(fuente_codigo="proveedor_prueba", respuesta_sha256="e"*64, campo_original="respuesta/nombre")
    assert ref.version_id is None
    with pytest.raises(ValidationError):
        ReferenciaDato(fuente_codigo="proveedor_prueba", campo_original="respuesta/nombre")


def test_manifiesto_no_mezcla_dos_versiones_de_la_misma_fuente():
    with pytest.raises(ValidationError):
        manifiesto(version(), version())


def test_manifiesto_hash_cambia_con_generacion_y_rechaza_mutacion():
    m = manifiesto()
    assert m.huella == ManifiestoBusqueda.model_validate_json(m.model_dump_json()).huella
    datos = m.model_dump()
    datos["fuentes"][0]["generacion_id"] = uuid4()
    assert m.huella != ManifiestoBusqueda(**datos).huella
    with pytest.raises(ValidationError):
        m.reglas_version = "otras"


def test_solicitud_publica_no_permite_fuentes_actor_o_generacion():
    base = dict(contexto=dict(tipo="EXPEDIENTE", expediente_id="exp-1", sujeto_rol="CONTRAPARTE"),
                criterio=dict(tipo_sujeto="PERSONA", nombre="Persona prueba"))
    for campo in ("actor", "fuentes", "manifiesto"):
        with pytest.raises(ValidationError):
            CrearConsultaBusqueda(**base, **{campo: {}})
    with pytest.raises(ValidationError):
        CrearConsultaBusqueda(contexto=dict(tipo="INDEPENDIENTE", motivo="Prueba independiente"),
                               criterio=base["criterio"])


def test_solicitud_interna_requiere_admision_con_zona():
    with pytest.raises(ValidationError):
        SolicitudBusquedaInterna(consulta_id=uuid4(), correlacion_id=uuid4(),
            contexto=dict(tipo="EXPEDIENTE", expediente_id="exp-1", sujeto_rol="CONTRAPARTE"),
            criterio=dict(tipo_sujeto="PERSONA", nombre="Persona prueba"), proveedor="archivos",
            implementacion="archivos", admitida_en=datetime(2026,1,1), manifiesto=manifiesto())


def test_capacidades_declaran_persona_y_empresa_sin_duplicados():
    capacidades = CapacidadesBusqueda(proveedor="prueba", adaptador_version="v1", campos=["nombre"],
                                      tipos_sujeto=["PERSONA", "ENTIDAD"])
    assert capacidades.campos == ("nombre",)
    with pytest.raises(ValidationError):
        CapacidadesBusqueda(proveedor="prueba", adaptador_version="v1", campos=["nombre","nombre"],
                            tipos_sujeto=["PERSONA"])


@pytest.mark.parametrize("rol_comercial", ["cliente", "proveedor"])
def test_natural_no_se_duplica_como_representante(catalogo, rol_comercial):
    r = preparar(catalogo, tipo_persona="natural", tipo_contraparte=rol_comercial,
        razon_social="Persona de prueba", nombre_representante="Persona de prueba",
        tipo_identificacion="NIT", numero_identificacion="0000456", digito_verificacion="8",
        tipo_doc_representante="PAS", numero_doc_representante="AB0001234",
        fecha_nacimiento="1980-03-15", nacionalidad="CO")
    assert len(r.sujetos) == 1 and r.sujetos[0].rol == "CONTRAPARTE"
    c = r.sujetos[0].criterio
    assert c.tipo_sujeto == "PERSONA" and c.fecha_nacimiento == date(1980,3,15)
    assert c.identificadores[1].tipo == "PASAPORTE" and c.identificadores[1].valor == "AB0001234"
    assert c.nacionalidades == ("CO",)
    # Los dos documentos de una persona natural usan su nacionalidad, no un domicilio.
    assert all(i.pais_emisor == "CO" for i in c.identificadores)
    assert r.omitidos[0].motivo == "BLOQUE_PERSONAL_ES_CONTRAPARTE"


def test_natural_sin_bloque_personal_sigue_consultable(catalogo):
    r = preparar(catalogo, tipo_persona="natural", numero_identificacion="000123", tipo_identificacion="CC")
    assert r.sujetos[0].criterio.nombre == "Empresa ficticia"
    assert r.sujetos[0].criterio.tipo_sujeto == "PERSONA"
    origen = next(o for o in r.sujetos[0].origenes if o.campo_expediente == "razon_social")
    assert origen.campo_criterio == "nombre"


def test_empresa_no_recibe_nacimiento_o_documento_del_representante(catalogo):
    r = preparar(catalogo, tipo_contraparte="cliente", tipo_identificacion="NIT",
        numero_identificacion="000456", nombre_representante="Representante prueba",
        tipo_doc_representante="CC", numero_doc_representante="000987",
        fecha_nacimiento="1980-03-15", nacionalidad="CO", pais="Colombia")
    empresa, persona = r.sujetos
    assert empresa.criterio.tipo_sujeto == "ENTIDAD" and empresa.criterio.fecha_nacimiento is None
    assert not empresa.criterio.nacionalidades
    assert empresa.criterio.identificadores[0].valor == "000456"
    # El NIT de la propia empresa sí usa su país de domicilio declarado: una empresa
    # no se registra con un NIT de un país distinto al suyo (no es una inferencia).
    assert empresa.criterio.identificadores[0].pais_emisor == "CO"
    assert empresa.criterio.ubicaciones[0].pais == "CO"
    assert persona.criterio.fecha_nacimiento == date(1980,3,15)
    assert persona.criterio.identificadores[0].valor == "000987"


def test_rol_cliente_proveedor_no_cambia_criterios(catalogo):
    a = preparar(catalogo, tipo_contraparte="cliente")
    b = preparar(catalogo, tipo_contraparte="proveedor")
    assert a.sujetos[0].criterio == b.sujetos[0].criterio


def test_nit_no_determina_naturaleza_y_bloque_ambiguo_no_se_mezcla(catalogo):
    r = preparar(catalogo, tipo_persona=None, tipo_identificacion="NIT", numero_identificacion="000123",
        nombre_representante="Nombre ambiguo", fecha_nacimiento="1980-03-15")
    assert len(r.sujetos) == 1
    assert r.sujetos[0].criterio.tipo_sujeto == "NO_DETERMINADO"
    assert r.sujetos[0].criterio.fecha_nacimiento is None
    assert r.omitidos[0].motivo == "NATURALEZA_NO_DETERMINADA"


@pytest.mark.parametrize("campo,valor,codigo", [
    ("fecha_nacimiento","1980","FECHA_NO_INTERPRETADA"),
    ("fecha_nacimiento","1980-02-31","FECHA_NO_INTERPRETADA"),
    ("nacionalidad","Pais desconocido","PAIS_NO_INTERPRETADO"),
])
def test_contexto_ininterpretable_se_conserva_sin_inventar(catalogo,campo,valor,codigo):
    r = preparar(catalogo,tipo_persona="natural",**{campo:valor})
    sujeto = r.sujetos[0]
    assert any(a.codigo == codigo for a in sujeto.avisos)
    assert any(o.valor_original == valor for o in sujeto.origenes)
    assert sujeto.criterio.fecha_nacimiento is None and sujeto.criterio.nacionalidades == ()


@pytest.mark.parametrize("tipo,digito", [(None,None),("DESCONOCIDO",None),("NIT","NA")])
def test_documento_no_interpretado_no_se_oculta_como_aplicado(catalogo,tipo,digito):
    r = preparar(catalogo,tipo_identificacion=tipo,numero_identificacion="000123",digito_verificacion=digito)
    sujeto = r.sujetos[0]
    assert sujeto.criterios_exigidos_no_interpretados == ("identificadores",)
    assert any(o.valor_original == "000123" for o in sujeto.origenes)


def test_sin_criterio_interpretable_omite_sujeto_pero_conserva_diagnostico(catalogo):
    r = preparar(catalogo,razon_social=None,numero_identificacion="000123",tipo_identificacion=None)
    assert not r.sujetos
    assert r.omitidos[0].motivo == "CRITERIO_PRIMARIO_NO_INTERPRETADO"
    assert any(o.valor_original == "000123" for o in r.omitidos[0].origenes)


def test_no_extrae_digito_de_la_base_y_usa_el_pais_de_domicilio_declarado(catalogo):
    r = preparar(catalogo,tipo_identificacion="NIT",numero_identificacion="9001234568",pais="CO")
    i = r.sujetos[0].criterio.identificadores[0]
    # El dígito no se extrae de un número más largo (eso sería inventar un dato).
    # El país sí se usa porque viene declarado como domicilio de la propia empresa.
    assert i.valor == "9001234568" and i.digito_verificacion is None and i.pais_emisor == "CO"


def test_no_asume_pais_del_documento_cuando_no_hay_dato_declarado(catalogo):
    r = preparar(catalogo,tipo_identificacion="NIT",numero_identificacion="9001234568",pais=None)
    i = r.sujetos[0].criterio.identificadores[0]
    assert i.pais_emisor is None


def test_documento_de_persona_natural_usa_su_nacionalidad_no_su_domicilio(catalogo):
    r = preparar(catalogo,tipo_persona="natural",tipo_identificacion="PASAPORTE",
        numero_identificacion="X1234567",nacionalidad="CO",pais="Panamá")
    i = r.sujetos[0].criterio.identificadores[0]
    assert i.pais_emisor == "CO"


def test_roles_geograficos_no_se_confunden(catalogo):
    r = preparar(catalogo,tipo_persona="natural",ciudad_nacimiento="Medellín",
        ciudad_expedicion="Cali",direccion_residencia="Calle prueba",ciudad_residencia="Bogotá",
        direccion_funciones="Oficina prueba",ciudad_funciones="Barranquilla",pais_funciones="CO",pais="CO")
    roles = {u.rol for u in r.sujetos[0].criterio.ubicaciones}
    assert roles == {"NACIMIENTO","EMISION","RESIDENCIA","FUNCIONES","DOMICILIO"}
    assert r.sujetos[0].criterio.ciudadanias == ()


def test_documento_repetido_no_se_duplica_y_origenes_permanecen(catalogo):
    r = preparar(catalogo,tipo_persona="natural",tipo_identificacion="CC",numero_identificacion="000123",
        tipo_doc_representante="CC",numero_doc_representante="000123")
    assert len(r.sujetos[0].criterio.identificadores) == 1
    assert sum(o.campo_criterio == "identificadores.valor" for o in r.sujetos[0].origenes) == 2


def test_catalogo_no_permite_alias_ambiguos(catalogo):
    datos = catalogo.model_dump()
    datos["identificadores"] = list(datos["identificadores"])
    datos["identificadores"].append(dict(tipo="OTRO",alias=["PAS"],esquema="OTRO",
        jurisdiccion_requerida=True,multiples_por_sujeto=True))
    with pytest.raises(ValidationError):
        CatalogoPreparacion(**datos)


def test_catalogo_huella_y_version_se_conservan(catalogo):
    r = preparar(catalogo)
    assert r.catalogo_huella == catalogo.huella
    datos = catalogo.model_dump()
    datos["version"] = "otra-version"
    assert CatalogoPreparacion(**datos).huella != r.catalogo_huella


@pytest.mark.parametrize("campo,valor", [
    ("fecha_nacimiento",None),("riesgo","ALTO"),("identificadores",[]),
])
def test_no_se_exigen_campos_ausentes_o_ajenos(campo,valor):
    datos = dict(tipo_sujeto="PERSONA",nombre="Persona prueba",campos_exigidos=[campo])
    if campo != "riesgo":
        datos[campo] = valor
    with pytest.raises(ValidationError):
        CriterioBusqueda(**datos)


def test_compatibilidad_20_conserva_serializacion_hash_y_version():
    datos = dict(version_contrato="2.0",contexto=dict(tipo="EXPEDIENTE",expediente_id="exp-1",
        sujeto_rol="CONTRAPARTE"),criterio=dict(tipo_sujeto="PERSONA",nombre="Persona prueba",
        identificadores=[dict(tipo="CC",valor="000123")]))
    vieja = CrearConsultaV2(**datos)
    cuerpo = vieja.model_dump(mode="json")
    referencia = json.loads((Path(__file__).resolve().parents[1]/"fixtures/listas_f61/solicitud_20.json").read_text())
    hash_esperado = referencia["hash_cuerpo"]
    assert cuerpo == referencia["solicitud"]
    assert SolicitudIdempotente(clave="prueba",solicitud=vieja).hash_cuerpo == hash_esperado
    assert set(Criterio.model_fields) == {"tipo_sujeto","nombre","nombres_adicionales","identificadores",
        "fecha_nacimiento","fecha_expedicion","nacionalidades","ubicacion"}
    nueva = CrearConsultaBusqueda(contexto=datos["contexto"],criterio=CriterioBusqueda(**datos["criterio"]))
    assert SolicitudIdempotenteBusqueda(clave="prueba",solicitud=nueva).hash_cuerpo != hash_esperado
    with pytest.raises(ValidationError):
        CrearConsultaV2.model_validate(nueva.model_dump())




# --- Internacionalización del país emisor: contra el catálogo real de producción, no el de pruebas.
# CATALOGO_MOTOR no trae una tabla de equivalencias de países poblada; el código ISO que ya
# guarda el formulario debe usarse y validarse directamente, sin asumir Colombia por defecto.
from services.listas.motor_busqueda import CATALOGO_MOTOR  # noqa: E402


def preparar_con_catalogo_real(**cambios):
    datos = {"expediente_id": "exp-1", "tipo_persona": "juridica", "razon_social": "Empresa ficticia", **cambios}
    return preparar_expediente(DatosExpedienteBusqueda(**datos), CATALOGO_MOTOR)


def test_pais_emisor_internacional_no_se_asume_colombia_con_catalogo_real():
    r = preparar_con_catalogo_real(tipo_identificacion="NIT", numero_identificacion="59536969", pais="GT")
    i = r.sujetos[0].criterio.identificadores[0]
    assert i.pais_emisor == "GT"
    assert not r.sujetos[0].avisos


def test_pais_emisor_colombia_tambien_funciona_con_catalogo_real():
    r = preparar_con_catalogo_real(tipo_identificacion="NIT", numero_identificacion="800080688-0", pais="CO")
    assert r.sujetos[0].criterio.identificadores[0].pais_emisor == "CO"


def test_nacionalidad_internacional_con_catalogo_real():
    r = preparar_expediente(DatosExpedienteBusqueda(expediente_id="exp-1", tipo_persona="natural",
        razon_social="Persona ficticia", nacionalidad="VE"), CATALOGO_MOTOR)
    assert r.sujetos[0].criterio.nacionalidades == ("VE",)


@pytest.mark.parametrize("valor", ["Colombia", "colombia", "ZZ", "123", ""])
def test_pais_no_valido_no_se_inventa_con_catalogo_real(valor):
    r = preparar_con_catalogo_real(tipo_identificacion="NIT", numero_identificacion="900123456", pais=valor)
    i = r.sujetos[0].criterio.identificadores[0]
    assert i.pais_emisor is None
    if valor:
        assert any(a.codigo == "PAIS_NO_INTERPRETADO" for a in r.sujetos[0].avisos)


def test_nit_guatemalteco_no_recibe_el_recorte_de_puntos_y_guion_de_colombia():
    """Un identificador tributario de otro país no debe tratarse con las reglas
    de formato colombianas (separador de miles con punto, dígito tras guion)."""
    from domain.listas.comparacion_identificadores import preparar_identificador
    from domain.listas.contratos_busqueda import IdentificadorConsulta
    gt = preparar_identificador(IdentificadorConsulta(tipo="NIT", valor="595.369-69", pais_emisor="GT"), CATALOGO_MOTOR)
    co = preparar_identificador(IdentificadorConsulta(tipo="NIT", valor="800.080.688-0", pais_emisor="CO"), CATALOGO_MOTOR)
    assert gt.valor == "595.369-69" and gt.digito is None  # literal, sin tocar
    assert co.valor == "800080688" and co.digito == "0"    # normalizado a la colombiana


# La razón social se conserva completa en el criterio de búsqueda (sin quitar sufijos).
@pytest.mark.parametrize("razon", [
    "Comercial Andina S.A.S.", "Comercial Andina S.A.", "Comercial Andina SAS",
    "Comercial Andina SA", "Comercial Andina LTDA", "Comercial Andina S.A.S. Trading",
])
def test_razon_social_se_envia_completa_sin_quitar_sufijos(razon):
    r = preparar(catalogo_real(), tipo_persona="juridica", razon_social=razon)
    assert r.sujetos[0].criterio.nombre == razon
    origen = next(o for o in r.sujetos[0].origenes if o.campo_expediente == "razon_social")
    assert origen.valor_original == razon


def catalogo_real():
    from services.listas.motor_busqueda import CATALOGO_MOTOR
    return CATALOGO_MOTOR
