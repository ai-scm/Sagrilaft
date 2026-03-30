"""
Utilidades compartidas entre validadores de documentos.

DRY : centraliza normalización, verificación de vigencia y comparación de campos
      que de otro modo se duplicarían en cada validador.
SRP : cada función tiene una responsabilidad única y bien delimitada.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Callable, Optional

from services.utils.texto import quitar_diacriticos

from services.alertas.normalizador_nombre import normalizar_razon_social
from services.alertas.normalizador_nit import normalizar_nit
from services.alertas.normalizador_numero_doc import normalizar_numero_doc
from core.contracts import HallazgoValidacion

# ─── Constantes ──────────────────────────────────────────────────────────────

FORMATO_FECHA = "%Y-%m-%d"
VIGENCIA_MAX_DIAS = 30

# Meses en español usados en cédulas colombianas (formato DD-MMM-AAAA)
_MESES_ES: dict[str, int] = {
    "ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6,
    "jul": 7, "ago": 8, "sep": 9, "oct": 10, "nov": 11, "dic": 12,
}


# ─── Normalización ───────────────────────────────────────────────────────────

def normalizar_texto(valor: Any) -> str:
    """
    Normaliza texto para comparación: minúsculas, sin espacios extremos
    y sin diacríticos (tildes, ñ→n, ü→u, etc.).

    Evita falsos negativos al comparar nombres con y sin tilde,
    frecuentes en datos colombianos extraídos por OCR.
    """
    if not valor:
        return ""
    return quitar_diacriticos(str(valor)).lower().strip()


def normalizar_identificacion(valor: Any) -> str:
    """Normaliza un número de identificación eliminando puntos, guiones y espacios."""
    if not valor:
        return ""
    return str(valor).replace(".", "").replace("-", "").replace(" ", "").strip()


# ─── Parseo de fechas ────────────────────────────────────────────────────────

def parsear_fecha(valor: Any) -> Optional[date]:
    """
    Parsea una fecha en cualquiera de los dos formatos posibles:
      - YYYY-MM-DD   (formulario con <input type="date">)
      - DD-MMM-AAAA  (cédula colombiana, ej: '01-SEP-1995')

    Retorna un objeto `date` o `None` si el formato no es reconocido.
    """
    if not valor:
        return None

    cadena = str(valor).strip()

    # Formato ISO: YYYY-MM-DD
    try:
        return datetime.strptime(cadena, "%Y-%m-%d").date()
    except ValueError:
        pass

    # Formato cédula: DD-MMM-AAAA (mes abreviado en español)
    partes = cadena.split("-")
    if len(partes) == 3:
        dia_str, mes_str, anio_str = partes
        mes_num = _MESES_ES.get(mes_str.lower())
        if mes_num:
            try:
                return date(int(anio_str), mes_num, int(dia_str))
            except ValueError:
                pass

    return None


# ─── Verificación de vigencia ─────────────────────────────────────────────────

def verificar_vigencia(
    fecha_str: Any,
    campo: str,
    max_dias: int = VIGENCIA_MAX_DIAS,
) -> Optional[HallazgoValidacion]:
    """
    Verifica que un documento no supere `max_dias` días de antigüedad.

    Args:
        fecha_str: Fecha del documento en formato YYYY-MM-DD.
        campo:     Nombre del campo para el hallazgo.
        max_dias:  Máximo de días permitidos (por defecto 30).

    Returns:
        HallazgoValidacion ok/error, o None si la fecha no es parseable.
    """
    if not fecha_str:
        return None
    try:
        fecha = datetime.strptime(str(fecha_str), FORMATO_FECHA)
        dias = (datetime.now() - fecha).days
        if dias > max_dias:
            return HallazgoValidacion.error(
                campo=campo,
                detalle=f"Documento tiene {dias} días. No debe superar {max_dias} días.",
                valor_documento=str(fecha_str),
            )
        return HallazgoValidacion.ok(
            campo=campo,
            detalle=f"Documento vigente ({dias} días).",
            valor_documento=str(fecha_str),
        )
    except ValueError:
        return None


# ─── Comparaciones reutilizables ─────────────────────────────────────────────

def comparar_texto(
    valor_doc: Any,
    valor_form: Any,
    campo: str,
    nombre: str,
    fuente: str,
) -> Optional[HallazgoValidacion]:
    """
    Compara dos textos normalizados y retorna un HallazgoValidacion.

    Usa normalizar_razon_social (superset de normalizar_texto): quita tildes,
    mayúsculas y además colapsa siglas societarias (S.A.S.→SAS, LTDA.→LTDA),
    garantizando el mismo criterio de comparación que el sistema de alertas
    en tiempo real (upload). Sin esta unificación, el mismo campo puede
    resultar coincidente al subir un doc y no-coincidente en la validación final.

    DRY : centraliza la lógica que de otro modo se duplicaría en cada validador.

    Args:
        valor_doc:  Valor extraído del documento por IA.
        valor_form: Valor ingresado en el formulario por el usuario.
        campo:      Nombre del campo para el hallazgo.
        nombre:     Nombre legible del campo (ej. "Razón social").
        fuente:     Nombre del documento de origen (ej. "RUT").
    """
    if not valor_doc or not valor_form:
        return None
    coincide = normalizar_razon_social(valor_doc) == normalizar_razon_social(valor_form)
    return (
        HallazgoValidacion.ok(
            campo=campo,
            detalle=f"{nombre} coincide con {fuente}.",
            valor_formulario=str(valor_form),
            valor_documento=str(valor_doc),
        ) if coincide else HallazgoValidacion.error(
            campo=campo,
            detalle=f"{nombre} NO coincide entre {fuente} y el formulario.",
            valor_formulario=str(valor_form),
            valor_documento=str(valor_doc),
        )
    )


def comparar_identificacion(
    valor_doc: Any,
    valor_form: Any,
    campo: str,
    nombre: str,
    fuente: str,
    normalizador: Callable[[Any], str] = normalizar_numero_doc,
) -> Optional[HallazgoValidacion]:
    """
    Compara dos números de identificación normalizados y retorna un HallazgoValidacion.

    El normalizador por defecto es normalizar_numero_doc (elimina no-alfanuméricos,
    sin truncar). Para comparar NITs se debe pasar normalizar_nit explícitamente,
    ya que los NITs colombianos incluyen un dígito de verificación opcional que
    debe descartarse antes de comparar (ej: "900.123.456-7" == "900123456").

    DRY : centraliza la lógica que de otro modo se duplicaría en cada validador.

    Args:
        valor_doc:    Valor extraído del documento por IA.
        valor_form:   Valor ingresado en el formulario por el usuario.
        campo:        Nombre del campo para el hallazgo.
        nombre:       Nombre legible del campo (ej. "NIT").
        fuente:       Nombre del documento de origen.
        normalizador: Función de normalización a aplicar. Por defecto
                      normalizar_numero_doc. Pasar normalizar_nit para NITs.
    """
    if not valor_doc or not valor_form:
        return None
    coincide = normalizador(valor_doc) == normalizador(valor_form)
    return (
        HallazgoValidacion.ok(
            campo=campo,
            detalle=f"{nombre} coincide con {fuente}.",
            valor_formulario=str(valor_form),
            valor_documento=str(valor_doc),
        ) if coincide else HallazgoValidacion.error(
            campo=campo,
            detalle=f"{nombre} NO coincide entre {fuente} y el formulario.",
            valor_formulario=str(valor_form),
            valor_documento=str(valor_doc),
        )
    )


def comparar_entre_documentos(
    valor_a: Any,
    valor_b: Any,
    campo: str,
    descripcion: str,
    nombre_doc_a: str,
    nombre_doc_b: str,
    normalizador: Callable[[Any], str] = normalizar_texto,
) -> Optional[HallazgoValidacion]:
    """
    Compara un campo presente en dos documentos distintos y retorna un hallazgo
    de consistencia.

    DRY : centraliza la lógica de cruce que de otro modo se repetiría por
          cada regla en ValidadorCruzadoDocumentos.

    Args:
        valor_a:      Valor extraído del primer documento.
        valor_b:      Valor extraído del segundo documento.
        campo:        Nombre del hallazgo generado.
        descripcion:  Descripción legible del campo (ej. "Razón social").
        nombre_doc_a: Nombre display del primer documento (ej. "el RUT").
        nombre_doc_b: Nombre display del segundo documento (ej. "el Certificado de Existencia").
        normalizador: Función de normalización a aplicar a ambos valores.

    Returns:
        HallazgoValidacion ok/error, o None si alguno de los valores no está disponible.
    """
    norm_a = normalizador(valor_a)
    norm_b = normalizador(valor_b)
    if not norm_a or not norm_b:
        return None
    coincide = norm_a == norm_b
    return (
        HallazgoValidacion.ok(
            campo=campo,
            detalle=f"{descripcion} coincide entre {nombre_doc_a} y {nombre_doc_b}.",
            valor_formulario=str(valor_b),
            valor_documento=str(valor_a),
        ) if coincide else HallazgoValidacion.error(
            campo=campo,
            detalle=f"{descripcion} NO coincide entre {nombre_doc_a} y {nombre_doc_b}.",
            valor_formulario=str(valor_b),
            valor_documento=str(valor_a),
        )
    )
