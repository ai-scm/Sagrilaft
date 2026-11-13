"""F5.3 desde recepción HTTP hasta informe persistido, sin importar listas."""
from pathlib import Path
from uuid import UUID
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import json
import os
import subprocess
import sys
import pytest
from sqlalchemy import select, func
from infrastructure.persistencia.modelos_listas import IntentoImportacion, VersionFuente, FuenteVersionActiva, ArchivoFuente
from infrastructure.persistencia.modelos_recepcion_listas import EventoRecepcionLista
from services.listas.validacion_archivos import TrabajadorValidacionArchivos
from domain.listas.errores import ConflictoListas
from .test_flujo_http import portal
from .test_recepcion_f52 import carga, reservar, enviar, BASE, datos

FIJOS=Path(__file__).resolve().parents[1]/'fixtures/listas_f5'


def recibir(carga,archivo='v1.xml'):
    contenido=(FIJOS/archivo).read_bytes()
    solicitud=datos(contenido)
    solicitud['formato']='SINTETICO_ZIP_V1' if archivo.endswith('.zip') else 'SINTETICO_XML_V1'
    respuesta=carga.cliente.post(BASE,json=solicitud,headers={'Idempotency-Key':archivo})
    assert respuesta.status_code==201,respuesta.text
    identificador=respuesta.json()['recepcion_id']
    assert enviar(carga,identificador,contenido).status_code==202
    return identificador


def trabajador(carga):
    return TrabajadorValidacionArchivos(carga.sesiones,carga.custodia,'development',habilitado=True)


@pytest.mark.parametrize('archivo',['v1.xml','v1.zip','invalido.xml'])
def test_validacion_persistida_sin_importar(carga,archivo):
    identificador=recibir(carga,archivo)
    assert trabajador(carga).ejecutar_uno()
    assert not trabajador(carga).ejecutar_uno()
    respuesta=carga.cliente.get(f'{BASE}/{identificador}/validacion')
    assert respuesta.status_code==200,respuesta.text
    valido=archivo!='invalido.xml'
    assert respuesta.json()['resultado']==('VALIDO' if valido else 'INVALIDO')
    with carga.sesiones() as sesion:
        intento=sesion.scalar(select(IntentoImportacion))
        progreso=carga.cliente.get(f'/api/administracion-listas/intentos/{intento.id}')
        assert progreso.status_code==200,progreso.text
        assert progreso.json()['registros_confirmados']==0
        assert intento.fase==('IMPORTACION' if valido else 'VALIDACION')
        assert intento.estado==('EN_CURSO' if valido else 'FALLIDO')
        assert sesion.scalar(select(func.count()).select_from(VersionFuente))==0
        assert sesion.scalar(select(FuenteVersionActiva.version_id)) is None
        assert sesion.scalar(select(func.count()).select_from(EventoRecepcionLista).where(EventoRecepcionLista.tipo=='VALIDACION_FINALIZADA'))==1
    assert carga.cliente.get(f'{BASE}/{identificador}/original').content==(FIJOS/archivo).read_bytes()


def test_informe_y_progreso_privados(carga):
    identificador=recibir(carga); trabajador(carga).ejecutar_uno()
    with carga.sesiones() as sesion: intento=sesion.scalar(select(IntentoImportacion))
    carga.cliente.headers['Authorization']='Bearer '+carga.token(['listas_cargador'],sub='otra-persona')
    assert carga.cliente.get(f'{BASE}/{identificador}/validacion').status_code==404
    assert carga.cliente.get(f'/api/administracion-listas/intentos/{intento.id}').status_code==404
    carga.cliente.headers.pop('Authorization')
    assert carga.cliente.get(f'{BASE}/{identificador}/validacion').status_code==401


def test_trabajador_concurrente_solo_uno_reclama(carga):
    recibir(carga)
    with ThreadPoolExecutor(max_workers=2) as grupo:
        resultados=list(grupo.map(lambda _:trabajador(carga).ejecutar_uno(),range(2)))
    assert sorted(resultados)==[False,True]


def test_fallo_sql_recuperable_sin_informe_parcial(carga,monkeypatch):
    from sqlalchemy.exc import OperationalError
    identificador=recibir(carga)
    servicio=trabajador(carga)
    original=servicio._evento
    def fallar(sesion,intento,tipo,detalle):
        if tipo=='VALIDACION_FINALIZADA': raise OperationalError('INSERT',{},Exception('ensayo'))
        return original(sesion,intento,tipo,detalle)
    with monkeypatch.context() as cambios:
        cambios.setattr(servicio,'_evento',fallar)
        with pytest.raises(OperationalError): servicio.ejecutar_uno()
    with carga.sesiones.begin() as sesion:
        intento=sesion.scalar(select(IntentoImportacion))
        assert intento.informe is None and intento.fase=='VALIDACION'
        intento.concesion_hasta=datetime.now(timezone.utc)-timedelta(seconds=1)
    assert trabajador(carga).ejecutar_uno()
    assert carga.cliente.get(f'{BASE}/{identificador}/validacion').json()['resultado']=='VALIDO'


def test_concesion_vencida_no_confirma(carga):
    recibir(carga)
    servicio=trabajador(carga); trabajo=servicio._reclamar()
    with carga.sesiones.begin() as sesion:
        sesion.get(IntentoImportacion,trabajo['id']).concesion_hasta=datetime.now(timezone.utc)-timedelta(seconds=1)
    with pytest.raises(ConflictoListas): servicio._confirmar(trabajo,{},None,None,None)
    assert trabajador(carga).ejecutar_uno()


def test_cli_valida_con_rol_restringido(carga):
    identificador=recibir(carga)
    entorno=dict(os.environ,LISTAS_CUSTODIA_DIRECTORIO=str(carga.custodia.directorio),LISTAS_ADMIN_HABILITADA='true')
    respuesta=subprocess.run([sys.executable,'scripts/validacion/ejecutar_validacion_archivos.py'],env=entorno,
        capture_output=True,text=True,timeout=20)
    assert respuesta.returncode==0,respuesta.stderr
    assert carga.cliente.get(f'{BASE}/{identificador}/validacion').json()['resultado']=='VALIDO'


def test_informe_corrupto_no_se_entrega(carga):
    identificador=recibir(carga); trabajador(carga).ejecutar_uno()
    with carga.sesiones() as sesion:
        intento=sesion.scalar(select(IntentoImportacion))
        archivo=sesion.get(ArchivoFuente,UUID(intento.informe['informe_id']))
    (carga.custodia.directorio/archivo.clave).write_bytes(b'alterado')
    assert carga.cliente.get(f'{BASE}/{identificador}/validacion').status_code==503


def test_flag_y_entorno_validador(carga):
    with pytest.raises(PermissionError):
        TrabajadorValidacionArchivos(carga.sesiones,carga.custodia,'development')
    with pytest.raises(PermissionError):
        TrabajadorValidacionArchivos(carga.sesiones,carga.custodia,'staging',habilitado=True)


def test_tiempo_agotado_termina_subproceso(carga,tmp_path,monkeypatch):
    import services.listas.validacion_archivos as modulo
    identificador=recibir(carga)
    ejecutable=tmp_path/'proceso-lento'
    # exec evita dejar nietos; el supervisor mata y espera al proceso al vencer el plazo.
    ejecutable.write_text('#!/bin/sh\nexec /bin/sleep 30\n'); ejecutable.chmod(0o700)
    servicio=trabajador(carga)
    servicio.perfil=servicio.perfil.model_copy(update={'validacion_segundos':1})
    with monkeypatch.context() as cambios:
        cambios.setattr(modulo.sys,'executable',str(ejecutable))
        # sleep no admite los argumentos de Python; usar un envoltorio que los ignore.
        assert servicio.ejecutar_uno()
    assert carga.cliente.get(f'{BASE}/{identificador}/validacion').json()['codigo']=='LIMITE_TIEMPO'


def test_memoria_insuficiente_no_confirma_validez(carga):
    identificador=recibir(carga)
    servicio=trabajador(carga)
    servicio.perfil=servicio.perfil.model_copy(update={'memoria_bytes':1024*1024})
    assert servicio.ejecutar_uno()
    assert carga.cliente.get(f'{BASE}/{identificador}/validacion').json()['resultado']=='INVALIDO'


def test_cuota_validacion_sin_reclamar(carga):
    recibir(carga)
    servicio=trabajador(carga)
    servicio.perfil=servicio.perfil.model_copy(update={'disco_temporal_bytes':1})
    with pytest.raises(ConflictoListas): servicio.ejecutar_uno()
    with carga.sesiones() as sesion:
        intento=sesion.scalar(select(IntentoImportacion))
        assert intento.numero_control==0 and intento.estado=='PENDIENTE'


def test_latido_renueva_solo_concesion_propia(carga):
    recibir(carga); servicio=trabajador(carga)
    trabajo=servicio._reclamar()
    with carga.sesiones.begin() as sesion:
        intento=sesion.get(IntentoImportacion,trabajo['id'])
        intento.concesion_hasta=datetime.now(timezone.utc)+timedelta(seconds=1)
    servicio._renovar(trabajo)
    with carga.sesiones() as sesion:
        assert sesion.get(IntentoImportacion,trabajo['id']).concesion_hasta>datetime.now(timezone.utc)+timedelta(seconds=60)
    with pytest.raises(ConflictoListas): servicio._renovar({**trabajo,'control':trabajo['control']-1})


def test_informe_faltante_no_se_entrega(carga):
    identificador=recibir(carga); trabajador(carga).ejecutar_uno()
    with carga.sesiones() as sesion:
        intento=sesion.scalar(select(IntentoImportacion))
        archivo=sesion.get(ArchivoFuente,UUID(intento.informe['informe_id']))
    (carga.custodia.directorio/archivo.clave).unlink()
    assert carga.cliente.get(f'{BASE}/{identificador}/validacion').status_code==503


def test_reclamaciones_agotadas_informan_fallo_operativo(carga):
    identificador=recibir(carga); servicio=trabajador(carga)
    for _ in range(3):
        trabajo=servicio._reclamar()
        with carga.sesiones.begin() as sesion:
            sesion.get(IntentoImportacion,trabajo['id']).concesion_hasta=datetime.now(timezone.utc)-timedelta(seconds=1)
    assert servicio._reclamar() is None
    respuesta=carga.cliente.get(f'{BASE}/{identificador}/validacion')
    assert respuesta.json()=={'resultado':'NO_COMPLETADA','codigo':'REINTENTOS_AGOTADOS'}
    assert carga.cliente.get(f'{BASE}/{identificador}').json()['validacion']=='FALLIDA'
    assert carga.cliente.get(f'/api/administracion-listas/intentos/{trabajo["id"]}').json()['estado']=='FALLIDO'
