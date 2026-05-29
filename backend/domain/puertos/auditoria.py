"""
Puerto de repositorio para auditoría y trazabilidad.

Contrato que el adaptador SQLAlchemy debe cumplir. Sin referencias a ORM.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

from domain.auditoria.entidades import EventoAuditoria


@runtime_checkable
class RepositorioAuditoria(Protocol):
    """Puerto de persistencia para el log de eventos de auditoría."""

    def registrar_evento(self, evento: EventoAuditoria) -> None:
        """Inserta un nuevo evento en el log (append-only). Nunca lanza si falla — loguea."""
        ...

    def listar_eventos(self, formulario_id: str) -> List[EventoAuditoria]:
        """Devuelve todos los eventos de un formulario, ordenados por created_at ASC."""
        ...

    def metricas_dashboard(self) -> Dict[str, Any]:
        """
        Calcula métricas operativas en tiempo real desde eventos_formulario y formularios.

        Retorna:
          por_estado: dict[estado, count]
          formularios_estancados: lista de {formulario_id, razon_social, estado, dias_sin_cambio}
          tiempo_promedio_por_estado: dict[estado, dias_promedio_float]
          total_expedientes: int
        """
        ...

    def listar_documentos_con_trazabilidad(
        self, formulario_id: str
    ) -> List[Dict[str, Any]]:
        """Documentos del formulario con hash y versión para reporte de auditoría."""
        ...
