"""Recepción sintética contra PostgreSQL migrado y JWT reales con claves locales."""
import hashlib
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import UUID
from concurrent.futures import ThreadPoolExecutor
import pytest
from sqlalchemy import select, func, text
from api.routers import recepciones_listas
from infrastructure.config.configuracion import SagrilaftListasConfig
from infrastructure.persistencia.modelos_listas import FuenteLista, ArchivoFuente, RecepcionFuente, IntentoImportacion, VersionFuente
from infrastructure.persistencia.modelos_recepcion_listas import ReservaRecepcionLista, EventoRecepcionLista
from infrastructure.listas.recepcion_archivo import ArchivoEnRecepcion, LimiteCarga
from domain.listas.administracion import RecepcionPropuesta
from domain.listas.errores import ConflictoListas, ErrorIntegridadEvidencia
from services.listas.recepcion import ServicioRecepcionListas
from services.listas.politica_v2 import PoliticaListasV2, ActorListas
from .test_flujo_http import portal

BASE='/api/administracion-listas/recepciones'
CONTENIDO=b'<sintetico>datos ficticios</sintetico>'


@pytest.fixture
def carga(portal):
    portal.app.include_router(recepciones_listas.enrutador)
    portal.app.state.config.listas_cautela = SagrilaftListasConfig(proveedor=None, implementacion='simulado', escenario='sin_coincidencias_v1', admin_habilitada=True)
    portal.cliente.headers['Authorization']='Bearer '+portal.token(['listas_cargador'])
    with portal.sesiones.begin() as sesion:
        sesion.add(FuenteLista(codigo='ofac_sdn_prueba', nombre='Solo pruebas', organismo='Ensayo local', url_oficial='FIXTURE_LOCAL'))
    actor=ActorListas.desde_identidad_validada(portal.app.state.config.keycloak.issuer,'operador-local',('listas_cargador',))
    portal.servicio=ServicioRecepcionListas(portal.sesiones,portal.custodia,
        PoliticaListasV2(portal.app.state.config.listas_cautela,'development'),actor,'development')
    return portal


def datos(contenido=CONTENIDO):
    return dict(fuente='ofac_sdn_prueba',formato='SINTETICO_XML_V1',nombre_original='prueba.xml',
        procedencia='FIXTURE_LOCAL',huella_declarada=hashlib.sha256(contenido).hexdigest())


def reservar(carga, clave='uno', contenido=CONTENIDO):
    respuesta=carga.cliente.post(BASE,json=datos(contenido),headers={'Idempotency-Key':clave})
    assert respuesta.status_code==201,respuesta.text
    return respuesta.json()['recepcion_id']


def enviar(carga, identificador, contenido=CONTENIDO):
    return carga.cliente.put(f'{BASE}/{identificador}/contenido', content=contenido, headers={'Content-Type':'application/octet-stream'})


def test_carga_original_reintento_y_trabajo_pendiente(carga):
    identificador=reservar(carga)
    assert enviar(carga,identificador).status_code==202
    assert reservar(carga)==identificador
    assert enviar(carga,identificador).status_code==202
    descarga=carga.cliente.get(f'{BASE}/{identificador}/original')
    assert descarga.content==CONTENIDO and descarga.headers['x-content-type-options']=='nosniff'
    with carga.sesiones() as sesion:
        assert sesion.scalar(select(func.count()).select_from(IntentoImportacion))==1
        assert sesion.scalar(select(func.count()).select_from(VersionFuente))==0
        intento=sesion.scalar(select(IntentoImportacion))
        assert intento.estado=='PENDIENTE' and intento.fase=='VALIDACION'


def test_misma_clave_otro_hash_conflicto(carga):
    reservar(carga)
    assert carga.cliente.post(BASE,json=datos(b'otro'),headers={'Idempotency-Key':'uno'}).status_code==409


def test_otra_recepcion_deduplica_bytes_no_actor(carga):
    primero=reservar(carga); assert enviar(carga,primero).status_code==202
    carga.cliente.headers['Authorization']='Bearer '+carga.token(['listas_cargador'],sub='otra-persona')
    segundo=reservar(carga); assert primero!=segundo
    assert enviar(carga,segundo).status_code==202
    assert carga.cliente.get(f'{BASE}/{primero}/original').status_code==404
    with carga.sesiones() as sesion:
        assert sesion.scalar(select(func.count()).select_from(ArchivoFuente))==1
        assert sesion.scalar(select(func.count()).select_from(RecepcionFuente))==2


@pytest.mark.parametrize('contenido',[b'',b'alterado'])
def test_hash_incorrecto_no_confirma_y_permite_reintento(carga,contenido):
    identificador=reservar(carga)
    assert enviar(carga,identificador,contenido).status_code==422
    assert enviar(carga,identificador).status_code==202
    assert not list(carga.custodia.directorio.glob('recepcion-*'))


@pytest.mark.parametrize('roles',[[],['acceso_clientes'],['listas_aprobador']])
def test_permiso_carga_independiente_de_carpeta(carga,roles):
    carga.cliente.headers['Authorization']='Bearer '+carga.token(roles)
    assert carga.cliente.post(BASE,json=datos(),headers={'Idempotency-Key':'uno'}).status_code==403


def test_flag_y_entorno_rechazan(carga):
    carga.app.state.config.listas_cautela=SagrilaftListasConfig(proveedor='deshabilitado')
    assert carga.cliente.post(BASE,json=datos(),headers={'Idempotency-Key':'uno'}).status_code==409
    carga.app.state.config.entorno='staging'
    assert carga.cliente.post(BASE,json=datos(),headers={'Idempotency-Key':'uno'}).status_code==403


def test_token_vencido_al_confirmar_no_guarda(carga,monkeypatch):
    from fastapi import HTTPException
    async def vencido(*_): raise HTTPException(401,'Sesión vencida')
    identificador=reservar(carga)
    monkeypatch.setattr(recepciones_listas,'_decodificar_jwt',vencido)
    assert enviar(carga,identificador).status_code==401
    assert carga.cliente.get(f'{BASE}/{identificador}').json()['estado']=='PENDIENTE'
    assert not list(carga.custodia.directorio.iterdir())


def test_limites_declarados_y_reales_sin_content_length(carga,monkeypatch):
    import services.listas.recepcion as modulo
    original=modulo.PerfilEnsayo().model_dump(); original['recibido_bytes']=4
    monkeypatch.setattr(modulo,'PerfilEnsayo',lambda:SimpleNamespace(**original))
    identificador=reservar(carga,contenido=b'1234')
    assert enviar(carga,identificador,b'12345').status_code==413
    respuesta=carga.cliente.put(f'{BASE}/{identificador}/contenido',content=iter([b'123',b'45']),headers={'Content-Type':'application/octet-stream'})
    assert respuesta.status_code==413
    assert enviar(carga,identificador,b'1234').status_code==202


def test_metadatos_grandes_y_formato_no_soportado(carga):
    assert carga.cliente.post(BASE,content=b'x'*16385,headers={'Idempotency-Key':'uno'}).status_code==413
    identificador=reservar(carga)
    assert carga.cliente.put(f'{BASE}/{identificador}/contenido',content=CONTENIDO,headers={'Content-Type':'multipart/form-data'}).status_code==415


def test_original_corrupto_no_se_entrega(carga):
    identificador=reservar(carga); assert enviar(carga,identificador).status_code==202
    (carga.custodia.directorio/hashlib.sha256(CONTENIDO).hexdigest()).write_bytes(b'alterado')
    assert carga.cliente.get(f'{BASE}/{identificador}/original').status_code==503


def test_reservas_concurrentes_y_concesion_exclusiva(carga):
    solicitud=RecepcionPropuesta(**datos(),clave='uno')
    with ThreadPoolExecutor(max_workers=2) as grupo:
        ids=list(grupo.map(lambda _:carga.servicio.reservar(solicitud),range(2)))
    assert ids[0]==ids[1]
    carga.servicio.reclamar(ids[0])
    with pytest.raises(ConflictoListas): carga.servicio.reclamar(ids[0])


def test_recupera_concesion_vencida_rechaza_ejecutor_anterior(carga):
    identificador=UUID(reservar(carga)); control,_=carga.servicio.reclamar(identificador)
    with carga.sesiones.begin() as sesion:
        sesion.get(ReservaRecepcionLista,identificador).concesion_hasta=datetime.now(timezone.utc)-timedelta(seconds=1)
    nuevo=ServicioRecepcionListas(carga.sesiones,carga.custodia,carga.servicio.politica,carga.servicio.actor,'development')
    segundo,_=nuevo.reclamar(identificador)
    objeto=carga.custodia.guardar(CONTENIDO)
    with pytest.raises(ConflictoListas): carga.servicio.confirmar(identificador,control,objeto)
    nuevo.confirmar(identificador,segundo,objeto)


def test_fallo_sql_revierte_recepcion_y_reutiliza_original(carga,monkeypatch):
    from sqlalchemy.exc import OperationalError
    identificador=UUID(reservar(carga)); control,_=carga.servicio.reclamar(identificador)
    objeto=carga.custodia.guardar(CONTENIDO)
    original=carga.servicio._evento
    def fallar(*args,**kwargs): raise OperationalError('INSERT evento',{},Exception('fallo de prueba'))
    monkeypatch.setattr(carga.servicio,'_evento',fallar)
    with pytest.raises(OperationalError): carga.servicio.confirmar(identificador,control,objeto)
    with carga.sesiones() as sesion:
        assert sesion.get(RecepcionFuente,identificador).estado=='PENDIENTE'
        assert sesion.scalar(select(func.count()).select_from(IntentoImportacion))==0
    monkeypatch.setattr(carga.servicio,'_evento',original)
    carga.servicio.confirmar(identificador,control,objeto)


def test_fallo_disco_libera_reserva(carga,monkeypatch):
    identificador=reservar(carga)
    original=ArchivoEnRecepcion.escribir
    def fallar(*_): raise OSError('Sin espacio simulado')
    monkeypatch.setattr(ArchivoEnRecepcion,'escribir',fallar)
    assert enviar(carga,identificador).status_code==503
    monkeypatch.setattr(ArchivoEnRecepcion,'escribir',original)
    assert enviar(carga,identificador).status_code==202


def test_eventos_inmutables_y_reserva_terminal(carga):
    from sqlalchemy.exc import DBAPIError
    identificador=UUID(reservar(carga)); assert enviar(carga,identificador).status_code==202
    for sentencia in ('DELETE FROM evento_recepcion_lista','UPDATE reserva_recepcion_lista SET intentos=0'):
        with pytest.raises(DBAPIError), carga.sesiones.begin() as sesion:
            sesion.execute(text(sentencia))


def test_presupuesto_transferencia_y_limite_por_actor(carga):
    primero=UUID(reservar(carga))
    segundo=UUID(reservar(carga,clave='dos'))
    control,_=carga.servicio.reclamar(primero)
    with pytest.raises(ConflictoListas): carga.servicio.reclamar(segundo)
    carga.servicio.interrumpir(primero,control,'PRUEBA')
    for _ in range(2):
        control,_=carga.servicio.reclamar(primero)
        carga.servicio.interrumpir(primero,control,'PRUEBA')
    with pytest.raises(ConflictoListas): carga.servicio.reclamar(primero)


def test_cuota_local(carga):
    perfil=carga.servicio.perfil.model_dump(); perfil['disco_temporal_bytes']=1
    carga.servicio.perfil=SimpleNamespace(**perfil)
    identificador=UUID(reservar(carga))
    with pytest.raises(ConflictoListas): carga.servicio.reclamar(identificador)


def test_cli_carga_fixture_sobre_http_local(carga):
    import socket
    import threading
    import time
    import subprocess
    import sys
    from pathlib import Path
    import uvicorn
    with socket.socket() as conexion:
        conexion.bind(('127.0.0.1',0)); puerto=conexion.getsockname()[1]
    servidor=uvicorn.Server(uvicorn.Config(carga.app,host='127.0.0.1',port=puerto,log_level='error'))
    hilo=threading.Thread(target=servidor.run,daemon=True); hilo.start()
    raiz=Path(__file__).resolve().parents[2]
    try:
        for _ in range(100):
            if servidor.started: break
            time.sleep(.05)
        assert servidor.started
        archivo=raiz/'tests/fixtures/listas_f5/v1.xml'
        respuesta=subprocess.run([sys.executable,str(raiz/'scripts/listas/cargar_sintetico.py'),str(archivo),
            '--url',f'http://127.0.0.1:{puerto}','--clave','cli-uno','--formato','SINTETICO_XML_V1'],
            input=carga.token(['listas_cargador'])+'\n',capture_output=True,text=True,timeout=20)
        assert respuesta.returncode==0,respuesta.stderr
        assert 'RECIBIDA' in respuesta.stdout and 'NO_EJECUTADA' in respuesta.stdout
        with carga.sesiones() as sesion:
            recepcion=sesion.scalar(select(RecepcionFuente))
            identificador=recepcion.id
        assert carga.cliente.get(f'{BASE}/{identificador}/original').content==archivo.read_bytes()
    finally:
        servidor.should_exit=True; hilo.join(timeout=10)


@pytest.mark.parametrize('fallo',['desconexion','tiempo'])
def test_interrupcion_de_flujo_libera_carga(carga,monkeypatch,fallo):
    import asyncio
    from starlette.requests import Request, ClientDisconnect
    import services.listas.recepcion as modulo
    identificador=reservar(carga)
    async def interrumpido(self):
        if fallo=='tiempo':
            await asyncio.sleep(.1)
        else:
            raise ClientDisconnect()
        yield b'no se completa'
    with monkeypatch.context() as cambios:
        perfil=modulo.PerfilEnsayo().model_dump(); perfil['carga_segundos']=.01
        cambios.setattr(modulo,'PerfilEnsayo',lambda:SimpleNamespace(**perfil))
        cambios.setattr(Request,'stream',interrumpido)
        assert enviar(carga,identificador).status_code==(408 if fallo=='tiempo' else 400)
    assert enviar(carga,identificador).status_code==202
    assert not list(carga.custodia.directorio.glob('recepcion-*'))


def test_conciliacion_informa_huerfanos_sin_borrarlos(carga):
    carga.custodia.guardar(b'original huerfano ficticio')
    ruta='/api/administracion-listas/conciliacion'
    assert carga.cliente.get(ruta).status_code==403
    carga.cliente.headers['Authorization']='Bearer '+carga.token(['listas_incidentes'])
    respuesta=carga.cliente.get(ruta)
    assert respuesta.status_code==200
    assert respuesta.json()['objetos_sin_referencia']==1 and respuesta.json()['eliminados']==0
    assert len(list(carga.custodia.directorio.iterdir()))==1


def test_downgrade_preserva_recepciones(carga):
    from alembic import command
    from alembic.config import Config
    from pathlib import Path
    identificador=reservar(carga); assert enviar(carga,identificador).status_code==202
    configuracion=Config(str(Path(__file__).resolve().parents[2]/'backend/alembic.ini'))
    with pytest.raises(RuntimeError,match='historial'):
        command.downgrade(configuracion,'b32c45d67e89')
    assert carga.cliente.get(f'{BASE}/{identificador}/original').content==CONTENIDO


def test_clave_distinta_del_hash_no_confirma(carga):
    from infrastructure.listas.custodia import ObjetoCustodiado
    identificador=UUID(reservar(carga))
    control,_=carga.servicio.reclamar(identificador)
    objeto=carga.custodia.guardar(CONTENIDO)
    with pytest.raises(ValueError,match='clave'):
        carga.servicio.confirmar(identificador,control,ObjetoCustodiado('otra-clave',objeto.huella,objeto.tamano_bytes))
    assert carga.servicio.consultar(identificador)['estado']=='PENDIENTE'


@pytest.mark.parametrize('defecto',['sin_trabajo','sin_evento','trabajo_ajeno'])
def test_base_rechaza_cierre_incompleto(carga,defecto):
    from sqlalchemy.exc import DBAPIError
    identificador=UUID(reservar(carga))
    otro=UUID(reservar(carga,clave='otra'))
    with pytest.raises(DBAPIError,match='Cierre de recepción|Trabajo de recepción no reasignable'), carga.sesiones.begin() as sesion:
        archivo=ArchivoFuente(clave=hashlib.sha256(CONTENIDO).hexdigest(),huella=hashlib.sha256(CONTENIDO).hexdigest(),
            tamano_bytes=len(CONTENIDO),nombre_recibido='prueba.xml',tipo_contenido='application/octet-stream')
        sesion.add(archivo); sesion.flush()
        recepcion=sesion.get(RecepcionFuente,identificador)
        recepcion.archivo_id=archivo.id; recepcion.estado='RECIBIDA'
        if defecto!='sin_trabajo':
            intento=IntentoImportacion(recepcion_id=otro if defecto=='trabajo_ajeno' else identificador,estado='PENDIENTE',fase='VALIDACION')
            sesion.add(intento); sesion.flush()
            sesion.get(ReservaRecepcionLista,identificador).intento_importacion_id=intento.id
            if defecto=='trabajo_ajeno':
                carga.servicio._evento(sesion,identificador,'RECIBIDA',archivo_id=str(archivo.id),intento_id=str(intento.id),sha256=archivo.huella)
    assert carga.servicio.consultar(identificador)['estado']=='PENDIENTE'
    assert enviar(carga,identificador).status_code==202


def test_publicaciones_simultaneas_conservan_un_original(carga):
    def publicar(_):
        escritura=ArchivoEnRecepcion(carga.custodia,1024)
        try:
            escritura.escribir(CONTENIDO)
            return escritura.confirmar(hashlib.sha256(CONTENIDO).hexdigest())
        finally:
            escritura.cerrar()
    with ThreadPoolExecutor(max_workers=2) as grupo:
        objetos=list(grupo.map(publicar,range(2)))
    assert objetos[0]==objetos[1]
    assert len(list(carga.custodia.directorio.iterdir()))==1
    assert (carga.custodia.directorio/objetos[0].clave).read_bytes()==CONTENIDO


@pytest.mark.parametrize('sincronizacion',[1,2])
def test_fallo_fsync_no_confirma_y_reintento_recupera(carga,monkeypatch,sincronizacion):
    import infrastructure.listas.recepcion_archivo as modulo
    identificador=reservar(carga)
    original=modulo.os.fsync
    llamadas=0
    def fallar(descriptor):
        nonlocal llamadas
        llamadas+=1
        if llamadas==sincronizacion:
            raise OSError('Sincronización fallida de prueba')
        return original(descriptor)
    with monkeypatch.context() as cambios:
        cambios.setattr(modulo.os,'fsync',fallar)
        assert enviar(carga,identificador).status_code==503
    assert carga.cliente.get(f'{BASE}/{identificador}').json()['estado']=='PENDIENTE'
    assert enviar(carga,identificador).status_code==202
    assert carga.cliente.get(f'{BASE}/{identificador}/original').content==CONTENIDO


@pytest.mark.parametrize('tipo',['enlace','fifo'])
def test_original_no_regular_se_rechaza(carga,tipo,tmp_path):
    import os
    from infrastructure.listas.recepcion_archivo import original_verificado
    huella=hashlib.sha256(CONTENIDO).hexdigest()
    ruta=carga.custodia.directorio/huella
    if tipo=='fifo':
        os.mkfifo(ruta)
    else:
        destino=tmp_path/'externo'; destino.write_bytes(CONTENIDO); ruta.symlink_to(destino)
    with pytest.raises((OSError,ErrorIntegridadEvidencia)):
        original_verificado(carga.custodia,huella,len(CONTENIDO))


def test_confirmaciones_concurrentes_crean_un_solo_trabajo(carga):
    identificador=UUID(reservar(carga))
    control,_=carga.servicio.reclamar(identificador)
    objeto=carga.custodia.guardar(CONTENIDO)
    with ThreadPoolExecutor(max_workers=2) as grupo:
        intentos=list(grupo.map(lambda _:carga.servicio.confirmar(identificador,control,objeto),range(2)))
    assert intentos[0]==intentos[1]
    with carga.sesiones() as sesion:
        assert sesion.scalar(select(func.count()).select_from(IntentoImportacion))==1
        assert sesion.scalar(select(func.count()).select_from(EventoRecepcionLista).where(EventoRecepcionLista.tipo=='RECIBIDA'))==1


def test_trabajo_confirmado_no_se_reasigna(carga):
    from sqlalchemy.exc import DBAPIError
    primero=UUID(reservar(carga))
    segundo=UUID(reservar(carga,clave='segunda'))
    assert enviar(carga,primero).status_code==202
    with pytest.raises(DBAPIError,match='no reasignable'), carga.sesiones.begin() as sesion:
        intento=sesion.scalar(select(IntentoImportacion).where(IntentoImportacion.recepcion_id==primero))
        intento.recepcion_id=segundo
    assert carga.cliente.get(f'{BASE}/{primero}/original').content==CONTENIDO


def test_sigkill_durante_recepcion_y_reinicio_real(carga,tmp_path):
    """Mata Uvicorn con bytes parciales en disco y reintenta por HTTP en otro PID."""
    import asyncio
    import http.client
    import json
    import os
    from pathlib import Path
    import signal
    import subprocess
    import sys
    import time
    from api.middleware import autenticacion

    contenido=b'<sintetico>'+b'x'*131072+b'</sintetico>'
    identificador=UUID(reservar(carga,contenido=contenido))
    claves=asyncio.run(autenticacion._obtener_jwks(None))
    puerto_archivo=tmp_path/'puerto'
    configuracion=tmp_path/'servidor.json'
    configuracion.write_text(json.dumps(dict(jwk=claves['keys'][0],
        custodia=str(carga.custodia.directorio),puerto=str(puerto_archivo))))
    procesos=[]
    autorizacion={'Authorization':'Bearer '+carga.token(['listas_cargador'])}
    evidencia={'recepcion_id':str(identificador),'bytes_totales':len(contenido)}

    def iniciar():
        puerto_archivo.unlink(missing_ok=True)
        proceso=subprocess.Popen([sys.executable,str(Path(__file__).with_name('servidor_recepcion_sintetica.py')),str(configuracion)])
        procesos.append(proceso)
        limite=time.monotonic()+15
        while time.monotonic()<limite:
            assert proceso.poll() is None, 'El servidor terminó antes de estar disponible'
            if puerto_archivo.exists():
                puerto=int(puerto_archivo.read_text())
                try:
                    estado,_=peticion(puerto,'GET',f'{BASE}/{identificador}')
                    if estado==200: return proceso,puerto
                except OSError:
                    pass
            time.sleep(.05)
        pytest.fail('Servidor local no disponible')

    def peticion(puerto,metodo,ruta,cuerpo=None):
        conexion=http.client.HTTPConnection('127.0.0.1',puerto,timeout=5)
        try:
            cabeceras={**autorizacion}
            if cuerpo is not None: cabeceras['Content-Type']='application/octet-stream'
            conexion.request(metodo,ruta,body=cuerpo,headers=cabeceras)
            respuesta=conexion.getresponse()
            return respuesta.status,respuesta.read()
        finally:
            conexion.close()

    conexion=None
    try:
        primero,puerto=iniciar()
        conexion=http.client.HTTPConnection('127.0.0.1',puerto,timeout=5)
        conexion.putrequest('PUT',f'{BASE}/{identificador}/contenido')
        for nombre,valor in {**autorizacion,'Content-Type':'application/octet-stream','Content-Length':str(len(contenido))}.items():
            conexion.putheader(nombre,valor)
        conexion.endheaders()
        conexion.send(contenido[:65536])
        limite=time.monotonic()+1.5
        while time.monotonic()<limite:
            temporales=list(carga.custodia.directorio.glob('recepcion-*'))
            if temporales and temporales[0].stat().st_size>0: break
            time.sleep(.01)
        assert temporales and 0<temporales[0].stat().st_size<len(contenido)
        primero.kill(); primero.wait(timeout=5)
        assert primero.returncode==-signal.SIGKILL
        conexion.close(); conexion=None
        evidencia.update(pid_interrumpido=primero.pid,senal='SIGKILL',bytes_parciales=temporales[0].stat().st_size)
        with carga.sesiones() as sesion:
            reserva=sesion.get(ReservaRecepcionLista,identificador)
            vencimiento=reserva.concesion_hasta
            assert reserva.intento_importacion_id is None
            assert sesion.get(RecepcionFuente,identificador).estado=='PENDIENTE'
            assert sesion.scalar(select(func.count()).select_from(ArchivoFuente))==0
            assert sesion.scalar(select(func.count()).select_from(IntentoImportacion))==0
        segundo,puerto=iniciar()
        assert segundo.pid!=primero.pid
        estado,cuerpo=peticion(puerto,'GET',f'{BASE}/{identificador}')
        assert estado==200 and json.loads(cuerpo)['estado']=='PENDIENTE'
        assert peticion(puerto,'PUT',f'{BASE}/{identificador}/contenido',contenido)[0]==409
        # Esperar el vencimiento real, sin UPDATE de la concesión ni reemplazo del reloj.
        while datetime.now(timezone.utc)<=vencimiento:
            time.sleep(.1)
        assert peticion(puerto,'PUT',f'{BASE}/{identificador}/contenido',contenido)[0]==202
        assert peticion(puerto,'PUT',f'{BASE}/{identificador}/contenido',contenido)[0]==202
        estado,original=peticion(puerto,'GET',f'{BASE}/{identificador}/original')
        assert estado==200 and original==contenido
        with carga.sesiones() as sesion:
            reserva=sesion.get(ReservaRecepcionLista,identificador)
            assert reserva.intentos==2 and reserva.numero_control==2
            assert sesion.scalar(select(func.count()).select_from(IntentoImportacion))==1
            assert sesion.scalar(select(func.count()).select_from(ArchivoFuente))==1
            assert sesion.scalar(select(func.count()).select_from(EventoRecepcionLista).where(EventoRecepcionLista.tipo=='RECIBIDA'))==1
        assert temporales[0].exists()  # Se conserva para conciliación; no se trata como original.
        evidencia.update(pid_reiniciado=segundo.pid,estado_final='RECIBIDA',trabajos=1,
            sha256=hashlib.sha256(original).hexdigest(),temporal_parcial_conservado=True,
            recuperacion='Reenvío completo después del vencimiento real de la concesión')
        Path(os.environ['LISTAS_EVIDENCIAS_DIRECTORIO'],'recuperacion-sigkill.json').write_text(json.dumps(evidencia,indent=2)+'\n')
    finally:
        if conexion: conexion.close()
        for proceso in procesos:
            if proceso.poll() is None:
                proceso.terminate()
                try: proceso.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proceso.kill(); proceso.wait(timeout=5)
