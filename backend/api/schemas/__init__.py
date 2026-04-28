"""
Schemas HTTP (Pydantic) expuestos por la API.

Objetivo: centralizar modelos de transporte sin concentrarlos en un único archivo.
Los módulos están nombrados con intención y organizados por contexto.
"""

from .acceso_manual import (
    AccesoManualCreado,
    AccesoManualResumen,
    CredencialesAccesoManual,
    SolicitudAccesoManual,
)
from .documentos import AlertaInconsistenciaResponse, DocumentoResponse
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
)
from .listas_cautela import BusquedaListaCautela, RespuestaListaCautela, ResultadoListaCautela
from .validaciones import ValidacionResponse

__all__ = [
    # Acceso manual
    "AccesoManualCreado",
    "AccesoManualResumen",
    "CredencialesAccesoManual",
    "SolicitudAccesoManual",
    # Documentos
    "AlertaInconsistenciaResponse",
    "DocumentoResponse",
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
    # Listas de cautela
    "BusquedaListaCautela",
    "RespuestaListaCautela",
    "ResultadoListaCautela",
    # Validaciones
    "ValidacionResponse",
]

