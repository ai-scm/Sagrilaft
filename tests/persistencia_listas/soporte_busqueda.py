"""Composición reutilizable del buscador sobre la base temporal del arnés."""
from infrastructure.config.configuracion import SagrilaftListasConfig
from infrastructure.persistencia.repositorios.busqueda_listas import RepositorioBusquedaListas
from services.listas.motor_busqueda import CATALOGO_MOTOR
from services.listas.politica_v2 import ActorListas, PoliticaListasV2
from services.listas.trabajador import TrabajadorListas


def habilitar_archivos(escenario, monkeypatch, codigo_fuente):
    configuracion = SagrilaftListasConfig(proveedor=None, implementacion="archivos", admin_habilitada=True)
    politica = PoliticaListasV2(configuracion,"development")
    escenario.busqueda = RepositorioBusquedaListas(escenario.sesiones,escenario.custodia,politica,CATALOGO_MOTOR)
    actor = ActorListas.desde_identidad_validada(escenario.app.state.config.keycloak.issuer,"operador-local",("listas_cargador",))
    escenario.generacion = escenario.busqueda.preparar(actor,escenario.version)
    escenario.app.state.config.listas_cautela = configuracion
    monkeypatch.setenv("LISTAS_ARCHIVOS_LOCAL_HABILITADA","true")
    monkeypatch.setenv("LISTAS_ARCHIVOS_FUENTES",codigo_fuente)
    monkeypatch.setenv("LISTAS_ARCHIVOS_POLITICA_ID",str(escenario.politica_id))
    escenario.trabajador = TrabajadorListas(escenario.sesiones,politica,escenario.custodia)
    escenario.cliente.headers["Authorization"] = "Bearer " + escenario.token()
