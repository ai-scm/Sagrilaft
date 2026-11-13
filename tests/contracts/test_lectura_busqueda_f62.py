"""Traducción de hechos sintéticos; no prueba clasificación ni listas reales."""
from pathlib import Path
from uuid import uuid4

import pytest

from domain.listas.catalogos_busqueda import CatalogoPreparacion, IDENTIFICADORES_INICIALES
from domain.listas.datos_busqueda import ReferenciaDato
from infrastructure.listas import adaptador_ofac
from infrastructure.listas.lectura_ofac_busqueda import interpretar, interpretar_fecha
from infrastructure.listas.representacion_busqueda import terminos_de


def nodo(etiqueta, texto="", atributos=None, hijos=()):
    return dict(etiqueta=etiqueta, texto=texto, atributos=atributos or {}, hijos=list(hijos))


def periodo(anio=1980, mes=3, dia=15, anio_fin=None, calendario="1", fijos=(True, True, True)):
    marcas = dict(zip(("YearFixed", "MonthFixed", "DayFixed"), (str(v).lower() for v in fijos)))
    def punto(tipo, valor):
        return nodo(tipo, hijos=[nodo("Year", str(valor)), nodo("Month", str(mes)), nodo("Day", str(dia))])
    return nodo("DatePeriod", atributos={"CalendarTypeID": calendario, **marcas}, hijos=[
        nodo("Start", atributos={"Approximate": "false", **marcas}, hijos=[punto("From", anio)]),
        nodo("End", atributos={"Approximate": "false", **marcas}, hijos=[punto("To", anio_fin or anio)])])


@pytest.fixture
def datos_ofac():
    archivo = Path(__file__).parents[1] / "fixtures/ofac_advanced/dos_entidades.xml"
    with archivo.open("rb") as entrada:
        contenido = next(adaptador_ofac.registros(entrada))
    return contenido


@pytest.fixture
def referencia():
    return ReferenciaDato(fuente_codigo="ofac_sdn", version_id=uuid4(), registro_id=uuid4(), campo_original="sujeto")


def traducir(contenido, referencia):
    return interpretar(contenido, referencia, CatalogoPreparacion(version="prueba-v1", identificadores=IDENTIFICADORES_INICIALES))


@pytest.mark.parametrize("fijos,precision", [((True,True,True), "DIA"), ((True,True,False), "MES"), ((True,False,False), "ANIO"), ((False,False,False), "NO_INTERPRETADA")])
def test_f62_fecha_conserva_precision_y_calendario(fijos, precision):
    fecha = interpretar_fecha(periodo(fijos=fijos))
    assert fecha.precision == precision
    if precision == "ANIO":
        assert fecha.valor.mes is None and fecha.valor.dia is None
    assert interpretar_fecha(periodo(calendario="9")).precision == "NO_INTERPRETADA"


def test_f62_fecha_original_legible_dia_exacto():
    fecha = interpretar_fecha(periodo(anio=1968, mes=1, dia=21))
    assert fecha.original == "1968-01-21"


def test_f62_fecha_original_legible_solo_anio():
    fecha = interpretar_fecha(periodo(anio=1980, fijos=(True, False, False)))
    assert fecha.original == "1980-03-15"  # componentes presentes aunque no fijos


def test_f62_fecha_original_legible_rango():
    fecha = interpretar_fecha(periodo(anio=1980, anio_fin=1982))
    assert fecha.original == "1980-03-15 a 1982-03-15"


def test_f62_fecha_original_legible_aproximada():
    datos = periodo(anio=1968, mes=1, dia=21)
    datos["hijos"][0]["atributos"]["Approximate"] = "true"
    fecha = interpretar_fecha(datos)
    assert fecha.original == "~1968-01-21"


def test_f62_fecha_original_legible_calendario_no_gregoriano():
    fecha = interpretar_fecha(periodo(calendario="9"))
    assert "no interpretado" in fecha.original.lower()


def test_f62_fecha_original_legible_sin_fijos():
    """Reproduce el bug del usuario: flags Fixed=false pero componentes presentes."""
    fecha = interpretar_fecha(periodo(anio=1968, mes=1, dia=21, fijos=(False, False, False)))
    assert fecha.original == "1968-01-21"
    assert "atributos" not in fecha.original
    assert "etiqueta" not in fecha.original


def test_f62_fecha_rango_aproximada_y_limite_aislado():
    datos = periodo(anio_fin=1982)
    datos["hijos"][0]["atributos"]["Approximate"] = "true"
    fecha = interpretar_fecha(datos)
    assert fecha.precision == "RANGO" and fecha.aproximada
    datos["hijos"].pop()
    assert interpretar_fecha(datos).precision == "NO_INTERPRETADA"


def test_f62_ofac_alias_documento_calidad_y_ceros(datos_ofac, referencia):
    registro, pendientes = traducir(datos_ofac, referencia)
    assert len(registro.nombres) == 2
    assert {n.tipo for n in registro.nombres} == {"PRINCIPAL", "ALIAS"}
    documento = registro.identificadores[0]
    assert documento.tipo == "PASAPORTE" and documento.esquema == "PASAPORTE"
    assert documento.valor == "00001231" and documento.pais_emisor == "MX"
    assert documento.calidad == "FALSO"  # El fixture declara Fraudulent; nunca corrobora.
    assert documento.referencia.identidad_origen == "100001"
    assert "sanciones" in pendientes


def test_f62_alias_debil_e_identidad_falsa(datos_ofac, referencia):
    identidad = next(adaptador_ofac.recorrer(datos_ofac["sujeto"], "Identity"))
    identidad["atributos"]["False"] = "true"
    next(adaptador_ofac.recorrer(identidad, "Alias"))["atributos"]["LowQuality"] = "true"
    registro, _ = traducir(datos_ofac, referencia)
    assert registro.nombres[0].alias_debil
    assert all(n.calidad == "FALSO" for n in registro.nombres)
    assert registro.identificadores[0].calidad == "FALSO"


def test_f62_documento_valido_no_implica_fiabilidad_confirmada(datos_ofac, referencia):
    datos_ofac["documentos"][0]["atributos"]["ValidityID"] = "1"
    registro, _ = traducir(datos_ofac, referencia)
    assert registro.identificadores[0].calidad == "DESCONOCIDO"


@pytest.mark.parametrize("codigo,calidad", [("1560","CONFIRMADO"), ("1561","FALSO"), ("91479","REPORTADO"), ("1","DESCONOCIDO"), ("nuevo","DESCONOCIDO")])
def test_f62_caracteristicas_mantienen_identidad_y_fiabilidad(datos_ofac, referencia, codigo, calidad):
    perfil = next(adaptador_ofac.recorrer(datos_ofac["sujeto"], "Profile"))
    perfil["hijos"].append(nodo("Feature", atributos={"FeatureTypeID": "8", "ID": "f1"}, hijos=[
        nodo("FeatureVersion", atributos={"ID": "v1", "ReliabilityID": codigo}, hijos=[periodo()]),
        nodo("IdentityReference", atributos={"IdentityID": "100001", "IdentityFeatureLinkTypeID": "1"})]))
    registro, _ = traducir(datos_ofac, referencia)
    hecho = next(h for h in registro.hechos if h.campo == "fecha_nacimiento")
    assert hecho.calidad == calidad
    assert hecho.referencia.identidad_origen == "100001" and hecho.valor.precision == "DIA"


def test_f62_documento_sin_numero_no_se_inventa(datos_ofac, referencia):
    datos_ofac["documentos"][0]["hijos"] = []
    registro, pendientes = traducir(datos_ofac, referencia)
    assert not registro.identificadores
    assert "IDRegDocument/9001" in pendientes


def test_f62_esquema_fiscal_comparte_catalogo(datos_ofac, referencia):
    datos_ofac["documentos"][0]["atributos"]["IDRegDocTypeID"] = "1575"
    registro, _ = traducir(datos_ofac, referencia)
    assert registro.identificadores[0].esquema == "REGISTRO_FISCAL"


def test_f62_documento_desconocido_se_conserva_y_advierte(datos_ofac, referencia):
    datos_ofac["documentos"][0]["atributos"]["IDRegDocTypeID"] = "nuevo"
    registro, pendientes = traducir(datos_ofac, referencia)
    assert registro.identificadores[0].esquema is None
    assert registro.identificadores[0].valor == "00001231"
    assert "IDRegDocument/9001" in pendientes


def test_f62_indice_no_quita_ceros_y_reconoce_unicode(datos_ofac, referencia):
    registro, _ = traducir(datos_ofac, referencia)
    copia = registro.model_dump()
    copia["nombres"][0]["valor"] = "ÁMBAR"
    from domain.listas.datos_busqueda import RegistroBusqueda
    uno = list(terminos_de(RegistroBusqueda.model_validate(copia)))
    copia["nombres"][0]["valor"] = "a\u0301mbar"
    assert uno == list(terminos_de(RegistroBusqueda.model_validate(copia)))
    copia["identificadores"][0]["valor"] = "1231"
    assert uno[-1] != list(terminos_de(RegistroBusqueda.model_validate(copia)))[-1]


@pytest.mark.parametrize("codigo,campo", [("10", "nacionalidad"), ("11", "ciudadania")])
def test_f62_nacionalidad_y_ciudadania_no_se_mezclan(datos_ofac, referencia, codigo, campo):
    perfil = next(adaptador_ofac.recorrer(datos_ofac["sujeto"], "Profile"))
    perfil["hijos"].append(nodo("Feature", atributos={"FeatureTypeID": codigo, "ID": "f1"}, hijos=[
        nodo("FeatureVersion", atributos={"ID": "v1", "ReliabilityID": "91479"}, hijos=[
            nodo("VersionDetail", texto="Mexico", atributos={"DetailTypeID": "1433"})]),
        nodo("IdentityReference", atributos={"IdentityID": "100001"})]))
    registro, _ = traducir(datos_ofac, referencia)
    hecho = next(h for h in registro.hechos if h.campo == campo)
    assert hecho.valor == "MX" and hecho.calidad == "REPORTADO"
    assert not any(h.campo == ("ciudadania" if codigo == "10" else "nacionalidad") for h in registro.hechos)


def test_f62_datos_sin_equivalencia_siguen_siendo_visibles(datos_ofac, referencia):
    perfil = next(adaptador_ofac.recorrer(datos_ofac["sujeto"], "Profile"))
    perfil["hijos"].append(nodo("Feature", atributos={"FeatureTypeID": "nuevo", "ID": "f1"}, hijos=[
        nodo("FeatureVersion", atributos={"ID": "v1", "ReliabilityID": "1"}, hijos=[
            nodo("VersionDetail", texto="Dato sin equivalencia", atributos={"DetailTypeID": "1432"})]),
        nodo("IdentityReference", atributos={"IdentityID": "100001"})]))
    registro, pendientes = traducir(datos_ofac, referencia)
    assert any(h.valor == "Dato sin equivalencia" for h in registro.hechos)
    assert "FeatureVersion/v1" in pendientes


def test_f62_fecha_documental_no_se_convierte_en_nacimiento(datos_ofac, referencia):
    datos_ofac["documentos"][0]["hijos"].append(nodo("DocumentDate", atributos={"IDRegDocDateTypeID": "1480"}, hijos=[periodo()]))
    registro, _ = traducir(datos_ofac, referencia)
    assert any(h.campo == "fecha_expedicion" for h in registro.hechos)
    assert not any(h.campo == "fecha_nacimiento" for h in registro.hechos)


# --- "Cedula No." (1570) solo se interpreta como CC cuando el país emisor es Colombia.
# Es una etiqueta genérica que OFAC reutiliza para el documento nacional de varios países;
# no debe equipararse con la cédula colombiana cuando el país es otro o no se identifica.
def test_f62_cedula_colombiana_se_compara_como_cc(datos_ofac, referencia):
    datos_ofac["catalogos"].append(nodo("Country", texto="Colombia", atributos={"ID": "90001", "ISO2": "CO"}))
    datos_ofac["documentos"][0]["atributos"].update(IDRegDocTypeID="1570", **{"IssuedBy-CountryID": "90001"})
    registro, pendientes = traducir(datos_ofac, referencia)
    identificador = registro.identificadores[0]
    assert identificador.tipo == "CC" and identificador.pais_emisor == "CO"
    assert "IDRegDocument/9001" not in pendientes  # esquema reconocido: no queda como dato sin equivalencia


def test_f62_cedula_venezolana_no_se_compara_como_cc(datos_ofac, referencia):
    datos_ofac["catalogos"].append(nodo("Country", texto="Venezuela", atributos={"ID": "90002", "ISO2": "VE"}))
    datos_ofac["documentos"][0]["atributos"].update(IDRegDocTypeID="1570", **{"IssuedBy-CountryID": "90002"})
    registro, _ = traducir(datos_ofac, referencia)
    identificador = registro.identificadores[0]
    assert identificador.tipo == "OFAC_DOCUMENTO:1570"  # se conserva, pero no se compara como CC
    assert identificador.pais_emisor == "VE"


def test_f62_cedula_sin_pais_declarado_no_se_compara_como_cc(datos_ofac, referencia):
    datos_ofac["documentos"][0]["atributos"].update(IDRegDocTypeID="1570")
    del datos_ofac["documentos"][0]["atributos"]["IssuedBy-CountryID"]
    registro, _ = traducir(datos_ofac, referencia)
    identificador = registro.identificadores[0]
    assert identificador.tipo == "OFAC_DOCUMENTO:1570"
    assert identificador.pais_emisor is None


def test_f62_cc_colombiano_coincide_contra_motor_real(datos_ofac, referencia):
    """Prueba positiva de punta a punta: la CC colombiana sí produce una coincidencia."""
    from domain.listas.contratos_busqueda import CriterioBusqueda, IdentificadorConsulta
    from services.listas.motor_busqueda import MotorBusqueda, CATALOGO_MOTOR
    from uuid import uuid4
    from datetime import date
    datos_ofac["catalogos"].append(nodo("Country", texto="Colombia", atributos={"ID": "90001", "ISO2": "CO"}))
    datos_ofac["documentos"][0]["atributos"].update(IDRegDocTypeID="1570", ValidityID="1", **{"IssuedBy-CountryID": "90001"})
    datos_ofac["documentos"][0]["hijos"][0]["texto"] = "71984381"
    registro, _ = traducir(datos_ofac, referencia)
    criterio = CriterioBusqueda(tipo_sujeto=registro.tipo_sujeto, nombre="cualquiera",
        identificadores=(IdentificadorConsulta(tipo="CC", valor="71984381", pais_emisor="CO"),),
        campos_exigidos=("identificadores",))
    evaluacion = MotorBusqueda(CATALOGO_MOTOR).evaluar(criterio, (registro,), uuid4(), {"ofac_sdn": uuid4()}, date.today())
    assert evaluacion.candidatos and any(
        m.resultado == "COINCIDE" and m.campo == "identificadores" for m in evaluacion.candidatos[0].motivos)


def test_f62_cc_de_otro_pais_no_coincide_contra_motor_real(datos_ofac, referencia):
    """Prueba negativa: el mismo número, con país distinto a Colombia, nunca cuenta como CC."""
    from domain.listas.contratos_busqueda import CriterioBusqueda, IdentificadorConsulta
    from services.listas.motor_busqueda import MotorBusqueda, CATALOGO_MOTOR
    from uuid import uuid4
    from datetime import date
    datos_ofac["catalogos"].append(nodo("Country", texto="Venezuela", atributos={"ID": "90002", "ISO2": "VE"}))
    datos_ofac["documentos"][0]["atributos"].update(IDRegDocTypeID="1570", ValidityID="1", **{"IssuedBy-CountryID": "90002"})
    datos_ofac["documentos"][0]["hijos"][0]["texto"] = "71984381"
    registro, _ = traducir(datos_ofac, referencia)
    criterio = CriterioBusqueda(tipo_sujeto=registro.tipo_sujeto, nombre="cualquiera",
        identificadores=(IdentificadorConsulta(tipo="CC", valor="71984381", pais_emisor="CO"),),
        campos_exigidos=("identificadores",))
    evaluacion = MotorBusqueda(CATALOGO_MOTOR).evaluar(criterio, (registro,), uuid4(), {"ofac_sdn": uuid4()}, date.today())
    assert "identificadores" in evaluacion.campos_no_aplicados
    assert not any(m.campo == "identificadores" and m.resultado in ("COINCIDE", "COMPATIBLE")
                   for c in evaluacion.candidatos for m in c.motivos)
