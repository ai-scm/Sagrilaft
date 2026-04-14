"""
Configuración centralizada de la aplicación.
Usa variables de entorno con valores por defecto seguros.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class AWSConfig:
    """Configuración de AWS Bedrock."""
    region: str = field(default_factory=lambda: os.getenv("AWS_REGION", "us-east-1"))
    access_key_id: str = field(default_factory=lambda: os.getenv("AWS_ACCESS_KEY_ID", ""))
    secret_access_key: str = field(default_factory=lambda: os.getenv("AWS_SECRET_ACCESS_KEY", ""))
    model_id: str = field(default_factory=lambda: os.getenv(
        "BEDROCK_MODEL_ID",
        "arn:aws:bedrock:us-east-1:385208337656:inference-profile/us.anthropic.claude-sonnet-4-6"
    ))
    max_tokens: int = 4096
    temperature: float = 0.0  # Determinístico para extracción de datos


@dataclass(frozen=True)
class AppConfig:
    """Configuración general de la aplicación."""
    upload_dir: Path = field(
        default_factory=lambda: Path(os.getenv("UPLOAD_DIR", BASE_DIR / "uploads")).resolve()
    )
    aws: AWSConfig = field(default_factory=AWSConfig)


def load_config() -> AppConfig:
    """Carga la configuración desde variables de entorno."""
    # Intentar cargar .env si existe
    env_path = BASE_DIR / ".env"
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    os.environ.setdefault(key.strip(), value.strip())

    return AppConfig()
