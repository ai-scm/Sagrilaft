"""
Contratos (Protocolos) y tipos de datos compartidos.
Definen las interfaces que deben cumplir extractores y validadores.

SOLID:
- I (Segregación de Interfaces): Protocolos pequeños y enfocados.
- D (Inversión de Dependencias): El código depende de estos protocolos,
  no de implementaciones concretas.

Este paquete es una fachada: cada submódulo agrupa DTOs de un área
(documentos, validación, acceso, envío de formulario, firma, listas)
y los Protocolos quedan en `protocolos.py`. Todos los nombres se
reexportan aquí para mantener compatibles las importaciones existentes
(`from domain.contratos import X`).
"""

from __future__ import annotations

from domain.contratos.acceso import (
    AccesoManualDatos,
    ResultadoCreacionAcceso,
    SolicitudCreacionAcceso,
)
from domain.contratos.documentos import DocumentoDatos, ResultadoExtraccion
from domain.contratos.envio_formulario import (
    ErrorCampoFormulario,
    ResultadoEnvioFormulario,
)
from domain.contratos.firma import SolicitudFirmaCreada
from domain.contratos.listas import RespuestaBusquedaLista, ResultadoBusquedaLista
from domain.contratos.protocolos import (
    ExtractorIAImp,
    IServicioFirmaExterna,
    ProveedorListaCautelaImp,
    ValidadorCruzadoImp,
    ValidadorDocumentoImp,
)
from domain.contratos.validacion import (
    AlertaInconsistencia,
    HallazgoValidacion,
    ResultadoComparacion,
)

__all__ = [
    "AccesoManualDatos",
    "AlertaInconsistencia",
    "DocumentoDatos",
    "ErrorCampoFormulario",
    "ExtractorIAImp",
    "HallazgoValidacion",
    "IServicioFirmaExterna",
    "ProveedorListaCautelaImp",
    "RespuestaBusquedaLista",
    "ResultadoBusquedaLista",
    "ResultadoComparacion",
    "ResultadoCreacionAcceso",
    "ResultadoEnvioFormulario",
    "ResultadoExtraccion",
    "SolicitudCreacionAcceso",
    "SolicitudFirmaCreada",
    "ValidadorCruzadoImp",
    "ValidadorDocumentoImp",
]
