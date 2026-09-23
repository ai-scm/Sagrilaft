"""
Harness de integración para SAGRILAFT.

La suite de integración usa la API real y la persistencia real, pero reemplaza
los bordes externos por dobles determinísticos. Así probamos los flujos del
sistema sin depender de AWS, Zoho, correo, Keycloak ni internet.
"""

from __future__ import annotations

import os
import socket
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx
import pytest
import uvicorn
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.limitador import limitador


RAIZ_PROYECTO = Path(__file__).resolve().parents[2]


def _preparar_entorno_de_integracion() -> None:
    """Define un entorno local seguro antes de importar la aplicación."""

    valores = {
        "APP_ENV": "test",
        # El módulo de persistencia crea un engine global al importarse con
        # parámetros de pool propios de Postgres. En las pruebas se sobreescribe
        # get_db con SQLite aislado, así que esta URL solo permite importar.
        "DATABASE_URL": "postgresql+psycopg://user:pass@localhost:5432/sagrilaft_test",
        "SECRET_KEY": "test-secret-key",
        "FRONTEND_URL": "http://frontend.test",
        "PORTAL_INTERNO_URL": "http://portal.test",
        "STORAGE_BACKEND": "local",
        "ZOHO_CLIENT_ID": "zoho-client-test",
        "ZOHO_CLIENT_SECRET": "zoho-secret-test",
        "ZOHO_REFRESH_TOKEN": "zoho-refresh-test",
        "ZOHO_REDIRECT_URI": "http://backend.test/oauth/zoho/callback",
        "ZOHO_WEBHOOK_SECRET": "zoho-webhook-test",
        "ZOHO_SIGN_TESTING": "true",
        "PROVEEDOR_LISTAS_CAUTELA": "dummy",
        "SES_NOTIFICACIONES_ENABLED": "false",
        "SNS_NOTIFICACIONES_ENABLED": "false",
        "PORTAL_AUTH_DISABLED": "true",
        "AWS_EC2_METADATA_DISABLED": "true",
    }
    for nombre, valor in valores.items():
        os.environ[nombre] = valor


_ENTORNO_ORIGINAL = {
    nombre: os.environ.get(nombre)
    for nombre in (
        "APP_ENV",
        "DATABASE_URL",
        "SECRET_KEY",
        "FRONTEND_URL",
        "PORTAL_INTERNO_URL",
        "STORAGE_BACKEND",
        "ZOHO_CLIENT_ID",
        "ZOHO_CLIENT_SECRET",
        "ZOHO_REFRESH_TOKEN",
        "ZOHO_REDIRECT_URI",
        "ZOHO_WEBHOOK_SECRET",
        "ZOHO_SIGN_TESTING",
        "PROVEEDOR_LISTAS_CAUTELA",
        "SES_NOTIFICACIONES_ENABLED",
        "SNS_NOTIFICACIONES_ENABLED",
        "PORTAL_AUTH_DISABLED",
        "AWS_EC2_METADATA_DISABLED",
    )
}
_preparar_entorno_de_integracion()

import main as modulo_app  # noqa: E402
from api.dependencies import obtener_servicio_email  # noqa: E402
from api.middleware.autenticacion import UsuarioPortalInterno, portal_interno  # noqa: E402
from domain.contratos import ResultadoExtraccion, SolicitudFirmaCreada  # noqa: E402
from infrastructure.config.configuracion import load_config  # noqa: E402
from infrastructure.persistencia.database import Base, get_db  # noqa: E402
from infrastructure.persistencia import models  # noqa: E402,F401
from infrastructure.storage.backend import LocalStorage  # noqa: E402
from main import app as aplicacion_sagrilaft  # noqa: E402


def _restaurar_entorno_original() -> None:
    """Evita que el harness altere el resultado de otras suites."""

    for nombre, valor in _ENTORNO_ORIGINAL.items():
        if valor is None:
            os.environ.pop(nombre, None)
        else:
            os.environ[nombre] = valor


_restaurar_entorno_original()


@dataclass
class NotificadorEnMemoria:
    """Doble del correo transaccional a contraparte."""

    accesos_creados: list[dict[str, Any]] = field(default_factory=list)
    devoluciones: list[dict[str, Any]] = field(default_factory=list)
    rechazos: list[dict[str, Any]] = field(default_factory=list)
    actualizaciones_reabiertas: list[dict[str, Any]] = field(default_factory=list)

    def enviar_notificacion_acceso_creado(self, **datos: Any) -> bool:
        self.accesos_creados.append(datos)
        return True

    def enviar_notificacion_devolucion(self, **datos: Any) -> bool:
        self.devoluciones.append(datos)
        return True

    def enviar_notificacion_rechazo(self, **datos: Any) -> bool:
        self.rechazos.append(datos)
        return True

    def enviar_notificacion_actualizacion_reabierta(self, **datos: Any) -> bool:
        self.actualizaciones_reabiertas.append(datos)
        return True


@dataclass
class AlertasPortalEnMemoria:
    """Doble de alertas internas del portal."""

    eventos: list[dict[str, Any]] = field(default_factory=list)

    def alertar(self, **datos: Any) -> bool:
        self.eventos.append(datos)
        return True

    def metricas(self) -> dict[str, Any]:
        return {"enviadas": len(self.eventos), "fallidas": 0}


@dataclass
class ExtractorIAEnMemoria:
    """Doble de Bedrock para análisis documental."""

    resultado: ResultadoExtraccion = field(
        default_factory=lambda: ResultadoExtraccion(
            extraido=False,
            mensaje="Extracción IA omitida en pruebas de integración.",
        )
    )
    solicitudes: list[dict[str, Any]] = field(default_factory=list)

    async def extraer(self, ruta_archivo: str, tipo_documento: str) -> ResultadoExtraccion:
        self.solicitudes.append(
            {"ruta_archivo": ruta_archivo, "tipo_documento": tipo_documento}
        )
        return self.resultado


@dataclass
class ZohoSignEnMemoria:
    """Doble de Zoho Sign para el ciclo de firma."""

    solicitudes_creadas: list[dict[str, Any]] = field(default_factory=list)
    solicitudes_canceladas: list[dict[str, Any]] = field(default_factory=list)
    estado_actual: str = "Completed"
    contenido_firmado: bytes = b"%PDF-1.4\n% documento firmado de prueba\n"
    proxima_llamada_falla_con: Exception | None = None
    """CA1/CA2: si se asigna, la siguiente llamada a crear_solicitud_firma_multiple
    levanta esta excepción en vez de crear la solicitud, y se limpia el flag
    (falla una sola vez, para poder simular un reintento exitoso después)."""

    def crear_solicitud_firma_multiple(self, **datos: Any) -> SolicitudFirmaCreada:
        if self.proxima_llamada_falla_con is not None:
            error = self.proxima_llamada_falla_con
            self.proxima_llamada_falla_con = None
            raise error
        self.solicitudes_creadas.append(datos)
        return SolicitudFirmaCreada(
            request_id=f"zoho-test-{len(self.solicitudes_creadas)}"
        )

    def descargar_documento_firmado(self, request_id: str, destino: Path) -> Path:
        destino.write_bytes(self.contenido_firmado)
        return destino

    def cancelar_solicitud_firma(self, request_id: str, motivo: str = "") -> bool:
        self.solicitudes_canceladas.append(
            {"request_id": request_id, "motivo": motivo}
        )
        return True

    def obtener_estado_solicitud(self, request_id: str) -> str:
        return self.estado_actual


@dataclass
class OrquestadorEnMemoria:
    """Doble del orquestador documental usado por la capa API."""

    extractor: ExtractorIAEnMemoria = field(default_factory=ExtractorIAEnMemoria)


@pytest.fixture
def anyio_backend():
    """FastAPI se prueba sobre asyncio; no se requiere backend trio."""

    return "asyncio"


@pytest.fixture
def sesion_bd():
    """Crea una base SQLite aislada para una prueba de integración."""

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    sesion = Session()
    try:
        yield sesion
    finally:
        sesion.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture
def usuario_portal():
    """Usuario interno autenticado con permisos sobre clientes y proveedores."""

    return UsuarioPortalInterno(
        sub="usuario-integracion",
        email="analista.integracion@blend360.com",
        roles=["acceso_clientes", "acceso_proveedores"],
    )


@pytest.fixture
def cambiar_usuario_portal():
    """Permite simular roles Keycloak distintos dentro de una prueba."""

    def _cambiar(
        roles: list[str],
        email: str = "analista.integracion@blend360.com",
    ) -> UsuarioPortalInterno:
        usuario = UsuarioPortalInterno(
            sub=f"usuario-integracion-{len(roles)}",
            email=email,
            roles=roles,
        )

        async def usar_usuario_de_prueba():
            return usuario

        aplicacion_sagrilaft.dependency_overrides[portal_interno] = usar_usuario_de_prueba
        return usuario

    return _cambiar


def _obtener_puerto_local_libre() -> int:
    """Reserva brevemente un puerto local para el servidor de integración."""

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as servidor:
        servidor.bind(("127.0.0.1", 0))
        return int(servidor.getsockname()[1])


def _esperar_servidor(base_url: str) -> None:
    """Espera a que Uvicorn acepte tráfico local."""

    limite = time.monotonic() + 10
    while time.monotonic() < limite:
        try:
            with httpx.Client(base_url=base_url, timeout=0.5) as cliente:
                respuesta = cliente.get("/health")
                if respuesta.status_code == 200:
                    return
        except httpx.HTTPError:
            time.sleep(0.05)
    raise RuntimeError("El servidor de integración no quedó disponible a tiempo.")


def _limpiar_rate_limiter() -> None:
    """Aísla los contadores del limitador entre pruebas de integración."""

    limitador._limiter.storage.reset()


@pytest.fixture
def cliente_api(sesion_bd, tmp_path, usuario_portal):
    """Cliente HTTP contra la app real con dependencias externas sustituidas."""

    _preparar_entorno_de_integracion()
    _limpiar_rate_limiter()

    notificador = NotificadorEnMemoria()
    alertas_portal = AlertasPortalEnMemoria()
    orquestador = OrquestadorEnMemoria()
    zoho_sign = ZohoSignEnMemoria()

    def usar_sesion_de_prueba():
        yield sesion_bd

    async def usar_usuario_de_prueba():
        return usuario_portal

    def usar_notificador_de_prueba():
        return notificador

    aplicacion_sagrilaft.dependency_overrides[get_db] = usar_sesion_de_prueba
    aplicacion_sagrilaft.dependency_overrides[portal_interno] = usar_usuario_de_prueba
    aplicacion_sagrilaft.dependency_overrides[obtener_servicio_email] = (
        usar_notificador_de_prueba
    )

    modulo_app.crear_orquestador_validacion = lambda _config: orquestador
    modulo_app.crear_alertas_portal = lambda _config: alertas_portal
    modulo_app.ZohoSignService = lambda _config: zoho_sign

    aplicacion_sagrilaft.state.config = load_config()
    aplicacion_sagrilaft.state.storage = LocalStorage(tmp_path / "uploads")
    aplicacion_sagrilaft.state.orchestrator = orquestador
    aplicacion_sagrilaft.state.zoho_sign = zoho_sign
    aplicacion_sagrilaft.state.alertas_portal = alertas_portal
    aplicacion_sagrilaft.state.notificador = notificador

    puerto = _obtener_puerto_local_libre()
    base_url = f"http://127.0.0.1:{puerto}"
    config_servidor = uvicorn.Config(
        aplicacion_sagrilaft,
        host="127.0.0.1",
        port=puerto,
        log_level="warning",
        lifespan="off",
    )
    servidor = uvicorn.Server(config_servidor)
    hilo_servidor = threading.Thread(target=servidor.run, daemon=True)
    hilo_servidor.start()
    _esperar_servidor(base_url)

    cliente = httpx.Client(base_url=base_url, timeout=10.0)
    try:
        yield cliente
    finally:
        cliente.close()
        servidor.should_exit = True
        hilo_servidor.join(timeout=5)

    _limpiar_rate_limiter()
    aplicacion_sagrilaft.dependency_overrides.clear()
    _restaurar_entorno_original()


@pytest.fixture
def dependencias_dobles(cliente_api):
    """Expone los dobles instalados en la app para hacer aserciones de dominio."""

    return {
        "extractor_ia": aplicacion_sagrilaft.state.orchestrator.extractor,
        "zoho_sign": aplicacion_sagrilaft.state.zoho_sign,
        "alertas_portal": aplicacion_sagrilaft.state.alertas_portal,
        "notificador": aplicacion_sagrilaft.state.notificador,
        "storage": aplicacion_sagrilaft.state.storage,
    }
