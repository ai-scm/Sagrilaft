"""Ejecutor recuperable. Solo consume trabajos ya admitidos y conserva su escenario."""
import logging
from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import select, or_
from domain.listas.contratos import Criterio
from domain.listas.contratos_busqueda import CriterioBusqueda, SolicitudBusquedaInterna
from domain.listas.puertos import SolicitudProveedorV2
from domain.listas.errores import TrabajoNoVigente, ErrorIntegridadEvidencia, VersionNoDisponible
from infrastructure.listas.simulado import SimuladorListasV2
from infrastructure.persistencia.modelos_listas import ConsultaLista, ConsultaFuente, TrabajoConsulta, BorradorConsulta
from infrastructure.persistencia.repositorios.consultas_listas import RepositorioConsultasListas
from services.listas.informes import calcular_huella
from services.listas.consulta_v2 import EjecutorConsultaV2

registro = logging.getLogger(__name__)


class TrabajadorListas:
    def __init__(self, sesiones, politica, custodia):
        self.sesiones = sesiones
        self.politica, self.custodia = politica, custodia
        # No es una entrada pública: trabaja exclusivamente sobre admisiones persistidas.
        self.repositorio = RepositorioConsultasListas(sesiones, politica, custodia,
            lambda *_: False, lambda *_: False, self._sin_archivos)

    @staticmethod
    def _sin_archivos(*_):
        raise RuntimeError("Archivos no implementado en F3")

    def ejecutar_uno(self):
        with self.sesiones() as sesion:
            identificador = sesion.scalar(select(TrabajoConsulta.consulta_id).where(
                TrabajoConsulta.fase != "FINALIZADA",
                or_(TrabajoConsulta.concesion_hasta.is_(None), TrabajoConsulta.concesion_hasta <= datetime.now(timezone.utc)))
                .order_by(TrabajoConsulta.creado_en, TrabajoConsulta.id).limit(1))
        if identificador is None:
            return False
        try:
            concesion = self.repositorio.reclamar(identificador)
        except TrabajoNoVigente:
            return False
        if concesion is None:
            return True
        with self.sesiones() as sesion:
            consulta = sesion.get(ConsultaLista, identificador)
            borrador = sesion.scalar(select(BorradorConsulta.id).where(BorradorConsulta.consulta_id == identificador))
            manifiesto = consulta.manifiesto
            criterio = consulta.criterio_original
            admitida_en = consulta.creado_en
            modo = consulta.implementacion
            version_contrato = consulta.version_contrato
        if modo == "archivos" and version_contrato == "2.1":
            return self._ejecutar_archivos(concesion, bool(borrador))
        if modo != "simulado" or manifiesto.get("adaptador") != "simulado-v1" or manifiesto.get("algoritmo") != "fixture-v1":
            self.repositorio.fallar(concesion, "IMPLEMENTACION_NO_DISPONIBLE")
            return True
        if not borrador:
            adaptador = SimuladorListasV2(manifiesto["escenario"])
            ejecutor = EjecutorConsultaV2(self.repositorio.politica, adaptador, lambda *_: False)
            resultado = ejecutor.ejecutar_admitida(SolicitudProveedorV2(consulta_id=identificador,
                correlacion_id=uuid4(), criterio=Criterio.model_validate(criterio), implementacion="simulado",
                proveedor="simulador", adaptador_version="simulado-v1", algoritmo_version="fixture-v1",
                parametros={"escenario": manifiesto["escenario"]}, admitida_en=admitida_en,
                huella_configuracion=calcular_huella(manifiesto)))
            self.repositorio.guardar_borrador(concesion, resultado)
        try:
            self.repositorio.preparar_informe(concesion)
            self.repositorio.cerrar(concesion)
        except (ErrorIntegridadEvidencia, OSError):
            self.repositorio.fallar(concesion, "CUSTODIA_NO_DISPONIBLE")
        return True

    def _ejecutar_archivos(self, concesion, tiene_borrador):
        from infrastructure.listas.fabrica import crear_consultor_archivos_local
        from services.listas.admision_archivos import leer_manifiesto
        try:
            if not tiene_borrador:
                with self.sesiones() as sesion:
                    consulta = sesion.get(ConsultaLista, concesion.consulta_id)
                    manifiesto = consulta.manifiesto
                    fijado, _, _ = leer_manifiesto(manifiesto)
                    coberturas = {c.detalle["fuente_codigo"]: {"id": c.id, "nombre": c.nombre_origen}
                        for c in sesion.scalars(select(ConsultaFuente).where(ConsultaFuente.consulta_id == consulta.id))}
                    solicitud = SolicitudBusquedaInterna(consulta_id=consulta.id, correlacion_id=consulta.id,
                        contexto={"tipo": "EXPEDIENTE", "expediente_id": consulta.expediente_id,
                                  "sujeto_rol": consulta.sujeto_rol, "motivo": consulta.motivo},
                        criterio=CriterioBusqueda.model_validate(consulta.criterio_original), proveedor=consulta.proveedor,
                        implementacion="archivos", admitida_en=consulta.creado_en, manifiesto=fijado)
                adaptador = crear_consultor_archivos_local(self.sesiones, self.politica, self.custodia,
                    self.politica.entorno, manifiesto, coberturas)
                resultado = adaptador.consultar(solicitud)
                self.repositorio.guardar_borrador(concesion, resultado)
            self.repositorio.preparar_informe(concesion)
            self.repositorio.cerrar(concesion)
        except VersionNoDisponible:
            self.repositorio.fallar(concesion, "RECETA_O_VERSION_NO_DISPONIBLE")
        except (ErrorIntegridadEvidencia, OSError):
            self.repositorio.fallar(concesion, "INTEGRIDAD_O_CUSTODIA_NO_DISPONIBLE")
        except (ValueError, KeyError, TypeError):
            self.repositorio.fallar(concesion, "DATOS_ADMITIDOS_NO_INTERPRETABLES")
        return True
