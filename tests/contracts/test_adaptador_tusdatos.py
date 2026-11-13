"""Intérprete del reporte de Tusdatos: alcance SAGRILAFT, minimización de datos y contrato 2.0. Sin red ni base."""
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
    assert {"interpol", "europol", "cidob", "policia", "ofac_nombre"} <= set(fuentes_para("PERSONA"))


# ── Interpretación de los reportes grabados ──────────────────────────────────

def test_cc_con_hallazgos_produce_candidatos_por_fuente():
    resultado = interpretar(REPORTES["report_cc_con_hallazgo"]).resultado
    assert resultado.estado_ejecucion == "COMPLETADA" and resultado.conclusion_busqueda == "CON_CANDIDATOS"
    por_fuente = {c.motivos[0].campo for c in resultado.candidatos}
    assert {"ofac", "ofac_nombre", "europol", "peps", "peps_denom", "cidob", "procuraduria"} <= por_fuente
    # ONU, INTERPOL y Contraloría solo dicen «true»; Policía devuelve una frase: quedan para revisión.
    assert {h.codigo for h in resultado.hallazgos_no_estructurados} == {"lista_onu", "interpol", "contraloria", "policia"}
    pep = next(c for c in resultado.candidatos if c.motivos[0].campo == "peps")
    assert pep.atributos["categoria_sagrilaft"] == "listas_restrictivas" and pep.uid_origen
    assert all(m.metodo == "PROVEEDOR" for c in resultado.candidatos for m in c.motivos)


def test_cc_sin_hallazgos_y_nit_concluyen_sin_candidatos():
    for nombre, tipo, valor, cantidad in (("report_cc_sin_hallazgo", "CC", "112", 11), ("report_nit", "NIT", "900000152", 6)):
        resultado = interpretar(REPORTES[nombre], tipo, valor).resultado
        assert resultado.estado_ejecucion == "COMPLETADA" and resultado.conclusion_busqueda == "SIN_CANDIDATOS"
        assert len(resultado.cobertura) == cantidad and all(c.estado == "CONSULTADA" for c in resultado.cobertura)


def test_fuentes_con_error_no_permiten_concluir():
    resultado = interpretar(REPORTES["report_cc_con_error"], "CC", "113").resultado
    assert resultado.estado_ejecucion == "FALLIDA" and resultado.conclusion_busqueda == "NO_CONCLUYENTE"
    assert resultado.error.codigo == "FUENTES_NO_CONSULTADAS"


def test_una_fuente_fallida_o_ausente_deja_resultado_parcial():
    reporte = copy.deepcopy(REPORTES["report_cc_sin_hallazgo"])
    reporte["errores"] = ["ofac_offline"]           # variante del código de OFAC
    del reporte["europol"]                           # no vino en el plan
    resultado = interpretar(reporte, "CC", "112").resultado
    estados = {c.fuente_codigo: c.estado for c in resultado.cobertura}
    assert estados["ofac"] == "FALLIDA" and estados["europol"] == "NO_DISPONIBLE"
    assert resultado.estado_ejecucion == "PARCIAL" and resultado.conclusion_busqueda == "NO_CONCLUYENTE"
    assert {"FUENTE_FALLIDA", "FUENTE_NO_DISPONIBLE"} <= {a.codigo for a in resultado.advertencias}


def test_texto_de_policia_sin_antecedentes_no_es_hallazgo():
    reporte = copy.deepcopy(REPORTES["report_cc_sin_hallazgo"])
    reporte["policia"] = "El ciudadano con Cédula de Ciudadanía Nº 112 NO TIENE ASUNTOS PENDIENTES CON LAS AUTORIDADES JUDICIALES"
    assert interpretar(reporte, "CC", "112").resultado.conclusion_busqueda == "SIN_CANDIDATOS"


def test_nivel_del_proveedor_se_informa_pero_no_decide():
    resultado = interpretar(REPORTES["report_cc_con_hallazgo"]).resultado
    nivel = next(a for a in resultado.advertencias if a.codigo == "NIVEL_INFORMADO_PROVEEDOR")
    assert "no es una decisión" in nivel.descripcion


def test_nombre_no_se_envia_y_queda_como_criterio_no_aplicado():
    resultado = interpretar(REPORTES["report_cc_sin_hallazgo"], criterio=criterio("CC", "112", nombre="Persona ficticia",
                                                                                  fecha_nacimiento="1980-01-01")).resultado
    descripciones = " ".join(a.descripcion for a in resultado.criterios_no_aplicados)
    assert "nombre" in descripciones and "fecha_nacimiento" in descripciones


def test_respeta_las_fuentes_fijadas_al_admitir():
    resultado = interpretar(REPORTES["report_cc_sin_hallazgo"], "CC", "112", fuentes=("ofac", "lista_onu")).resultado
    assert [c.fuente_codigo for c in resultado.cobertura] == ["ofac", "lista_onu"]
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
    assert [x.id for x in uno.candidatos] == [x.id for x in dos.candidatos]


def test_cierre_sin_reporte_cumple_el_contrato():
    resultado = resultado_sin_reporte(consulta_id=uuid.uuid4(), sujeto="PERSONA", codigo="TITULAR_NO_AUTORIZA",
                                      mensaje="El titular no autoriza", fecha_inicio=AHORA, fecha_fin=AHORA)
    assert resultado.estado_ejecucion == "FALLIDA" and resultado.conclusion_busqueda == "NO_CONCLUYENTE"
    assert resultado.error.codigo == "TITULAR_NO_AUTORIZA" and not resultado.error.reintentable
