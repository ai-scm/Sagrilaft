"""
Schemas HTTP (Pydantic) expuestos por la API.

Objetivo: centralizar modelos de transporte sin concentrarlos en un único archivo.
Los módulos están nombrados con intención y organizados por contexto.
"""

from .acceso_manual import (
    AccesoManualCreado,
    AccesoManualResumen,
    ActualizarCorreoAcceso,
    CredencialesAccesoManual,
    EstadoCorreoAcceso,
    SolicitudAccesoManual,
)
from .documentos import AlertaInconsistenciaResponse, DocumentoResponse
from .comunes import FechaServidorResponse
from .formularios import (
    Accionista,
    BeneficiarioFinal,
    CredencialesEnvioFormulario,
    EntidadConParticipacion,
    FormularioBase,
    FormularioConDetalles,
    FormularioCreate,
    FormularioResponse,
    FormularioUpdate,
    InformacionBancariaPago,
    MiembroJunta,
    PersonaVinculadaBase,
    ReferenciaBancaria,
    ReferenciaComercial,
    ResultadoValidacionEnvio,
    SolicitudEnvioFormulario,
)
from .expedientes import (
    ComparacionVersionFormulario,
    ExpedienteDetalle,
    ExpedienteResumen,
    ResumenCierreExpediente,
    ResumenDevolucion,
    ResumenReaperturaActualizacion,
    ResumenReaperturaRevisionFirmado,
    ResumenRechazo,
    SolicitudDevolucion,
    SolicitudReaperturaActualizacion,
    SolicitudReaperturaRevisionFirmado,
    SolicitudRechazo,
    SolicitudAuditoriaAlerta,
    SagrilaftConsultaManual,
)
from .listas_cautela import BusquedaListaCautela, RespuestaListaCautela, ResultadoListaCautela
from .validaciones import ValidacionResponse
from .webhooks import ZohoWebhookPayload

__all__ = [
    # Acceso manual
    "AccesoManualCreado",
    "AccesoManualResumen",
    "ActualizarCorreoAcceso",
    "CredencialesAccesoManual",
    "EstadoCorreoAcceso",
    "SolicitudAccesoManual",
    # Documentos
    "AlertaInconsistenciaResponse",
    "DocumentoResponse",
    "FechaServidorResponse",
    # Formularios
    "Accionista",
    "BeneficiarioFinal",
    "CredencialesEnvioFormulario",
    "EntidadConParticipacion",
    "FormularioBase",
    "FormularioConDetalles",
    "FormularioCreate",
    "FormularioResponse",
    "FormularioUpdate",
    "InformacionBancariaPago",
    "MiembroJunta",
    "PersonaVinculadaBase",
    "ReferenciaBancaria",
    "ReferenciaComercial",
    "ResultadoValidacionEnvio",
    "SolicitudEnvioFormulario",
    # Expedientes
    "ExpedienteDetalle",
    "ExpedienteResumen",
    "ComparacionVersionFormulario",
    "ResumenCierreExpediente",
    "ResumenDevolucion",
    "ResumenReaperturaActualizacion",
    "ResumenReaperturaRevisionFirmado",
    "ResumenRechazo",
    "SolicitudDevolucion",
    "SolicitudReaperturaActualizacion",
    "SolicitudReaperturaRevisionFirmado",
    "SolicitudRechazo",
    "SolicitudAuditoriaAlerta",
    "SagrilaftConsultaManual",
    # Listas de cautela
    "BusquedaListaCautela",
    "RespuestaListaCautela",
    "ResultadoListaCautela",
    # Validaciones
    "ValidacionResponse",
    # Webhooks
    "ZohoWebhookPayload",
]
