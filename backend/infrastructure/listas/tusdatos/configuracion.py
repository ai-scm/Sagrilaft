"""Configuración del cliente Tusdatos; los secretos llegan por variables de entorno (Secrets Manager en ECS)."""
import os
from dataclasses import dataclass, field
from urllib.parse import urlsplit

from domain.listas.puertos import ListasNoDisponibles

# Ambiente de pruebas publicado por Tusdatos: respuestas estáticas, sin créditos, solo HTTP.
HOST_SANDBOX = "docs.tusdatos.co"
HOST_PRODUCCION = "dash-board.tusdatos.co"


def _activo(variable: str) -> bool:
    return os.getenv(variable, "true").strip().lower() not in {"false", "0", "no", "off"}


@dataclass(frozen=True)
class ConfiguracionTusdatos:
    url_base: str
    token: str = field(default="", repr=False)
    usuario: str = field(default="", repr=False)
    clave: str = field(default="", repr=False)
    tiempo_conexion: float = 5.0
    tiempo_lectura: float = 20.0
    tiempo_pdf: float = 60.0
    # Con este saldo o menos se registra un aviso (y la métrica TusdatosCreditosRestantes).
    alerta_creditos: int = 100
    # Guardar las capturas de pantalla por fuente que Tusdatos publica junto con el reporte.
    capturas: bool = True
    # Recuperar gratis, después del cierre, lo que quedó incompleto: recargar las fuentes que
    # fallaron (/api/retry) y volver a pedir el PDF y las capturas que no llegaron.
    recuperar: bool = True

    def __post_init__(self):
        partes = urlsplit(self.url_base)
        if partes.scheme not in {"http", "https"} or not partes.hostname or partes.path not in {"", "/"}:
            raise ListasNoDisponibles("LISTAS_TUSDATOS_URL debe ser solo esquema y host")
        if partes.scheme == "http" and partes.hostname != HOST_SANDBOX:
            raise ListasNoDisponibles("Solo el sandbox de Tusdatos admite HTTP")
        if bool(self.token) == bool(self.usuario or self.clave):
            raise ListasNoDisponibles("Configure LISTAS_TUSDATOS_TOKEN o usuario y clave, no ambos")
        if not self.token and not (self.usuario and self.clave):
            raise ListasNoDisponibles("Faltan usuario o clave de Tusdatos")
        if self.alerta_creditos < 0:
            raise ListasNoDisponibles("LISTAS_TUSDATOS_ALERTA_CREDITOS no puede ser negativo")
        for nombre in ("tiempo_conexion", "tiempo_lectura", "tiempo_pdf"):
            if not 0 < getattr(self, nombre) <= 120:
                raise ListasNoDisponibles(f"{nombre} debe estar entre 0 y 120 segundos")

    @property
    def es_sandbox(self) -> bool:
        return urlsplit(self.url_base).hostname == HOST_SANDBOX

    def validar_entorno(self, entorno: str) -> None:
        # Producción acepta API Token (preferido) o usuario y clave (Basic Auth): la cuenta demo no
        # pudo crear tokens (403), así que no se depende de que Tusdatos los habilite en el plan.
        if entorno == "production" and self.es_sandbox:
            raise ListasNoDisponibles("Producción no puede usar el sandbox de Tusdatos")

    @classmethod
    def desde_entorno(cls, entorno: str) -> "ConfiguracionTusdatos":
        url = os.getenv("LISTAS_TUSDATOS_URL", "").strip()
        if not url:
            raise ListasNoDisponibles("Falta LISTAS_TUSDATOS_URL")

        def segundos(variable, defecto):
            valor = os.getenv(variable)
            try:
                return float(valor) if valor else defecto
            except ValueError:
                raise ListasNoDisponibles(f"{variable} no es un número") from None

        configuracion = cls(url_base=url.rstrip("/"), token=os.getenv("LISTAS_TUSDATOS_TOKEN", "").strip(),
            usuario=os.getenv("LISTAS_TUSDATOS_USUARIO", "").strip(), clave=os.getenv("LISTAS_TUSDATOS_CLAVE", ""),
            tiempo_conexion=segundos("LISTAS_TUSDATOS_TIEMPO_CONEXION", 5.0),
            tiempo_lectura=segundos("LISTAS_TUSDATOS_TIEMPO_LECTURA", 20.0),
            tiempo_pdf=segundos("LISTAS_TUSDATOS_TIEMPO_PDF", 60.0),
            alerta_creditos=int(segundos("LISTAS_TUSDATOS_ALERTA_CREDITOS", 100)),
            capturas=_activo("LISTAS_TUSDATOS_CAPTURAS"),
            recuperar=_activo("LISTAS_TUSDATOS_RECUPERAR"))
        configuracion.validar_entorno(entorno)
        return configuracion
