"""
Adaptador SQLAlchemy del repositorio de auditoría.

Implementa RepositorioAuditoria usando la sesión compartida del request.
Nunca lanza excepciones en registrar_evento — un fallo de auditoría no debe
interrumpir la operación de negocio que lo originó.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import func, text
from sqlalchemy.orm import Session

from domain.auditoria.entidades import EventoAuditoria
from infrastructure.persistencia.models import (
    DocumentoAdjunto,
    EventoFormulario,
    Formulario,
)

logger = logging.getLogger(__name__)

# Umbral para considerar un formulario "estancado" (días sin cambio de estado)
_DIAS_ESTANCADO = 15


def _orm_a_evento(orm: EventoFormulario) -> EventoAuditoria:
    metadata = None
    if orm.metadata_json:
        try:
            metadata = json.loads(orm.metadata_json)
        except (json.JSONDecodeError, TypeError):
            pass
    return EventoAuditoria(
        id=orm.id,
        formulario_id=orm.formulario_id,
        tipo_evento=orm.tipo_evento,
        estado_anterior=orm.estado_anterior,
        estado_nuevo=orm.estado_nuevo,
        actor_id=orm.actor_id,
        actor_tipo=orm.actor_tipo,
        metadata=metadata,
        created_at=orm.created_at,
    )


class RepositorioAuditoriaSQLAlchemy:
    """Adaptador de persistencia para el log de auditoría."""

    def __init__(self, sesion: Session) -> None:
        self._sesion = sesion

    # ─── Escritura ────────────────────────────────────────────────────────────

    def registrar_evento(self, evento: EventoAuditoria) -> None:
        """Inserta un evento en el log de auditoría. Silencia errores para no interrumpir el flujo."""
        try:
            metadata_json = json.dumps(evento.metadata, ensure_ascii=False) if evento.metadata else None
            orm = EventoFormulario(
                formulario_id=evento.formulario_id,
                tipo_evento=evento.tipo_evento,
                estado_anterior=evento.estado_anterior,
                estado_nuevo=evento.estado_nuevo,
                actor_id=evento.actor_id,
                actor_tipo=evento.actor_tipo,
                metadata_json=metadata_json,
            )
            self._sesion.add(orm)
            # No hacemos commit aquí — lo hace el caller en la misma transacción
        except Exception:
            logger.exception(
                "Error al registrar evento de auditoría tipo=%s formulario=%s",
                evento.tipo_evento, evento.formulario_id,
            )

    # ─── Lectura ──────────────────────────────────────────────────────────────

    def listar_eventos(self, formulario_id: str) -> List[EventoAuditoria]:
        orms = (
            self._sesion.query(EventoFormulario)
            .filter(EventoFormulario.formulario_id == formulario_id)
            .order_by(EventoFormulario.created_at.asc())
            .all()
        )
        return [_orm_a_evento(o) for o in orms]

    # ─── Métricas operativas ──────────────────────────────────────────────────

    def metricas_dashboard(self) -> Dict[str, Any]:
        """
        Métricas en tiempo real del estado operativo de expedientes.

        Usa una sola consulta por grupo lógico para mantener el impacto en BD mínimo.
        """
        from domain.formulario.tipos import EstadoFormulario

        estados_activos = [
            EstadoFormulario.ENVIADO.value,
            EstadoFormulario.EN_CORRECCION.value,
            EstadoFormulario.VALIDADO.value,
            EstadoFormulario.RECHAZADO.value,
            EstadoFormulario.PENDIENTE_FIRMA.value,
            EstadoFormulario.FIRMADO.value,
        ]

        # ── Conteo por estado ─────────────────────────────────────────────────
        filas_estado = (
            self._sesion.query(Formulario.estado, func.count(Formulario.id))
            .filter(Formulario.estado.in_(estados_activos))
            .group_by(Formulario.estado)
            .all()
        )
        por_estado = {estado: conteo for estado, conteo in filas_estado}

        # ── Expedientes estancados (sin cambio de estado en > N días) ─────────
        umbral_sql = text(
            "NOW() - INTERVAL ':dias days'"
        )
        ahora = datetime.now(timezone.utc)
        formularios_activos = (
            self._sesion.query(Formulario)
            .filter(Formulario.estado.in_([
                EstadoFormulario.ENVIADO.value,
                EstadoFormulario.EN_CORRECCION.value,
                EstadoFormulario.VALIDADO.value,
                EstadoFormulario.PENDIENTE_FIRMA.value,
            ]))
            .all()
        )

        # El updated_at cambia en cualquier UPDATE, no solo en estado.
        # Usamos el último evento registrado para mayor precisión.
        estancados = []
        for f in formularios_activos:
            ultimo_evento = (
                self._sesion.query(EventoFormulario)
                .filter(EventoFormulario.formulario_id == f.id)
                .order_by(EventoFormulario.created_at.desc())
                .first()
            )
            referencia = (ultimo_evento.created_at if ultimo_evento else f.updated_at) or f.created_at
            if referencia and referencia.tzinfo is None:
                referencia = referencia.replace(tzinfo=timezone.utc)
            dias_sin_cambio = (ahora - referencia).days if referencia else 0
            if dias_sin_cambio >= _DIAS_ESTANCADO:
                estancados.append({
                    "formulario_id":   f.id,
                    "codigo_peticion": f.codigo_peticion,
                    "razon_social":    f.razon_social,
                    "estado":          f.estado,
                    "dias_sin_cambio": dias_sin_cambio,
                })

        estancados.sort(key=lambda x: x["dias_sin_cambio"], reverse=True)

        # ── Tiempo promedio entre eventos de transición por estado destino ─────
        # Para cada estado, calculamos el promedio de días que los formularios
        # tardaron en llegar a ese estado desde su evento anterior.
        tiempo_por_estado: Dict[str, Optional[float]] = {}
        for estado in estados_activos:
            pares = (
                self._sesion.query(
                    EventoFormulario.created_at,
                )
                .filter(
                    EventoFormulario.estado_nuevo == estado,
                    EventoFormulario.actor_tipo != "DB_DIRECTO",
                )
                .all()
            )
            if pares:
                # Promedio desde created_at del formulario hasta este evento
                # (simplificado — suficiente para un dashboard operativo)
                tiempo_por_estado[estado] = None  # calculado más abajo via SQL
            else:
                tiempo_por_estado[estado] = None

        # Consulta simplificada: días promedio desde creación del formulario hasta llegar a estado
        for estado in estados_activos:
            fila = (
                self._sesion.query(
                    func.avg(
                        func.extract(
                            "epoch",
                            EventoFormulario.created_at - Formulario.created_at,
                        ) / 86400.0
                    )
                )
                .join(Formulario, Formulario.id == EventoFormulario.formulario_id)
                .filter(
                    EventoFormulario.estado_nuevo == estado,
                    EventoFormulario.actor_tipo != "DB_DIRECTO",
                )
                .first()
            )
            if fila and fila[0] is not None:
                tiempo_por_estado[estado] = round(float(fila[0]), 1)

        return {
            "por_estado":                por_estado,
            "formularios_estancados":    estancados,
            "tiempo_promedio_por_estado": tiempo_por_estado,
            "total_expedientes":         sum(por_estado.values()),
            "dias_umbral_estancado":     _DIAS_ESTANCADO,
        }

    # ─── Documentos con trazabilidad ─────────────────────────────────────────

    def listar_documentos_con_trazabilidad(
        self, formulario_id: str
    ) -> List[Dict[str, Any]]:
        """Documentos activos del formulario con campos de trazabilidad."""
        orms = (
            self._sesion.query(DocumentoAdjunto)
            .filter(
                DocumentoAdjunto.formulario_id == formulario_id,
                DocumentoAdjunto.deleted_at.is_(None),
            )
            .order_by(DocumentoAdjunto.created_at.asc())
            .all()
        )
        return [
            {
                "id":                   o.id,
                "tipo_documento":       o.tipo_documento,
                "nombre_archivo":       o.nombre_archivo,
                "tamano":               o.tamano,
                "version_numero":       o.version_numero or 1,
                "subido_por":           o.subido_por,
                "hash_sha256":          o.hash_sha256,
                "created_at":           o.created_at,
            }
            for o in orms
        ]
