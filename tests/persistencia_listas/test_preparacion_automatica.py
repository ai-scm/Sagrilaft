"""El trabajador prepara la búsqueda solo de versiones activadas por una persona."""
import pytest
from sqlalchemy import func, select

from infrastructure.persistencia.modelos_busqueda_listas import GeneracionBusqueda
from services.listas.trabajador_preparacion_busqueda import TrabajadorPreparacionBusqueda
from .test_busqueda_f62 import busqueda, activar  # noqa: F401
from .test_administracion_f55 import administracion  # noqa: F401
from .test_flujo_http import portal  # noqa: F401
from .test_recepcion_f52 import carga  # noqa: F401


def trabajador(a, reloj=None):
    extra = {"reloj": reloj} if reloj else {}
    return TrabajadorPreparacionBusqueda(a.sesiones, a.custodia, a.busqueda.politica, "development", True,
                                         catalogo=a.busqueda.catalogo, **extra)


def generaciones(a):
    with a.sesiones() as sesion:
        return sesion.scalar(select(func.count()).select_from(GeneracionBusqueda))


def test_no_prepara_versiones_sin_activar(busqueda):
    a = busqueda
    assert trabajador(a).ejecutar_uno() is False
    assert generaciones(a) == 0


def test_prepara_la_version_activa_una_sola_vez(busqueda):
    a = busqueda
    activar(a)
    t = trabajador(a)
    assert t.ejecutar_uno() is True
    assert generaciones(a) == 1
    assert t.ejecutar_uno() is False  # idempotente: ya existe para la receta vigente
    assert generaciones(a) == 1


def test_fallo_no_reintenta_en_bucle_y_reintenta_tras_la_espera(busqueda, monkeypatch):
    a = busqueda
    activar(a)
    ahora = [1000.0]
    t = trabajador(a, reloj=lambda: ahora[0])
    llamadas = []
    from domain.listas.errores import ErrorIntegridadEvidencia
    original = t.repositorio.preparar
    def falla(*args, **kwargs):
        llamadas.append(1)
        raise ErrorIntegridadEvidencia("simulado")
    monkeypatch.setattr(t.repositorio, "preparar", falla)
    assert t.ejecutar_uno() is False and len(llamadas) == 1
    assert t.ejecutar_uno() is False and len(llamadas) == 1  # en espera
    ahora[0] += 301
    monkeypatch.setattr(t.repositorio, "preparar", original)
    assert t.ejecutar_uno() is True and generaciones(a) == 1


def test_actor_tecnico_no_puede_aprobar_ni_activar():
    from services.listas.trabajador_preparacion_busqueda import ACTOR_PREPARACION
    assert ACTOR_PREPARACION.permisos == frozenset({"listas.comparar"})
