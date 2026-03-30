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

import re
from typing import Any, Callable, Dict, List, Optional


# ═══════════════════════════════════════════════════════════════
# Normalizadores de valor (OCP: agregar aquí sin tocar el motor)
# ═══════════════════════════════════════════════════════════════

def _normalizar_tipo_persona(valor: Any) -> Optional[str]:
    """
    Normaliza el campo "Tipo de Persona" a los valores que usa el select del formulario:
    "juridica" o "natural".

    Aplica a RUT (sección 24) y Certificado de Existencia.
    """
    if valor is None:
        return None

    texto = re.sub(r'\s+', ' ', str(valor)).strip().upper()

    if 'JURIDICA' in texto or 'JURÍDICA' in texto:
        return 'juridica'
    if 'NATURAL' in texto:
        return 'natural'

    return None


def _normalizar_tipo_identificacion(valor: Any) -> Optional[str]:
    """
    Convierte cualquier variación textual del tipo de identificación
    al código canónico que usa el formulario: NIT | CC | CE | PAS.

    Capa de seguridad frente a respuestas inesperadas del modelo IA.
    El prompt ya solicita valores normalizados; esta función es el
    fallback robusto para variaciones ortográficas o de idioma.
    """
    if valor is None:
        return None

    texto = re.sub(r'[.\s\-]', '', str(valor)).upper()

    _TABLA_NORMALIZACION: Dict[str, str] = {
        # NIT y variaciones
        'NIT':                               'NIT',
        'NUMERODEIDENTIFICACIONTRIBUTARIA':  'NIT',
        'NROTRIBUTARIO':                     'NIT',
        # Cédula de Ciudadanía
        'CC':                                'CC',
        'CEDULADECIUDADANIA':                'CC',
        'CÉDULADECIUDADANÍA':                'CC',
        'CEDULA':                            'CC',
        'CÉDULA':                            'CC',
        # Cédula de Extranjería
        'CE':                                'CE',
        'CEDULADEEXTRANJERIA':               'CE',
        'CÉDULADEEXTRANJERÍIA':              'CE',
        'CEDULAEXTRANJERIA':                 'CE',
        'EXTRANJERIA':                       'CE',
        # Pasaporte
        'PAS':                               'PAS',
        'PASAPORTE':                         'PAS',
        'PASSPORT':                          'PAS',
    }

    return _TABLA_NORMALIZACION.get(texto)


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
            "tipo_persona": "tipo_persona",
            "direccion":    "direccion",
            "correo":       "correo",
            "telefono":     "telefono",
            "codigo_ica":   "codigo_ica",
        },
        "certificado_existencia": {
            "razon_social":        "razon_social",
            "tipo_persona":        "tipo_persona",
            "tipo_identificacion": "tipo_identificacion",
            "nit":                 "numero_identificacion",
            "representante_legal": "nombre_representante",
            "cedula_representante":"numero_doc_representante",
            "termino_duracion":    "termino_duracion",
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

    # Transformaciones de valor por (tipo_documento, campo_formulario).
    # OCP: agregar una nueva transformación sin modificar el motor de mapeo.
    _TRANSFORMACIONES: Dict[str, Dict[str, Callable[[Any], Any]]] = {
        "rut": {
            "tipo_persona": _normalizar_tipo_persona,
        },
        "certificado_existencia": {
            "tipo_persona":        _normalizar_tipo_persona,
            "tipo_identificacion": _normalizar_tipo_identificacion,
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

        Aplica transformaciones de valor cuando están configuradas en
        _TRANSFORMACIONES (ej. normalización de tipo_identificacion).
        Solo incluye los campos con valor no nulo tras la transformación.

        Args:
            tipo_documento:  Clave del tipo de documento (ej. "rut").
            datos_extraidos: Datos crudos extraídos por el extractor IA.

        Returns:
            Diccionario campo_formulario → valor, solo para campos presentes.
            Retorna {} si el tipo de documento no tiene mapeo configurado.
        """
        mapeo = cls._MAPEO_POR_TIPO.get(tipo_documento, {})
        transformaciones = cls._TRANSFORMACIONES.get(tipo_documento, {})
        resultado = {}

        for campo_doc, campo_formulario in mapeo.items():
            valor = datos_extraidos.get(campo_doc)
            if valor is None:
                continue
            transformar = transformaciones.get(campo_formulario)
            if transformar:
                valor = transformar(valor)
            if valor is not None:
                resultado[campo_formulario] = valor

        return resultado

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
