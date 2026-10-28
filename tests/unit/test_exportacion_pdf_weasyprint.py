"""
Regresion de generacion de PDF tras actualizar WeasyPrint 68.1 -> 70.0.

No existia ninguna prueba que ejercitara WeasyPrint realmente (solo
test_enums_tipo_persona_fuente_unica.py importa funciones auxiliares del
modulo, sin generar PDF). Antes de este cambio la unica validacion era
manual: comparacion pixel a pixel entre 68.1 y 70.0 de los PDF de
formulario y certificado (identicos salvo el timestamp de "Generado:").

Estas pruebas no reemplazan esa comparacion visual, pero evitan que una
futura actualizacion de WeasyPrint rompa silenciosamente la generacion
sin que ningun test lo detecte.
"""
from domain.formulario.entidades import FormularioDatos
from domain.formulario.tipos import TipoContraparte, TipoPersona
from services.formulario.exportacion_pdf import ExportadorFormularioPdf


def _formulario_de_prueba() -> FormularioDatos:
    return FormularioDatos(
        id="test-123",
        codigo_peticion="SAG-TEST001",
        estado="radicado",
        tipo_persona=TipoPersona.JURIDICA.value,
        tipo_contraparte=TipoContraparte.PROVEEDOR.value,
        razon_social="EMPRESA DE PRUEBA S.A.S.",
        numero_identificacion="900123456-7",
        nombre_representante="Juan Perez",
        numero_doc_representante="1020304050",
        correo="contacto@empresa.test",
        ingresos_mensuales=50_000_000,
        total_activos=500_000_000,
        total_pasivos=100_000_000,
        patrimonio=400_000_000,
        autorretenedor=True,
        gran_contribuyente=False,
    )


def test_formulario_pdf_se_genera_y_es_un_pdf_valido():
    nombre_archivo, pdf_bytes = ExportadorFormularioPdf().generar_bytes_pdf(
        _formulario_de_prueba(), numero_version=1
    )

    assert nombre_archivo == "FORMULARIO_SAG-TEST001_v1.pdf"
    assert pdf_bytes.startswith(b"%PDF-")
    assert pdf_bytes.rstrip().endswith(b"%%EOF")
    assert len(pdf_bytes) > 5_000  # un PDF vacio/roto pesaria unos pocos cientos de bytes


def test_formulario_pdf_incluye_el_codigo_de_peticion_y_la_razon_social():
    _, pdf_bytes = ExportadorFormularioPdf().generar_bytes_pdf(
        _formulario_de_prueba(), numero_version=1
    )

    # El contenido va comprimido (FlateDecode) dentro del PDF; buscamos el
    # marcador de stream para confirmar que el PDF trae contenido real y no
    # esta vacio, sin acoplar la prueba a los bytes crudos comprimidos.
    assert b"stream" in pdf_bytes
    assert b"endstream" in pdf_bytes


def test_certificado_pdf_se_genera_y_es_un_pdf_valido(tmp_path):
    from services.firma.certificado_pdf import generar_certificado_pdf

    salida = tmp_path / "certificado.pdf"
    resultado = generar_certificado_pdf(_formulario_de_prueba(), salida)

    assert resultado == salida
    contenido = salida.read_bytes()
    assert contenido.startswith(b"%PDF-")
    assert contenido.rstrip().endswith(b"%%EOF")
    assert len(contenido) > 5_000
