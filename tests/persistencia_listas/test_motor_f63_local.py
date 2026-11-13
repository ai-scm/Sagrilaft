"""Uso explícito del motor con la representación F6.2, sin conectar rutas F6.4."""
from uuid import uuid4
from datetime import date

from sqlalchemy import select

from domain.listas.contratos_busqueda import CriterioBusqueda
from infrastructure.persistencia.modelos_listas import ConsultaLista, RegistroLista
from services.listas.motor_busqueda import CATALOGO_MOTOR, MotorBusqueda
from .test_flujo_http import portal
from .test_recepcion_f52 import carga
from .test_administracion_f55 import administracion
from .test_busqueda_f62 import busqueda, activar, fijar


def test_f63_replica_evaluacion_sin_alterar_originales_ni_crear_consulta_http(busqueda):
    a = busqueda
    a.busqueda.catalogo = CATALOGO_MOTOR
    generacion = a.busqueda.preparar(a.actor, a.version)
    activar(a)
    fijada = fijar(a, generacion)
    consulta_id, cobertura_id = uuid4(), uuid4()
    criterio = CriterioBusqueda(tipo_sujeto="PERSONA", nombre="Persona ficticia Ámbar")
    with a.sesiones.begin() as sesion:
        originales = [(r.id, r.huella_semantica) for r in sesion.scalars(select(RegistroLista).order_by(RegistroLista.id))]
        lectura = a.busqueda.leer_fijada(sesion, fijada)
        assert lectura.no_interpretados
        resultado = MotorBusqueda().evaluar(criterio, lectura.registros, consulta_id,
            {fijada.fuente_codigo: cobertura_id}, date(2026,11,8))
        assert len(resultado.candidatos) == 1
        assert resultado.candidatos[0].nivel == "MEDIA"
        assert resultado.candidatos[0].registro_id in {i for i, _ in originales}
        assert not sesion.scalars(select(ConsultaLista)).all()
        assert originales == [(r.id, r.huella_semantica) for r in sesion.scalars(select(RegistroLista).order_by(RegistroLista.id))]
    with a.sesiones.begin() as sesion:
        segunda = a.busqueda.leer_fijada(sesion, fijada)
        assert MotorBusqueda().evaluar(criterio, segunda.registros, consulta_id,
            {fijada.fuente_codigo: cobertura_id}, resultado.fecha_referencia) == resultado
