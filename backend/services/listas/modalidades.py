"""Registro único de modalidades de consulta.

Cada modalidad (simulado, archivos y externo) declara aquí su contrato,
su disponibilidad, su admisión y su ejecución. El servicio común, la ruta de
disponibilidad y el trabajador preguntan al registro en lugar de comparar nombres de
implementación, de modo que una modalidad nueva se agrega registrándola sin tocar
las demás.
"""
from uuid import UUID, uuid4

from domain.listas.puertos import ListasNoDisponibles
from services.listas.modalidad_base import (  # noqa: F401  (ConsultaAdmitida se reexporta al trabajador)
    ConsultaAdmitida, ModalidadListas, crear_grupo_por_documento, datos_sujeto,
)
from services.listas.modalidad_externa import ModalidadExterna


class ModalidadSimulada:
    """Escenarios ficticios versionados; nunca sustituye a otra modalidad."""
    implementacion = "simulado"
    version_contrato = "2.0"

    @staticmethod
    def _capacidades(escenario: str):
        from infrastructure.listas.simulado import SimuladorListasV2
        return SimuladorListasV2(escenario).capacidades()

    def disponible(self, entorno):
        return True

    def recuperar_reintento(self, servicio, solicitud, clave):
        # El repositorio resuelve el reintento 2.0 dentro de la misma admisión.
        return None

    def manifiesto(self, config) -> dict:
        capacidades = self._capacidades(config.escenario)
        return {"implementacion": self.implementacion, "proveedor": capacidades.proveedor,
                "adaptador": capacidades.adaptador_version, "algoritmo": capacidades.algoritmo_version,
                "escenario": config.escenario}

    def crear(self, servicio, solicitud, clave):
        from domain.listas.contratos import SolicitudIdempotente
        config = servicio.politica.config
        capacidades = self._capacidades(config.escenario)
        if any(i.tipo not in capacidades.tipos_identificador for i in solicitud.criterio.identificadores):
            raise ValueError("Tipo de identificador no soportado por el simulador")
        return servicio.repositorio.admitir(servicio.actor, SolicitudIdempotente(clave=clave, solicitud=solicitud),
                                            capacidades.proveedor, self.manifiesto(config))

    def crear_grupo(self, servicio, expediente_id, clave, sesion):
        config = servicio.politica.config
        capacidades = self._capacidades(config.escenario)
        tipos = set(capacidades.tipos_identificador)
        manifiesto = self.manifiesto(config)

        def criterio_para(rol, expediente):
            nombre, tipo, documento = datos_sujeto(rol, expediente)
            criterio = {"tipo_sujeto": "NO_DETERMINADO" if rol == "CONTRAPARTE" else "PERSONA"}
            if nombre and nombre.strip():
                criterio["nombre"] = nombre.strip()
            if documento and tipo in tipos:
                criterio["identificadores"] = [{"tipo": tipo, "valor": documento}]
            if len(criterio) == 1:
                return None, "No hay criterios utilizables por el simulador"
            return criterio, ""

        return crear_grupo_por_documento(servicio, expediente_id, clave, sesion, proveedor=capacidades.proveedor,
                                         criterio_para=criterio_para, manifiesto_para=lambda _criterio: manifiesto)

    def reconoce(self, consulta):
        return (consulta.implementacion == self.implementacion
                and consulta.manifiesto.get("adaptador") == "simulado-v1"
                and consulta.manifiesto.get("algoritmo") == "fixture-v1")

    def ejecutar(self, trabajador, concesion, consulta):
        from domain.listas.contratos import Criterio
        from domain.listas.errores import ErrorIntegridadEvidencia
        from domain.listas.puertos import SolicitudProveedorV2
        from infrastructure.listas.simulado import SimuladorListasV2
        from services.listas.consulta_v2 import EjecutorConsultaV2
        from services.listas.informes import calcular_huella
        if not consulta.tiene_borrador:
            # El escenario es el conservado en la admisión, no el configurado ahora.
            adaptador = SimuladorListasV2(consulta.manifiesto["escenario"])
            ejecutor = EjecutorConsultaV2(trabajador.repositorio.politica, adaptador, lambda *_: False)
            resultado = ejecutor.ejecutar_admitida(SolicitudProveedorV2(consulta_id=consulta.id,
                correlacion_id=uuid4(), criterio=Criterio.model_validate(consulta.criterio), implementacion="simulado",
                proveedor="simulador", adaptador_version="simulado-v1", algoritmo_version="fixture-v1",
                parametros={"escenario": consulta.manifiesto["escenario"]}, admitida_en=consulta.admitida_en,
                huella_configuracion=calcular_huella(consulta.manifiesto)))
            trabajador.repositorio.guardar_borrador(concesion, resultado)
        try:
            trabajador.repositorio.preparar_informe(concesion)
            trabajador.repositorio.cerrar(concesion)
        except (ErrorIntegridadEvidencia, OSError):
            trabajador.repositorio.fallar(concesion, "CUSTODIA_NO_DISPONIBLE")


class ModalidadArchivos:
    """Listas importadas en PostgreSQL y evaluadas con el buscador local."""
    implementacion = "archivos"
    version_contrato = "2.1"

    def disponible(self, entorno):
        from infrastructure.listas.configuracion_archivos import ConfiguracionArchivosLocal
        try:
            ConfiguracionArchivosLocal.cargar(entorno)
            return True
        except ListasNoDisponibles:
            return False

    def recuperar_reintento(self, servicio, solicitud, clave):
        from domain.listas.contratos_busqueda import SolicitudIdempotenteBusqueda
        from services.listas.servicio_archivos_portal import recuperar_reintento
        return recuperar_reintento(servicio, SolicitudIdempotenteBusqueda(clave=clave, solicitud=solicitud))

    def crear(self, servicio, solicitud, clave):
        from services.listas.servicio_archivos_portal import crear_individual
        return crear_individual(servicio, solicitud, clave)

    def crear_grupo(self, servicio, expediente_id, clave, sesion):
        from services.listas.servicio_archivos_portal import crear_grupo
        return crear_grupo(servicio, expediente_id, clave, sesion, uuid4())

    def reconoce(self, consulta):
        return consulta.implementacion == self.implementacion and consulta.version_contrato == self.version_contrato

    def ejecutar(self, trabajador, concesion, consulta):
        from sqlalchemy import select
        from domain.listas.contratos_busqueda import CriterioBusqueda, SolicitudBusquedaInterna
        from domain.listas.errores import ErrorIntegridadEvidencia, VersionNoDisponible
        from infrastructure.listas.fabrica import crear_consultor_archivos_local
        from infrastructure.persistencia.modelos_listas import ConsultaFuente, ConsultaLista
        from services.listas.admision_archivos import leer_manifiesto
        try:
            if not consulta.tiene_borrador:
                with trabajador.sesiones() as sesion:
                    fila = sesion.get(ConsultaLista, concesion.consulta_id)
                    manifiesto = fila.manifiesto
                    fijado, _, _ = leer_manifiesto(manifiesto)
                    coberturas = {c.detalle["fuente_codigo"]: {"id": c.id, "nombre": c.nombre_origen}
                        for c in sesion.scalars(select(ConsultaFuente).where(ConsultaFuente.consulta_id == fila.id))}
                    solicitud = SolicitudBusquedaInterna(consulta_id=fila.id, correlacion_id=fila.id,
                        contexto={"tipo": "EXPEDIENTE", "expediente_id": fila.expediente_id,
                                  "sujeto_rol": fila.sujeto_rol, "motivo": fila.motivo},
                        criterio=CriterioBusqueda.model_validate(fila.criterio_original), proveedor=fila.proveedor,
                        implementacion="archivos", admitida_en=fila.creado_en, manifiesto=fijado)
                adaptador = crear_consultor_archivos_local(trabajador.sesiones, trabajador.politica, trabajador.custodia,
                    trabajador.politica.entorno, manifiesto, coberturas)
                resultado = adaptador.consultar(solicitud)
                trabajador.repositorio.guardar_borrador(concesion, resultado)
            trabajador.repositorio.preparar_informe(concesion)
            trabajador.repositorio.cerrar(concesion)
        except VersionNoDisponible:
            trabajador.repositorio.fallar(concesion, "RECETA_O_VERSION_NO_DISPONIBLE")
        except (ErrorIntegridadEvidencia, OSError):
            trabajador.repositorio.fallar(concesion, "INTEGRIDAD_O_CUSTODIA_NO_DISPONIBLE")
        except (ValueError, KeyError, TypeError):
            trabajador.repositorio.fallar(concesion, "DATOS_ADMITIDOS_NO_INTERPRETABLES")


# El orden no importa: cada implementación tiene una sola modalidad.
MODALIDADES: dict[str, ModalidadListas] = {
    ModalidadSimulada.implementacion: ModalidadSimulada(),
    ModalidadArchivos.implementacion: ModalidadArchivos(),
    ModalidadExterna.implementacion: ModalidadExterna(),
}


def modalidad_vigente(config) -> ModalidadListas:
    """La modalidad configurada; deshabilitado o pendiente nunca se sustituye por otra."""
    if config.implementacion == "deshabilitado":
        raise ListasNoDisponibles("Consultas deshabilitadas")
    try:
        return MODALIDADES[config.implementacion]
    except KeyError:
        raise ListasNoDisponibles(f"Modalidad {config.implementacion} pendiente de implementación") from None


def reintento_admitido(servicio, solicitud, clave) -> UUID | None:
    """Un reintento ya admitido se responde igual aunque la configuración haya cambiado después."""
    for modalidad in MODALIDADES.values():
        if modalidad.version_contrato == solicitud.version_contrato:
            anterior = modalidad.recuperar_reintento(servicio, solicitud, clave)
            if anterior:
                return anterior
    return None


def modalidad_disponible(config, entorno) -> ModalidadListas | None:
    try:
        modalidad = modalidad_vigente(config)
    except ListasNoDisponibles:
        return None
    return modalidad if modalidad.disponible(entorno) else None


def modalidad_de_consulta(consulta: ConsultaAdmitida) -> ModalidadListas | None:
    """La modalidad que admitió la consulta, aunque la configuración haya cambiado después."""
    return next((m for m in MODALIDADES.values() if m.reconoce(consulta)), None)
