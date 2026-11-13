"""F3: HTTP, JWT firmado, PostgreSQL y PDF reales; sin servicios externos."""
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select, text, func

from api import dependencias_listas
from api.middleware import autenticacion
from api.routers import consultas_listas, listas_cautela, expedientes
from infrastructure.config.configuracion import KeycloakConfig, SagrilaftListasConfig
from infrastructure.persistencia.models import Formulario, ResultadoValidacion
from infrastructure.persistencia.modelos_listas import ConsultaLista, TrabajoConsulta, EvidenciaConsulta
from infrastructure.persistencia.modelos_grupos_listas import GrupoConsultaLista
from infrastructure.listas.custodia import CustodiaLocalListas
from services.listas.politica_v2 import PoliticaListasV2
from services.listas.trabajador import TrabajadorListas
from .conftest import RAIZ


@pytest.fixture
def portal(sesiones, tmp_path, monkeypatch):
    configuracion = SagrilaftListasConfig(proveedor=None, implementacion="simulado", escenario="coincidencia_v1")
    keycloak = KeycloakConfig(url="http://identidad.local", realm="pruebas", client_id="portal")
    clave = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(clave.public_key()))
    jwk.update(kid="clave-local", use="sig", alg="RS256")
    async def claves_locales(_):
        return {"keys": [jwk]}
    monkeypatch.setattr(autenticacion, "_obtener_jwks", claves_locales)
    monkeypatch.setattr(autenticacion, "_AUTH_DESHABILITADA", False)
    aplicacion = FastAPI()
    aplicacion.state.config = SimpleNamespace(keycloak=keycloak, listas_cautela=configuracion, entorno="development")
    aplicacion.include_router(consultas_listas.enrutador)
    aplicacion.include_router(listas_cautela.enrutador)
    aplicacion.include_router(expedientes.enrutador)
    custodia = CustodiaLocalListas(tmp_path / "custodia")
    aplicacion.dependency_overrides[dependencias_listas.sesiones_listas] = lambda: sesiones
    aplicacion.dependency_overrides[dependencias_listas.custodia_listas] = lambda: custodia
    expediente_id, ajeno_id = str(uuid4()), str(uuid4())
    with sesiones.begin() as sesion:
        for identificador, carpeta in ((expediente_id, "cliente"), (ajeno_id, "proveedor")):
            sesion.add(Formulario(id=identificador, tipo_contraparte=carpeta, estado="enviado", razon_social="Empresa ficticia",
                numero_identificacion="00001234", tipo_identificacion="NIT", nombre_representante="Persona ficticia",
                numero_doc_representante="00004321", tipo_doc_representante="CC", sagrilaft_reporte_id="reporte-heredado"))
    def token(roles=None, sin_exp=False, **cambios):
        contenido = {"sub": "operador-local", "iss": keycloak.issuer, "aud": "portal", "azp": "portal",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
            "realm_access": {"roles": roles if roles is not None else ["acceso_clientes", "listas_revisor"]}}
        contenido.update(cambios)
        if sin_exp:
            contenido.pop("exp")
        return jwt.encode(contenido, clave, algorithm="RS256", headers={"kid": "clave-local"})
    cliente = TestClient(aplicacion)
    cliente.headers["Authorization"] = f"Bearer {token()}"
    trabajador = TrabajadorListas(sesiones, PoliticaListasV2(configuracion, "development"), custodia)
    yield SimpleNamespace(cliente=cliente, app=aplicacion, expediente=expediente_id, ajeno=ajeno_id,
        token=token, trabajador=trabajador, sesiones=sesiones, custodia=custodia)
    cliente.close()


def crear(portal, clave="consulta-1", expediente=None):
    return portal.cliente.post(f"/api/expedientes/{expediente or portal.expediente}/consultas-listas",
        headers={"Idempotency-Key": clave}, json={"criterio": {"tipo_sujeto": "PERSONA", "nombre": "Persona ficticia"}})


def finalizar(portal):
    respuesta = crear(portal)
    assert respuesta.status_code == 202, respuesta.text
    consulta_id = respuesta.json()["consulta_id"]
    assert portal.trabajador.ejecutar_uno()
    respuesta = portal.cliente.get(f"/api/consultas-listas/{consulta_id}")
    assert respuesta.status_code == 200, respuesta.text
    return respuesta.json()


@pytest.mark.parametrize("escenario,estado,conclusion", [
    ("coincidencia_v1", "COMPLETADA", "CON_CANDIDATOS"),
    ("sin_coincidencias_v1", "COMPLETADA", "SIN_CANDIDATOS"),
    ("parcial_v1", "PARCIAL", "NO_CONCLUYENTE"),
    ("error_v1", "FALLIDA", "NO_CONCLUYENTE"),
])
def test_http_completo_no_decide_estado_ni_riesgo(portal, escenario, estado, conclusion):
    portal.app.state.config.listas_cautela = SagrilaftListasConfig(proveedor=None, implementacion="simulado", escenario=escenario)
    detalle = finalizar(portal)
    consulta = detalle["consulta"]
    assert consulta["estado_ejecucion"] == estado and consulta["conclusion_busqueda"] == conclusion
    assert "riesgo" not in consulta
    evidencia = consulta["evidencias"][0]["id"]
    pdf = portal.cliente.get(f"/api/consultas-listas/{consulta['consulta_id']}/evidencias/{evidencia}")
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    with portal.sesiones() as sesion:
        expediente = sesion.get(Formulario, portal.expediente)
        assert expediente.estado == "enviado" and expediente.sagrilaft_reporte_id == "reporte-heredado"


@pytest.mark.parametrize("cambios", [{"exp": 1}, {"iss": "otro"}, {"aud": "otro"}, {"azp": "otro"}, {"sub": ""}, {"sin_exp": True}, {"exp": None}])
def test_jwt_invalido_no_admite(portal, cambios):
    portal.cliente.headers["Authorization"] = f"Bearer {portal.token(**cambios)}"
    assert crear(portal).status_code == 401
    with portal.sesiones() as sesion:
        assert sesion.scalar(select(func.count()).select_from(ConsultaLista)) == 0


def test_firma_y_ausencia_token(portal):
    portal.cliente.headers.pop("Authorization")
    assert crear(portal).status_code == 401
    portal.cliente.headers["Authorization"] = "Bearer token.invalido.firma"
    assert crear(portal).status_code == 401


def test_roles_y_acceso_cruzado(portal):
    assert crear(portal, expediente=portal.ajeno).status_code == 404
    portal.cliente.headers["Authorization"] = f"Bearer {portal.token(['acceso_clientes'])}"
    assert crear(portal).status_code == 403


def test_grupo_atomico_y_reintento_preserva_datos_originales(portal):
    ruta = f"/api/expedientes/{portal.expediente}/consultas-listas/grupos"
    respuesta = portal.cliente.post(ruta, headers={"Idempotency-Key": "ambos"})
    assert respuesta.status_code == 202, respuesta.text
    assert len(respuesta.json()["consultas"]) == 2
    with portal.sesiones.begin() as sesion:
        sesion.get(Formulario, portal.expediente).nombre_representante = "Cambio posterior"
    assert portal.cliente.post(ruta, headers={"Idempotency-Key": "ambos"}).json() == respuesta.json()
    assert portal.trabajador.ejecutar_uno() and portal.trabajador.ejecutar_uno()
    for consulta in respuesta.json()["consultas"]:
        detalle = portal.cliente.get(f"/api/consultas-listas/{consulta['consulta_id']}").json()["consulta"]
        assert detalle["estado_ejecucion"] == "COMPLETADA"
        assert detalle["criterio"]["nombre"] != "Cambio posterior"
    with portal.sesiones() as sesion:
        assert sesion.scalar(select(func.count()).select_from(GrupoConsultaLista)) == 1


def test_historial_reconsulta_pdf_y_revision_aditiva(portal):
    detalle = finalizar(portal)["consulta"]
    ruta = f"/api/consultas-listas/{detalle['consulta_id']}"
    pdf_ruta = f"{ruta}/evidencias/{detalle['evidencias'][0]['id']}"
    original = portal.cliente.get(pdf_ruta).content
    revision = portal.cliente.post(f"{ruta}/revisiones", json={"resultado": "DESCARTADA", "justificacion": "Documento distinto"})
    assert revision.status_code == 201, revision.text
    assert portal.cliente.post(f"{ruta}/revisiones", json={"resultado": "REQUIERE_INFORMACION", "justificacion": "Revisión adicional",
        "revision_previa_id": revision.json()["revision_id"]}).status_code == 201
    assert crear(portal, "segunda").status_code == 202
    portal.trabajador.ejecutar_uno()
    historial = portal.cliente.get(f"/api/expedientes/{portal.expediente}/consultas-listas?limite=1").json()
    assert historial["siguiente"] and historial["legado"]["reporte_id"] == "reporte-heredado"
    assert len(portal.cliente.get(f"{ruta}").json()["revisiones"]) == 2
    portal.app.state.config.listas_cautela = SagrilaftListasConfig(proveedor="deshabilitado")
    assert crear(portal, "tercera").status_code == 409
    assert portal.cliente.get(pdf_ruta).content == original
    portal.cliente.headers["Authorization"] = f"Bearer {portal.token(['acceso_proveedores', 'listas_revisor'])}"
    assert portal.cliente.get(pdf_ruta).status_code == 404


def test_consultor_no_revisa_y_referencias_ajenas_no_valen(portal):
    detalle = finalizar(portal)["consulta"]
    ruta = f"/api/consultas-listas/{detalle['consulta_id']}/revisiones"
    portal.cliente.headers["Authorization"] = f"Bearer {portal.token(['acceso_clientes','listas_operador'])}"
    assert portal.cliente.post(ruta, json={"resultado": "DESCARTADA", "justificacion": "Prueba"}).status_code == 403
    portal.cliente.headers["Authorization"] = f"Bearer {portal.token()}"
    assert portal.cliente.post(ruta, json={"resultado": "DESCARTADA", "justificacion": "Prueba", "coincidencia_id": str(uuid4())}).status_code == 404


def test_reinicio_real_trabajador_utiliza_manifiesto_admitido(portal):
    respuesta = crear(portal)
    consulta_id = respuesta.json()["consulta_id"]
    concesion = portal.trabajador.repositorio.reclamar(UUID(consulta_id), 1)
    with portal.sesiones.begin() as sesion:
        sesion.execute(text("UPDATE trabajo_consulta SET concesion_hasta=now()-interval '1 second' WHERE consulta_id=:id"), {"id": consulta_id})
    entorno = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "LANG": "C.UTF-8", "APP_ENV": "development",
        "DATABASE_URL": os.environ["LISTAS_PRUEBA_URL"], "LISTAS_PRUEBA_DIRECTORIO": os.environ["LISTAS_PRUEBA_DIRECTORIO"],
        "LISTAS_CUSTODIA_DIRECTORIO": str(portal.custodia.directorio), "SECRET_KEY": "local", "PORTAL_INTERNO_URL": "http://portal.test",
        "PROVEEDOR_LISTAS_CAUTELA": "deshabilitado", "AWS_EC2_METADATA_DISABLED": "true"}
    for _ in range(2):
        subprocess.run([sys.executable, str(RAIZ / "scripts/validacion/ejecutar_trabajador_listas.py"), "--una-vez"], env=entorno, check=True, capture_output=True)
    consulta = portal.cliente.get(f"/api/consultas-listas/{consulta_id}").json()["consulta"]
    assert consulta["conclusion_busqueda"] == "CON_CANDIDATOS"
    with portal.sesiones() as sesion:
        assert sesion.scalar(select(func.count()).select_from(EvidenciaConsulta)) == 1


def test_rutas_anteriores_no_ejecutan_ni_deciden(portal):
    for ruta in (f"/api/expedientes/{portal.expediente}/verificar-sagrilaft", "/api/listas-cautela/buscar"):
        assert portal.cliente.post(ruta).status_code == 410
    assert portal.cliente.get(f"/api/expedientes/{portal.expediente}/sagrilaft/pdf").status_code == 410


def test_limpieza_documental_preserva_antecedentes_de_listas(portal):
    from infrastructure.persistencia.repositorios.validacion import RepositorioValidacionSQLAlchemy
    with portal.sesiones.begin() as sesion:
        sesion.add(ResultadoValidacion(formulario_id=portal.expediente, tipo="lista_cautela", campo="Anterior", resultado="error", detalle="Antecedente"))
        sesion.add(ResultadoValidacion(formulario_id=portal.expediente, tipo="documento", campo="Prueba", resultado="ok", detalle="Prueba"))
    with portal.sesiones.begin() as sesion:
        RepositorioValidacionSQLAlchemy(sesion).limpiar_validaciones(portal.expediente)
    with portal.sesiones() as sesion:
        filas = list(sesion.scalars(select(ResultadoValidacion).where(ResultadoValidacion.formulario_id == portal.expediente)))
        assert len(filas) == 1 and filas[0].tipo == "lista_cautela"


@pytest.mark.parametrize("fallo_red", ["ninguno", "transitorio", "persistente"])
def test_navegador_con_api_postgres_y_trabajador_reales(portal, tmp_path, fallo_red, verificar_presentacion=False):
    import socket
    import threading
    import time
    import urllib.request
    import uvicorn
    def puerto_local():
        with socket.socket() as conexion:
            conexion.bind(("127.0.0.1", 0))
            return conexion.getsockname()[1]
    puerto_api, puerto_portal = puerto_local(), puerto_local()
    servidor = uvicorn.Server(uvicorn.Config(portal.app, host="127.0.0.1", port=puerto_api, log_level="error"))
    hilo = threading.Thread(target=servidor.run, daemon=True)
    terminar = threading.Event()
    errores = []
    def procesar():
        while not terminar.is_set():
            try:
                if not portal.trabajador.ejecutar_uno():
                    terminar.wait(0.1)
            except Exception as error:
                errores.append(type(error).__name__)
                terminar.set()
    trabajador = threading.Thread(target=procesar, daemon=True)
    entorno = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(Path.home()),
               "VITE_BACKEND_URL": f"http://127.0.0.1:{puerto_api}"}
    hilo.start()
    trabajador.start()
    with (tmp_path / "vite.log").open("w") as salida:
        vite = subprocess.Popen(["node", str(RAIZ / "frontend/node_modules/vite/bin/vite.js"), "--host", "127.0.0.1",
                                 "--port", str(puerto_portal), "--strictPort"], cwd=RAIZ / "frontend/apps/portal-interno", env=entorno,
                                stdout=salida, stderr=subprocess.STDOUT)
        try:
            url = f"http://127.0.0.1:{puerto_portal}"
            for _ in range(100):
                try:
                    with urllib.request.urlopen(url, timeout=0.2):
                        break
                except OSError:
                    time.sleep(0.1)
            parametros = tmp_path / "navegador.json"
            parametros.write_text(json.dumps({"url": url, "token": portal.token(), "fallo_red": fallo_red,
                "verificar_presentacion": verificar_presentacion,
                "mediciones": str(Path(os.environ["LISTAS_EVIDENCIAS_DIRECTORIO"]) / f"navegador-{tmp_path.name}-{fallo_red}.json"),
                "expediente": {"id": portal.expediente, "razon_social": "Empresa ficticia", "tipo_identificacion": "NIT", "numero_identificacion": "001234"},
                "captura": str(Path(os.environ["LISTAS_EVIDENCIAS_DIRECTORIO"]) / f"portal-{fallo_red}.png")}))
            parametros.chmod(0o600)
            resultado = subprocess.run(["node", str(RAIZ / "tests/navegador_listas/flujo.mjs"), str(parametros)],
                                       capture_output=True, text=True, timeout=60)
            assert resultado.returncode == 0, resultado.stdout + resultado.stderr
            assert errores == []
        finally:
            terminar.set()
            trabajador.join(timeout=10)
            servidor.should_exit = True
            hilo.join(timeout=10)
            vite.terminate()
            vite.wait(timeout=10)


def test_grupo_concurrente_no_duplica(portal):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    barrera = Barrier(2)
    def solicitar(_):
        barrera.wait()
        respuesta = portal.cliente.post(f"/api/expedientes/{portal.expediente}/consultas-listas/grupos", headers={"Idempotency-Key": "simultanea"})
        assert respuesta.status_code == 202, respuesta.text
        return respuesta.json()
    with ThreadPoolExecutor(max_workers=2) as ejecutor:
        respuestas = list(ejecutor.map(solicitar, range(2)))
    assert respuestas[0] == respuestas[1]
    with portal.sesiones() as sesion:
        assert sesion.scalar(select(func.count()).select_from(ConsultaLista)) == 2


def test_grupo_revierte_todos_los_hijos_si_falla_admision(portal, monkeypatch):
    from infrastructure.persistencia.repositorios.consultas_listas import RepositorioConsultasListas
    original = RepositorioConsultasListas.admitir
    contador = []
    def admitir(self, *argumentos, **opciones):
        contador.append(True)
        if len(contador) == 2:
            raise RuntimeError("Fallo simulado al admitir segundo sujeto")
        return original(self, *argumentos, **opciones)
    monkeypatch.setattr(RepositorioConsultasListas, "admitir", admitir)
    with pytest.raises(RuntimeError, match="segundo sujeto"):
        portal.cliente.post(f"/api/expedientes/{portal.expediente}/consultas-listas/grupos", headers={"Idempotency-Key": "rollback"})
    with portal.sesiones() as sesion:
        assert sesion.scalar(select(func.count()).select_from(ConsultaLista)) == 0
        assert sesion.scalar(select(func.count()).select_from(GrupoConsultaLista)) == 0


def test_grupo_informa_sujeto_sin_criterios(portal):
    with portal.sesiones.begin() as sesion:
        expediente = sesion.get(Formulario, portal.expediente)
        expediente.nombre_representante = None
        expediente.numero_doc_representante = None
    respuesta = portal.cliente.post(f"/api/expedientes/{portal.expediente}/consultas-listas/grupos", headers={"Idempotency-Key": "incompleta"})
    assert respuesta.status_code == 202, respuesta.text
    assert len(respuesta.json()["consultas"]) == 1
    assert respuesta.json()["no_consultados"][0]["sujeto_rol"] == "REPRESENTANTE"


def test_custodia_fallida_es_visible_sin_pdf_inventado(portal, monkeypatch):
    consulta_id = crear(portal).json()["consulta_id"]
    def fallar(_):
        raise OSError("Fallo simulado de disco")
    monkeypatch.setattr(portal.custodia, "guardar", fallar)
    assert portal.trabajador.ejecutar_uno()
    respuesta = portal.cliente.get(f"/api/consultas-listas/{consulta_id}")
    assert respuesta.status_code == 200, respuesta.text
    consulta = respuesta.json()["consulta"]
    assert consulta["estado_ejecucion"] == "FALLIDA"
    assert consulta["conclusion_busqueda"] == "NO_CONCLUYENTE"
    assert consulta["evidencias"] == []
    assert consulta["error"]["codigo"] == "CUSTODIA_NO_DISPONIBLE"


def test_evidencia_corrupta_no_se_entrega(portal):
    consulta = finalizar(portal)["consulta"]
    evidencia = consulta["evidencias"][0]
    (portal.custodia.directorio / evidencia["sha256"]).write_bytes(b"alteracion ficticia")
    respuesta = portal.cliente.get(f"/api/consultas-listas/{consulta['consulta_id']}/evidencias/{evidencia['id']}")
    assert respuesta.status_code == 503


def test_peticion_repetida_y_conflictiva(portal):
    primera = crear(portal)
    assert primera.status_code == 202
    assert crear(portal).json() == primera.json()
    distinta = portal.cliente.post(f"/api/expedientes/{portal.expediente}/consultas-listas", headers={"Idempotency-Key": "consulta-1"},
        json={"criterio": {"tipo_sujeto": "PERSONA", "nombre": "Otra persona ficticia"}})
    assert distinta.status_code == 409
