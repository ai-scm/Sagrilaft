"""
Protocolos (Interfaces) de dominio.

SOLID:
- I (Segregación de Interfaces): Protocolos pequeños y enfocados.
- D (Inversión de Dependencias): El código depende de estos protocolos,
  no de implementaciones concretas.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

from domain.contratos.documentos import ResultadoExtraccion
from domain.contratos.firma import SolicitudFirmaCreada
from domain.contratos.listas import ResultadoBusquedaLista
from domain.contratos.validacion import HallazgoValidacion


@runtime_checkable
class ExtractorIAImp(Protocol):
    """
    Interfaz para la extracción de datos desde documentos usando IA.

    Implementaciones:
        - ExtractorBedrock: AWS Bedrock / Claude.
    """

    async def extraer(
        self,
        ruta_archivo: str,
        tipo_documento: str,
    ) -> ResultadoExtraccion:
        """Extrae datos estructurados de un archivo usando IA."""
        ...


@runtime_checkable
class ValidadorDocumentoImp(Protocol):
    """
    Interfaz para validadores de documentos específicos.

    Cada tipo de documento (Cámara de Comercio, RUT, etc.) tiene
    su propio validador que implementa este Protocolo.

    SOLID - S: Cada validador tiene una única responsabilidad.
    SOLID - L: Los subtipos son intercambiables sin romper el orquestador.
    """

    @property
    def tipo_documento(self) -> str:
        """Tipo de documento que valida (ej: 'certificado_existencia')."""
        ...

    def validar(
        self,
        datos_extraidos: ResultadoExtraccion,
        datos_formulario: Dict[str, Any],
    ) -> List[HallazgoValidacion]:
        """Compara datos extraídos del documento contra datos del formulario."""
        ...


@runtime_checkable
class ValidadorCruzadoImp(Protocol):
    """
    Interfaz para la validación de consistencia entre documentos.

    SOLID - S: Responsabilidad única: verificar coherencia entre documentos.
    SOLID - I: Interfaz mínima y enfocada, separada de ValidadorDocumentoImp.
    SOLID - D: El orquestador depende de esta abstracción, no de implementaciones.
    """

    def validar_cruzado(
        self,
        extracciones: Dict[str, Dict[str, Any]],
    ) -> List[HallazgoValidacion]:
        """Verifica la consistencia de datos entre los documentos adjuntos."""
        ...


@runtime_checkable
class IServicioFirmaExterna(Protocol):
    """
    Puerto para servicios externos de firma electrónica (ZohoSign, DocuSign, etc.).

    DIP: FirmaService depende de esta abstracción, no de ZohoSignService concreto.
    OCP: cambiar de proveedor solo requiere implementar este Protocol.
    """

    def crear_solicitud_firma_multiple(
        self,
        pdf_paths: List[Any],
        nombre_documento: str,
        correo_firmante: str,
        nombre_firmante: str,
    ) -> SolicitudFirmaCreada:
        """Envía uno o más PDFs al proveedor y crea la solicitud de firma."""
        ...

    def descargar_documento_firmado(self, request_id: str, destino: Any) -> Any:
        """Descarga el documento firmado a la ruta de destino y devuelve la ruta real."""
        ...

    def cancelar_solicitud_firma(self, request_id: str, motivo: Optional[str] = None) -> None:
        """Cancela una solicitud de firma activa."""
        ...

    def obtener_estado_solicitud(self, request_id: str) -> str:
        """Consulta el estado actual de una solicitud en el proveedor externo."""
        ...


@runtime_checkable
class ProveedorListaCautelaImp(Protocol):
    """
    Puerto para proveedores de listas de cautela (OFAC, ONU, Procuraduría, etc.).

    OCP: agregar una lista nueva solo requiere implementar este Protocol.
    DIP: ListaCautelaService depende de esta abstracción, no de implementaciones.
    """

    nombre: str

    def buscar(
        self,
        nombre: str,
        numero_identificacion: Optional[str] = None,
    ) -> ResultadoBusquedaLista:
        """Busca un nombre e identificación en esta lista de cautela."""
        ...
