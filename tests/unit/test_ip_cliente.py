"""
IP real del cliente detrás del balanceador (api/ip_cliente.py).

En AWS el backend recibe todas las conexiones desde la IP privada del ALB
(10.0.x.x) y el ALB agrega la IP real al final de X-Forwarded-For. Antes de este
cambio el backend usaba la IP del ALB, así que todos los clientes compartían el
mismo cupo del limitador y los registros de seguridad no tenían la IP real.
"""

from pathlib import Path

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.extension import _rate_limit_exceeded_handler

from api import ip_cliente as modulo
from api.ip_cliente import interpretar_redes, ip_cliente, redes_confiables, resolver_ip_cliente
from api.limitador import limitador

VPC = interpretar_redes("10.0.0.0/16")
ALB = "10.0.0.213"
CLIENTE = "200.1.1.1"
OTRO_CLIENTE = "181.50.2.3"


# ── Regla pura ───────────────────────────────────────────────────────────────

def test_desde_el_alb_usa_la_ip_que_agrego_el_alb():
    assert resolver_ip_cliente(ALB, CLIENTE, VPC) == CLIENTE


def test_una_ip_falsa_escrita_por_el_cliente_se_ignora():
    # El cliente envía "X-Forwarded-For: 1.2.3.4"; el ALB agrega su IP real al final.
    assert resolver_ip_cliente(ALB, f"1.2.3.4, {CLIENTE}", VPC) == CLIENTE


def test_varias_ips_falsas_tampoco_cuentan():
    assert resolver_ip_cliente(ALB, f"1.1.1.1, 2.2.2.2, 3.3.3.3, {CLIENTE}", VPC) == CLIENTE


def test_sin_cabecera_usa_la_conexion():
    assert resolver_ip_cliente(ALB, None, VPC) == ALB
    assert resolver_ip_cliente(ALB, "", VPC) == ALB


def test_conexion_que_no_es_de_confianza_ignora_la_cabecera():
    # Alguien que llegara al backend sin pasar por el ALB no puede elegir su IP.
    assert resolver_ip_cliente(CLIENTE, "1.2.3.4", VPC) == CLIENTE


def test_salta_proxies_de_confianza_encadenados():
    # Local: navegador → nginx (172.x) → backend. nginx también es de confianza.
    redes = interpretar_redes("172.16.0.0/12")
    assert resolver_ip_cliente("172.18.0.5", f"{CLIENTE}, 172.18.0.9", redes) == CLIENTE


def test_cadena_solo_de_confianza_usa_la_conexion():
    assert resolver_ip_cliente(ALB, "10.0.1.7", VPC) == ALB


def test_entrada_mal_formada_no_se_usa():
    assert resolver_ip_cliente(ALB, f"{CLIENTE}, no-es-ip", VPC) == ALB
    assert resolver_ip_cliente(ALB, f"{CLIENTE}:443", VPC) == ALB


def test_origen_desconocido_o_no_ip():
    assert resolver_ip_cliente(None, CLIENTE, VPC) == "unknown"
    assert resolver_ip_cliente("testclient", CLIENTE, VPC) == "testclient"


def test_ipv6():
    redes = interpretar_redes("10.0.0.0/16,fd00::/8")
    assert resolver_ip_cliente("fd00::1", "2001:db8::5", redes) == "2001:db8::5"


# ── Configuración ────────────────────────────────────────────────────────────

def test_interpreta_ips_y_rangos_separados_por_coma():
    redes = interpretar_redes(" 10.0.0.0/16 , 127.0.0.1 ,")
    assert [str(r) for r in redes] == ["10.0.0.0/16", "127.0.0.1/32"]


def test_valor_invalido_falla_con_mensaje_claro():
    with pytest.raises(ValueError, match="TRUSTED_PROXY_IPS"):
        interpretar_redes("10.0.0.0/16,*")


@pytest.fixture
def redes_desde_entorno(monkeypatch):
    def _configurar(valor):
        if valor is None:
            monkeypatch.delenv("TRUSTED_PROXY_IPS", raising=False)
        else:
            monkeypatch.setenv("TRUSTED_PROXY_IPS", valor)
        redes_confiables.cache_clear()
    yield _configurar
    redes_confiables.cache_clear()


def test_sin_variable_solo_confia_en_localhost(redes_desde_entorno):
    redes_desde_entorno(None)
    assert [str(r) for r in redes_confiables()] == ["127.0.0.1/32"]


def test_valor_de_aws_confia_en_la_vpc(redes_desde_entorno):
    redes_desde_entorno("10.0.0.0/16")
    assert resolver_ip_cliente(ALB, CLIENTE, redes_confiables()) == CLIENTE


def test_valor_anterior_172_no_cubre_el_alb(redes_desde_entorno):
    # Documenta el fallo original: con 172.0.0.0/8 la IP del ALB no es de confianza.
    redes_desde_entorno("172.0.0.0/8")
    assert resolver_ip_cliente(ALB, CLIENTE, redes_confiables()) == ALB


# ── Con peticiones reales ────────────────────────────────────────────────────

def _desde(ip_conexion, app):
    """Envuelve la app para que la conexión llegue desde ``ip_conexion`` (como el ALB)."""

    async def envoltura(scope, receive, send):
        if scope["type"] == "http":
            scope = dict(scope, client=(ip_conexion, 40000))
        await app(scope, receive, send)

    return envoltura


def _app_con_limite(limite: str) -> FastAPI:
    lim = Limiter(key_func=ip_cliente)
    app = FastAPI()
    app.state.limiter = lim
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    @app.get("/ip")
    @lim.limit(limite)
    def ver_ip(request: Request):
        return {"ip": ip_cliente(request)}

    return app


@pytest.fixture
def vpc_en_entorno(redes_desde_entorno):
    redes_desde_entorno("10.0.0.0/16")


def test_la_peticion_ve_la_ip_real(vpc_en_entorno):
    cliente = TestClient(_desde(ALB, _app_con_limite("100/minute")))
    r = cliente.get("/ip", headers={"X-Forwarded-For": f"1.2.3.4, {CLIENTE}"})
    assert r.json() == {"ip": CLIENTE}


def test_cada_cliente_tiene_su_propio_cupo(vpc_en_entorno):
    cliente = TestClient(_desde(ALB, _app_con_limite("2/minute")))

    def pedir(ip):
        return cliente.get("/ip", headers={"X-Forwarded-For": ip}).status_code

    assert [pedir(CLIENTE), pedir(CLIENTE), pedir(CLIENTE)] == [200, 200, 429]
    # Otro cliente detrás del mismo ALB no queda bloqueado por el primero.
    assert [pedir(OTRO_CLIENTE), pedir(OTRO_CLIENTE)] == [200, 200]


def test_cambiar_la_ip_falsa_no_salta_el_limite(vpc_en_entorno):
    cliente = TestClient(_desde(ALB, _app_con_limite("2/minute")))
    codigos = [
        cliente.get("/ip", headers={"X-Forwarded-For": f"9.9.9.{i}, {CLIENTE}"}).status_code
        for i in range(3)
    ]
    assert codigos == [200, 200, 429]


# ── Cableado ─────────────────────────────────────────────────────────────────

def test_el_limitador_de_la_app_usa_la_ip_real():
    assert limitador._key_func is ip_cliente


def test_uvicorn_no_reescribe_la_ip():
    entrypoint = (Path(modulo.__file__).resolve().parents[1] / "entrypoint.sh").read_text()
    assert "--no-proxy-headers" in entrypoint
    assert "--forwarded-allow-ips" not in entrypoint
    assert "\n    --proxy-headers" not in entrypoint
