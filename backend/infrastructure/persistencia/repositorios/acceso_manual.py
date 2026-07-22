"""Adaptador de persistencia para accesos manuales — usado por AccesoManualService."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session, joinedload

from domain.contratos import (
    AccesoManualDatos,
    ResultadoCreacionAcceso,
    SolicitudCreacionAcceso,
)
from domain.formulario.entidades import FormularioDatos
from infrastructure.persistencia.models import AccesoManual, Formulario

from ._mappers import _orm_acceso_manual_a_datos, _orm_formulario_a_datos


class RepositorioAccesoManualSQLAlchemy:
    """Adaptador de persistencia para accesos manuales — usado por AccesoManualService."""

    def __init__(self, sesion: Session) -> None:
        self._sesion = sesion

    def obtener_acceso_por_token(self, token: str) -> Optional[AccesoManualDatos]:
        orm = (
            self._sesion.query(AccesoManual)
            .options(joinedload(AccesoManual.formulario))
            .filter(AccesoManual.token_diligenciamiento == token)
            .first()
        )
        return _orm_acceso_manual_a_datos(orm, con_formulario=True) if orm else None

    def obtener_acceso_por_formulario_id(
        self, formulario_id: str, *, cargar_formulario: bool = False
    ) -> Optional[AccesoManualDatos]:
        consulta = self._sesion.query(AccesoManual).filter(
            AccesoManual.formulario_id == formulario_id
        )
        if cargar_formulario:
            consulta = consulta.options(joinedload(AccesoManual.formulario))
        orm = consulta.first()
        return _orm_acceso_manual_a_datos(orm, con_formulario=cargar_formulario) if orm else None

    def obtener_formulario_por_codigo(self, codigo_peticion: str) -> Optional[FormularioDatos]:
        """Carga relaciones para que construir_snapshot_formulario funcione correctamente."""
        orm = (
            self._sesion.query(Formulario)
            .options(
                joinedload(Formulario.documentos),
                joinedload(Formulario.validaciones),
            )
            .filter(Formulario.codigo_peticion == codigo_peticion)
            .first()
        )
        return _orm_formulario_a_datos(orm, cargar_relaciones=True) if orm else None

    def obtener_formulario_completo(self, formulario_id: str) -> Optional[FormularioDatos]:
        """Carga documentos y validaciones para construir el snapshot completo."""
        orm = (
            self._sesion.query(Formulario)
            .options(
                joinedload(Formulario.documentos),
                joinedload(Formulario.validaciones),
            )
            .filter(Formulario.id == formulario_id)
            .first()
        )
        return _orm_formulario_a_datos(orm, cargar_relaciones=True) if orm else None

    def listar_accesos(self) -> List[AccesoManualDatos]:
        orms = (
            self._sesion.query(AccesoManual)
            .options(joinedload(AccesoManual.formulario))
            .order_by(AccesoManual.created_at.desc())
            .all()
        )
        return [_orm_acceso_manual_a_datos(orm, con_formulario=True) for orm in orms]

    def crear_formulario_y_acceso(
        self,
        solicitud: SolicitudCreacionAcceso,
        pin_hash: str,
        token: str,
    ) -> ResultadoCreacionAcceso:
        """Crea el Formulario y el AccesoManual en una sola transacción."""
        formulario = Formulario(
            tipo_contraparte=solicitud.tipo_contraparte,
            razon_social=solicitud.razon_social,
        )
        self._sesion.add(formulario)
        self._sesion.flush()  # genera formulario.id antes del acceso

        acceso = AccesoManual(
            pin_hash=pin_hash,
            token_diligenciamiento=token,
            correo_destinatario=solicitud.correo_destinatario,
            razon_social=solicitud.razon_social,
            tipo_contraparte=solicitud.tipo_contraparte,
            area_responsable=solicitud.area_responsable,
            formulario_id=formulario.id,
        )
        self._sesion.add(acceso)
        self._sesion.commit()
        self._sesion.refresh(formulario)
        self._sesion.refresh(acceso)

        return ResultadoCreacionAcceso(
            formulario_id=formulario.id,
            codigo_peticion=formulario.codigo_peticion,
            token_diligenciamiento=acceso.token_diligenciamiento,
            correo_destinatario=acceso.correo_destinatario,
            razon_social=acceso.razon_social,
            tipo_contraparte=acceso.tipo_contraparte or "",
            area_responsable=acceso.area_responsable or "",
            created_at=acceso.created_at,
            expires_at=acceso.expires_at,
        )

    def marcar_consumido(self, acceso_id: str, timestamp: datetime) -> None:
        orm = self._sesion.query(AccesoManual).filter(AccesoManual.id == acceso_id).first()
        if orm:
            orm.consumed_at = timestamp
            self._sesion.commit()

    def reactivar_acceso(
        self, acceso_id: str, nuevo_token: str, nuevo_expires_at: datetime
    ) -> None:
        """Actualiza el acceso sin commit — el caller (ExpedienteService) maneja la transacción."""
        orm = self._sesion.query(AccesoManual).filter(AccesoManual.id == acceso_id).first()
        if orm:
            orm.token_diligenciamiento = nuevo_token
            orm.consumed_at = None
            orm.expires_at = nuevo_expires_at

    def actualizar_correo_por_token(self, token: str, correo: str) -> None:
        """Actualiza el correo_destinatario del acceso asociado a un token."""
        acceso = self._sesion.query(AccesoManual).filter(AccesoManual.token_diligenciamiento == token).first()
        if acceso:
            acceso.correo_destinatario = correo
            self._sesion.commit()

    def obtener_acceso_activo_por_correo(self, correo: str) -> Optional[AccesoManualDatos]:
        """Obtiene el acceso más reciente que no esté consumido ni expirado para un correo."""
        from datetime import datetime, timezone
        ahora = datetime.now(timezone.utc)
        orm = (
            self._sesion.query(AccesoManual)
            .options(joinedload(AccesoManual.formulario))
            .filter(
                AccesoManual.correo_destinatario == correo,
                AccesoManual.consumed_at.is_(None),
                AccesoManual.expires_at > ahora,
            )
            .order_by(AccesoManual.created_at.desc())
            .first()
        )
        return _orm_acceso_manual_a_datos(orm, con_formulario=True) if orm else None

    def reenviar_acceso(self, acceso_id: str, nuevo_pin_hash: str, nuevo_token: str, timestamp: datetime) -> None:
        orm = self._sesion.query(AccesoManual).filter(AccesoManual.id == acceso_id).first()
        if orm:
            orm.pin_hash = nuevo_pin_hash
            orm.token_diligenciamiento = nuevo_token
            orm.ultimo_envio_correo = timestamp
            self._sesion.commit()
