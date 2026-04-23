"""
AccesoManualService — gestión de accesos manuales al formulario SAGRILAFT.

Responsabilidades:
  - Generar credenciales criptográficamente seguras (código de petición, PIN, token).
  - Hashear el PIN con Argon2 antes de persistirlo.
  - Crear el Formulario pre-inicializado y el AccesoManual vinculado.
  - Resolver tokens de diligenciamiento entrantes.
  - Verificar credenciales (código + PIN) para recuperación de sesión.

SRP: este servicio no conoce lógica de formulario más allá de la creación inicial.
"""

import logging
import secrets
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from sqlalchemy.orm import Session

from domain.excepciones import (
    AccesoExpiradoError,
    CredencialesAccesoInvalidasError,
    FormularioYaEnviadoError,
    TokenDiligenciamientoInvalidoError,
)
from models import AccesoManual, EstadoFormulario, Formulario
from schemas import SolicitudAccesoManual
from services.formulario.serializacion import construir_snapshot_formulario

logger = logging.getLogger(__name__)

# Alphabet sin caracteres ambiguos (0/O, 1/I/l) para mayor legibilidad
_ALFABETO_PIN = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"
_LONGITUD_PIN = 8

_verificador_pin = PasswordHasher(
    time_cost=2,
    memory_cost=32768,  # 64 MB
    parallelism=2,
    hash_len=32,
    salt_len=16,
)

# Hash de un valor aleatorio generado al importar el módulo.
# Se usa cuando el código de petición no existe en la BD para que la verificación
# Argon2 siempre se ejecute y el tiempo de respuesta sea indistinguible del caso
# donde el código sí existe (prevención de enumeración por análisis de timing).
_HASH_DUMMY = _verificador_pin.hash(secrets.token_urlsafe(32))


def _generar_pin() -> str:
    return "".join(secrets.choice(_ALFABETO_PIN) for _ in range(_LONGITUD_PIN))


def _verificar_pin(pin_hash: str, pin: str) -> None:
    """Verifica el PIN contra su hash Argon2. Lanza CredencialesAccesoInvalidasError si no coincide."""
    try:
        _verificador_pin.verify(pin_hash, pin)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        raise CredencialesAccesoInvalidasError()


def _verificar_vigencia(acceso: "AccesoManual") -> None:
    """Lanza AccesoExpiradoError si el acceso superó su fecha de vigencia.

    Nota sobre zonas horarias:
    - SQLite suele devolver datetimes sin zona horaria (naive) que representan UTC.
    - En otros motores o configuraciones, expires_at puede venir con tzinfo.
    Se compara en el mismo "tipo" (naive vs aware) para evitar TypeError y
    preservar la semántica esperada (UTC).
    """
    expires_at = acceso.expires_at
    if expires_at is None:
        return

    ahora: datetime
    if expires_at.tzinfo is None:
        ahora = datetime.utcnow()
    else:
        ahora = datetime.now(timezone.utc)
        expires_at = expires_at.astimezone(timezone.utc)

    if ahora > expires_at:
        raise AccesoExpiradoError()


def _verificar_no_consumido(acceso: "AccesoManual", token: str) -> None:
    """
    Lanza TokenDiligenciamientoInvalidoError si el token ya fue consumido.

    Se usa un error genérico para no revelar detalles adicionales al consumidor del enlace.
    """
    if acceso.consumed_at is not None:
        raise TokenDiligenciamientoInvalidoError(token)


class AccesoManualService:
    """
    Servicio de negocio para la creación y resolución de accesos manuales.

    Depende de una sesión de base de datos y una URL base para construir
    el enlace de diligenciamiento enviado al destinatario externo.
    """

    def __init__(self, sesion: Session, url_base: str = "") -> None:
        self._sesion = sesion
        self._url_base = url_base.rstrip("/")

    # ─── Creación ────────────────────────────────────────────────────────────

    def crear_acceso(self, solicitud: SolicitudAccesoManual) -> Dict[str, Any]:
        """
        Genera credenciales únicas, persiste el AccesoManual y el Formulario
        pre-inicializado, y devuelve el PIN en texto plano UNA SOLA VEZ.

        El PIN nunca se vuelve a exponer tras esta llamada.
        """
        pin = _generar_pin()
        pin_hash = _verificador_pin.hash(pin)
        token = secrets.token_urlsafe(32)

        formulario = Formulario(
            tipo_contraparte=solicitud.tipo_contraparte,
            razon_social=solicitud.razon_social,
            correo=solicitud.correo_destinatario,
        )
        self._sesion.add(formulario)
        self._sesion.flush()

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

        # TODO: integrar servicio de email para enviar credenciales al destinatario
        logger.info(
            "Acceso manual creado — empresa: '%s' (%s), destinatario: %s, código: %s",
            solicitud.razon_social,
            solicitud.tipo_contraparte,
            solicitud.correo_destinatario,
            formulario.codigo_peticion,
        )

        enlace = f"{self._url_base}/?token={token}"
        return {
            "formulario_id":           formulario.id,
            "codigo_peticion":         formulario.codigo_peticion,
            "pin":                     pin,
            "token_diligenciamiento":  token,
            "enlace_diligenciamiento": enlace,
            "correo_destinatario":     solicitud.correo_destinatario,
            "razon_social":            solicitud.razon_social,
            "tipo_contraparte":        solicitud.tipo_contraparte,
            "area_responsable":        solicitud.area_responsable,
            "created_at":              acceso.created_at,
        }

    # ─── Listado ─────────────────────────────────────────────────────────────

    def listar_accesos(self) -> List[Dict[str, Any]]:
        """Devuelve todos los accesos creados, ordenados del más reciente al más antiguo."""
        accesos = (
            self._sesion.query(AccesoManual)
            .join(Formulario, AccesoManual.formulario_id == Formulario.id)
            .order_by(AccesoManual.created_at.desc())
            .all()
        )
        return [
            {
                "id":                  a.id,
                "formulario_id":       a.formulario_id,
                "codigo_peticion":     a.formulario.codigo_peticion,
                "correo_destinatario": a.correo_destinatario,
                "razon_social":        a.razon_social,
                "tipo_contraparte":    a.tipo_contraparte,
                "area_responsable":    a.area_responsable,
                "estado_formulario":   a.formulario.estado,
                "created_at":          a.created_at,
            }
            for a in accesos
        ]

    # ─── Resolución de token ──────────────────────────────────────────────────

    def resolver_token(self, token: str) -> Dict[str, Any]:
        """
        Valida el token de diligenciamiento y devuelve el Formulario vinculado.

        Usado cuando el destinatario externo accede desde el enlace recibido por correo.
        """
        acceso = (
            self._sesion.query(AccesoManual)
            .filter(AccesoManual.token_diligenciamiento == token)
            .first()
        )
        if not acceso:
            raise TokenDiligenciamientoInvalidoError(token)

        _verificar_vigencia(acceso)
        _verificar_no_consumido(acceso, token)
        if acceso.formulario.estado != EstadoFormulario.BORRADOR:
            raise TokenDiligenciamientoInvalidoError(token)
        return construir_snapshot_formulario(acceso.formulario)

    # ─── Verificación de credenciales ────────────────────────────────────────

    def buscar_formulario_por_credenciales(
        self, codigo_peticion: str, pin: str
    ) -> Dict[str, Any]:
        """
        Verifica el par (código de petición + PIN) y devuelve el Formulario asociado.

        El tiempo de respuesta es constante independientemente de si el código existe,
        previniendo la enumeración de códigos válidos mediante análisis de timing.
        Lanza CredencialesAccesoInvalidasError si el código no existe o el PIN no coincide.
        """
        formulario = (
            self._sesion.query(Formulario)
            .filter(Formulario.codigo_peticion == codigo_peticion)
            .first()
        )
        acceso = (
            self._sesion.query(AccesoManual)
            .filter(AccesoManual.formulario_id == formulario.id)
            .first()
        ) if formulario else None

        # Argon2 siempre se ejecuta: _HASH_DUMMY garantiza latencia constante cuando
        # el código no existe, haciendo imposible distinguir "código inválido" de "PIN incorrecto".
        _verificar_pin(acceso.pin_hash if acceso else _HASH_DUMMY, pin)

        # Importante: nunca revelar si falló el código o el PIN.
        # Si no existe formulario o acceso, devolvemos el mismo error genérico.
        if not formulario or not acceso:
            raise CredencialesAccesoInvalidasError()

        _verificar_vigencia(acceso)

        if formulario.estado != EstadoFormulario.BORRADOR:
            raise FormularioYaEnviadoError()

        return construir_snapshot_formulario(formulario)

    # ─── Verificación de credenciales al enviar ──────────────────────────────

    def verificar_credenciales_si_aplica(
        self,
        formulario_id: str,
        token: Optional[str] = None,
        codigo_peticion: Optional[str] = None,
        pin: Optional[str] = None,
    ) -> None:
        """
        Verifica credenciales solo cuando el formulario tiene AccesoManual vinculado.

        Para formularios regulares (sin AccesoManual) retorna sin hacer nada.
        Para formularios con AccesoManual acepta token O (código+PIN). Lanza
        CredencialesAccesoInvalidasError en cualquier forma de fallo para no
        revelar qué campo falló (prevención de enumeración).
        """
        acceso = (
            self._sesion.query(AccesoManual)
            .filter(AccesoManual.formulario_id == formulario_id)
            .first()
        )
        if not acceso:
            return  # formulario regular, sin PIN requerido

        _verificar_vigencia(acceso)

        # Verificar por token de diligenciamiento (flujo enlace por correo)
        if token:
            if acceso.consumed_at is not None:
                raise FormularioYaEnviadoError()
            if not secrets.compare_digest(acceso.token_diligenciamiento, token):
                raise CredencialesAccesoInvalidasError()
            return

        # Verificar por código de petición + PIN (flujo recuperación de sesión)
        if codigo_peticion and pin:
            if not secrets.compare_digest(acceso.formulario.codigo_peticion, codigo_peticion):
                raise CredencialesAccesoInvalidasError()
            _verificar_pin(acceso.pin_hash, pin)
            return

        raise CredencialesAccesoInvalidasError()

    # ─── Consumo de token al enviar ──────────────────────────────────────────

    def consumir_token_al_enviar(self, formulario_id: str, token: str) -> None:
        """
        Marca el token de diligenciamiento como consumido tras un envío exitoso.

        Es idempotente: si ya estaba consumido no hace nada.
        """
        acceso = (
            self._sesion.query(AccesoManual)
            .filter(AccesoManual.formulario_id == formulario_id)
            .first()
        )
        if not acceso:
            return

        if not secrets.compare_digest(acceso.token_diligenciamiento, token):
            raise CredencialesAccesoInvalidasError()

        if acceso.consumed_at is not None:
            return

        acceso.consumed_at = datetime.now(timezone.utc)
        self._sesion.commit()
