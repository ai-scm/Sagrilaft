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
from typing import Any, Dict, List, Literal, Optional

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from domain.contratos import AccesoManualDatos, SolicitudCreacionAcceso
from domain.excepciones import (
    AccesoExpiradoError,
    CredencialesAccesoInvalidasError,
    FormularioYaEnviadoError,
    TokenConsumidoError,
    TokenDiligenciamientoInvalidoError,
)
from domain.puertos.repositorios import RepositorioAccesoManual
from domain.utils.estado_formulario import es_estado_editable
from domain.utils.fechas import (
    DIAS_HABILES_VIGENCIA_ACCESO,
    ahora_utc,
    normalizar_datetime_utc,
    sumar_dias_habiles,
)
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


def _esta_expirado(acceso: AccesoManualDatos) -> bool:
    expires_at = acceso.expires_at
    if expires_at is None:
        return False
    return ahora_utc() > normalizar_datetime_utc(expires_at)


def _verificar_vigencia(acceso: AccesoManualDatos) -> None:
    """Lanza AccesoExpiradoError si el acceso superó su fecha de vigencia."""
    if _esta_expirado(acceso):
        raise AccesoExpiradoError()


def _verificar_no_consumido(acceso: AccesoManualDatos) -> None:
    """Lanza TokenConsumidoError si el acceso ya fue utilizado."""
    if acceso.consumed_at is not None:
        raise TokenConsumidoError()


def _calcular_estado_acceso(acceso: AccesoManualDatos) -> Literal["activo", "consumido", "expirado"]:
    """
    Determina el estado del acceso sin lanzar excepciones — apto para listados.

    Retorna:
      "consumido" — el formulario fue enviado (el acceso ya no es usable).
      "expirado"  — el plazo de 5 días hábiles venció sin que se enviara el formulario.
      "activo"    — las credenciales son válidas y el formulario sigue abierto.
    """
    if acceso.consumed_at is not None:
        return "consumido"

    # Fuente de verdad funcional: el formulario ya no está editable.
    # Nota: consumed_at puede estar vacío en datos históricos; el estado debe
    # seguir reflejando que el acceso ya fue usado.
    if acceso.estado_formulario and not es_estado_editable(acceso.estado_formulario):
        return "consumido"

    if _esta_expirado(acceso):
        return "expirado"

    return "activo"


class AccesoManualService:
    """
    Servicio de negocio para la creación y resolución de accesos manuales.

    Depende de un repositorio y una URL base para construir
    el enlace de diligenciamiento enviado al destinatario externo.
    """

    def __init__(self, repo: RepositorioAccesoManual, url_base: str = "") -> None:
        self._repo = repo
        self._url_base = url_base.rstrip("/")

    # ─── Serialización / DTOs ───────────────────────────────────────────────

    def _construir_enlace_diligenciamiento(self, token: str) -> str:
        return f"{self._url_base}/?token={token}"

    def _serializar_acceso_creado(self, resultado, pin: str) -> Dict[str, Any]:
        return {
            "formulario_id":            resultado.formulario_id,
            "codigo_peticion":          resultado.codigo_peticion,
            "pin":                      pin,
            "token_diligenciamiento":   resultado.token_diligenciamiento,
            "enlace_diligenciamiento":  self._construir_enlace_diligenciamiento(
                resultado.token_diligenciamiento
            ),
            "correo_destinatario":      resultado.correo_destinatario,
            "razon_social":             resultado.razon_social,
            "tipo_contraparte":         resultado.tipo_contraparte,
            "area_responsable":         resultado.area_responsable,
            "created_at":               resultado.created_at,
            "expires_at":               resultado.expires_at,
        }

    @staticmethod
    def _serializar_acceso_listado(acceso: AccesoManualDatos) -> Dict[str, Any]:
        return {
            "id":                  acceso.id,
            "formulario_id":       acceso.formulario_id,
            "codigo_peticion":     acceso.codigo_peticion,
            "correo_destinatario": acceso.correo_destinatario,
            "razon_social":        acceso.razon_social,
            "tipo_contraparte":    acceso.tipo_contraparte,
            "area_responsable":    acceso.area_responsable,
            "estado_acceso":       _calcular_estado_acceso(acceso),
            "created_at":          acceso.created_at,
            "expires_at":          acceso.expires_at,
            "consumed_at":         acceso.consumed_at,
        }

    # ─── Creación ────────────────────────────────────────────────────────────

    def crear_acceso(self, solicitud: SolicitudCreacionAcceso) -> Dict[str, Any]:
        """
        Genera credenciales únicas, persiste el AccesoManual y el Formulario
        pre-inicializado, y devuelve el PIN en texto plano UNA SOLA VEZ.

        El PIN nunca se vuelve a exponer tras esta llamada.
        """
        pin = _generar_pin()
        pin_hash = _verificador_pin.hash(pin)
        token = secrets.token_urlsafe(32)

        resultado = self._repo.crear_formulario_y_acceso(solicitud, pin_hash, token)

        logger.info(
            "Acceso manual creado — empresa: '%s' (%s), destinatario: %s, código: %s",
            solicitud.razon_social,
            solicitud.tipo_contraparte,
            solicitud.correo_destinatario,
            resultado.codigo_peticion,
        )

        return self._serializar_acceso_creado(resultado, pin)

    # ─── Listado ─────────────────────────────────────────────────────────────

    def listar_accesos(self) -> List[Dict[str, Any]]:
        """Devuelve todos los accesos creados, ordenados del más reciente al más antiguo."""
        accesos = self._repo.listar_accesos()
        return [self._serializar_acceso_listado(acceso) for acceso in accesos]

    # ─── Resolución de token ──────────────────────────────────────────────────

    @staticmethod
    def _validar_acceso_para_token(acceso: AccesoManualDatos) -> None:
        _verificar_vigencia(acceso)
        _verificar_no_consumido(acceso)
        if not es_estado_editable(acceso.estado_formulario):
            raise TokenConsumidoError()

    def resolver_token(self, token: str) -> Dict[str, Any]:
        """
        Valida el token de diligenciamiento y devuelve el Formulario vinculado.

        Usado cuando el destinatario externo accede desde el enlace recibido por correo.
        """
        acceso = self._repo.obtener_acceso_por_token(token)
        if not acceso:
            raise TokenDiligenciamientoInvalidoError(token)

        self._validar_acceso_para_token(acceso)
        formulario = self._repo.obtener_formulario_completo(acceso.formulario_id)
        return construir_snapshot_formulario(formulario)

    def registrar_correo_desde_token(self, token: str, correo: str) -> None:
        """
        Registra el correo del destinatario en el acceso (y formulario) asociado al token.
        Valida que el token sea correcto y vigente.
        """
        acceso = self._repo.obtener_acceso_por_token(token)
        if not acceso:
            raise TokenDiligenciamientoInvalidoError(token)

        self._validar_acceso_para_token(acceso)
        self._repo.actualizar_correo_por_token(token, correo)

    def verificar_estado_correo(self, token: str) -> bool:
        """
        Verifica si el acceso asociado al token tiene correo registrado.

        Endpoint liviano: no carga el snapshot completo del formulario.
        Retorna True si correo_destinatario está presente, False en caso contrario.

        Raises:
            TokenDiligenciamientoInvalidoError: si el token no existe.
            AccesoExpiradoError: si el acceso ya venció.
            TokenConsumidoError: si el formulario ya fue enviado.
        """
        acceso = self._repo.obtener_acceso_por_token(token)
        if not acceso:
            raise TokenDiligenciamientoInvalidoError(token)

        self._validar_acceso_para_token(acceso)
        return bool(acceso.correo_destinatario and acceso.correo_destinatario.strip())

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
        formulario = self._repo.obtener_formulario_por_codigo(codigo_peticion)
        acceso = (
            self._repo.obtener_acceso_por_formulario_id(formulario.id, cargar_formulario=True)
            if formulario else None
        )

        # Argon2 siempre se ejecuta: _HASH_DUMMY garantiza latencia constante cuando
        # el código no existe, haciendo imposible distinguir "código inválido" de "PIN incorrecto".
        _verificar_pin(acceso.pin_hash if acceso else _HASH_DUMMY, pin)

        # Importante: nunca revelar si falló el código o el PIN.
        if not formulario or not acceso:
            raise CredencialesAccesoInvalidasError()

        _verificar_vigencia(acceso)

        if not es_estado_editable(formulario.estado):
            raise FormularioYaEnviadoError()

        return construir_snapshot_formulario(formulario)

    # ─── Verificación de credenciales al enviar ──────────────────────────────

    @staticmethod
    def _verificar_por_token(acceso: AccesoManualDatos, token: str) -> None:
        if acceso.consumed_at is not None:
            raise FormularioYaEnviadoError()
        if not es_estado_editable(acceso.estado_formulario):
            raise FormularioYaEnviadoError()
        if not secrets.compare_digest(acceso.token_diligenciamiento, token):
            raise CredencialesAccesoInvalidasError()

    @staticmethod
    def _verificar_por_codigo_y_pin(
        acceso: AccesoManualDatos, codigo_peticion: str, pin: str
    ) -> None:
        if not secrets.compare_digest(acceso.codigo_peticion, codigo_peticion):
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
        acceso = self._repo.obtener_acceso_por_formulario_id(
            formulario_id, cargar_formulario=True
        )
        if not acceso:
            return  # formulario regular, sin PIN requerido

        _verificar_vigencia(acceso)

        if not es_estado_editable(acceso.estado_formulario):
            raise FormularioYaEnviadoError()

        # Verificar por token de diligenciamiento (flujo enlace por correo)
        if token:
            self._verificar_por_token(acceso, token)
            return

        # Verificar por código de petición + PIN (flujo recuperación de sesión)
        if codigo_peticion and pin:
            self._verificar_por_codigo_y_pin(acceso, codigo_peticion, pin)
            return

        raise CredencialesAccesoInvalidasError()

    # ─── Consulta de datos del destinatario ──────────────────────────────────

    def obtener_correo_destinatario(self, formulario_id: str) -> Optional[str]:
        """
        Retorna el correo del destinatario vinculado al formulario.

        Lectura pura — no modifica el acceso. Retorna None si el formulario
        no tiene AccesoManual asociado (formularios sin acceso externo).
        """
        acceso = self._repo.obtener_acceso_por_formulario_id(formulario_id)
        return acceso.correo_destinatario if acceso else None

    # ─── Reactivación para trabajo externo ───────────────────────────────────

    def reactivar_acceso_para_trabajo_expediente(
        self, formulario_id: str
    ) -> Optional[dict]:
        """
        Regenera el token y restablece el vencimiento del acceso para una nueva
        ronda de trabajo externo sobre el expediente.

        El caller (ExpedienteService) agrupa este cambio en su propia transacción;
        reactivar_acceso NO hace commit — el commit lo emite RepositorioExpediente.

        Returns:
            {"correo_destinatario": str, "enlace_diligenciamiento": str}
            o None si el formulario no tiene AccesoManual vinculado.
        """
        acceso = self._repo.obtener_acceso_por_formulario_id(formulario_id)
        if not acceso:
            return None

        nuevo_token = secrets.token_urlsafe(32)
        nuevo_expires_at = sumar_dias_habiles(ahora_utc(), DIAS_HABILES_VIGENCIA_ACCESO)
        self._repo.reactivar_acceso(acceso.id, nuevo_token, nuevo_expires_at)

        return {
            "correo_destinatario":    acceso.correo_destinatario,
            "enlace_diligenciamiento": self._construir_enlace_diligenciamiento(nuevo_token),
        }

    def reactivar_acceso_para_correccion(
        self, formulario_id: str
    ) -> Optional[dict]:
        """Alias de negocio para el flujo histórico de devolución por corrección."""
        return self.reactivar_acceso_para_trabajo_expediente(formulario_id)

    # ─── Consumo de token al enviar ──────────────────────────────────────────

    def marcar_consumido_al_enviar(self, formulario_id: str) -> None:
        """
        Marca un AccesoManual como consumido tras un envío exitoso.

        No re-valida el token porque se espera que el router ya haya verificado
        credenciales en verificar_credenciales_si_aplica().

        Es idempotente: si no hay acceso manual o ya estaba consumido, no hace nada.
        """
        acceso = self._repo.obtener_acceso_por_formulario_id(formulario_id)
        if not acceso:
            return
        if acceso.consumed_at is not None:
            return
        self._repo.marcar_consumido(acceso.id, ahora_utc())
