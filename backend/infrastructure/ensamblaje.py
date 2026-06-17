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

from infrastructure.configuracion import AppConfig
from infrastructure.ia.bedrock_extractor import ExtractorBedrock
from domain.contratos import ProveedorListaCautelaImp
from services.listas.proveedores_simulados import PROVEEDORES_SIMULADOS
from services.listas.servicio_listas_cautela import ListaCautelaService
from services.validacion.orquestador import OrquestadorValidacionDocumentos
from services.validacion.validadores.camara_comercio import ValidadorCamaraComercio
from services.validacion.validadores.cedula import ValidadorCedula
from services.validacion.validadores.cruzado import ValidadorCruzadoDocumentos, REGLAS_CRUCE_PREDETERMINADAS
from services.validacion.validadores.estados_financieros import ValidadorEstadosFinancieros
from services.validacion.validadores.referencia_bancaria import ValidadorReferenciaBancaria
from services.validacion.validadores.rut import ValidadorRut

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


def crear_alertas_portal(config: AppConfig):
    """
    Fábrica: crea el adaptador de alertas (SES preferido, SNS fallback).

    Prioridad:
      1. SES si está configurado (recomendado: control total sobre MIME headers)
      2. SNS si está configurado (legacy)
      3. None si ninguno está disponible

    Retorna None en lugar de lanzar excepción para no bloquear el arranque
    en entornos sin alertas (desarrollo local, staging sin credenciales).
    
    Parámetros:
        config: Configuración de la aplicación (incluye URL del portal interno)
    """
    # Preferencia 1: SES (control total sobre Content-Type)
    if config.ses.configurado:
        from infrastructure.notificaciones.ses_alertas import SesAlertasPortal
        alertas = SesAlertasPortal(
            ses_config=config.ses,
            aws_config=config.aws,
            url_portal_interno=config.portal_interno_url,
        )
        logger.info(
            "Alertas SES habilitadas (origen=%s, portal_url=%s)",
            config.ses.email_origen,
            config.portal_interno_url,
        )
        return alertas

    # Preferencia 2: SNS (legacy, se convierte a plaintext)
    if config.sns.configurado:
        from infrastructure.notificaciones.sns_alertas import SnsAlertasPortal
        alertas = SnsAlertasPortal(
            sns_config=config.sns,
            aws_config=config.aws,
            url_portal_interno=config.portal_interno_url,
        )
        logger.info(
            "Alertas SNS habilitadas (topic=%s, portal_url=%s)",
            config.sns.topic_arn,
            config.portal_interno_url,
        )
        return alertas

    # Fallback: ninguno configurado
    logger.info("Alertas al portal deshabilitadas (SES y SNS no configurados).")
    return None


def crear_servicio_listas_cautela(
    proveedores: Optional[List[ProveedorListaCautelaImp]] = None,
) -> ListaCautelaService:
    """
    Construye el servicio de listas de cautela con los proveedores disponibles.

    En este proyecto los proveedores son simulados por defecto; en producción
    se reemplazan por implementaciones reales.
    """
    return ListaCautelaService(proveedores=proveedores or PROVEEDORES_SIMULADOS)
