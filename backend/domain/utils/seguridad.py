"""
Utilidades de seguridad para registros de auditoría.

Los sistemas de cumplimiento como SAGRILAFT generan registros continuos de
actividad. Parte de lo que se registra proviene de fuentes externas (correos,
tokens, rutas). Si esos valores llegan directamente al log sin sanitizar,
un atacante puede inyectar saltos de línea para fabricar líneas falsas que
parecen eventos legítimos — OWASP A09:2021 (Log Injection).

sanitizar_log es el paso previo obligatorio cada vez que un dato externo
toca un registro de auditoría.
"""

import re


def sanitizar_log(valor: object) -> str:
    """Elimina caracteres de control ASCII del valor antes de escribirlo en un log."""
    return re.sub(r"[\x00-\x1f\x7f]", " ", str(valor)).strip()
