"""
Configuración centralizada de la aplicación.
Usa variables de entorno con valores por defecto seguros.
"""

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

_log = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent


def entorno_actual() -> str:
    """Única fuente de verdad para APP_ENV: "development" | "staging" | "production".

    Es obligatorio y no tiene valor por defecto: un entorno mal configurado
    debe fallar de inmediato en el arranque, nunca asumir "production" en
    silencio (eso fue exactamente el bug que motivó esta función: antes
    `api/middleware/autenticacion.py` leía la misma variable por su cuenta
    con un default distinto al de `AppConfig`).
    """
    valor = os.getenv("APP_ENV")
    if not valor:
        raise RuntimeError(
            "La variable de entorno APP_ENV no está definida. "
            "Valores válidos: development, staging, production."
        )
    return valor.lower()


def _region_aws_por_defecto() -> str:
    """Región AWS: única fuente de verdad para el default 'us-east-1'.

    Reutilizada por AWSConfig y S3Config — antes cada una repetía el
    mismo `os.getenv("AWS_REGION", "us-east-1")` por su cuenta.
    """
    return os.getenv("AWS_REGION", "us-east-1")


def _int_env(nombre: str, default: int) -> int:
    return int(os.getenv(nombre, str(default)))


def _float_env(nombre: str, default: float) -> float:
    return float(os.getenv(nombre, str(default)))


@dataclass(frozen=True)
class ZohoSignConfig:
    """Configuración de ZohoSign para firma electrónica."""
    client_id:      str = field(default_factory=lambda: os.getenv("ZOHO_CLIENT_ID", ""))
    client_secret:  str = field(default_factory=lambda: os.getenv("ZOHO_CLIENT_SECRET", ""))
    refresh_token:  str = field(default_factory=lambda: os.getenv("ZOHO_REFRESH_TOKEN", ""))
    redirect_uri:   str = field(default_factory=lambda: os.getenv("ZOHO_REDIRECT_URI", ""))
    webhook_secret: str = field(default_factory=lambda: os.getenv("ZOHO_WEBHOOK_SECRET", ""))
    webhook_signature_header: str = field(
        default_factory=lambda: os.getenv("ZOHO_WEBHOOK_SIGNATURE_HEADER", "X-ZS-WEBHOOK-SIGNATURE")
    )
    modo_prueba:    bool = field(
        default_factory=lambda: os.getenv("ZOHO_SIGN_TESTING", "false").lower() == "true"
    )
    margen_refresco_segundos: int = field(
        default_factory=lambda: _int_env("ZOHO_REFRESH_MARGIN_SECONDS", 300)
    )
    segundos_expiracion_token_default: int = field(
        default_factory=lambda: _int_env("ZOHO_TOKEN_EXPIRATION_DEFAULT_SECONDS", 3600)
    )
    max_intentos_http: int = field(
        default_factory=lambda: _int_env("ZOHO_HTTP_MAX_ATTEMPTS", 3)
    )
    espera_inicial_reintento_segundos: float = field(
        default_factory=lambda: _float_env("ZOHO_HTTP_INITIAL_RETRY_WAIT_SECONDS", 1.0)
    )
    factor_backoff_exponencial: int = field(
        default_factory=lambda: _int_env("ZOHO_HTTP_BACKOFF_FACTOR", 2)
    )
    timeout_token_segundos: int = field(
        default_factory=lambda: _int_env("ZOHO_TOKEN_TIMEOUT_SECONDS", 15)
    )
    timeout_consulta_segundos: int = field(
        default_factory=lambda: _int_env("ZOHO_STATUS_TIMEOUT_SECONDS", 15)
    )
    timeout_cancelacion_segundos: int = field(
        default_factory=lambda: _int_env("ZOHO_CANCEL_TIMEOUT_SECONDS", 15)
    )
    timeout_crear_solicitud_segundos: int = field(
        default_factory=lambda: _int_env("ZOHO_CREATE_REQUEST_TIMEOUT_SECONDS", 30)
    )
    timeout_enviar_solicitud_segundos: int = field(
        default_factory=lambda: _int_env("ZOHO_SUBMIT_REQUEST_TIMEOUT_SECONDS", 30)
    )
    timeout_descarga_segundos: int = field(
        default_factory=lambda: _int_env("ZOHO_DOWNLOAD_TIMEOUT_SECONDS", 60)
    )
    dias_expiracion_solicitud_firma: int = field(
        default_factory=lambda: _int_env("ZOHO_SIGN_REQUEST_EXPIRATION_DAYS", 15)
    )

    def validar(self) -> None:
        """Lanza RuntimeError si ZohoSign no está configurado correctamente.

        Siempre valida las credenciales OAuth, tanto en sandbox (modo_prueba=True)
        como en producción (modo_prueba=False), ya que ambos modos hacen llamadas
        reales a la API de Zoho.

        webhook_secret se omite: se valida en FirmaService al recibir el webhook,
        ya que puede estar ausente en entornos sin URL pública.
        """
        _REQUERIDAS = {
            "client_id":     "ZOHO_CLIENT_ID",
            "client_secret": "ZOHO_CLIENT_SECRET",
            "refresh_token": "ZOHO_REFRESH_TOKEN",
            "redirect_uri":  "ZOHO_REDIRECT_URI",
        }
        faltantes = [
            var_env
            for campo, var_env in _REQUERIDAS.items()
            if not getattr(self, campo)
        ]
        if faltantes:
            raise RuntimeError(
                f"Configuración ZohoSign incompleta. "
                f"Variables de entorno faltantes: {', '.join(faltantes)}"
            )


@dataclass(frozen=True)
class AWSConfig:
    """Configuración de AWS Bedrock."""
    region: str = field(default_factory=_region_aws_por_defecto)
    access_key_id: str = field(default_factory=lambda: os.getenv("AWS_ACCESS_KEY_ID", ""))
    secret_access_key: str = field(default_factory=lambda: os.getenv("AWS_SECRET_ACCESS_KEY", ""))
    model_id: str = field(default_factory=lambda: os.getenv("BEDROCK_MODEL_ID", ""))
    max_tokens: int = 4096
    temperature: float = 0.0  # Determinístico para extracción de datos


@dataclass(frozen=True)
class SmtpConfig:
    """Configuración SMTP para envío de correos transaccionales."""
    host:      str = field(default_factory=lambda: os.getenv("SMTP_HOST", ""))
    puerto:    int = field(default_factory=lambda: int(os.getenv("SMTP_PORT", "587")))
    usuario:   str = field(default_factory=lambda: os.getenv("SMTP_USER", ""))
    contrasena: str = field(default_factory=lambda: os.getenv("SMTP_PASSWORD", ""))
    remitente:  str = field(default_factory=lambda: os.getenv("SMTP_FROM", ""))


@dataclass(frozen=True)
class KeycloakConfig:
    """Configuración para integración con Keycloak (portal interno).

    Mientras url esté vacío, la integración permanece inactiva.
    Ver api/middleware/autenticacion.py para activarla.

    En Docker, KEYCLOAK_URL apunta al servicio interno (keycloak:8080) para
    poder buscar las claves JWKS. KEYCLOAK_ISSUER_URL permite indicar la URL
    pública con la que el browser llega a Keycloak (localhost:8080), que es la
    que Keycloak escribe como `iss` en los tokens.
    """
    url:        str = field(default_factory=lambda: os.getenv("KEYCLOAK_URL", ""))
    realm:      str = field(default_factory=lambda: os.getenv("KEYCLOAK_REALM", "sagrilaft"))
    client_id:  str = field(default_factory=lambda: os.getenv("KEYCLOAK_CLIENT_ID", ""))
    issuer_url: str = field(default_factory=lambda: os.getenv("KEYCLOAK_ISSUER_URL", ""))

    @property
    def configurado(self) -> bool:
        return bool(self.url and self.realm and self.client_id)

    @property
    def jwks_uri(self) -> str:
        return f"{self.url}/realms/{self.realm}/protocol/openid-connect/certs"

    @property
    def issuer(self) -> str:
        base = self.issuer_url or self.url
        return f"{base}/realms/{self.realm}"


@dataclass(frozen=True)
class S3Config:
    """Configuración para almacenamiento de archivos en Amazon S3."""
    bucket: str = field(default_factory=lambda: os.getenv("S3_BUCKET", ""))
    # Reutiliza AWS_REGION de AWSConfig para no duplicar variables
    region: str = field(default_factory=_region_aws_por_defecto)

    @property
    def configurado(self) -> bool:
        return bool(self.bucket)


def _require_db_url() -> str:
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "La variable de entorno DATABASE_URL no está definida. "
            "Ejemplo: postgresql+psycopg://usuario:contraseña@localhost:5432/sagrilaft"
        )
    return url


def _require_portal_interno_url() -> str:
    """URL base del portal interno — obligatoria, sin default hardcodeado.

    Antes tenía como default "https://portal.sagrilaft.com", un dominio que
    ni siquiera coincide con el real de producción y que además estaba
    repetido en sns_alertas.py y ses_alertas.py. AppConfig es la única fuente
    de verdad; los adaptadores de alertas la reciben inyectada (ensamblaje.py).
    """
    url = os.getenv("PORTAL_INTERNO_URL")
    if not url:
        raise RuntimeError(
            "La variable de entorno PORTAL_INTERNO_URL no está definida. "
            "Ejemplo: https://portal.miempresa.com"
        )
    return url


@dataclass(frozen=True)
class SnsConfig:
    """Configuración de Amazon SNS para alertas al portal interno."""
    topic_arn: str = field(default_factory=lambda: os.getenv("SNS_TOPIC_ARN", ""))
    habilitado: bool = field(
        default_factory=lambda: os.getenv("SNS_NOTIFICACIONES_ENABLED", "false").lower() == "true"
    )

    @property
    def configurado(self) -> bool:
        return bool(self.topic_arn and self.habilitado)


@dataclass(frozen=True)
class SesConfig:
    """Configuración de Amazon SES para envío directo de emails (alternativa a SNS).
    
    SES permite control total sobre MIME headers (Content-Type: text/html),
    evitando que intermediarios conviertan HTML a markdown.
    """
    email_origen: str = field(default_factory=lambda: os.getenv("SES_EMAIL_ORIGEN", ""))
    habilitado: bool = field(
        default_factory=lambda: os.getenv("SES_NOTIFICACIONES_ENABLED", "false").lower() == "true"
    )

    @property
    def configurado(self) -> bool:
        return bool(self.email_origen and self.habilitado)


@dataclass(frozen=True)
class SagrilaftListasConfig:
    """Configuración del proveedor de listas de cautela (verificación PLAFT).

    "dummy" simula resultados y puede usarse en desarrollo/staging mientras la
    API real no esté disponible; "sagrilaft" consulta la API real (tusdatos.co);
    "deshabilitado" omite la consulta. Ver validación de arranque en
    `load_config()`.
    """
    proveedor: str = field(default_factory=lambda: os.getenv("PROVEEDOR_LISTAS_CAUTELA", "dummy").lower())
    api_url: str = field(default_factory=lambda: os.getenv("SAGRILAFT_API_URL", ""))
    api_key: str = field(default_factory=lambda: os.getenv("SAGRILAFT_API_KEY", ""))

    @property
    def configurado(self) -> bool:
        return bool(self.api_url and self.api_key)


@dataclass(frozen=True)
class AppConfig:
    """Configuración general de la aplicación."""
    db_url: str = field(default_factory=_require_db_url)
    upload_dir: Path = field(
        default_factory=lambda: Path(os.getenv("UPLOAD_DIR", BASE_DIR / "uploads")).resolve()
    )
    frontend_urls: list[str] = field(
        default_factory=lambda: [
            u.strip()
            for u in os.getenv("FRONTEND_URL", "http://localhost:5173").split(",")
            if u.strip()
        ]
    )
    aws: AWSConfig = field(default_factory=AWSConfig)
    zoho_sign: ZohoSignConfig = field(default_factory=ZohoSignConfig)
    smtp: SmtpConfig = field(default_factory=SmtpConfig)
    keycloak: KeycloakConfig = field(default_factory=KeycloakConfig)
    s3: S3Config = field(default_factory=S3Config)
    sns: SnsConfig = field(default_factory=SnsConfig)
    ses: SesConfig = field(default_factory=SesConfig)
    listas_cautela: SagrilaftListasConfig = field(default_factory=SagrilaftListasConfig)
    # URL base del portal interno — usada en enlaces de notificaciones por correo
    portal_interno_url: str = field(default_factory=_require_portal_interno_url)
    # "local" usa el volumen del servidor; "s3" usa Amazon S3
    storage_backend: str = field(default_factory=lambda: os.getenv("STORAGE_BACKEND", "local"))
    # Clave para firmar reportes de auditoría con HMAC-SHA256
    secret_key: str = field(
    default_factory=lambda:
        os.environ["SECRET_KEY"]
)
    # "development" | "staging" | "production" — controla comportamiento del health check y logs
    entorno: str = field(default_factory=entorno_actual)
    # Límite de tamaño para archivos subidos (documentos, cargas manuales, reportes finales)
    max_upload_mb: int = field(default_factory=lambda: int(os.getenv("MAX_UPLOAD_SIZE_MB", "15")))

def load_config() -> AppConfig:
    """Carga la configuración desde variables de entorno."""
    try:
        from dotenv import load_dotenv
        load_dotenv(BASE_DIR / ".env", override=False)
    except ImportError:
        pass  # python-dotenv opcional; en producción las vars vienen del entorno del SO

    cfg = AppConfig()

    storage_backend = cfg.storage_backend.lower()

    if cfg.entorno in {"production", "staging"}:
        if storage_backend != "s3":
            raise RuntimeError(
                f"STORAGE_BACKEND={cfg.storage_backend!r} no permitido en APP_ENV={cfg.entorno}. "
                "Produccion y staging deben usar STORAGE_BACKEND=s3."
            )
        if not cfg.s3.bucket:
            raise RuntimeError(
                f"S3_BUCKET es obligatorio en APP_ENV={cfg.entorno} con STORAGE_BACKEND=s3."
            )
        if cfg.entorno == "production" and cfg.listas_cautela.proveedor == "dummy":
            raise RuntimeError(
                f"PROVEEDOR_LISTAS_CAUTELA=dummy no está permitido en APP_ENV={cfg.entorno}. "
                "Configure PROVEEDOR_LISTAS_CAUTELA=sagrilaft (con SAGRILAFT_API_URL y "
                "SAGRILAFT_API_KEY) o =deshabilitado si la verificación se omite a propósito."
            )
        if cfg.listas_cautela.proveedor == "sagrilaft" and not cfg.listas_cautela.configurado:
            raise RuntimeError(
                f"PROVEEDOR_LISTAS_CAUTELA=sagrilaft requiere SAGRILAFT_API_URL y "
                f"SAGRILAFT_API_KEY en APP_ENV={cfg.entorno}."
            )
        if not os.getenv("FRONTEND_URL"):
            raise RuntimeError(
                f"FRONTEND_URL es obligatorio en APP_ENV={cfg.entorno}. "
                "Sin esta variable, CORS cae al valor de desarrollo "
                "(http://localhost:5173) y bloqueará al frontend real."
            )

    if not cfg.aws.model_id:
        _log.warning(
            "BEDROCK_MODEL_ID no configurado — el análisis IA estará deshabilitado."
        )
    elif not (cfg.aws.access_key_id and cfg.aws.secret_access_key):
        _log.info(
            "AWS sin credenciales explícitas (AWS_ACCESS_KEY_ID vacío). "
            "Se usará el IAM Role/Task Role del entorno — correcto en ECS, "
            "configura AWS_ACCESS_KEY_ID si corres fuera de AWS."
        )

    return cfg
