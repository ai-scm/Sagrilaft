"""
Validador de consistencia cruzada entre documentos.

Verifica que los datos clave (cédula, NIT, razón social, dirección) sean
coherentes entre los distintos documentos adjuntos al formulario.

SOLID:
- S (Responsabilidad Única): Esta clase solo valida cruces entre documentos.
- O (Abierto/Cerrado): Nuevas reglas se agregan en REGLAS_CRUCE_PREDETERMINADAS
  sin modificar la lógica de ValidadorCruzadoDocumentos.
- D (Inversión de Dependencias): Implementa IValidadorCruzado; el orquestador
  depende de la abstracción, no de esta clase concreta.

DRY: La lógica de comparación está centralizada en comparar_entre_documentos.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Literal, Optional

from services.alertas.normalizador_nit import normalizar_nit
from services.alertas.normalizador_nombre import normalizar_razon_social
from services.alertas.normalizador_numero_doc import normalizar_numero_doc
from core.contratos import HallazgoValidacion
from services.validators._utils import comparar_entre_documentos

# ─── Tipos de normalización disponibles ──────────────────────────────────────
# "texto"         → normalizar_razon_social (siglas, tildes, mayúsculas)
# "nit"           → normalizar_nit (solo dígitos, trunca dígito verificación)
# "identificacion"→ normalizar_numero_doc (alfanumérico, sin truncar — para cédulas)

TipoNormalizacion = Literal["texto", "nit", "identificacion"]

_NORMALIZADORES: Dict[str, Callable[[Any], str]] = {
    "texto":          normalizar_razon_social,
    "nit":            normalizar_nit,
    "identificacion": normalizar_numero_doc,
}


# ─── Objeto de valor: regla de cruce ─────────────────────────────────────────

@dataclass(frozen=True)
class ReglaCruce:
    """
    Define de forma declarativa una regla de consistencia entre dos campos
    pertenecientes a dos documentos distintos.

    Al ser un dataclass frozen, es inmutable y seguro para usar como constante.

    Attributes:
        campo:             Nombre del hallazgo generado (ej. "cruce_nit").
        doc_a:             Tipo de documento fuente A (ej. "rut").
        clave_a:           Campo dentro del documento A (ej. "nit").
        nombre_doc_a:      Nombre legible del documento A (ej. "el RUT").
        doc_b:             Tipo de documento fuente B (ej. "certificado_existencia").
        clave_b:           Campo dentro del documento B (ej. "nit").
        nombre_doc_b:      Nombre legible del documento B.
        descripcion:       Descripción del campo comparado (ej. "NIT").
        tipo_normalizacion: Estrategia de normalización: "texto" o "identificacion".
    """
    campo: str
    doc_a: str
    clave_a: str
    nombre_doc_a: str
    doc_b: str
    clave_b: str
    nombre_doc_b: str
    descripcion: str
    tipo_normalizacion: TipoNormalizacion = "texto"


# ─── Reglas predeterminadas del sistema ──────────────────────────────────────

REGLAS_CRUCE_PREDETERMINADAS: List[ReglaCruce] = [
    ReglaCruce(
        campo="cruce_cedula_vs_camara",
        doc_a="cedula_representante",
        clave_a="numero_documento",
        nombre_doc_a="la cédula",
        doc_b="certificado_existencia",
        clave_b="cedula_representante",
        nombre_doc_b="el Certificado de Existencia",
        descripcion="Cédula del representante",
        tipo_normalizacion="identificacion",
    ),
    ReglaCruce(
        campo="cruce_cedula_vs_rut",
        doc_a="cedula_representante",
        clave_a="numero_documento",
        nombre_doc_a="la cédula",
        doc_b="rut",
        clave_b="cedula_representante",
        nombre_doc_b="el RUT",
        descripcion="Cédula del representante",
        tipo_normalizacion="identificacion",
    ),
    ReglaCruce(
        campo="cruce_razon_social",
        doc_a="rut",
        clave_a="razon_social",
        nombre_doc_a="el RUT",
        doc_b="certificado_existencia",
        clave_b="razon_social",
        nombre_doc_b="el Certificado de Existencia",
        descripcion="Razón social",
        tipo_normalizacion="texto",
    ),
    ReglaCruce(
        campo="cruce_nit",
        doc_a="rut",
        clave_a="nit",
        nombre_doc_a="el RUT",
        doc_b="certificado_existencia",
        clave_b="nit",
        nombre_doc_b="el Certificado de Existencia",
        descripcion="NIT",
        tipo_normalizacion="nit",
    ),
    ReglaCruce(
        campo="cruce_direccion",
        doc_a="rut",
        clave_a="direccion",
        nombre_doc_a="el RUT",
        doc_b="certificado_existencia",
        clave_b="direccion",
        nombre_doc_b="el Certificado de Existencia",
        descripcion="Dirección",
        tipo_normalizacion="texto",
    ),
]


# ─── Validador cruzado ────────────────────────────────────────────────────────

class ValidadorCruzadoDocumentos:
    """
    Aplica un conjunto de reglas de cruce para verificar la consistencia
    de datos entre los documentos adjuntos al formulario.

    OCP: Nuevas reglas se inyectan en el constructor; la lógica de aplicación
    no cambia al agregar o quitar reglas.

    Implementa el protocolo IValidadorCruzado.
    """

    def __init__(self, reglas: List[ReglaCruce]) -> None:
        """
        Args:
            reglas: Lista de ReglaCruce a aplicar. Inyectar
                    REGLAS_CRUCE_PREDETERMINADAS para el comportamiento estándar.
        """
        self._reglas = reglas

    def validar_cruzado(
        self,
        extracciones: Dict[str, Dict[str, Any]],
    ) -> List[HallazgoValidacion]:
        """
        Aplica todas las reglas registradas sobre las extracciones disponibles.

        Args:
            extracciones: Mapa tipo_documento → datos extraídos por IA.

        Returns:
            Lista de hallazgos de consistencia (solo los que tienen ambos valores).
        """
        hallazgos: List[HallazgoValidacion] = []
        for regla in self._reglas:
            hallazgo = self._aplicar_regla(regla, extracciones)
            if hallazgo:
                hallazgos.append(hallazgo)
        return hallazgos

    def _aplicar_regla(
        self,
        regla: ReglaCruce,
        extracciones: Dict[str, Dict[str, Any]],
    ) -> Optional[HallazgoValidacion]:
        """Extrae los valores de ambos documentos y delega la comparación."""
        datos_a = extracciones.get(regla.doc_a) or {}
        datos_b = extracciones.get(regla.doc_b) or {}
        normalizador = _NORMALIZADORES[regla.tipo_normalizacion]
        return comparar_entre_documentos(
            valor_a=datos_a.get(regla.clave_a),
            valor_b=datos_b.get(regla.clave_b),
            campo=regla.campo,
            descripcion=regla.descripcion,
            nombre_doc_a=regla.nombre_doc_a,
            nombre_doc_b=regla.nombre_doc_b,
            normalizador=normalizador,
        )
