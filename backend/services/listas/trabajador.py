"""Ejecutor recuperable. Solo consume trabajos ya admitidos; la modalidad que los admitió los ejecuta."""
import logging
from sqlalchemy import select, or_
from domain.listas.errores import TrabajoNoVigente
from infrastructure.persistencia.modelos_listas import ConsultaLista, TrabajoConsulta, BorradorConsulta
from infrastructure.persistencia.repositorios.consultas_listas import RepositorioConsultasListas
from services.listas.modalidades import ConsultaAdmitida, modalidad_de_consulta

registro = logging.getLogger(__name__)


class TrabajadorListas:
    def __init__(self, sesiones, politica, custodia, reloj=None):
        self.sesiones = sesiones
        self.politica, self.custodia = politica, custodia
        # No es una entrada pública: trabaja exclusivamente sobre admisiones persistidas.
        self.repositorio = RepositorioConsultasListas(sesiones, politica, custodia,
            lambda *_: False, lambda *_: False, self._sin_archivos, reloj=reloj)

    @staticmethod
    def _sin_archivos(*_):
        raise RuntimeError("Archivos no implementado en F3")

    def ejecutar_uno(self):
        with self.sesiones() as sesion:
            identificador = sesion.scalar(select(TrabajoConsulta.consulta_id).where(
                TrabajoConsulta.fase != "FINALIZADA",
                or_(TrabajoConsulta.concesion_hasta.is_(None), TrabajoConsulta.concesion_hasta <= self.repositorio.reloj()))
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
            admitida = ConsultaAdmitida(id=identificador, implementacion=consulta.implementacion,
                version_contrato=consulta.version_contrato, manifiesto=consulta.manifiesto,
                criterio=consulta.criterio_original, admitida_en=consulta.creado_en, tiene_borrador=bool(borrador))
        modalidad = modalidad_de_consulta(admitida)
        if modalidad is None:
            self.repositorio.fallar(concesion, "IMPLEMENTACION_NO_DISPONIBLE")
            return True
        modalidad.ejecutar(self, concesion, admitida)
        return True
