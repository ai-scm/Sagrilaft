"""El informe presenta datos guardados; no reclasifica ni imprime cálculos internos."""
import copy

import pytest
from pydantic import ValidationError

from domain.listas.contratos_busqueda import ResultadoBusquedaF6
from services.listas.informes import version_informe
from services.listas.presentacion_informe import presentar_informe
from test_busqueda_f61 import resultado_archivos


def datos_informe():
    resultado = resultado_archivos().model_dump(mode="json")
    resultado["generador_informe_version"] = "informe-listas-f6-v2"
    return dict(resultado=resultado, criterio={"nombre":"Persona de prueba"},
        contexto={"expediente_id":"exp-ficticio","sujeto_rol":"CONTRAPARTE"},
        manifiesto={},version_generador="informe-listas-f6-v2")


@pytest.mark.parametrize("version,marca,esperada", [
    ("2.0",None,"informe-listas-v1"), ("2.1",None,"informe-listas-v1"),
    ("2.1","informe-listas-f6-v2","informe-listas-f6-v2"),
])
def test_f65_generador_depende_del_resultado_conservado(version,marca,esperada):
    resultado = {"version_contrato":version}
    if marca:
        resultado["generador_informe_version"] = marca
    assert version_informe(resultado) == esperada


def test_f65_generador_no_disponible_no_se_sustituye():
    with pytest.raises(ValueError,match="no disponible"):
        version_informe({"version_contrato":"2.1","generador_informe_version":"inexistente"})


def test_f65_html_escapa_datos_y_no_expone_puntajes_o_manifiesto_crudo():
    datos = datos_informe()
    candidato = datos["resultado"]["candidatos"][0]
    candidato["nombre_principal"] = '<img src="https://externo.invalid/dato" onerror="alert(1)">'
    candidato["puntaje"] = 0.987654
    datos["manifiesto"]["parametros"] = {"umbral_interno":0.876543}
    anterior = copy.deepcopy(datos)
    html = presentar_informe(datos)
    assert "<img" not in html and "&lt;img" in html
    assert "0.987654" not in html and "0.876543" not in html and "puntaje" not in html
    assert "MEDIA" in html and candidato["explicacion"] in html
    assert datos == anterior


@pytest.mark.parametrize("estado,conclusion,esperado", [
    ("COMPLETADA","SIN_CANDIDATOS","Sin candidatos en las fuentes consultadas"),
    ("PARCIAL","NO_CONCLUYENTE","Resultado no concluyente"),
    ("FALLIDA","NO_CONCLUYENTE","Resultado no concluyente"),
])
def test_f65_no_confunde_ausencia_de_candidatos_con_aprobacion(estado,conclusion,esperado):
    datos = datos_informe()
    datos["resultado"].update(estado_ejecucion=estado,conclusion_busqueda=conclusion,candidatos=[])
    html = presentar_informe(datos)
    assert esperado in html
    assert "no constituye aprobación" in html
    assert "revisión humana" in html


@pytest.mark.parametrize("campo", ["nombres","identificadores","relaciones"])
def test_f65_contexto_de_otro_registro_es_rechazado(campo):
    datos = resultado_archivos().model_dump(mode="json")
    candidato = datos["candidatos"][0]
    ref = dict(candidato["motivos"][0]["referencia"],fuente_codigo="otra_fuente")
    ejemplo = {
        "nombres":dict(valor="Alias ficticio",tipo="ALIAS",referencia=ref),
        "identificadores":dict(tipo="PASAPORTE",valor="FICTICIO01",referencia=ref),
        "relaciones":dict(tipo="VINCULO",direccion="SALIENTE",fuente_destino="lista_prueba",
            version_destino_id=ref["version_id"],registro_destino_id=ref["registro_id"],referencia=ref),
    }
    candidato[campo] = [ejemplo[campo]]
    with pytest.raises(ValidationError,match="otro registro"):
        ResultadoBusquedaF6.model_validate(datos)


def test_f65_resultado_anterior_sin_contexto_nuevo_sigue_siendo_valido():
    datos = resultado_archivos().model_dump(mode="json")
    for campo in ("nombres","identificadores","relaciones"):
        datos["candidatos"][0].pop(campo)
    datos.pop("generador_informe_version")
    anterior = copy.deepcopy(datos)
    resultado = ResultadoBusquedaF6.model_validate(datos)
    assert resultado.candidatos[0].nivel == "MEDIA"
    assert resultado.candidatos[0].nombres == () and datos == anterior
    assert resultado.generador_informe_version == "informe-listas-v1"
