"""Fijación 2.1 dentro de la misma transacción que crea la consulta y su trabajo."""
from dataclasses import asdict
from uuid import uuid4

from sqlalchemy import select

from domain.listas.catalogos_busqueda import CatalogoPreparacion
from domain.listas.contratos_busqueda import ManifiestoBusqueda
from domain.listas.errores import ErrorIntegridadEvidencia, VersionNoDisponible
from infrastructure.listas.adaptadores_busqueda import obtener_lector
from infrastructure.listas.representacion_busqueda import NORMALIZACION_BUSQUEDA
from infrastructure.persistencia.modelos_busqueda_listas import GeneracionBusqueda
from infrastructure.persistencia.modelos_listas import ConsultaFuente, FuenteLista, FuenteVersionActiva, PoliticaListas, VersionFuente
from infrastructure.persistencia.repositorios.busqueda_listas import RepositorioBusquedaListas
from services.listas.informes import calcular_huella
from services.listas.motor_busqueda import CATALOGO_MOTOR, MotorBusqueda, ParametrosMotor, VERSION_REGLAS, VERSION_ALGORITMO

VERSION_ADAPTADOR = "archivos-f64-v1"


def sellar_manifiesto(datos):
    return {**datos, "huella": calcular_huella(datos)}


def leer_manifiesto(datos):
    copia = dict(datos)
    huella = copia.pop("huella", None)
    if huella != calcular_huella(copia):
        raise ErrorIntegridadEvidencia("Manifiesto de búsqueda alterado")
    busqueda = ManifiestoBusqueda.model_validate(copia["busqueda"])
    catalogo = CatalogoPreparacion.model_validate(copia["catalogo"])
    parametros = ParametrosMotor(**copia["parametros"])
    if (copia.get("adaptador"), busqueda.reglas_version, busqueda.algoritmo_version,
            busqueda.catalogos_hash, busqueda.parametros_internos_hash) != (
            VERSION_ADAPTADOR, VERSION_REGLAS, VERSION_ALGORITMO, catalogo.huella, parametros.huella):
        raise VersionNoDisponible("La receta admitida no está disponible; no se sustituye")
    return busqueda, catalogo, parametros


class AdmisionArchivos:
    def __init__(self, sesiones, custodia, politica, configuracion):
        self.configuracion = configuracion
        self.busqueda = RepositorioBusquedaListas(sesiones, custodia, politica, CATALOGO_MOTOR)

    def preparar(self, sesion, consulta_id, solicitud, criterio, preparacion=None):
        politica = sesion.get(PoliticaListas, self.configuracion.politica_id)
        if politica is None or politica.parametros.get("solo_pruebas") is not True:
            raise VersionNoDisponible("Se requiere política explícita de pruebas; no se asume vigencia productiva")
        if politica.huella != calcular_huella(politica.parametros):
            raise ErrorIntegridadEvidencia("Política de pruebas alterada")
        parametros = ParametrosMotor()
        MotorBusqueda(CATALOGO_MOTOR, parametros).validar_criterio(criterio)
        fijadas, coberturas = [], []
        for codigo in sorted(self.configuracion.fuentes):
            fuente = sesion.scalar(select(FuenteLista).where(FuenteLista.codigo == codigo))
            if fuente is None:
                raise VersionNoDisponible("Fuente requerida no registrada")
            puntero = sesion.scalar(select(FuenteVersionActiva).where(FuenteVersionActiva.fuente_id == fuente.id)
                .with_for_update(read=True).execution_options(populate_existing=True))
            if puntero is None or puntero.version_id is None:
                raise VersionNoDisponible("Fuente requerida sin versión activa")
            version = sesion.get(VersionFuente, puntero.version_id, populate_existing=True)
            lector = obtener_lector(version.formato)
            generacion = sesion.scalar(select(GeneracionBusqueda).where(
                GeneracionBusqueda.version_id == version.id,
                GeneracionBusqueda.catalogo_huella == CATALOGO_MOTOR.huella,
                GeneracionBusqueda.adaptador_version == lector.VERSION_ADAPTADOR,
                GeneracionBusqueda.normalizacion_version == NORMALIZACION_BUSQUEDA))
            if generacion is None:
                raise VersionNoDisponible("Falta preparar la generación de búsqueda para la receta activa")
            fijada = self.busqueda.fijar_activas(sesion, {codigo: generacion.id})[0]
            fijadas.append(fijada)
            coberturas.append(ConsultaFuente(id=uuid4(), consulta_id=consulta_id, fuente_id=fuente.id,
                version_id=version.id, revision_activa=fijada.revision_activa, nombre_origen=fuente.nombre,
                estado="PENDIENTE", requerida=True, detalle={"huella_contenido": version.huella_contenido,
                    "fuente_codigo": codigo, "fijada": fijada.model_dump(mode="json")}))
        manifiesto = ManifiestoBusqueda(politica_version=str(politica.id), reglas_version=VERSION_REGLAS,
            algoritmo_version=VERSION_ALGORITMO, catalogos_hash=CATALOGO_MOTOR.huella,
            parametros_internos_hash=parametros.huella, fuentes=fijadas)
        datos = dict(implementacion="archivos", adaptador=VERSION_ADAPTADOR,
            busqueda=manifiesto.model_dump(mode="json"), catalogo=CATALOGO_MOTOR.model_dump(mode="json"),
            parametros=asdict(parametros), politica_huella=politica.huella,
            solicitud_original=solicitud.model_dump(mode="json"), criterio_efectivo=criterio.model_dump(mode="json"), preparacion=preparacion)
        return sellar_manifiesto(datos), coberturas
