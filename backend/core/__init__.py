"""
Módulo core — configuración de la aplicación.

Exporta los símbolos públicos de core.config para que los importadores
existentes (`from core import load_config`) sigan funcionando sin cambios.
"""

from core.config import AppConfig, AWSConfig, load_config

__all__ = ["AppConfig", "AWSConfig", "load_config"]
