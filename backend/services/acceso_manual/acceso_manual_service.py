"""
AccesoManualService — gestión de accesos manuales al formulario SAGRILAFT.

Responsabilidades:
  - Generar credenciales criptográficamente seguras (código de petición, PIN, token).
  - Hashear el PIN con Argon2 antes de persistirlo.
  - Crear el Formulario pre-inicializado y el AccesoManual vinculado.
  - Resolver tokens de diligenciamiento entrantes.
  - Verificar credenciales (código + PIN) para recuperación de sesión.
  - Calcular el estado operativo del acceso (activo, consumido, expirado) para listados.

SRP: este servicio no implementa lógica de negocio del formulario (campos/reglas),
solo reglas de acceso (vigencia, consumo y autorización del envío).
"""

import logging
import secrets
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from sqlalchemy.orm import Session, joinedload

from domain.excepciones import (
    AccesoExpiradoError,
    CredencialesAccesoInvalidasError,
    FormularioYaEnviadoError,
    TokenDiligenciamientoInvalidoError,
)
from models import AccesoManual, Formulario
from schemas import SolicitudAccesoManual
from services.formulario.serializacion import construir_snapshot_formulario
from services.utils.estado_formulario import es_estado_borrador

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


def _normalizar_datetime_utc(valor: datetime) -> datetime:
    """Normaliza un datetime a UTC aware.

    Nota SQLite: suele devolver datetimes naive que representan UTC. En ese caso,
    se asume UTC y se añade tzinfo para evitar comparaciones naive/aware.
    """
    if valor.tzinfo is None:
        return valor.replace(tzinfo=timezone.utc)
    return valor.astimezone(timezone.utc)


def _ahora_utc() -> datetime:
    return datetime.now(timezone.utc)


def _esta_expirado(acceso: "AccesoManual") -> bool:
    expires_at = acceso.expires_at
    if expires_at is None:
        return False
    return _ahora_utc() > _normalizar_datetime_utc(expires_at)


def _verificar_vigencia(acceso: "AccesoManual") -> None:
    """Lanza AccesoExpiradoError si el acceso superó su fecha de vigencia."""
    if _esta_expirado(acceso):
        raise AccesoExpiradoError()


def _verificar_no_consumido(acceso: "AccesoManual", token: str) -> None:
    """
    Lanza TokenDiligenciamientoInvalidoError si el token ya fue consumido.

    Se usa un error genérico para no revelar detalles adicionales al consumidor del enlace.
    """
    if acceso.consumed_at is not None:
        raise TokenDiligenciamientoInvalidoError(token)


def _calcular_estado_acceso(acceso: "AccesoManual") -> Literal["activo", "consumido", "expirado"]:
    """
    Determina el estado del acceso sin lanzar excepciones — apto para listados.

    Retorna:
      "consumido" — el formulario fue enviado (el acceso ya no es usable).
      "expirado"  — el plazo de 5 días hábiles venció sin que se enviara el formulario.
      "activo"    — las credenciales son válidas y el formulario sigue abierto.
    """
    if acceso.consumed_at is not None:
        return "consumido"

    # Fuente de verdad funcional: el formulario ya no está en borrador.
    # Nota: consumed_at puede estar vacío en datos históricos; el estado debe
    # seguir reflejando que el acceso ya fue usado.
    formulario = getattr(acceso, "formulario", None)
    if formulario is not None and not es_estado_borrador(formulario.estado):
        return "consumido"

    if _esta_expirado(acceso):
        return "expirado"

    return "activo"


class AccesoManualService:
    """
    Servicio de negocio para la creación y resolución de accesos manuales.

    Depende de una sesión de base de datos y una URL base para construir
    el enlace de diligenciamiento enviado al destinatario externo.
    """

    def __init__(self, sesion: Session, url_base: str = "") -> None:
        self._sesion = sesion
        self._url_base = url_base.rstrip("/")

    # ─── Accesos a datos (queries) ──────────────────────────────────────────

    def _obtener_acceso_por_token(self, token: str) -> Optional[AccesoManual]:
        return (
            self._sesion.query(AccesoManual)
            .options(joinedload(AccesoManual.formulario))
            .filter(AccesoManual.token_diligenciamiento == token)
            .first()
        )

    def _obtener_acceso_por_formulario_id(
        self, formulario_id: str, *, cargar_formulario: bool = False
    ) -> Optional[AccesoManual]:
        consulta = self._sesion.query(AccesoManual).filter(AccesoManual.formulario_id == formulario_id)
        if cargar_formulario:
            consulta = consulta.options(joinedload(AccesoManual.formulario))
        return consulta.first()

    def _obtener_formulario_por_codigo(self, codigo_peticion: str) -> Optional[Formulario]:
        return (
            self._sesion.query(Formulario)
            .filter(Formulario.codigo_peticion == codigo_peticion)
            .first()
        )

    def _obtener_acceso_por_formulario(self, formulario: Formulario) -> Optional[AccesoManual]:
        return (
            self._sesion.query(AccesoManual)
            .filter(AccesoManual.formulario_id == formulario.id)
            .first()
        )

    # ─── Serialización / DTOs ───────────────────────────────────────────────

    def _construir_enlace_diligenciamiento(self, token: str) -> str:
        return f"{self._url_base}/?token={token}"

    def _serializar_acceso_creado(
        self,
        *,
        formulario: Formulario,
        acceso: AccesoManual,
        pin: str,
    ) -> Dict[str, Any]:
        return {
            "formulario_id": formulario.id,
            "codigo_peticion": formulario.codigo_peticion,
            "pin": pin,
            "token_diligenciamiento": acceso.token_diligenciamiento,
            "enlace_diligenciamiento": self._construir_enlace_diligenciamiento(acceso.token_diligenciamiento),
            "correo_destinatario": acceso.correo_destinatario,
            "razon_social": acceso.razon_social,
            "tipo_contraparte": acceso.tipo_contraparte,
            "area_responsable": acceso.area_responsable,
            "created_at": acceso.created_at,
            "expires_at": acceso.expires_at,
        }

    @staticmethod
    def _serializar_acceso_listado(acceso: AccesoManual) -> Dict[str, Any]:
        return {
            "id": acceso.id,
            "formulario_id": acceso.formulario_id,
            "codigo_peticion": acceso.formulario.codigo_peticion,
            "correo_destinatario": acceso.correo_destinatario,
            "razon_social": acceso.razon_social,
            "tipo_contraparte": acceso.tipo_contraparte,
            "area_responsable": acceso.area_responsable,
            "estado_acceso": _calcular_estado_acceso(acceso),
            "created_at": acceso.created_at,
            "expires_at": acceso.expires_at,
            "consumed_at": acceso.consumed_at,
        }

    # ─── Creación ────────────────────────────────────────────────────────────

    @staticmethod
    def _crear_formulario_preinicializado(solicitud: SolicitudAccesoManual) -> Formulario:
        return Formulario(
            tipo_contraparte=solicitud.tipo_contraparte,
            razon_social=solicitud.razon_social,
            correo=solicitud.correo_destinatario,
        )

    @staticmethod
    def _crear_acceso_manual(
        *,
        solicitud: SolicitudAccesoManual,
        formulario_id: Any,
        pin_hash: str,
        token_diligenciamiento: str,
    ) -> AccesoManual:
        return AccesoManual(
            pin_hash=pin_hash,
            token_diligenciamiento=token_diligenciamiento,
            correo_destinatario=solicitud.correo_destinatario,
            razon_social=solicitud.razon_social,
            tipo_contraparte=solicitud.tipo_contraparte,
            area_responsable=solicitud.area_responsable,
            formulario_id=formulario_id,
        )

    def crear_acceso(self, solicitud: SolicitudAccesoManual) -> Dict[str, Any]:
        """
        Genera credenciales únicas, persiste el AccesoManual y el Formulario
        pre-inicializado, y devuelve el PIN en texto plano UNA SOLA VEZ.

        El PIN nunca se vuelve a exponer tras esta llamada.
        """
        pin = _generar_pin()
        pin_hash = _verificador_pin.hash(pin)
        token_diligenciamiento = secrets.token_urlsafe(32)

        formulario = self._crear_formulario_preinicializado(solicitud)
        self._sesion.add(formulario)
        self._sesion.flush()

        acceso = self._crear_acceso_manual(
            solicitud=solicitud,
            formulario_id=formulario.id,
            pin_hash=pin_hash,
            token_diligenciamiento=token_diligenciamiento,
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

        return self._serializar_acceso_creado(formulario=formulario, acceso=acceso, pin=pin)

    # ─── Listado ─────────────────────────────────────────────────────────────

    def listar_accesos(self) -> List[Dict[str, Any]]:
        """Devuelve todos los accesos creados, ordenados del más reciente al más antiguo."""
        accesos = (
            self._sesion.query(AccesoManual)
            .options(joinedload(AccesoManual.formulario))
            .order_by(AccesoManual.created_at.desc())
            .all()
        )
        return [self._serializar_acceso_listado(acceso) for acceso in accesos]

    # ─── Resolución de token ──────────────────────────────────────────────────

    @staticmethod
    def _validar_acceso_para_token(acceso: AccesoManual, token: str) -> None:
        _verificar_vigencia(acceso)
        _verificar_no_consumido(acceso, token)
        if not es_estado_borrador(acceso.formulario.estado):
            raise TokenDiligenciamientoInvalidoError(token)

    def resolver_token(self, token: str) -> Dict[str, Any]:
        """
        Valida el token de diligenciamiento y devuelve el Formulario vinculado.

        Usado cuando el destinatario externo accede desde el enlace recibido por correo.
        """
        acceso = self._obtener_acceso_por_token(token)
        if not acceso:
            raise TokenDiligenciamientoInvalidoError(token)

        self._validar_acceso_para_token(acceso, token)
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
        formulario = self._obtener_formulario_por_codigo(codigo_peticion)
        acceso = self._obtener_acceso_por_formulario(formulario) if formulario else None

        # Argon2 siempre se ejecuta: _HASH_DUMMY garantiza latencia constante cuando
        # el código no existe, haciendo imposible distinguir "código inválido" de "PIN incorrecto".
        _verificar_pin(acceso.pin_hash if acceso else _HASH_DUMMY, pin)

        # Importante: nunca revelar si falló el código o el PIN.
        # Si no existe formulario o acceso, devolvemos el mismo error genérico.
        if not formulario or not acceso:
            raise CredencialesAccesoInvalidasError()

        _verificar_vigencia(acceso)

        if not es_estado_borrador(formulario.estado):
            raise FormularioYaEnviadoError()

        return construir_snapshot_formulario(formulario)

    # ─── Verificación de credenciales al enviar ──────────────────────────────

    @staticmethod
    def _verificar_por_token(acceso: AccesoManual, token: str) -> None:
        if acceso.consumed_at is not None:
            raise FormularioYaEnviadoError()
        if not secrets.compare_digest(acceso.token_diligenciamiento, token):
            raise CredencialesAccesoInvalidasError()

    @staticmethod
    def _verificar_por_codigo_y_pin(acceso: AccesoManual, codigo_peticion: str, pin: str) -> None:
        if not secrets.compare_digest(acceso.formulario.codigo_peticion, codigo_peticion):
            raise CredencialesAccesoInvalidasError()
        _verificar_pin(acceso.pin_hash, pin)

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
        acceso = self._obtener_acceso_por_formulario_id(formulario_id, cargar_formulario=True)
        if not acceso:
            return  # formulario regular, sin PIN requerido

        _verificar_vigencia(acceso)

        # Verificar por token de diligenciamiento (flujo enlace por correo)
        if token:
            self._verificar_por_token(acceso, token)
            return

        # Verificar por código de petición + PIN (flujo recuperación de sesión)
        if codigo_peticion and pin:
            self._verificar_por_codigo_y_pin(acceso, codigo_peticion, pin)
            return

        raise CredencialesAccesoInvalidasError()

    # ─── Consumo de token al enviar ──────────────────────────────────────────

    def _marcar_consumido(self, acceso: "AccesoManual") -> None:
        """Marca `consumed_at` si no estaba marcado (idempotente)."""
        if acceso.consumed_at is not None:
            return
        acceso.consumed_at = _ahora_utc()
        self._sesion.commit()

    def consumir_token_al_enviar(self, formulario_id: str, token: str) -> None:
        """
        Marca el token de diligenciamiento como consumido tras un envío exitoso.

        Es idempotente: si ya estaba consumido no hace nada.
        """
        acceso = self._obtener_acceso_por_formulario_id(formulario_id)
        if not acceso:
            return

        if not secrets.compare_digest(acceso.token_diligenciamiento, token):
            raise CredencialesAccesoInvalidasError()

        self._marcar_consumido(acceso)

    def marcar_consumido_al_enviar(self, formulario_id: str) -> None:
        """
        Marca un AccesoManual como consumido tras un envío exitoso.

        A diferencia de consumir_token_al_enviar(), este método NO valida token
        porque se espera que el router ya haya verificado credenciales (token o
        código+PIN) en verificar_credenciales_si_aplica().

        Es idempotente: si no hay acceso manual o ya estaba consumido, no hace nada.
        """
        acceso = self._obtener_acceso_por_formulario_id(formulario_id)
        if not acceso:
            return

        self._marcar_consumido(acceso)
