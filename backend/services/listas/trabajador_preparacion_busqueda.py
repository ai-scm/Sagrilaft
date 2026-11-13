"""Prepara la generación de búsqueda de cada versión ACTIVA que aún no la tiene.

No aprueba ni activa nada: solo deriva datos de una versión que una persona ya activó.
Es idempotente (``preparar`` reutiliza una generación íntegra) y recuperable (una caída
revierte la transacción completa y el siguiente ciclo repite desde cero).
"""
import logging
import time
from datetime import datetime, timezone

from sqlalchemy import select

from domain.listas.errores import ConflictoListas, ErrorIntegridadEvidencia
from infrastructure.listas.adaptadores_archivos import fuentes_habilitadas
from infrastructure.listas.adaptadores_busqueda import obtener_lector
from infrastructure.listas.representacion_busqueda import NORMALIZACION_BUSQUEDA
from infrastructure.persistencia.modelos_busqueda_listas import GeneracionBusqueda
from infrastructure.persistencia.modelos_listas import FuenteLista, FuenteVersionActiva, IntentoImportacion, VersionFuente
from infrastructure.persistencia.repositorios.busqueda_listas import RepositorioBusquedaListas
from services.listas.autorizacion_administrativa import exigir_entorno_sintetico
from services.listas.motor_busqueda import CATALOGO_MOTOR
from services.listas.politica_v2 import ActorListas

registro = logging.getLogger(__name__)

# Identidad técnica interna: solo puede "comparar" (derivar datos); no aprueba ni activa.
ACTOR_PREPARACION = ActorListas("servicio-local", "preparador-busqueda-v2", frozenset({"listas.comparar"}))
ESPERA_TRAS_FALLO = 300  # segundos antes de reintentar una versión que falló


class TrabajadorPreparacionBusqueda:
    def __init__(self, sesiones, custodia, politica, entorno, habilitado=False, reloj=time.monotonic,
                 catalogo=CATALOGO_MOTOR):
        exigir_entorno_sintetico(entorno)
        if not habilitado:
            raise PermissionError("Administración deshabilitada")
        self.sesiones, self.reloj, self.catalogo = sesiones, reloj, catalogo
        self.repositorio = RepositorioBusquedaListas(sesiones, custodia, politica, catalogo)
        self._reintentar_despues = {}

    def _pendiente(self):
        """Primera versión activa, de una fuente habilitada, sin generación para la receta vigente."""
        with self.sesiones.begin() as sesion:
            if sesion.scalar(select(IntentoImportacion.id).where(
                    IntentoImportacion.estado == "EN_CURSO",
                    IntentoImportacion.concesion_hasta > datetime.now(timezone.utc)).limit(1)):
                return None
            filas = sesion.execute(select(VersionFuente.id, VersionFuente.formato)
                .join(FuenteVersionActiva, FuenteVersionActiva.version_id == VersionFuente.id)
                .join(FuenteLista, FuenteLista.id == VersionFuente.fuente_id)
                .where(VersionFuente.estado == "VALIDA", FuenteLista.codigo.in_(fuentes_habilitadas()))
                .order_by(VersionFuente.id)).all()
            for version_id, formato in filas:
                if self._reintentar_despues.get(version_id, 0) > self.reloj():
                    continue
                if sesion.scalar(select(GeneracionBusqueda.id).where(
                        GeneracionBusqueda.version_id == version_id,
                        GeneracionBusqueda.estado == "LISTA",
                        GeneracionBusqueda.adaptador_version == obtener_lector(formato).VERSION_ADAPTADOR,
                        GeneracionBusqueda.normalizacion_version == NORMALIZACION_BUSQUEDA,
                        GeneracionBusqueda.catalogo_huella == self.catalogo.huella).limit(1)) is None:
                    return version_id
        return None

    def ejecutar_uno(self):
        version_id = self._pendiente()
        if version_id is None:
            return False
        inicio = self.reloj()
        try:
            generacion = self.repositorio.preparar(ACTOR_PREPARACION, version_id)
        except (ConflictoListas, ErrorIntegridadEvidencia, PermissionError) as error:
            # Solo clase y versión: nunca contenido de las listas.
            registro.warning("PREPARACION_BUSQUEDA_FALLIDA version=%s clase=%s", version_id, type(error).__name__)
            self._reintentar_despues[version_id] = self.reloj() + ESPERA_TRAS_FALLO
            return False
        self._reintentar_despues.pop(version_id, None)
        registro.info("PREPARACION_BUSQUEDA_LISTA version=%s generacion=%s segundos=%.1f",
                      version_id, generacion, self.reloj() - inicio)
        return True
