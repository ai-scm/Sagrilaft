"""
Configuración y lógica de pre-llenado de formularios desde documentos IA.

Centraliza el mapeo entre campos extraídos por IA y campos del formulario,
eliminando el acoplamiento entre FormularioService y bedrock_extractor.py.

SOLID:
- S (Responsabilidad Única): Módulo dedicado exclusivamente al mapeo de campos.
- O (Abierto/Cerrado): Agregar un tipo de documento nuevo solo requiere extender
  _MAPEO_POR_TIPO en MapeadorCamposFormulario, sin modificar la lógica de mapeo.
- D (Inversión de Dependencias): FormularioService y ExtractorBedrock dependen
  de este módulo neutral; ninguno depende del otro.

DRY: Elimina la duplicación entre _mapear_campos_prellenado (formulario_service)
     y obtener_campos_prellenado (bedrock_extractor), unificando la lógica aquí.

Encapsulación: _MAPEO_POR_TIPO vive como constante privada de clase en lugar de
un dict global expuesto, evitando modificaciones accidentales desde otros módulos.
"""

from __future__ import annotations

from typing import Any, Dict, List


# ═══════════════════════════════════════════════════════════════
# Mapeador de campos IA → formulario
# ═══════════════════════════════════════════════════════════════

class MapeadorCamposFormulario:
    """
    Mapea los campos extraídos por IA de un documento a los campos del formulario.

    SOLID - S: Responsabilidad única — transformar datos de documento a datos
               de formulario.
    SOLID - O: Para soportar un nuevo tipo de documento, agregar una entrada en
               _MAPEO_POR_TIPO; la lógica de mapeo no necesita cambiar.

    Uso preferido:
        campos = MapeadorCamposFormulario.mapear("rut", datos_extraidos)
        tipos  = MapeadorCamposFormulario.tipos_soportados()
    """

    _MAPEO_POR_TIPO: Dict[str, Dict[str, str]] = {
        "rut": {
            "razon_social": "razon_social",
            "nit":          "numero_identificacion",
            "direccion":    "direccion",
            "correo":       "correo",
            "telefono":     "telefono",
            "codigo_ica":   "codigo_ica",
        },
        "certificado_existencia": {
            "razon_social":        "razon_social",
            "nit":                 "numero_identificacion",
            "representante_legal": "nombre_representante",
            "cedula_representante":"numero_doc_representante",
            "direccion":           "direccion",
            "municipio":           "ciudad",
            "correo":              "correo",
            "telefono":            "telefono",
        },
        "cedula_representante": {
            "nombre":           "nombre_representante",
            "numero_documento": "numero_doc_representante",
            "tipo_documento":   "tipo_doc_representante",
            "fecha_nacimiento": "fecha_nacimiento",
            "lugar_nacimiento": "ciudad_nacimiento",
            "fecha_expedicion": "fecha_expedicion",
            "lugar_expedicion": "ciudad_expedicion",
        },
        "estados_financieros": {
            "total_activos": "total_activos",
            "total_pasivos": "total_pasivos",
            "patrimonio":    "patrimonio",
            "ingresos":      "ingresos_mensuales",
            "egresos":       "egresos_mensuales",
        },
    }

    @classmethod
    def mapear(
        cls,
        tipo_documento: str,
        datos_extraidos: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Mapea los datos extraídos de un documento a los campos del formulario.

        Solo incluye los campos con valor no nulo en el resultado.

        Args:
            tipo_documento:  Clave del tipo de documento (ej. "rut").
            datos_extraidos: Datos crudos extraídos por el extractor IA.

        Returns:
            Diccionario campo_formulario → valor, solo para campos presentes.
            Retorna {} si el tipo de documento no tiene mapeo configurado.
        """
        mapeo = cls._MAPEO_POR_TIPO.get(tipo_documento, {})
        return {
            campo_formulario: datos_extraidos[campo_doc]
            for campo_doc, campo_formulario in mapeo.items()
            if datos_extraidos.get(campo_doc) is not None
        }

    @classmethod
    def tipos_soportados(cls) -> List[str]:
        """
        Retorna la lista de tipos de documento con mapeo de pre-llenado configurado.

        Útil para validar o descubrir qué documentos generan sugerencias en el
        formulario sin necesidad de acceder a la estructura interna.

        Returns:
            Lista de claves de tipo de documento (ej. ["rut", "certificado_existencia", ...]).
        """
        return list(cls._MAPEO_POR_TIPO.keys())


# ─── Alias funcional (DRY: interfaz para código existente) ───────────────────

def mapear_campos_para_formulario(
    tipo_documento: str,
    datos_extraidos: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Interfaz funcional de MapeadorCamposFormulario.mapear.

    Permite llamar el mapeo sin instanciar ni referenciar la clase directamente.
    Usado por FormularioService y ExtractorBedrock.

    Args:
        tipo_documento:  Clave del tipo de documento procesado (ej. "rut").
        datos_extraidos: Datos crudos extraídos por el extractor IA.

    Returns:
        Diccionario campo_formulario → valor, solo para campos no nulos.
    """
    return MapeadorCamposFormulario.mapear(tipo_documento, datos_extraidos)
