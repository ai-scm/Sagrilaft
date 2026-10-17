"""
DTOs (tipos de datos) compartidos del dominio.

Este paquete es una fachada: cada submódulo agrupa DTOs de un área
(documentos, validación, acceso, envío de formulario, firma, listas).
Todos los nombres se reexportan aquí para mantener compatibles las
importaciones existentes (`from domain.contratos import X`).

Los Protocols (interfaces de puertos) viven en `domain.puertos` —
ver `domain/puertos/extraccion_ia.py`, `validadores.py`,
`firma_externa.py` y `proveedor_lista_cautela.py`.
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
    "HallazgoValidacion",
    "RespuestaBusquedaLista",
    "ResultadoBusquedaLista",
    "ResultadoComparacion",
    "ResultadoCreacionAcceso",
    "ResultadoEnvioFormulario",
    "ResultadoExtraccion",
    "SolicitudCreacionAcceso",
    "SolicitudFirmaCreada",
]
