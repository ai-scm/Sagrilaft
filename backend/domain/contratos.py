"""
Contratos (Protocolos) y tipos de datos compartidos.
Definen las interfaces que deben cumplir extractores y validadores.

SOLID:
- I (Segregación de Interfaces): Protocolos pequeños y enfocados.
- D (Inversión de Dependencias): El código depende de estos protocolos,
  no de implementaciones concretas.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable


# ═══════════════════════════════════════════════════════════════
# Entidades y Value Objects de Dominio
# ═══════════════════════════════════════════════════════════════

@dataclass
class DocumentoDatos:
    """
    Snapshot de un documento adjunto al formulario.

    Entidad de dominio libre de SQLAlchemy — reemplaza DocumentoAdjunto ORM
    en la capa de aplicación. Los repositorios realizan el mapping internamente.
    """
    id: str
    formulario_id: str
    tipo_documento: str
    nombre_archivo: str
    ruta_archivo: str
    content_type: Optional[str] = None
    tamano: Optional[int] = None
    deleted_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


@dataclass
class ResultadoExtraccion:
    """
    Resultado de la extracción IA de un documento.

    Attributes:
        extraido:   True si la extracción fue exitosa.
        datos:      Campos estructurados extraídos del documento.
        mensaje:    Descripción del resultado o del error ocurrido.
        confianza:  Nivel de confianza de la extracción (0.0 a 1.0).
    """
    extraido: bool
    datos: Dict[str, Any] = field(default_factory=dict)
    mensaje: str = ""
    confianza: float = 0.0


@dataclass
class HallazgoValidacion:
    """
    Un hallazgo individual de validación documental.

    Attributes:
        resultado:         Nivel del hallazgo: "ok", "error" o "advertencia".
        campo:             Campo del formulario al que aplica.
        detalle:           Descripción legible del hallazgo.
        valor_formulario:  Valor ingresado por el usuario (si aplica).
        valor_documento:   Valor extraído del documento (si aplica).
    """
    resultado: str          # "ok" | "error" | "advertencia"
    campo: str
    detalle: str
    valor_formulario: Optional[str] = None
    valor_documento: Optional[str] = None

    # ── Métodos de fábrica ── evitan repetir resultado="ok"|"error"|"advertencia" ──

    @classmethod
    def ok(
        cls,
        campo: str,
        detalle: str,
        valor_formulario: Optional[str] = None,
        valor_documento: Optional[str] = None,
    ) -> "HallazgoValidacion":
        return cls("ok", campo, detalle, valor_formulario, valor_documento)

    @classmethod
    def error(
        cls,
        campo: str,
        detalle: str,
        valor_formulario: Optional[str] = None,
        valor_documento: Optional[str] = None,
    ) -> "HallazgoValidacion":
        return cls("error", campo, detalle, valor_formulario, valor_documento)

    @classmethod
    def advertencia(
        cls,
        campo: str,
        detalle: str,
        valor_formulario: Optional[str] = None,
        valor_documento: Optional[str] = None,
    ) -> "HallazgoValidacion":
        return cls("advertencia", campo, detalle, valor_formulario, valor_documento)


@dataclass(frozen=True)
class ResultadoComparacion:
    """
    Resultado de comparar un campo del formulario contra el extraído de un documento.

    Value Object inmutable y genérico que reemplaza los cuatro dataclasses específicos
    anteriores (ResultadoComparacion, ResultadoComparacionNit, ResultadoComparacionNumeroDoc,
    ResultadoComparacionDireccion). Todos tenían los mismos cinco campos.

    OCP: agregar un nuevo tipo de comparación no requiere crear otro dataclass,
         solo instanciar Comparador con el normalizador correspondiente.
    """

    coincide: bool
    valor_formulario_original: str
    valor_documento_original: str
    valor_formulario_normalizado: str
    valor_documento_normalizado: str


@dataclass(frozen=True)
class AlertaInconsistencia:
    """
    Inconsistencia detectada entre un campo del formulario y un documento adjunto.

    Value Object inmutable y unificado para todos los tipos de alerta de campo.
    Reemplaza las 5 clases específicas anteriores (AlertaInconsistenciaNombre,
    AlertaInconsistenciaNit, etc.) con un único modelo agnóstico del campo.

    Lenguaje ubicuo:
        - tipo_documento:     clave del tipo de documento (ej. "certificado_existencia").
        - nombre_documento:   nombre legible del documento para mostrar al usuario.
        - seccion_referencia: ubicación exacta del campo dentro del documento.
        - valor_formulario:   valor ingresado por el usuario en el formulario.
        - valor_documento:    valor extraído del documento por la IA.
        - tipo_alerta:        gravedad: "error" | "advertencia".
        - mensaje:            descripción legible para el usuario final.

    OCP: agregar un nuevo tipo de alerta no requiere crear una nueva clase,
         solo instanciar AlertaInconsistencia con los valores correspondientes.
    """

    tipo_documento: str
    nombre_documento: str
    seccion_referencia: str
    valor_formulario: str
    valor_documento: str
    tipo_alerta: str   # "error" | "advertencia"
    mensaje: str


@dataclass
class AccesoManualDatos:
    """Snapshot completo de un AccesoManual — campos para firma y acceso."""
    id: str
    formulario_id: str
    razon_social: str
    correo_destinatario: str
    # Campos extendidos — default vacío para compatibilidad con usos parciales (FirmaService)
    tipo_contraparte: str = ""
    area_responsable: str = ""
    pin_hash: str = ""
    token_diligenciamiento: str = ""
    consumed_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    estado_formulario: str = ""
    codigo_peticion: str = ""


@dataclass
class SolicitudCreacionAcceso:
    """DTO de entrada para crear un acceso manual al formulario SAGRILAFT."""
    tipo_contraparte: str
    razon_social: str
    correo_destinatario: str
    area_responsable: str


@dataclass
class ResultadoCreacionAcceso:
    """Datos retornados tras crear formulario + acceso manual en un solo paso."""
    formulario_id: str
    codigo_peticion: str
    token_diligenciamiento: str
    correo_destinatario: str
    razon_social: str
    tipo_contraparte: str
    area_responsable: str
    created_at: datetime
    expires_at: datetime


@dataclass
class ErrorCampoFormulario:
    """Error de validación de un campo del formulario antes del envío."""
    campo: str
    mensaje: str


@dataclass
class ResultadoEnvioFormulario:
    """Resultado del intento de envío final de un formulario."""
    valido: bool
    errores: List["ErrorCampoFormulario"] = field(default_factory=list)


@dataclass
class SolicitudFirmaCreada:
    """Resultado de crear una solicitud de firma electrónica en un proveedor externo."""
    request_id: str


@dataclass
class ResultadoBusquedaLista:
    """Resultado de consultar un proveedor de listas de cautela."""
    lista: str
    encontrado: bool
    detalle: Optional[str] = None
    nivel_riesgo: Optional[str] = None  # "bajo" | "medio" | "alto"


@dataclass
class RespuestaBusquedaLista:
    """Respuesta consolidada de búsqueda en todas las listas de cautela."""
    nombre_buscado: str
    resultados: List[ResultadoBusquedaLista] = field(default_factory=list)
    riesgo_general: str = "bajo"  # "bajo" | "medio" | "alto"


# ═══════════════════════════════════════════════════════════════
# Protocolos (Interfaces)
# ═══════════════════════════════════════════════════════════════

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

    def cancelar_solicitud_firma(self, request_id: str) -> None:
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
