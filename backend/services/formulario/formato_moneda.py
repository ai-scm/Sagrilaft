from __future__ import annotations

from typing import Any, Optional

_SIMBOLO_POR_MONEDA = {
    "COP": "$",
    "USD": "US$",
    "EUR": "€",
    "PEN": "S/",
    "BRL": "R$",
    "CLP": "CL$",
    "ARS": "AR$",
}

_LOCALE_POR_MONEDA = {
    "COP": "es-CO",
    "USD": "en-US",
    "EUR": "de-DE",
    "PEN": "es-PE",
    "BRL": "pt-BR",
    "CLP": "es-CL",
    "ARS": "es-AR",
}

_MONEDAS_CON_SEPARADOR_COMA = {"USD", "PEN"}


def extraer_entero_monetario(valor: Any) -> Optional[int]:
    if valor is None or valor == "":
        return None
    if isinstance(valor, bool):
        return None
    if isinstance(valor, (int, float)):
        return int(valor)

    texto = str(valor).strip()
    if not texto:
        return None

    try:
        return int(float(texto.replace(",", "")))
    except (ValueError, TypeError):
        digitos = "".join(caracter for caracter in texto if caracter.isdigit())
        return int(digitos) if digitos else None


def formatear_monto_monetario(valor: Any, moneda: Any) -> str:
    numero = extraer_entero_monetario(valor)
    if numero is None:
        return "" if valor in (None, "") else str(valor)

    codigo_moneda = str(moneda or "COP").strip().upper()
    simbolo = _SIMBOLO_POR_MONEDA.get(codigo_moneda, "$")
    separador_miles = "," if codigo_moneda in _MONEDAS_CON_SEPARADOR_COMA else "."
    monto = f"{numero:,}".replace(",", separador_miles)
    return f"{simbolo} {monto}"

