from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_serializer, field_validator

from domain.formulario.tipos import EstadoFormulario, TipoContraparte, TipoPersona, TipoSolicitud
from domain.catalogo_correcciones import validar_campos_corregibles
from .formularios import AlertaInconsistenciaResponse

from .comunes import a_iso_utc


class ExpedienteResumen(BaseModel):
    """Vista compacta de un formulario enviado, para listados en el portal interno."""

    formulario_id: str
    codigo_peticion: str
    razon_social: Optional[str] = None
    numero_identificacion: Optional[str] = None
    tipo_contraparte: Optional[TipoContraparte] = None
    tipo_persona: Optional[TipoPersona] = None
    tipo_solicitud: Optional[TipoSolicitud] = None
    estado: EstadoFormulario
    modo_trabajo: Optional[str] = None
    numero_correccion: int = 0
    cantidad_documentos: int
    created_at: datetime
    updated_at: datetime

    @field_serializer("created_at", "updated_at", when_used="json")
    def _serializar_fechas(self, valor: datetime) -> str:
        return a_iso_utc(valor) or ""


class DocumentoResumen(BaseModel):
    """Metadatos mínimos de un documento adjunto para descarga desde el portal."""

    id: str
    tipo_documento: str
    nombre_archivo: str
    tamano: Optional[int] = None
    version_numero: int = 1
    version_anterior_id: Optional[str] = None
    subido_por: Optional[str] = None
    created_at: Optional[datetime] = None

    @field_serializer("created_at", when_used="json")
    def _serializar_created_at(self, valor: Optional[datetime]) -> Optional[str]:
        return a_iso_utc(valor) if valor else None


class ExpedienteDetalle(BaseModel):
    """
    Vista de detalle de un expediente para el portal interno.

    Expone únicamente los campos que la pantalla necesita.
    Los datos del formulario (financieros, tributarios, representante legal, etc.)
    no se incluyen — están disponibles exclusivamente en el PDF descargable.
    """

    formulario_id: str
    codigo_peticion: str
    razon_social: Optional[str] = None
    tipo_contraparte: Optional[TipoContraparte] = None
    tipo_persona: Optional[TipoPersona] = None
    tipo_solicitud: Optional[TipoSolicitud] = None
    estado: EstadoFormulario
    modo_trabajo: Optional[str] = None
    numero_correccion: int = 0
    campos_a_corregir: Optional[str] = None
    causal_cierre: Optional[str] = None
    sagrilaft_reporte_id: Optional[str] = None
    documento_firmado_disponible: bool = False
    updated_at: datetime
    documentos: List[DocumentoResumen] = Field(default_factory=list)
    alertas_inconsistencia: List[AlertaInconsistenciaResponse] = Field(default_factory=list)

    @field_serializer("updated_at", when_used="json")
    def _serializar_fecha(self, valor: datetime) -> str:
        return a_iso_utc(valor) or ""


class CambioCampoVersion(BaseModel):
    """Cambio detectado entre la versión anterior y la corregida."""

    campo: str
    etiqueta: str
    valor_anterior: str
    valor_corregido: str


class ComparacionVersionFormulario(BaseModel):
    """Comparación estructurada entre dos versiones consecutivas del formulario."""

    disponible: bool
    motivo: Optional[str] = None
    version_anterior: int
    version_corregida: int
    moneda_anterior: Optional[str] = None
    moneda_corregida: Optional[str] = None
    documento_anterior_id: Optional[str] = None
    documento_corregido_id: str
    total_cambios: int
    cambios: List[CambioCampoVersion] = Field(default_factory=list)
    campos_complejos: Dict[str, Dict[str, Any]] = Field(default_factory=dict)


class SolicitudDevolucion(BaseModel):
    """Datos requeridos para devolver un formulario al remitente para corrección."""

    especificaciones: str = Field(
        min_length=20,
        max_length=2000,
        description=(
            "Descripción exacta de qué información debe corregirse o completarse. "
            "Este texto se incluye en el correo enviado al destinatario."
        ),
    )
    campos_identificados: List[str] = Field(
        default_factory=list,
        description=(
            "IDs de los campos específicos del formulario que requieren corrección. "
            "Deben corresponder a identificadores del catálogo de campos del formulario."
        ),
    )

    @field_validator("campos_identificados")
    @classmethod
    def _validar_campos(cls, v: List[str]) -> List[str]:
        return validar_campos_corregibles(v)


class ResumenDevolucion(BaseModel):
    """Resultado de una operación de devolución de formulario."""

    estado:            str
    correo_notificado: Optional[str] = None
    correo_enviado:    bool = False


class SolicitudRechazo(BaseModel):
    """Datos requeridos para rechazar un formulario de forma definitiva."""

    motivo: str = Field(
        min_length=20,
        max_length=1000,
        description=(
            "Justificación interna del rechazo. Queda registrada en la auditoría "
            "y nunca se envía al destinatario."
        ),
    )
    mensaje_para_destinatario: Optional[str] = Field(
        default=None,
        min_length=10,
        max_length=500,
        description=(
            "Mensaje opcional que se envía por correo al destinatario. "
            "El operador lo redacta sin exponer el motivo interno de compliance. "
            "Si se omite, no se envía ninguna notificación."
        ),
    )

class SagrilaftConsultaManual(BaseModel):
    """Datos ingresados manualmente por el analista para consultar listas cautela."""
    tipo_identificacion: str
    numero_identificacion: str
    nombre_completo: str
    fecha_expedicion: Optional[str] = None


class ResumenRechazo(BaseModel):
    """Resultado de una operación de rechazo de formulario."""

    estado:               str
    motivo:               str
    notificacion_enviada: bool


class ResumenCierreExpediente(BaseModel):
    """Resultado de una operación de cierre de expediente."""

    estado: str
    causal_cierre: Optional[str] = None
    reporte_final_cargado: Optional[bool] = None
    version_numero: Optional[int] = None


class SolicitudReaperturaActualizacion(BaseModel):
    """Datos requeridos para reabrir un expediente cerrado por actualización."""

    justificacion: str = Field(
        min_length=20,
        max_length=1000,
        description="Justificación interna de la reapertura para auditoría.",
    )


class ResumenReaperturaActualizacion(BaseModel):
    """Resultado de una reapertura por actualización periódica."""

    estado: str
    modo_trabajo: str
    correo_notificado: Optional[str] = None
    correo_enviado: bool = False


class SolicitudReaperturaRevisionFirmado(BaseModel):
    """Datos requeridos para reabrir revisión de un documento ya firmado."""

    motivo: str = Field(
        min_length=20,
        max_length=1000,
        description=(
            "Justificación interna de la reapertura. No invalida la firma electrónica "
            "y queda registrada en auditoría."
        ),
    )

    @field_validator("motivo")
    @classmethod
    def _validar_motivo(cls, valor: str) -> str:
        motivo = valor.strip()
        if len(motivo) < 20:
            raise ValueError("El motivo debe tener al menos 20 caracteres.")
        return motivo


class ResumenReaperturaRevisionFirmado(BaseModel):
    """Resultado de reabrir revisión de un documento firmado."""

    estado: str
    documento_firmado_conservado: bool = True


class SolicitudAuditoriaAlerta(BaseModel):
    estado_auditoria: str = Field(
        description="Nuevo estado de la alerta: FALSO_POSITIVO_IA, RIESGO_ACEPTADO, PENDIENTE"
    )
