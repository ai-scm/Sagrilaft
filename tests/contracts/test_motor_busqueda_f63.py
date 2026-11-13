"""Reglas funcionales del motor con corpus ficticio; sin HTTP, SQL ni SDN real."""
from datetime import date
import json
import os
from pathlib import Path
from uuid import NAMESPACE_URL, uuid4, uuid5

import pytest

from domain.listas.contratos_busqueda import CriterioBusqueda
from domain.listas.datos_busqueda import RegistroBusqueda
from services.listas.motor_busqueda import CATALOGO_MOTOR, CriterioNoUtilizable, MotorBusqueda, ParametrosMotor

VERSION = uuid5(NAMESPACE_URL, "version-ficticia-f63")
FECHA = date(2026, 11, 8)
CONSULTA = uuid5(NAMESPACE_URL, "consulta-ficticia-f63")
COBERTURA = uuid5(NAMESPACE_URL, "cobertura-ficticia-f63")
NOMBRE = "Juan Carlos Pérez Gómez"


def referencia(identificador="S1", campo="registro", identidad="A", fuente="lista_ficticia", version=VERSION):
    return dict(fuente_codigo=fuente, version_id=version, registro_id=uuid5(NAMESPACE_URL, identificador),
        campo_original=campo, identidad_origen=identidad)


def persona(identificador="S1", nacimiento="1980-03-15", nombre=NOMBRE):
    ref = lambda campo: referencia(identificador, campo)
    return RegistroBusqueda.model_validate(dict(tipo_sujeto="PERSONA", referencia=ref("registro"),
        nombres=[dict(valor=nombre, tipo="PRINCIPAL", referencia=ref("nombre")),
                 dict(valor="Juan Pérez", tipo="ALIAS", referencia=ref("alias")),
                 dict(valor="El Capitán", tipo="ALIAS", alias_debil=True, referencia=ref("alias_debil"))],
        identificadores=[dict(tipo="PASAPORTE", esquema="PASAPORTE", valor="AB0001234", pais_emisor="CO",
                             calidad="CONFIRMADO", referencia=ref("pasaporte"))],
        hechos=[dict(tipo="FECHA", campo="fecha_nacimiento", calidad="CONFIRMADO", referencia=ref("nacimiento"),
            valor=dict(original=nacimiento, calendario="GREGORIANO", precision="DIA",
                       valor=dict(anio=int(nacimiento[:4]), mes=int(nacimiento[5:7]), dia=int(nacimiento[8:])))),
            dict(tipo="TEXTO", campo="nacionalidad", valor="CO", referencia=ref("nacionalidad")),
            dict(tipo="UBICACION", campo="ubicacion", valor=dict(rol="DOMICILIO", texto="Bogotá", pais="CO"), referencia=ref("domicilio"))]))


def empresa(identificador="S2", nombre="Comercial Andina S.A.S."):
    ref = lambda campo: referencia(identificador, campo)
    return RegistroBusqueda.model_validate(dict(tipo_sujeto="ENTIDAD", referencia=ref("registro"),
        nombres=[dict(valor=nombre, tipo="PRINCIPAL", referencia=ref("nombre"))],
        identificadores=[dict(tipo="NIT", esquema="REGISTRO_FISCAL", valor="900123456", digito_verificacion="8",
            pais_emisor="CO", calidad="CONFIRMADO", referencia=ref("nit"),
            vigencia=dict(desde="2020-01-01", hasta="2030-12-31", calidad="CONFIRMADO"))]))


def cambiar(registro, funcion):
    datos = registro.model_dump()
    funcion(datos)
    return RegistroBusqueda.model_validate(datos)


def consulta(nombre=None, valor=None, tipo="PASAPORTE", pais="CO", digito=None, naturaleza="PERSONA", **otros):
    identificadores = [] if valor is None else [dict(tipo=tipo, valor=valor, pais_emisor=pais, digito_verificacion=digito)]
    return CriterioBusqueda(tipo_sujeto=naturaleza, nombre=nombre, identificadores=identificadores, **otros)


def evaluar(criterio, registros=None, motor=None, consulta_id=CONSULTA):
    registros = tuple([persona()] if registros is None else registros)
    coberturas = {r.referencia.fuente_codigo: COBERTURA for r in registros}
    return (motor or MotorBusqueda()).evaluar(criterio, registros, consulta_id, coberturas, FECHA)


def caso_prioritario(caso):
    registros, esperado = [persona()], ["MEDIA"]
    entradas = {"N-01": "JUAN CARLOS PEREZ GOMEZ", "N-03": "Juan Pérez", "N-04": "El Capitán",
                "N-05": "Juan Carlos Peres Gómez", "N-06": "uJan Carlos Pérez Gómez"}
    if caso in entradas:
        criterio = consulta(entradas[caso])
        esperado = ["BAJA"] if caso == "N-04" else esperado
    elif caso.startswith("I-"):
        valor = {"I-01": "AB0001234", "I-02": "AB0001235", "I-03": "AB0001234", "I-06": "AB1234"}[caso]
        criterio = consulta(valor=valor, pais=None if caso == "I-03" else "CO")
        esperado = {"I-01": ["ALTA"], "I-02": [], "I-03": ["MEDIA"], "I-06": []}[caso]
    elif caso in {"C-01", "C-02", "C-03"}:
        criterio = consulta(None if caso == "C-03" else NOMBRE,
            valor="AB0001234" if caso == "C-03" else None,
            fecha_nacimiento="1980-03-15" if caso == "C-01" else "1985-03-15")
        esperado = [{"C-01": "ALTA", "C-02": "BAJA", "C-03": "MEDIA"}[caso]]
    elif caso == "C-04":
        def parcial(datos):
            datos["hechos"][0]["valor"].update(precision="ANIO", valor=dict(anio=1980))
        registros = [cambiar(persona(), parcial)]
        criterio = consulta(NOMBRE, fecha_nacimiento="1980-03-15")
    elif caso == "C-12":
        registros.append(persona("S3", nacimiento="1985-04-16"))
        criterio, esperado = consulta(NOMBRE), ["MEDIA", "MEDIA"]
    elif caso == "C-15":
        registros = [cambiar(persona(), lambda d: d["hechos"][0].update(calidad="REPORTADO"))]
        criterio = consulta(NOMBRE, fecha_nacimiento="1980-03-15")
    elif caso == "C-19":
        registros = [cambiar(persona(), lambda d: d["hechos"][0]["referencia"].update(identidad_origen="B"))]
        criterio = consulta(NOMBRE, fecha_nacimiento="1980-03-15")
    elif caso in {"B-01", "B-06", "B-07"}:
        registros = [empresa()]
        criterio = consulta("Comercial Andina S.A.S." if caso == "B-06" else None,
            valor="900999999" if caso == "B-06" else "900123456", tipo="NIT",
            digito="9" if caso == "B-07" else "8", naturaleza="ENTIDAD")
        esperado = [{"B-01": "ALTA", "B-06": "BAJA", "B-07": "MEDIA"}[caso]]
    elif caso == "B-03":
        registros = [empresa(nombre="Comercial Andina Trading")]
        criterio, esperado = consulta("Comercial Andina", naturaleza="ENTIDAD"), ["BAJA"]
    else:
        raise AssertionError(caso)
    return criterio, registros, esperado


CASOS_PRIORITARIOS_MOTOR = ["N-01", "N-03", "N-04", "N-05", "N-06", "I-01", "I-02", "I-03", "I-06",
    "C-01", "C-02", "C-03", "C-04", "C-12", "C-15", "C-19", "B-01", "B-03", "B-06", "B-07"]


@pytest.mark.parametrize("caso", CASOS_PRIORITARIOS_MOTOR)
def test_f63_casos_prioritarios_motor(caso):
    criterio, registros, esperados = caso_prioritario(caso)
    resultado = evaluar(criterio, registros)
    assert sorted(c.nivel for c in resultado.candidatos) == sorted(esperados)
    assert resultado.concluyente
    for candidato in resultado.candidatos:
        assert candidato.explicacion and candidato.regla_codigo and candidato.regla_version
        assert candidato.motivos and candidato.algoritmo_version
        assert candidato.revision_prioritaria == (caso in {"C-02", "C-03", "B-06", "B-07"})


def test_f63_B08_cliente_proveedor_y_representante_no_cambian_reglas():
    from services.listas.preparacion_criterios import DatosExpedienteBusqueda, preparar_expediente
    criterios = []
    for rol in ("cliente", "proveedor"):
        datos = DatosExpedienteBusqueda(expediente_id="ficticio", tipo_persona="juridica", tipo_contraparte=rol,
            razon_social="Comercial Andina S.A.S.", nombre_representante=NOMBRE)
        preparados = preparar_expediente(datos, CATALOGO_MOTOR)
        assert [s.rol for s in preparados.sujetos] == ["CONTRAPARTE", "REPRESENTANTE"]
        criterios.append(tuple(s.criterio for s in preparados.sujetos))
    assert criterios[0] == criterios[1]
    assert evaluar(criterios[0][0], [empresa()]).candidatos[0].nivel == "MEDIA"
    assert evaluar(criterios[0][1]).candidatos[0].nivel == "MEDIA"


@pytest.mark.parametrize("calidad", ["DESCONOCIDO", "REPORTADO", "FALSO"])
def test_f63_documento_solo_fraudulento_impide_alta(calidad):
    """OFAC no certifica la identidad de un documento, solo si es válido o fraudulento
    (ValidityID). Por eso ALTA exige que no esté marcado fraudulento, no que esté
    'confirmado' (un estándar que la fuente no ofrece para documentos)."""
    registro = cambiar(persona(), lambda d: d["identificadores"][0].update(calidad=calidad))
    resultado = evaluar(consulta(valor="AB0001234"), [registro])
    assert resultado.candidatos[0].nivel == ("BAJA" if calidad == "FALSO" else "ALTA")


@pytest.mark.parametrize("calidad", ["DESCONOCIDO", "REPORTADO", "FALSO"])
def test_f63_nacimiento_sin_confirmacion_nunca_alta(calidad):
    registro = cambiar(persona(), lambda d: d["hechos"][0].update(calidad=calidad))
    assert evaluar(consulta(NOMBRE, fecha_nacimiento="1980-03-15"), [registro]).candidatos[0].nivel == "MEDIA"


def test_f63_documento_ambiguo_no_fusiona_ni_da_alta():
    resultado = evaluar(consulta(valor="AB0001234"), [persona(), persona("otro")])
    assert len(resultado.candidatos) == 2
    assert all(c.nivel == "MEDIA" for c in resultado.candidatos)
    assert all(any(m.metodo == "DOCUMENTO_AMBIGUO" for m in c.motivos) for c in resultado.candidatos)


@pytest.mark.parametrize("datos", [dict(pais="US"), dict(tipo="CC"), dict(valor="AB0001235"), dict(valor="AB1234")])
def test_f63_no_fabrica_igualdad_documental(datos):
    entrada = dict(valor="AB0001234", pais="CO")
    entrada.update(datos)
    candidatos = evaluar(consulta(**entrada)).candidatos
    assert [c.nivel for c in candidatos] == (["MEDIA"] if datos == dict(pais="US") else [])


def test_f63_tipo_desconocido_no_pasa_por_empresa_ni_alta():
    candidato = evaluar(consulta(valor="AB0001234", naturaleza="NO_DETERMINADO")).candidatos[0]
    assert candidato.nivel == "MEDIA"


def test_f63_tipo_incompatible_se_destaca_y_no_alta():
    candidato = evaluar(consulta(valor="900123456", digito="8", tipo="NIT", naturaleza="PERSONA"), [empresa()]).candidatos[0]
    assert candidato.nivel == "MEDIA" and candidato.revision_prioritaria


def test_f63_nombre_incompatible_con_documento_fuerte_media_prioritaria():
    candidato = evaluar(consulta("Ana Lucía Martínez Rojas", valor="AB0001234")).candidatos[0]
    assert candidato.nivel == "MEDIA" and candidato.revision_prioritaria
    assert any(m.metodo == "NOMBRE_COMPLETO_INCOMPATIBLE" for m in candidato.motivos)


def test_f63_documento_fuerte_no_exige_datos_opcionales():
    assert evaluar(consulta(valor="AB0001234")).candidatos[0].nivel == "ALTA"


def test_f63_pasaporte_diferente_no_es_exclusion_por_nombre():
    candidato = evaluar(consulta(NOMBRE, valor="OTRO0001")).candidatos[0]
    assert candidato.nivel == "MEDIA" and not candidato.revision_prioritaria


def test_f63_nit_sin_periodo_confirmado_no_inventa_contradiccion_fuerte():
    registro = cambiar(empresa(), lambda d: d["identificadores"][0].update(vigencia=None))
    candidato = evaluar(consulta("Comercial Andina S.A.S.", valor="900999999", tipo="NIT", digito="8", naturaleza="ENTIDAD"), [registro]).candidatos[0]
    assert candidato.nivel == "MEDIA" and not candidato.revision_prioritaria


@pytest.mark.parametrize("valor,digito,pais,nivel", [("900.123.456-8",None,"CO","ALTA"), ("900123456",None,"CO","MEDIA"), ("9001234568",None,"CO",None), ("900123456","8",None,"MEDIA")])
def test_f63_nit_formato_explicito_sin_recortar_digitos(valor, digito, pais, nivel):
    candidatos = evaluar(consulta(valor=valor, digito=digito, tipo="NIT", naturaleza="ENTIDAD", pais=pais), [empresa()]).candidatos
    assert [c.nivel for c in candidatos] == ([nivel] if nivel else [])


def test_f63_digito_interno_contradice_digito_separado_rechaza_criterio():
    with pytest.raises(CriterioNoUtilizable):
        evaluar(consulta(valor="900123456-8", digito="9", tipo="NIT", naturaleza="ENTIDAD"), [empresa()])


@pytest.mark.parametrize("nombre", ["Juan", "Empresa", "Servicios", "A B", "---"])
def test_f63_nombre_generico_pide_mas_datos(nombre):
    with pytest.raises(CriterioNoUtilizable):
        evaluar(consulta(nombre))


def test_f63_nombre_incompleto_o_inicial_no_da_alta_aun_con_nacimiento():
    for nombre in ("Juan Carlos Pérez", "J Carlos Pérez Gómez"):
        candidato = evaluar(consulta(nombre, fecha_nacimiento="1980-03-15")).candidatos[0]
        assert candidato.nivel == "BAJA"


def test_f63_no_combina_partes_de_alias():
    r = cambiar(persona(), lambda d: d.update(nombres=[
        dict(valor="Juan Carlos Rivera Soto", tipo="PRINCIPAL", referencia=referencia(campo="nombre")),
        dict(valor="Andrés Miguel Pérez Gómez", tipo="ALIAS", referencia=referencia(campo="alias"))]))
    resultado = evaluar(consulta(NOMBRE, fecha_nacimiento="1980-03-15"), [r])
    assert not any(c.nivel == "ALTA" for c in resultado.candidatos)


def test_f63_nombres_en_otro_alfabeto_se_conservan():
    candidato = evaluar(consulta("Александр Иванов"), [persona(nombre="Александр Иванов")]).candidatos[0]
    assert candidato.nivel == "MEDIA" and candidato.nombre_principal == "Александр Иванов"


def test_f63_nacionalidad_y_domicilio_no_elevan_ni_excluyen():
    for pais in ("CO", "US"):
        candidato = evaluar(consulta(NOMBRE, nacionalidades=[pais], ubicaciones=[dict(rol="DOMICILIO", pais=pais)])).candidatos[0]
        assert candidato.nivel == "MEDIA"
        assert any(m.campo == "nacionalidad" for m in candidato.motivos)
        assert any(m.campo == "ubicaciones" for m in candidato.motivos)


def test_f63_relacion_no_crea_candidato_por_asociacion():
    r = cambiar(empresa(), lambda d: d.update(relaciones=[dict(tipo="RELACION", direccion="SALIENTE", fuente_destino="lista_ficticia",
        version_destino_id=VERSION, registro_destino_id=persona().referencia.registro_id, referencia=referencia("S2", "relacion"))]))
    assert len(evaluar(consulta(NOMBRE), [persona(), r]).candidatos) == 1


def test_f63_identidades_incompatibles_sin_referencia_no_se_mezclan():
    r = cambiar(persona(), lambda d: d["hechos"][0]["referencia"].update(identidad_origen=None))
    assert evaluar(consulta(NOMBRE, fecha_nacimiento="1980-03-15"), [r]).candidatos[0].nivel == "MEDIA"


def test_f63_alternativas_fecha_no_crean_contradiccion_global():
    def alternativa(d):
        d["hechos"] = (*d["hechos"], {**d["hechos"][0], "valor": dict(original="1985-03-15", calendario="GREGORIANO", precision="DIA", valor=dict(anio=1985,mes=3,dia=15))})
    r = cambiar(persona(), alternativa)
    c = evaluar(consulta(NOMBRE, fecha_nacimiento="1980-03-15"), [r]).candidatos[0]
    assert c.nivel == "ALTA" and not c.revision_prioritaria


def test_f63_transposicion_y_orden_dan_motivos_sin_puntaje():
    for nombre in ("Pérez Gómez Juan Carlos", "uJan Carlos Pérez Gómez"):
        c = evaluar(consulta(nombre)).candidatos[0]
        assert c.nivel == "MEDIA"
        assert not {"score", "puntaje", "similitud", "riesgo", "aprobado", "rechazado"} & c.model_dump().keys()


@pytest.mark.parametrize("parametros", [ParametrosMotor(maximo_registros=1), ParametrosMotor(maximo_candidatos=1)])
def test_f63_limites_no_se_presentan_como_busqueda_completa(parametros):
    r = evaluar(consulta(NOMBRE), [persona(), persona("S3")], MotorBusqueda(parametros=parametros))
    assert not r.concluyente and r.advertencias
    assert len(r.candidatos) == 1


def test_f63_criterio_exigido_desconocido_no_se_presenta_aplicado():
    r = evaluar(consulta(NOMBRE, valor="123", tipo="DESCONOCIDO", campos_exigidos=["identificadores"]))
    assert not r.concluyente and r.campos_no_aplicados == ("identificadores",)


def test_f63_sin_resultados_no_asigna_baja():
    r = evaluar(consulta("Ana Lucía Martínez Rojas"))
    assert r.concluyente and not r.candidatos


def test_f63_reintento_ids_y_parametros_reproducibles_sin_mutar_entrada():
    registros, criterio = [persona()], consulta(NOMBRE, fecha_nacimiento="1980-03-15")
    previo = registros[0].model_dump_json()
    assert evaluar(criterio, registros) == evaluar(criterio, registros)
    assert registros[0].model_dump_json() == previo
    assert evaluar(criterio, registros).candidatos[0].id != evaluar(criterio, registros, consulta_id=uuid4()).candidatos[0].id


def test_f63_no_mezcla_versiones_y_no_duplica_registros():
    with pytest.raises(ValueError, match="duplicado"):
        evaluar(consulta(NOMBRE), [persona(), persona()])
    r = cambiar(persona("S3"), lambda d: None)
    d = r.model_dump()
    for elemento in [d["referencia"], *[n["referencia"] for n in d["nombres"]], *[n["referencia"] for n in d["identificadores"]], *[n["referencia"] for n in d["hechos"]]]:
        elemento["version_id"] = uuid5(NAMESPACE_URL, "otra-version")
    with pytest.raises(ValueError, match="versiones"):
        evaluar(consulta(NOMBRE), [persona(), RegistroBusqueda.model_validate(d)])


def test_f63_enie_es_variacion_y_no_igualdad_normalizada():
    from domain.listas.comparacion_nombres import comparar_nombre
    assert comparar_nombre("Andrés Muñoz", "Andres Munoz").metodo == "VARIACION_MENOR"
    assert comparar_nombre("Andrés Muñoz", "ANDRES MUÑOZ").metodo == "NOMBRE_NORMALIZADO"


def test_f63_multiples_errores_no_se_vuelven_nombre_completo_para_alta():
    r = evaluar(consulta("Juam Carlod Peres Gomej", fecha_nacimiento="1980-03-15"))
    assert not any(c.nivel == "ALTA" for c in r.candidatos)


def test_f63_tipo_incompatible_por_nombre_no_genera_candidato_identidad():
    assert not evaluar(consulta("Comercial Andina S.A.S."), [empresa()]).candidatos


def test_f63_no_usa_nacimiento_de_empresa_como_personal():
    def agregar(d):
        d["hechos"] = [dict(tipo="FECHA", campo="fecha_nacimiento", calidad="CONFIRMADO", referencia=referencia("S2", "fecha"),
            valor=dict(original="1980-03-15", calendario="GREGORIANO", precision="DIA", valor=dict(anio=1980,mes=3,dia=15)))]
    registro = cambiar(empresa(), agregar)
    candidato = evaluar(consulta("Comercial Andina S.A.S.", naturaleza="ENTIDAD", fecha_nacimiento="1980-03-15"), [registro]).candidatos[0]
    assert candidato.nivel == "MEDIA"


@pytest.mark.parametrize("aproximada,precision", [(True,"DIA"), (False,"MES"), (False,"RANGO")])
def test_f63_fecha_compatible_no_es_fuerte(aproximada, precision):
    def modificar(d):
        f = d["hechos"][0]["valor"]
        f["aproximada"] = aproximada
        if precision == "MES":
            f.update(precision=precision, valor=dict(anio=1980,mes=3))
        elif precision == "RANGO":
            f.update(precision=precision, valor=None, desde=dict(anio=1979), hasta=dict(anio=1981))
    registro = cambiar(persona(), modificar)
    candidato = evaluar(consulta(NOMBRE, fecha_nacimiento="1980-03-15"), [registro]).candidatos[0]
    assert candidato.nivel == "MEDIA"


def test_f63_fecha_no_interpretada_exigida_no_concluyente():
    def modificar(d):
        d["hechos"][0]["valor"].update(precision="NO_INTERPRETADA", calendario="OTRO", valor=None)
    registro = cambiar(persona(), modificar)
    resultado = evaluar(consulta(NOMBRE, fecha_nacimiento="1980-03-15", campos_exigidos=["fecha_nacimiento"]), [registro])
    assert not resultado.concluyente and resultado.candidatos[0].nivel == "MEDIA"


def test_f63_fuente_sin_esquema_no_declara_ausencia_por_documento():
    registro = cambiar(persona(), lambda d: d["identificadores"][0].update(tipo="NO_MAPEADO", esquema=None))
    resultado = evaluar(consulta(valor="AB0001234"), [registro])
    assert not resultado.concluyente and not resultado.candidatos


def test_f63_vinculacion_documental_ausente_no_da_alta():
    registro = cambiar(persona(), lambda d: [n["referencia"].update(identidad_origen="B") for n in d["nombres"]])
    candidato = evaluar(consulta(NOMBRE, valor="AB0001234"), [registro]).candidatos[0]
    assert candidato.nivel == "MEDIA"


def test_f63_documento_sin_esquema_explicito_no_da_alta():
    registro = cambiar(persona(), lambda d: d["identificadores"][0].update(esquema=None))
    assert evaluar(consulta(valor="AB0001234"), [registro]).candidatos[0].nivel == "MEDIA"


def test_f63_solo_un_nombre_debil_no_usa_nacimiento_para_alta():
    candidato = evaluar(consulta("El Capitán", fecha_nacimiento="1980-03-15")).candidatos[0]
    assert candidato.nivel == "BAJA"


def test_f63_truncar_registros_no_permite_documento_alta():
    motor = MotorBusqueda(parametros=ParametrosMotor(maximo_registros=1))
    resultado = evaluar(consulta(valor="AB0001234"), [persona(), persona("S3")], motor)
    assert not resultado.concluyente and resultado.candidatos[0].nivel == "MEDIA"


def test_f63_nueva_fuente_y_esquema_fiscal_sin_cambiar_motor():
    from domain.listas.catalogos_busqueda import CatalogoPreparacion, DefinicionIdentificador
    definicion = DefinicionIdentificador(tipo="REGISTRO_PROPIO", esquema="REGISTRO_FISCAL", jurisdiccion_requerida=False, multiples_por_sujeto=False)
    catalogo = CatalogoPreparacion(version="lista-propia-v1", identificadores=(*CATALOGO_MOTOR.identificadores, definicion))
    def modificar(d):
        for ref in [d["referencia"], d["nombres"][0]["referencia"], d["identificadores"][0]["referencia"]]:
            ref["fuente_codigo"] = "lista_propia"
        d["identificadores"][0].update(tipo="REGISTRO_PROPIO", valor="AbC001", esquema="REGISTRO_FISCAL", digito_verificacion=None, pais_emisor=None, calidad="FALSO")
    registro = cambiar(empresa(), modificar)
    motor = MotorBusqueda(catalogo)
    assert evaluar(consulta(valor="AbC001", tipo="REGISTRO_PROPIO", pais=None, naturaleza="ENTIDAD"), [registro], motor).candidatos[0].nivel == "BAJA"
    assert not evaluar(consulta(valor="abc001", tipo="REGISTRO_PROPIO", pais=None, naturaleza="ENTIDAD"), [registro], motor).candidatos
    registro = cambiar(registro, lambda d: d["identificadores"][0].update(calidad="DESCONOCIDO"))
    assert evaluar(consulta(valor="AbC001", tipo="REGISTRO_PROPIO", pais=None, naturaleza="ENTIDAD"), [registro], motor).candidatos[0].nivel == "ALTA"


def test_f63_dos_fuentes_no_se_fusionan_ni_hacen_documento_ambiguo():
    r = persona("S2")
    d = r.model_dump()
    for ref in [d["referencia"], *[n["referencia"] for n in d["nombres"]], *[n["referencia"] for n in d["identificadores"]], *[n["referencia"] for n in d["hechos"]]]:
        ref["fuente_codigo"] = "otra_lista"
    registros = (persona(), RegistroBusqueda.model_validate(d))
    resultado = MotorBusqueda().evaluar(consulta(valor="AB0001234"), registros, CONSULTA,
        {"lista_ficticia": COBERTURA, "otra_lista": uuid4()}, FECHA)
    assert [c.nivel for c in resultado.candidatos] == ["ALTA", "ALTA"]
    assert len({c.id for c in resultado.candidatos}) == 2


def test_f63_vigencia_invertida_rechazada_y_ausente_no_inventada():
    from pydantic import ValidationError
    from domain.listas.datos_busqueda import VigenciaIdentificador
    with pytest.raises(ValidationError):
        VigenciaIdentificador(desde="2030-01-01", hasta="2020-01-01")
    assert persona().identificadores[0].vigencia is None


CORPUS_CALIBRACION = json.loads((Path(__file__).parents[1] / "fixtures/listas_f63/calibracion_nombres.json").read_text())


def calibrar(caso):
    registro = empresa(nombre=caso["fuente"]) if caso["tipo"] == "ENTIDAD" else persona(nombre=caso["fuente"])
    # Estos pares aíslan la comparación de un solo nombre, sin alias ni apoyos.
    registro = cambiar(registro, lambda d: d.update(nombres=d["nombres"][:1], identificadores=(), hechos=()))
    return evaluar(consulta(caso["consulta"], naturaleza=caso["tipo"]), [registro])


@pytest.mark.parametrize("caso", CORPUS_CALIBRACION["casos"], ids=lambda c:c["id"])
def test_f63_calibracion_adicional_sintetica(caso):
    resultado = calibrar(caso)
    assert [c.nivel for c in resultado.candidatos] == ([caso["nivel"]] if caso["nivel"] else [])


def test_f63_evidencia_reproducible_de_casos_y_calibracion():
    prioridades = []
    for caso in CASOS_PRIORITARIOS_MOTOR:
        criterio, registros, esperado = caso_prioritario(caso)
        prioridades.append(dict(caso=caso, esperado=esperado,
            criterio=criterio.model_dump(mode="json"), resultado=evaluar(criterio, registros).model_dump(mode="json")))
    calibracion = []
    for caso in CORPUS_CALIBRACION["casos"]:
        resultado = calibrar(caso)
        obtenidos = [c.nivel.value for c in resultado.candidatos]
        calibracion.append(dict(**caso, obtenido=obtenidos))
    assert all(c["obtenido"] == ([c["nivel"]] if c["nivel"] else []) for c in calibracion)
    directorio = os.getenv("LISTAS_F63_EVIDENCIAS_DIRECTORIO")
    if directorio:
        destino = Path(directorio)
        destino.mkdir(parents=True, exist_ok=True)
        (destino / "clasificaciones_sinteticas.json").write_text(json.dumps(prioridades, ensure_ascii=False, indent=2))
        resumen = dict(version=CORPUS_CALIBRACION["version"], casos=calibracion,
            casos_recuperables=sum(c["nivel"] is not None for c in calibracion),
            negativos_sin_candidato=sum(c["nivel"] is None for c in calibracion),
            altas_por_nombre=sum("ALTA" in c["obtenido"] for c in calibracion),
            desviaciones=sum(c["obtenido"] != ([c["nivel"]] if c["nivel"] else []) for c in calibracion),
            nota="Corpus sintético pequeño; no estima tasas generales ni valida producción.")
        (destino / "calibracion_sintetica.json").write_text(json.dumps(resumen, ensure_ascii=False, indent=2))


def test_f63_documento_fuerte_mas_apodo_publicado_no_inventa_otro_nombre_civil():
    candidato = evaluar(consulta("El Capitán", valor="AB0001234")).candidatos[0]
    assert candidato.nivel == "ALTA" and not candidato.revision_prioritaria


@pytest.mark.parametrize("valor", ["***123", "AB...?", "N/A", "SIN DATO", "----"])
def test_f63_identificadores_enmascarados_o_ausentes_no_dan_alta(valor):
    registro = cambiar(persona(), lambda d: d["identificadores"][0].update(valor=valor))
    with pytest.raises(CriterioNoUtilizable):
        evaluar(consulta(valor=valor), [registro])


def test_f63_guardas_documentales_en_combinaciones_de_calidad_y_contexto():
    from itertools import product
    for calidad, pais_fuente, pais_consulta, esquema, identidad in product(
            ["CONFIRMADO", "REPORTADO", "DESCONOCIDO", "FALSO"], ["CO", "US", None], ["CO", None], ["PASAPORTE", None], ["A", None]):
        def modificar(d):
            d["identificadores"][0].update(calidad=calidad, pais_emisor=pais_fuente, esquema=esquema)
            d["identificadores"][0]["referencia"]["identidad_origen"] = identidad
        resultado = evaluar(consulta(valor="AB0001234", pais=pais_consulta), [cambiar(persona(), modificar)])
        # ALTA exige que el documento no esté marcado fraudulento (OFAC no certifica más
        # que eso), más las guardas de jurisdicción, esquema y pertenencia a la misma identidad.
        permitido = calidad != "FALSO" and pais_fuente == pais_consulta == "CO" and esquema == "PASAPORTE" and identidad == "A"
        assert (resultado.candidatos[0].nivel == "ALTA") == permitido


def test_f63_guardas_nacimiento_en_combinaciones_de_precision_y_pertenencia():
    from itertools import product
    for calidad, precision, aproximada, identidad, debil in product(
            ["CONFIRMADO", "REPORTADO", "DESCONOCIDO", "FALSO"], ["DIA", "MES", "ANIO"], [False, True], ["A", "B", None], [False, True]):
        def modificar(d):
            f = d["hechos"][0]
            f.update(calidad=calidad)
            f["referencia"]["identidad_origen"] = identidad
            f["valor"].update(precision=precision, aproximada=aproximada,
                valor=dict(anio=1980, mes=3 if precision != "ANIO" else None, dia=15 if precision == "DIA" else None))
            d["nombres"][0]["alias_debil"] = debil
        resultado = evaluar(consulta(NOMBRE, fecha_nacimiento="1980-03-15"), [cambiar(persona(), modificar)])
        permitido = calidad == "CONFIRMADO" and precision == "DIA" and not aproximada and identidad == "A" and not debil
        assert (resultado.candidatos[0].nivel == "ALTA") == permitido


def test_f63_no_admite_evaluacion_sin_cobertura_o_fecha_explicitas():
    with pytest.raises(ValueError, match="cobertura"):
        MotorBusqueda().evaluar(consulta(NOMBRE), (), CONSULTA, {}, FECHA)
    with pytest.raises(ValueError, match="fecha"):
        MotorBusqueda().evaluar(consulta(NOMBRE), (persona(),), CONSULTA, {"lista_ficticia":COBERTURA}, None)


def test_f63_corpus_vacio_con_cobertura_no_inventa_candidato():
    resultado = MotorBusqueda().evaluar(consulta(NOMBRE), (), CONSULTA, {"lista_ficticia":COBERTURA}, FECHA)
    assert resultado.concluyente and resultado.candidatos == ()


def test_f63_pais_geografico_ausente_no_es_diferente():
    registro = cambiar(persona(), lambda d: d["hechos"][2]["valor"].update(pais=None))
    candidato = evaluar(consulta(NOMBRE, ubicaciones=[dict(rol="DOMICILIO", pais="CO")]), [registro]).candidatos[0]
    motivos = [m for m in candidato.motivos if m.campo == "ubicaciones"]
    assert motivos and all(m.resultado == "AUSENTE" for m in motivos)


def test_f63_dato_fiscal_falso_no_se_usa_como_conflicto_confirmado():
    registro = cambiar(empresa(), lambda d: d["identificadores"][0].update(calidad="FALSO"))
    candidato = evaluar(consulta(valor="900123456", digito="9", tipo="NIT", naturaleza="ENTIDAD"), [registro]).candidatos[0]
    assert candidato.nivel == "BAJA" and not candidato.revision_prioritaria


# --- La razón social se conserva y compara tal como fue ingresada: ninguna palabra se quita,
# incluidas las terminaciones societarias (S.A., S.A.S., SAS, SA, LTDA).
def test_sufijo_societario_no_se_ignora_al_comparar():
    from domain.listas.comparacion_nombres import comparar_nombre
    # Antes, "S.A.S." se quitaba y el nombre pasaba a ser completo. Ahora no lo es.
    comparacion = comparar_nombre("Comercial Andina S.A.S.", "Comercial Andina")
    assert comparacion is not None and comparacion.completo is False
    assert comparacion.metodo != "FORMA_SOCIETARIA"


def test_sufijos_distintos_no_son_el_mismo_nombre():
    from domain.listas.comparacion_nombres import comparar_nombre
    # Palabras finales distintas: no es igualdad. "Comercial" es genérica y solo queda "Andina",
    # así que no sustenta revisión por prefijo (regla: no coincidir por palabras genéricas).
    # Con una palabra distintiva compartida ("Andina") y la misma forma general, se revisa como BAJA
    # por prefijo compartido: no se quita ningún sufijo, y "comercial" no cuenta como distintiva.
    revision = comparar_nombre("Comercial Andina SAS", "Comercial Andina SA", ("comercial",))
    assert revision.metodo == "PREFIJO_COMPARTIDO" and revision.completo is False
    # Solo genéricas o conectores compartidos: no hay revisión.
    assert comparar_nombre("Comercial del Norte S.A.S.", "Comercial del Sur S.A.S.", ("comercial",)) is None
    assert comparar_nombre("Comercial Andina LTDA", "Comercial Andina").completo is False


def test_razon_social_identica_con_sufijo_sigue_coincidiendo():
    from domain.listas.comparacion_nombres import comparar_nombre
    assert comparar_nombre("Comercial Andina S.A.S.", "Comercial Andina S.A.S.").metodo == "NOMBRE_NORMALIZADO"


def test_motor_no_tiene_sufijos_como_palabras_genericas():
    """Un nombre compuesto solo de sufijos o de genéricos no debe quedar 'sin utilidad'
    por una lista de sufijos que ya no se aplica."""
    from services.listas.motor_busqueda import ParametrosMotor
    for sufijo in ("sa", "sas", "ltda"):
        assert sufijo not in ParametrosMotor().genericos


def test_comparar_nombre_no_acepta_parametro_de_entidad():
    import inspect
    from domain.listas.comparacion_nombres import comparar_nombre
    assert list(inspect.signature(comparar_nombre).parameters) == ["consultado", "publicado", "genericos", "admitir_iniciales"]


# --- El control del dígito de verificación solo está implementado para Colombia (nit-co-v1):
# exigirlo para el NIT de otro país sería imponer una regla de formato que no le corresponde.
def test_nit_internacional_sin_digito_puede_llegar_a_alta():
    registro = cambiar(empresa(), lambda d: d["identificadores"][0].update(
        valor="59536969", digito_verificacion=None, pais_emisor="GT", calidad="DESCONOCIDO"))
    resultado = evaluar(consulta("Comercial Andina S.A.S.", valor="59536969", tipo="NIT",
        pais="GT", naturaleza="ENTIDAD"), [registro])
    assert resultado.candidatos[0].nivel == "ALTA"


def test_nit_colombiano_sigue_exigiendo_el_digito():
    resultado_sin_digito = evaluar(consulta("Comercial Andina S.A.S.", valor="900123456", tipo="NIT",
        pais="CO", naturaleza="ENTIDAD"), [empresa()])
    assert resultado_sin_digito.candidatos[0].nivel != "ALTA"
    assert any(m.metodo == "CONTROL_FISCAL_INCOMPLETO" for m in resultado_sin_digito.candidatos[0].motivos)
    resultado_con_digito = evaluar(consulta("Comercial Andina S.A.S.", valor="900123456", tipo="NIT",
        pais="CO", digito="8", naturaleza="ENTIDAD"), [empresa()])
    assert resultado_con_digito.candidatos[0].nivel == "ALTA"


def test_nit_internacional_con_digito_equivocado_no_se_bloquea_por_control():
    """El dígito que alguien escriba para un NIT no colombiano no se interpreta con la
    regla colombiana (no se 'inventa' un control fiscal que ese país no tiene)."""
    registro = cambiar(empresa(), lambda d: d["identificadores"][0].update(
        valor="59536969", digito_verificacion=None, pais_emisor="GT", calidad="DESCONOCIDO"))
    resultado = evaluar(consulta("Comercial Andina S.A.S.", valor="59536969", tipo="NIT",
        pais="GT", digito="9", naturaleza="ENTIDAD"), [registro])
    assert not any(m.metodo == "CONTROL_FISCAL_INCOMPLETO" for m in resultado.candidatos[0].motivos)


# --- Pasaporte: OFAC publica algunos con espacios o guiones; se quitan solo esos separadores.
@pytest.mark.parametrize("escrito,publicado,coincide", [
    ("091971993", "09 1971993", True),
    ("09-1971993", "09 1971993", True),
    ("072130A", "072130-A", True),
    ("AB0001234", "AB0001235", False),
    ("09197199", "09 1971993", False),
])
def test_pasaporte_normaliza_solo_separadores(escrito, publicado, coincide):
    from domain.listas.comparacion_identificadores import preparar_identificador
    from domain.listas.contratos_busqueda import IdentificadorConsulta
    from domain.listas.datos_busqueda import IdentificadorFuente
    registro = cambiar(persona(), lambda d: d["identificadores"][0].update(valor=publicado, calidad="CONFIRMADO"))
    resultado = evaluar(consulta(valor=escrito), [registro])
    tiene_coincidencia = any(m.resultado in ("COINCIDE", "COMPATIBLE") and m.campo == "identificadores"
                             for m in resultado.candidatos[0].motivos) if resultado.candidatos else False
    assert tiene_coincidencia == coincide


def test_pasaporte_con_separadores_no_cambia_letras_ni_digitos():
    from domain.listas.comparacion_identificadores import preparar_identificador
    from domain.listas.contratos_busqueda import IdentificadorConsulta
    from services.listas.motor_busqueda import CATALOGO_MOTOR
    preparado = preparar_identificador(IdentificadorConsulta(tipo="PASAPORTE", valor="a1 b-2", pais_emisor="CO"), CATALOGO_MOTOR)
    assert preparado.valor == "a1b2"


# --- Cédula de extranjería: no hay equivalencia confiable en OFAC; nunca compara por número.
def test_cedula_extranjeria_no_compara_por_numero_y_sigue_por_nombre():
    from domain.listas.contratos_busqueda import IdentificadorConsulta
    criterio = consulta(NOMBRE, valor="71984381", tipo="CE", pais="CO")
    resultado = evaluar(criterio, [persona()])
    assert not any(m.campo == "identificadores" and m.resultado in ("COINCIDE", "COMPATIBLE")
                   for c in resultado.candidatos for m in c.motivos)
    assert resultado.candidatos  # la consulta continúa por nombre
