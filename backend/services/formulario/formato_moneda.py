from __future__ import annotations

from decimal import Decimal
from typing import Any, Optional

_MONEDA_PREDETERMINADA = "COP"
_MONEDA_PERSONALIZADA = "OTRA"

_MONEDA_POR_CODIGO = {
    "COP": {"simbolo": "$", "separador_miles": "."},
    "USD": {"simbolo": "US$", "separador_miles": ","},
    "EUR": {"simbolo": "€", "separador_miles": "."},
    "PEN": {"simbolo": "S/", "separador_miles": ","},
    "BRL": {"simbolo": "R$", "separador_miles": "."},
    "CLP": {"simbolo": "CL$", "separador_miles": "."},
    "ARS": {"simbolo": "AR$", "separador_miles": "."},
    "MXN": {"simbolo": "MX$", "separador_miles": ","},
    "GBP": {"simbolo": "£", "separador_miles": ","},
    "JPY": {"simbolo": "¥", "separador_miles": ","},
    "CHF": {"simbolo": "CHF", "separador_miles": "'"},
    "AUD": {"simbolo": "A$", "separador_miles": ","},
    "CAD": {"simbolo": "C$", "separador_miles": ","},
    "NZD": {"simbolo": "NZ$", "separador_miles": ","},
    "CNY": {"simbolo": "¥", "separador_miles": ","},
    "HKD": {"simbolo": "HK$", "separador_miles": ","},
    "SGD": {"simbolo": "S$", "separador_miles": ","},
    "OTRA": {"simbolo": "", "separador_miles": "."},
}


def obtener_codigo_iso_moneda(valor: Any) -> Optional[str]:
    codigo = str(valor or "").strip().upper()
    if len(codigo) == 3 and codigo.isalpha() and codigo in _MONEDA_POR_CODIGO:
        return codigo
    return None


def resolver_moneda_para_formato(moneda: Any, moneda_otra: Any = None) -> str:
    codigo_moneda = str(moneda or "").strip().upper()
    if codigo_moneda == _MONEDA_PERSONALIZADA:
        return obtener_codigo_iso_moneda(moneda_otra) or _MONEDA_PREDETERMINADA
    return obtener_codigo_iso_moneda(codigo_moneda) or _MONEDA_PREDETERMINADA


def extraer_entero_monetario(valor: Any) -> Optional[int]:
    if valor is None or valor == "":
        return None
    if isinstance(valor, bool):
        return None
    if isinstance(valor, (int, float, Decimal)):
        return int(valor)

    texto = str(valor).strip()
    if not texto:
        return None

    try:
        return int(float(texto.replace(",", "")))
    except (ValueError, TypeError):
        digitos = "".join(caracter for caracter in texto if caracter.isdigit())
        return int(digitos) if digitos else None


def formatear_monto_monetario(valor: Any, moneda: Any, moneda_otra: Any = None) -> str:
    numero = extraer_entero_monetario(valor)
    if numero is None:
        return "" if valor in (None, "") else str(valor)

    codigo_declaracion = str(moneda or "").strip().upper()
    codigo_moneda = resolver_moneda_para_formato(moneda, moneda_otra)
    configuracion = _MONEDA_POR_CODIGO[codigo_moneda]
    es_otra_sin_iso = codigo_declaracion == _MONEDA_PERSONALIZADA and not obtener_codigo_iso_moneda(moneda_otra)
    simbolo = "" if es_otra_sin_iso else configuracion["simbolo"]
    separador_miles = configuracion["separador_miles"]
    monto = f"{numero:,}".replace(",", separador_miles)
    return f"{simbolo} {monto}".strip()
