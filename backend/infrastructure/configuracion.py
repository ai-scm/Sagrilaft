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


@dataclass(frozen=True)
class ZohoSignConfig:
    """Configuración de ZohoSign para firma electrónica."""
    client_id:      str = field(default_factory=lambda: os.getenv("ZOHO_CLIENT_ID", ""))
    client_secret:  str = field(default_factory=lambda: os.getenv("ZOHO_CLIENT_SECRET", ""))
    refresh_token:  str = field(default_factory=lambda: os.getenv("ZOHO_REFRESH_TOKEN", ""))
    webhook_secret: str = field(default_factory=lambda: os.getenv("ZOHO_WEBHOOK_SECRET", ""))
    modo_prueba:    bool = field(
        default_factory=lambda: os.getenv("ZOHO_SIGN_TESTING", "false").lower() == "true"
    )

    def validar(self) -> None:
        """Lanza RuntimeError si las credenciales OAuth de ZohoSign no están configuradas.

        webhook_secret se omite: se valida en FirmaService al recibir el webhook,
        ya que puede estar ausente en entornos sin URL pública.
        """
        _REQUERIDAS = {
            "client_id":     "ZOHO_CLIENT_ID",
            "client_secret": "ZOHO_CLIENT_SECRET",
            "refresh_token": "ZOHO_REFRESH_TOKEN",
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
    region: str = field(default_factory=lambda: os.getenv("AWS_REGION", "us-east-1"))
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
    region: str = field(default_factory=lambda: os.getenv("AWS_REGION", "us-east-1"))

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
    # "local" usa el volumen del servidor; "s3" usa Amazon S3
    storage_backend: str = field(default_factory=lambda: os.getenv("STORAGE_BACKEND", "local"))
    # Clave para firmar reportes de auditoría con HMAC-SHA256
    secret_key: str = field(default_factory=lambda: os.getenv("SECRET_KEY", "cambiar-en-produccion"))


def load_config() -> AppConfig:
    """Carga la configuración desde variables de entorno."""
    try:
        from dotenv import load_dotenv
        load_dotenv(BASE_DIR / ".env", override=False)
    except ImportError:
        pass  # python-dotenv opcional; en producción las vars vienen del entorno del SO

    cfg = AppConfig()

    if not cfg.aws.model_id:
        _log.warning(
            "BEDROCK_MODEL_ID no configurado — el análisis IA estará deshabilitado."
        )
    elif not (cfg.aws.access_key_id and cfg.aws.secret_access_key):
        _log.info(
            "AWS sin credenciales explícitas (AWS_ACCESS_KEY_ID vacío). "
            "Se usará el IAM Role del entorno — correcto en EC2, "
            "configura AWS_ACCESS_KEY_ID si corres fuera de AWS."
        )

    return cfg
