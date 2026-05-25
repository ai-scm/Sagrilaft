"""
Re-exporta el mapeador de campos desde domain.utils.mapeo_campos.

La lógica real vive en domain/ — este módulo mantiene la ruta de importación
para los callers internos de services/ sin introducir dependencias cruzadas.
"""

from domain.utils.mapeo_campos import MapeadorCamposFormulario, mapear_campos_para_formulario

__all__ = ["MapeadorCamposFormulario", "mapear_campos_para_formulario"]
