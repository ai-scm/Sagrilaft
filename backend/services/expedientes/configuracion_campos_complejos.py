"""
ConfiguracionCamposComplejos — definición de campos complejos para comparación.

Responsabilidades:
  - Definir qué campos son complejos y requieren visualización especial.
  - Proporcionar configuración de campos (etiquetas, tipos, subcampos).
  - Ser extensible a través de inyección de dependencias.
"""

from typing import Any, Dict, Set


class ConfiguracionCamposComplejos:
    """Administra la configuración de campos complejos para reportes de comparación."""

    def __init__(self, configuracion: Dict[str, Dict[str, Any]]):
        """
        Inicializa con un diccionario de configuración.
        
        Argumentos:
            configuracion: Dict con estructura {nombre_campo: {tipo, campos, ...}}
        """
        self._configuracion = configuracion

    @classmethod
    def por_defecto(cls) -> "ConfiguracionCamposComplejos":
        """Factory method que retorna la configuración estándar por defecto."""
        return cls(_CONFIGURACION_ESTANDAR)

    def obtener(self, nombre_campo: str) -> Dict[str, Any]:
        """
        Obtiene la configuración de un campo específico.
        
        Argumentos:
            nombre_campo: Nombre del campo a buscar
            
        Retorna:
            Dict con tipo y detalles del campo, o defecto si no existe
        """
        return self._configuracion.get(
            nombre_campo,
            {"tipo": "arregloObjetos", "campos": []},
        )

    def es_campo_complejo(self, nombre_campo: str) -> bool:
        """
        Determina si un campo es complejo.
        
        Argumentos:
            nombre_campo: Nombre del campo a verificar
            
        Retorna:
            True si el campo está registrado como complejo
        """
        return nombre_campo in self._configuracion

    def campos_complejos(self) -> Set[str]:
        """Retorna el conjunto de todos los campos complejos registrados."""
        return set(self._configuracion.keys())


# Configuración estándar de campos complejos
_CONFIGURACION_ESTANDAR = {
    "junta_directiva": {
        "tipo": "arregloObjetos",
        "campos": [
            {"clave": "nombre", "etiqueta": "Nombre"},
            {"clave": "cargo", "etiqueta": "Cargo"},
            {"clave": "tipo_id", "etiqueta": "Tipo ID"},
            {"clave": "numero_id", "etiqueta": "Número ID"},
            {"clave": "es_pep", "etiqueta": "PEP"},
            {"clave": "vinculos_pep", "etiqueta": "Vínculos PEP"},
        ]
    },
    "accionistas": {
        "tipo": "arregloObjetos",
        "campos": [
            {"clave": "nombre", "etiqueta": "Nombre"},
            {"clave": "tipo_id", "etiqueta": "Tipo ID"},
            {"clave": "numero_id", "etiqueta": "Número ID"},
            {"clave": "porcentaje", "etiqueta": "Porcentaje"},
            {"clave": "es_pep", "etiqueta": "PEP"},
            {"clave": "vinculos_pep", "etiqueta": "Vínculos PEP"},
        ]
    },
    "beneficiario_final": {
        "tipo": "arregloObjetos",
        "campos": [
            {"clave": "nombre", "etiqueta": "Nombre"},
            {"clave": "tipo_id", "etiqueta": "Tipo ID"},
            {"clave": "numero_id", "etiqueta": "Número ID"},
            {"clave": "porcentaje", "etiqueta": "Porcentaje"},
            {"clave": "es_pep", "etiqueta": "PEP"},
            {"clave": "vinculos_pep", "etiqueta": "Vínculos PEP"},
        ]
    },
    "referencias_comerciales": {
        "tipo": "arregloObjetos",
        "campos": [
            {"clave": "nombre_establecimiento", "etiqueta": "Establecimiento"},
            {"clave": "ciudad", "etiqueta": "Ciudad"},
            {"clave": "persona_contacto", "etiqueta": "Persona de contacto"},
            {"clave": "telefono", "etiqueta": "Teléfono"},
        ]
    },
    "referencias_bancarias": {
        "tipo": "arregloObjetos",
        "campos": [
            {"clave": "entidad", "etiqueta": "Entidad"},
            {"clave": "producto", "etiqueta": "Producto"},
        ]
    },
    "tipos_transaccion": {
        "tipo": "arregloSimple",
        "etiquetasValores": {
            "importacion": "Importación",
            "exportacion": "Exportación",
            "inversiones": "Inversiones",
            "pago_servicios": "Pago de servicios",
            "otras": "Otras",
        }
    },
}
