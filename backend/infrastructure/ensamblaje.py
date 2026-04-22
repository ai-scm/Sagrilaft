"""
Ensamblaje de la aplicación (wiring / composition).

Responsabilidad:
- Construir y conectar adaptadores e implementaciones concretas.
- Registrar validadores y dependencias técnicas.

Nota: este módulo NO contiene lógica de negocio; solo composición.
"""

from __future__ import annotations

import logging
from typing import List, Optional

from core.configuracion import AppConfig
from services.extractores.bedrock_extractor import ExtractorBedrock
from services.listas.protocolo_listas import ProveedorListaCautelaImp
from services.listas.proveedores_simulados import PROVEEDORES_SIMULADOS
from services.listas.servicio_listas_cautela import ListaCautelaService
from services.orquestacion.orquestador_documentos import OrquestadorValidacionDocumentos
from services.validators.camara_comercio import ValidadorCamaraComercio
from services.validators.cedula import ValidadorCedula
from services.validators.cruzado import ValidadorCruzadoDocumentos, REGLAS_CRUCE_PREDETERMINADAS
from services.validators.estados_financieros import ValidadorEstadosFinancieros
from services.validators.referencia_bancaria import ValidadorReferenciaBancaria
from services.validators.rut import ValidadorRut

logger = logging.getLogger(__name__)


def crear_extractor_ia(config: AppConfig) -> ExtractorBedrock:
    """Fábrica: crea el extractor IA Bedrock con la configuración proporcionada."""
    logger.info(
        "Usando extractor Bedrock (región=%s, modelo=%s)",
        config.aws.region, config.aws.model_id,
    )
    return ExtractorBedrock(
        region=config.aws.region,
        modelo_id=config.aws.model_id,
        max_tokens=config.aws.max_tokens,
    )


def crear_orquestador_validacion(config: AppConfig) -> OrquestadorValidacionDocumentos:
    """Fábrica: crea y configura el orquestador con todos los validadores."""
    extractor = crear_extractor_ia(config)
    validador_cruzado = ValidadorCruzadoDocumentos(REGLAS_CRUCE_PREDETERMINADAS)
    orquestador = OrquestadorValidacionDocumentos(extractor, validador_cruzado)

    # Registrar validadores (OCP: agregar nuevos aquí sin tocar más código)
    orquestador.registrar_validador(ValidadorCamaraComercio())
    orquestador.registrar_validador(ValidadorRut())
    orquestador.registrar_validador(ValidadorEstadosFinancieros())
    orquestador.registrar_validador(ValidadorCedula())
    orquestador.registrar_validador(ValidadorReferenciaBancaria())

    logger.info("Validadores registrados: %s", ", ".join(orquestador.tipos_registrados))
    return orquestador


def crear_servicio_listas_cautela(
    proveedores: Optional[List[ProveedorListaCautelaImp]] = None,
) -> ListaCautelaService:
    """
    Construye el servicio de listas de cautela con los proveedores disponibles.

    En este proyecto los proveedores son simulados por defecto; en producción
    se reemplazan por implementaciones reales.
    """
    return ListaCautelaService(proveedores=proveedores or PROVEEDORES_SIMULADOS)
