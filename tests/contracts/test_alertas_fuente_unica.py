"""
Verifica que TipoAlerta (dominio) sea la única fuente de verdad para el
concepto de "tipo de alerta" en el módulo de notificaciones.

Contexto: antes existía `TipoAlertaTemplate` en templates_correos.py —un
enum duplicado de `domain.puertos.alertas_portal.TipoAlerta`— y un
diccionario `_ASUNTO_POR_TIPO` copiado igual en sns_alertas.py y
ses_alertas.py, más un método `_mapear_tipo_alerta` idéntico en ambos
adaptadores para traducir entre los dos enums.
"""

from pathlib import Path

import pytest

from domain.puertos.alertas_portal import TipoAlerta
from infrastructure.notificaciones.templates_correos import (
    CONFIGURACION_ALERTA,
    obtener_asunto_correo,
)


def test_configuracion_alerta_cubre_todos_los_tipos_de_alerta():
    """Cada TipoAlerta del dominio debe tener su configuración de template."""
    for tipo in TipoAlerta:
        assert tipo in CONFIGURACION_ALERTA, f"Falta configuración para {tipo}"


@pytest.mark.parametrize("tipo", list(TipoAlerta))
def test_obtener_asunto_correo_tiene_prefijo_sagrilaft(tipo):
    asunto = obtener_asunto_correo(tipo)
    assert asunto.startswith("[SAGRILAFT]")


def test_templates_correos_no_redefine_tipo_alerta():
    """templates_correos.py no debe volver a declarar su propio enum de tipos."""
    import infrastructure.notificaciones.templates_correos as modulo

    codigo_fuente = Path(modulo.__file__).read_text(encoding="utf-8")
    assert "TipoAlertaTemplate" not in codigo_fuente
    assert "from domain.puertos.alertas_portal import TipoAlerta" in codigo_fuente


def test_adaptadores_no_duplican_asuntos_ni_mapeo():
    """sns_alertas.py y ses_alertas.py deben reutilizar obtener_asunto_correo,
    sin diccionarios propios de asuntos ni métodos de mapeo entre enums."""
    import infrastructure.notificaciones.sns_alertas as sns_modulo
    import infrastructure.notificaciones.ses_alertas as ses_modulo

    for modulo in (sns_modulo, ses_modulo):
        codigo_fuente = Path(modulo.__file__).read_text(encoding="utf-8")
        assert "_ASUNTO_POR_TIPO" not in codigo_fuente
        assert "_mapear_tipo_alerta" not in codigo_fuente
        assert "obtener_asunto_correo" in codigo_fuente
