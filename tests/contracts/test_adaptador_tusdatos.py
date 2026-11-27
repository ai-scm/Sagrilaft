"""Intérprete del reporte de Tusdatos: alcance SAGRILAFT, minimización de datos y contrato propio `tusdatos-1`."""
import copy
import json
import uuid
from datetime import date, datetime, timezone

import pytest

from domain.listas.contratos import Criterio
from infrastructure.listas.tusdatos.adaptador import (
    CAMPOS_APROBADOS, fuentes_para, interpretar_reporte, resultado_sin_reporte, traducir_criterio,
)
from soporte_tusdatos import SimuladorTusdatos

AHORA = datetime(2026, 11, 12, 15, 0, tzinfo=timezone.utc)
REPORTES = {nombre: caso["respuesta"]["json"] for nombre, caso in SimuladorTusdatos().casos.items() if nombre.startswith("report_")}


def criterio(tipo="CC", valor="111", **extra):
    return Criterio.model_validate({"tipo_sujeto": "PERSONA", "identificadores": [{"tipo": tipo, "valor": valor}], **extra})


def interpretar(reporte, tipo="CC", valor="111", **opciones):
    c = opciones.pop("criterio", None) or criterio(tipo, valor)
    return interpretar_reporte(reporte, consulta_id=uuid.uuid4(), solicitud=traducir_criterio(c), criterio=c,
                               fecha_inicio=AHORA, fecha_fin=AHORA, **opciones)


# ── Traducción del criterio ──────────────────────────────────────────────────

@pytest.mark.parametrize("tipo,esperado,sujeto", [("CC", "CC", "PERSONA"), ("NIT", "NIT", "EMPRESA"),
                                                   ("PAS", "PP", "PERSONA"), ("PASAPORTE", "PP", "PERSONA")])
def test_tipos_del_expediente_se_traducen(tipo, esperado, sujeto):
    traducida = traducir_criterio(criterio(tipo, "381310014", nombre="JUAN PEREZ PEREZ"))
    assert traducida.tipo_documento == esperado and traducida.sujeto == sujeto
    assert traducida.nombre == ("JUAN PEREZ PEREZ" if esperado == "PP" else None)


@pytest.mark.parametrize("tipo,lleva_fecha", [("CC", True), ("CE", True), ("NIT", False), ("PAS", False)])
def test_fecha_de_expedicion_solo_viaja_con_cc_y_ce(tipo, lleva_fecha):
    traducida = traducir_criterio(criterio(tipo, "381310014", nombre="JUAN PEREZ PEREZ", fecha_expedicion="2014-12-01"))
    assert (traducida.fecha_expedicion is not None) is lleva_fecha
    assert traducir_criterio(criterio("CC", "111")).fecha_expedicion is None  # en CC es opcional


def test_ce_exige_fecha_y_pasaporte_exige_nombre():
    with pytest.raises(ValueError, match="fecha de expedición"):
        traducir_criterio(criterio("CE", "960696"))
    assert traducir_criterio(criterio("CE", "960696", fecha_expedicion="2001-11-01")).fecha_expedicion == date(2001, 11, 1)
    with pytest.raises(ValueError, match="nombre completo"):
        traducir_criterio(criterio("PAS", "381310014"))


def test_sin_documento_soportado_no_se_consulta():
    with pytest.raises(ValueError, match="Tusdatos requiere"):
        traducir_criterio(Criterio.model_validate({"tipo_sujeto": "PERSONA", "nombre": "Persona ficticia"}))
    with pytest.raises(ValueError):
        traducir_criterio(criterio("TI", "123"))


def test_empresa_no_incluye_fuentes_solo_de_personas():
    assert set(fuentes_para("EMPRESA")) == {"ofac", "lista_onu", "peps", "peps_denom", "procuraduria", "contraloria"}
    assert {"interpol", "europol", "cidob", "policia", "ofac_nombre", "peps_funcion_publica"} <= set(fuentes_para("PERSONA"))


# ── Interpretación de los reportes grabados ──────────────────────────────────

def fuente(resultado, codigo):
    return next(f for f in resultado.fuentes if f.codigo == codigo)


def test_cc_con_hallazgos_da_registros_por_fuente_en_un_solo_lugar():
    resultado = interpretar(REPORTES["report_cc_con_hallazgo"]).resultado
    assert resultado.version_contrato == "tusdatos-1"
    assert resultado.estado_ejecucion == "COMPLETADA" and resultado.conclusion_busqueda == "CON_CANDIDATOS"
    con_registro = {f.codigo for f in resultado.fuentes if f.estado == "CON_REGISTRO"}
    # Todas las coincidencias quedan en su fuente: también ONU, INTERPOL, Contraloría (true) y Policía (texto).
    assert con_registro == {"ofac", "ofac_nombre", "lista_onu", "interpol", "europol", "peps", "peps_denom", "cidob",
                            "peps_funcion_publica", "procuraduria", "contraloria", "policia"}
    assert fuente(resultado, "lista_onu").registros[0].sin_detalle
    assert {r.campo for r in fuente(resultado, "contraloria").registros} == {"contraloria", "contraloria2"}
    assert "asuntos pendientes" in fuente(resultado, "policia").registros[0].detalle["texto"]
    pep = fuente(resultado, "peps").registros[0]
    assert pep.categoria == "listas_restrictivas" and pep.identificador_origen
    assert resultado.titular_nombre == "MIGUEL FERNANDO PEREZ GOMEZ"


def test_el_detalle_se_conserva_completo_y_estructurado():
    """Antes se aplanaba a texto y se cortaba en 500 caracteres (Procuraduría quedaba en «\\"Fech»)."""
    reporte = REPORTES["report_cc_con_hallazgo"]
    procuraduria = fuente(interpretar(reporte).resultado, "procuraduria").registros[0]
    assert procuraduria.detalle == reporte["procuraduria"][0] and not procuraduria.detalle_recortado
    assert isinstance(procuraduria.detalle["datos"], list)
    europol = fuente(interpretar(reporte).resultado, "europol").registros[0]
    assert europol.detalle["crimes"] == ["crimen1", "crimen2"]


def test_detalle_desmedido_se_guarda_parcial_y_avisado():
    reporte = copy.deepcopy(REPORTES["report_cc_con_hallazgo"])
    reporte["europol"] = {"name": "X", **{f"campo_{i}": "y" * 1000 for i in range(60)}}
    registro = fuente(interpretar(reporte).resultado, "europol").registros[0]
    assert registro.detalle_recortado and registro.detalle["name"] == "X"
    assert len(json.dumps(registro.detalle)) <= 32_000


def test_sin_campos_heredados_de_la_busqueda_por_archivos():
    texto = json.dumps(interpretar(REPORTES["report_cc_con_hallazgo"]).resultado.model_dump(mode="json"))
    for heredado in ("hash_contenido", "revision_activa", "version_declarada", "puntaje", "escala_puntaje",
                     "motivos", "valor_consultado", "Nombre resuelto por el proveedor", "hallazgos_no_estructurados",
                     "criterios_no_aplicados", "cobertura"):
        assert f'"{heredado}"' not in texto and heredado not in texto


def test_cc_sin_hallazgos_y_nit_concluyen_sin_candidatos():
    # La cédula suma PEP por función pública (12 fuentes); el NIT no la incluye (6).
    for nombre, tipo, valor, cantidad in (("report_cc_sin_hallazgo", "CC", "112", 12), ("report_nit", "NIT", "900000152", 6)):
        resultado = interpretar(REPORTES[nombre], tipo, valor).resultado
        assert resultado.estado_ejecucion == "COMPLETADA" and resultado.conclusion_busqueda == "SIN_CANDIDATOS"
        assert len(resultado.fuentes) == cantidad
        assert all(f.estado == "SIN_REGISTRO" for f in resultado.fuentes if f.requerida)


def test_fuentes_con_error_no_permiten_concluir():
    resultado = interpretar(REPORTES["report_cc_con_error"], "CC", "113").resultado
    assert resultado.estado_ejecucion == "FALLIDA" and resultado.conclusion_busqueda == "NO_CONCLUYENTE"
    assert resultado.error.codigo == "FUENTES_NO_CONSULTADAS"


def test_una_fuente_fallida_o_ausente_deja_resultado_parcial_sin_avisos_repetidos():
    reporte = copy.deepcopy(REPORTES["report_cc_sin_hallazgo"])
    reporte["errores"] = ["ofac_offline"]           # variante del código de OFAC
    del reporte["europol"]                           # no vino en el plan
    resultado = interpretar(reporte, "CC", "112").resultado
    assert fuente(resultado, "ofac").estado == "NO_CONSULTADA" and fuente(resultado, "europol").estado == "NO_INCLUIDA"
    assert resultado.estado_ejecucion == "PARCIAL" and resultado.conclusion_busqueda == "NO_CONCLUYENTE"
    assert resultado.avisos == ()  # el estado de cada fuente no se repite como aviso


def test_texto_de_policia_sin_antecedentes_no_es_hallazgo():
    reporte = copy.deepcopy(REPORTES["report_cc_sin_hallazgo"])
    reporte["policia"] = "El ciudadano con Cédula de Ciudadanía Nº 112 NO TIENE ASUNTOS PENDIENTES CON LAS AUTORIDADES JUDICIALES"
    assert interpretar(reporte, "CC", "112").resultado.conclusion_busqueda == "SIN_CANDIDATOS"


def test_nivel_del_proveedor_se_informa_pero_no_decide():
    resultado = interpretar(REPORTES["report_cc_con_hallazgo"]).resultado
    assert resultado.nivel_informado_proveedor == "alto"
    sin = interpretar(REPORTES["report_cc_sin_hallazgo"], "CC", "112").resultado
    assert sin.conclusion_busqueda == "SIN_CANDIDATOS"


def test_hallazgos_informados_usan_el_codigo_y_el_catalogo_oficial():
    reporte = copy.deepcopy(REPORTES["report_cc_sin_hallazgo"])
    reporte["dict_hallazgos"] = {"infos": [{"codigo": "ofac_nombre_info", "hallazgo": "texto que puede cambiar"}],
                                 "altos": [{"codigo": "listas_restrictivas_denom", "hallazgo": "x"},
                                           {"codigo": "policia_novedad_administrativa", "hallazgo": "x"},
                                           {"codigo": "sisben", "hallazgo": "fuera de alcance"}]}
    resultado = interpretar(reporte, "CC", "112").resultado
    info = fuente(resultado, "ofac_nombre").hallazgos[0]
    assert info.codigo == "ofac_nombre_info" and info.nivel == "informativo" and "coincidencias parciales" in info.descripcion
    assert fuente(resultado, "peps_denom").hallazgos[0].codigo == "listas_restrictivas_denom"
    assert fuente(resultado, "policia").hallazgos[0].codigo == "policia_novedad_administrativa"
    assert not fuente(resultado, "ofac").hallazgos  # ofac_nombre_info no es de OFAC por documento
    assert "sisben" not in json.dumps(resultado.model_dump(mode="json"))


def test_version_y_resumen_de_pep_se_conservan_si_vienen():
    reporte = copy.deepcopy(REPORTES["report_cc_con_hallazgo"])
    reporte["peps_version"] = "2026.11.20"
    reporte["peps_consolidado"] = [{"categoria": "Listas restrictivas", "nombre_lista": "OFAC", "origen": "INTERNACIONAL",
                                    "tipo_lista": "OFAC"}]
    peps = fuente(interpretar(reporte).resultado, "peps")
    assert peps.version_base == "2026.11.20" and peps.resumen[0]["nombre_lista"] == "OFAC"
    assert fuente(interpretar(reporte).resultado, "peps_denom").resumen == ()


def test_nombre_oficial_de_la_fuente_sale_del_catalogo():
    resultado = interpretar(REPORTES["report_cc_sin_hallazgo"], "CC", "112").resultado
    assert fuente(resultado, "ofac").nombre.startswith("Lista Clinton (OFAC)")
    assert fuente(resultado, "ofac").estructura_documentada is False
    assert fuente(resultado, "procuraduria").estructura_documentada is True


def test_respeta_las_fuentes_fijadas_al_admitir():
    resultado = interpretar(REPORTES["report_cc_sin_hallazgo"], "CC", "112", fuentes=("ofac", "lista_onu")).resultado
    assert [f.codigo for f in resultado.fuentes] == ["ofac", "lista_onu"]
    with pytest.raises(ValueError):
        interpretar(REPORTES["report_cc_sin_hallazgo"], "CC", "112", fuentes=("sisben",))


# ── Minimización de datos ────────────────────────────────────────────────────

SENSIBLES = ("sisben", "ruaf", "fosyga", "delitos_sexuales", "simit", "rues", "libretamilitar", "iadb", "offshoreleaks")


def test_solo_las_fuentes_aprobadas_llegan_a_la_base():
    interpretacion = interpretar(REPORTES["report_cc_con_hallazgo"])
    filtrada = interpretacion.respuesta_filtrada
    assert set(filtrada["fuentes"]) <= CAMPOS_APROBADOS
    texto = json.dumps(filtrada, ensure_ascii=False).casefold()
    assert all(f'"{clave}"' not in texto for clave in SENSIBLES)
    hallazgos = [h for lista in filtrada["dict_hallazgos"].values() for h in lista]
    assert all(h["codigo"] not in SENSIBLES for h in hallazgos)
    resultado = json.dumps(interpretacion.resultado.model_dump(mode="json"), ensure_ascii=False).casefold()
    assert all(f'"{clave}"' not in resultado for clave in SENSIBLES)


def test_ids_son_estables_para_la_misma_consulta():
    consulta_id, c = uuid.uuid4(), criterio()
    uno, dos = (interpretar_reporte(REPORTES["report_cc_con_hallazgo"], consulta_id=consulta_id, solicitud=traducir_criterio(c),
                                    criterio=c, fecha_inicio=AHORA, fecha_fin=AHORA).resultado for _ in range(2))
    assert [r.id for f in uno.fuentes for r in f.registros] == [r.id for f in dos.fuentes for r in f.registros]
    assert [f.id for f in uno.fuentes] == [f.id for f in dos.fuentes]


def test_cierre_sin_reporte_cumple_el_contrato():
    resultado = resultado_sin_reporte(consulta_id=uuid.uuid4(), sujeto="PERSONA", codigo="TITULAR_NO_AUTORIZA",
                                      mensaje="El titular no autoriza", fecha_inicio=AHORA, fecha_fin=AHORA)
    assert resultado.estado_ejecucion == "FALLIDA" and resultado.conclusion_busqueda == "NO_CONCLUYENTE"
    assert resultado.error.codigo == "TITULAR_NO_AUTORIZA" and not resultado.error.reintentable
    assert {f.estado for f in resultado.fuentes} == {"NO_CONSULTADA"} and resultado.avisos == ()


# ── Correcciones frente al catálogo de Tusdatos ──────────────────────────────

def test_error_de_onu_con_el_codigo_corto_no_pasa_como_consultada():
    """El catálogo de errores usa `onu` además de `lista_onu`; antes la falla se perdía."""
    reporte = copy.deepcopy(REPORTES["report_cc_sin_hallazgo"])
    reporte["errores"] = ["onu"]
    resultado = interpretar(reporte, "CC", "112").resultado
    assert fuente(resultado, "lista_onu").estado == "NO_CONSULTADA"
    assert resultado.estado_ejecucion == "PARCIAL" and resultado.conclusion_busqueda == "NO_CONCLUYENTE"


def test_documento_no_validado_queda_advertido():
    reporte = REPORTES["report_cc_sin_hallazgo"]
    advertido = interpretar(reporte, "CC", "112", validado=False).resultado
    assert "DOCUMENTO_NO_VALIDADO" in {a.codigo for a in advertido.avisos} and advertido.documento_validado is False
    for validado in (True, None):  # None: el proveedor no valida pasaportes ni NIT
        resultado = interpretar(reporte, "CC", "112", validado=validado).resultado
        assert "DOCUMENTO_NO_VALIDADO" not in {a.codigo for a in resultado.avisos}


def test_pep_por_funcion_publica_da_registro_con_su_detalle():
    resultado = interpretar(REPORTES["report_cc_con_hallazgo"]).resultado
    registro = fuente(resultado, "peps_funcion_publica").registros[0]
    assert registro.titulo == "MIGUEL FERNANDO PEREZ GOMEZ"
    assert registro.detalle["DENOMINACION_CARGO"] == "Secretario de Planeación"
    assert "peps_funcion_publica" in interpretar(REPORTES["report_cc_con_hallazgo"]).respuesta_filtrada["fuentes"]


def test_pep_por_funcion_publica_ausente_no_impide_concluir_pero_con_error_si():
    sin = interpretar(REPORTES["report_cc_sin_hallazgo"], "CC", "112").resultado
    funcion = fuente(sin, "peps_funcion_publica")
    assert funcion.estado == "NO_INCLUIDA" and funcion.requerida is False
    assert sin.estado_ejecucion == "COMPLETADA" and sin.avisos == ()
    reporte = copy.deepcopy(REPORTES["report_cc_sin_hallazgo"])
    reporte["errores"] = ["peps_funcion_publica"]
    fallida = interpretar(reporte, "CC", "112").resultado
    assert fuente(fallida, "peps_funcion_publica").estado == "NO_CONSULTADA"
    assert fuente(fallida, "peps_funcion_publica").requerida is True
    assert fallida.estado_ejecucion == "PARCIAL"


def test_fuente_ausente_pero_con_error_cuenta_como_no_consultada():
    reporte = copy.deepcopy(REPORTES["report_cc_sin_hallazgo"])
    del reporte["interpol"]
    reporte["errores"] = ["interpol"]
    assert fuente(interpretar(reporte, "CC", "112").resultado, "interpol").estado == "NO_CONSULTADA"


def test_codigos_de_las_fuentes_coinciden_con_el_catalogo_de_errores():
    """Catálogo /api/catalogo-errores-fuentes del sandbox (13-11-2026), filtrado a las fuentes aprobadas."""
    catalogo = {"cidob", "contraloria", "contraloria_db", "europol", "interpol", "lista_onu", "onu", "ofac",
                "ofac_database_id", "ofac_database_nombre", "ofac_nombre", "ofac_offline", "peps", "peps_denom",
                "peps_funcion_publica", "policia", "procuraduria", "procuraduria_db"}
    from infrastructure.listas.tusdatos.adaptador import FUENTES
    reconocidos = {codigo for f in FUENTES for codigo in f.errores}
    assert catalogo <= reconocidos


@pytest.mark.parametrize("valor,esperado", [("900.123.456-7", "900.123.456"), ("900123456 - 7", "900123456"),
                                            ("900123456", "900123456"), ("9001234567", "9001234567")])
def test_nit_se_envia_sin_digito_de_verificacion(valor, esperado):
    assert traducir_criterio(criterio("NIT", valor)).numero == esperado


def test_cedula_no_pierde_su_ultimo_digito():
    assert traducir_criterio(criterio("CC", "79.123.456-7")).numero == "79.123.456-7"


def test_codigos_de_estado_omiten_las_copias_en_base_de_datos():
    from infrastructure.listas.tusdatos.adaptador import FUENTES_POR_CODIGO
    assert FUENTES_POR_CODIGO["ofac"].codigos_estado == {"ofac"}
    assert FUENTES_POR_CODIGO["lista_onu"].codigos_estado == {"lista_onu", "onu"}
    assert FUENTES_POR_CODIGO["procuraduria"].codigos_estado == {"procuraduria"}


def test_fuente_fallida_que_tusdatos_reporta_caida_lo_dice_en_el_motivo():
    reporte = copy.deepcopy(REPORTES["report_cc_sin_hallazgo"])
    reporte["errores"] = ["procuraduria", "policia"]
    resultado = interpretar(reporte, "CC", "112", fuentes_caidas=frozenset({"procuraduria"})).resultado
    assert "caída o en mantenimiento" in fuente(resultado, "procuraduria").motivo
    assert fuente(resultado, "policia").motivo == "Tusdatos informó error al consultar la fuente"
    assert resultado.estado_ejecucion == "PARCIAL"


def test_capturas_por_fuente_y_ruta_guardada():
    from infrastructure.listas.tusdatos.adaptador import FUENTES_POR_CODIGO, filtrar_reporte
    capturas = {codigo: f.captura for codigo, f in FUENTES_POR_CODIGO.items() if f.captura}
    # Nombres de archivo de la sección «Evidencias» de Tusdatos (ONU se guarda como onu.jpg).
    assert capturas == {"ofac": "ofac", "ofac_nombre": "ofac_nombre", "lista_onu": "onu", "interpol": "interpol",
                        "europol": "europol", "cidob": "cidob", "procuraduria": "procuraduria", "policia": "policia"}
    assert filtrar_reporte(REPORTES["report_cc_con_hallazgo"])["dest"] == "static/img/63776b99-4f26-4f11-b426-dcbbb124dfb8"
