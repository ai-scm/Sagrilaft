"""F5.5: solicitudes y ejecución con JWT reales y PostgreSQL desechable."""
from concurrent.futures import ThreadPoolExecutor
from uuid import UUID, uuid4
import pytest
from sqlalchemy import select, func, text
from sqlalchemy.exc import DBAPIError, OperationalError
from api.routers import administracion_versiones
from domain.listas.administracion import EjecucionAdministrativa, OperacionMotivada
from domain.listas.errores import ConflictoListas
from infrastructure.persistencia.modelos_listas import (VersionFuente, FuenteVersionActiva, PoliticaListas,
    EventoActivacion, ArchivoFuente, EsquemaFuente, RevisionComparacion)
from infrastructure.persistencia.modelos_administracion_listas import (SolicitudAdministrativaLista,
    TrabajoComparacionLista, EventoAdministrativoLista)
from services.listas.informes import calcular_huella
from services.listas.politica_v2 import ActorListas, PoliticaListasV2
from services.listas.administracion_versiones import ServicioAdministracionVersiones
from services.listas.trabajador_comparacion import TrabajadorComparacionListas
from .test_flujo_http import portal
from .test_recepcion_f52 import carga
from .test_importacion_f54 import preparar, importador

BASE = '/api/administracion-listas'


@pytest.fixture
def administracion(carga, monkeypatch):
    carga.app.include_router(administracion_versiones.enrutador)
    preparar(carga)
    assert importador(carga).ejecutar_uno()
    with carga.sesiones.begin() as sesion:
        version = sesion.scalar(select(VersionFuente))
        carga.version, carga.fuente = version.id, version.fuente_id
        carga.politica_id = uuid4()
        parametros = {'solo_pruebas': True}
        sesion.add(PoliticaListas(id=carga.politica_id, codigo='administracion-sintetica', version=1,
            parametros=parametros, huella=calcular_huella(parametros),
            aprobador_emisor=carga.app.state.config.keycloak.issuer, aprobador_sujeto='revisor-politica'))
    monkeypatch.setenv('LISTAS_ADMIN_POLITICA_ID', str(carga.politica_id))
    return carga


def identidad(a, sujeto='operador-local', roles=('listas_cargador',)):
    a.cliente.headers['Authorization'] = 'Bearer ' + a.token(list(roles), sub=sujeto)


def servicio(a, sujeto='revisor', roles=('listas_aprobador',), **opciones):
    return ServicioAdministracionVersiones(a.sesiones, a.custodia,
        PoliticaListasV2(a.app.state.config.listas_cautela, 'development'),
        ActorListas.desde_identidad_validada(a.app.state.config.keycloak.issuer, sujeto, roles),
        'development', lambda: a.politica_id, **opciones)


def comparar(a, destino=None, revision=0, clave='comparar'):
    respuesta = a.cliente.post(BASE+'/comparaciones', json={'fuente_id':str(a.fuente),
        'destino_id':str(destino or a.version), 'revision_esperada':revision, 'clave':clave})
    assert respuesta.status_code == 202, respuesta.text
    comparacion = respuesta.json()['comparacion_id']
    assert TrabajadorComparacionListas(a.sesiones, a.custodia, 'development', True).ejecutar_uno()
    informe = a.cliente.get(BASE+'/comparaciones/'+comparacion)
    assert informe.status_code == 200, informe.text
    assert informe.json()['estado'] == 'COMPLETADO', informe.text
    return comparacion


def solicitar(a, comparacion=None, tipo='ACTIVACION', clave='solicitar'):
    comparacion = comparacion or comparar(a)
    respuesta = a.cliente.post(BASE+'/solicitudes', json={'comparacion_id':comparacion,
        'politica_id':str(a.politica_id), 'tipo':tipo, 'motivo':'Cambio sintético revisable', 'clave':clave})
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()['solicitud_id']


def decidir(a, solicitud, decision='APROBADA', clave='decidir'):
    return a.cliente.post(BASE+f'/solicitudes/{solicitud}/decisiones', json={'solicitud_id':solicitud,
        'decision':decision, 'motivo':'Revisión de evidencia sintética', 'clave':clave})


def aprobada(a):
    solicitud = solicitar(a)
    identidad(a, 'revisor', ('listas_aprobador',))
    respuesta = decidir(a, solicitud)
    assert respuesta.status_code == 201, respuesta.text
    return solicitud, respuesta.json()['revision_id']


def ejecutar(a, solicitud, aprobacion, revision=0, clave='ejecutar'):
    return a.cliente.post(BASE+f'/solicitudes/{solicitud}/ejecuciones', json={'solicitud_id':solicitud,
        'aprobacion_id':aprobacion, 'revision_esperada':revision, 'clave':clave})


def test_flujo_http_dos_personas_idempotencia_y_auditoria(administracion):
    a = administracion
    solicitud, aprobacion = aprobada(a)
    primera = ejecutar(a, solicitud, aprobacion)
    assert primera.status_code == 200, primera.text
    assert ejecutar(a, solicitud, aprobacion).json() == primera.json()
    assert ejecutar(a, solicitud, aprobacion, clave='otra').status_code == 409
    assert a.cliente.get(BASE+'/solicitudes/'+solicitud).json()['estado'] == 'EJECUTADA'
    with a.sesiones() as sesion:
        assert sesion.get(FuenteVersionActiva, a.fuente).version_id == a.version
        assert sesion.scalar(select(func.count()).select_from(EventoActivacion)) == 1
        assert sesion.scalar(select(func.count()).select_from(EventoAdministrativoLista)) == 5


@pytest.mark.parametrize('sin_exp,roles', [(True,['listas_aprobador']),(False,[])])
def test_jwt_y_permisos_reales(administracion,sin_exp,roles):
    a=administracion
    a.cliente.headers['Authorization']='Bearer '+a.token(roles,sin_exp=sin_exp)
    respuesta=a.cliente.post(BASE+'/comparaciones',json={'fuente_id':str(a.fuente),'destino_id':str(a.version),'revision_esperada':0,'clave':'uno'})
    assert respuesta.status_code == (401 if sin_exp else 403)


def test_solicitante_aprueba_y_tercero_no_ejecuta(administracion):
    a=administracion
    solicitud=solicitar(a)
    identidad(a,'operador-local',('listas_aprobador',))
    respuesta=decidir(a,solicitud)
    assert respuesta.status_code==201, respuesta.text
    aprobacion=respuesta.json()['revision_id']
    identidad(a,'tercero',('listas_aprobador',))
    assert ejecutar(a,solicitud,aprobacion).status_code==403
    identidad(a,'operador-local',('listas_aprobador',))
    assert ejecutar(a,solicitud,aprobacion).status_code==200
    with a.sesiones() as sesion:
        revision=sesion.get(RevisionComparacion, UUID(aprobacion))
        evento=sesion.scalar(select(EventoActivacion))
        assert revision.actor_sujeto == evento.actor_sujeto == 'operador-local'
        assert evento.destino_id == a.version
        assert revision.creado_en is not None and evento.creado_en is not None


def test_rechazo_no_se_convierte_en_aprobacion(administracion):
    a=administracion; solicitud=solicitar(a)
    identidad(a,'revisor',('listas_aprobador',))
    assert decidir(a,solicitud,'RECHAZADA').status_code==201
    assert decidir(a,solicitud,clave='otra').status_code==409


def test_revocacion_impide_ejecucion(administracion):
    a=administracion; solicitud,aprobacion=aprobada(a)
    respuesta=a.cliente.post(BASE+f'/revisiones/{aprobacion}/revocaciones',json={'objeto_id':aprobacion,'motivo':'Revisión retirada','clave':'revocar'})
    assert respuesta.status_code==201,respuesta.text
    assert ejecutar(a,solicitud,aprobacion).status_code==409


def test_politica_cambiada_no_ejecuta(administracion,monkeypatch):
    a=administracion; solicitud,aprobacion=aprobada(a)
    monkeypatch.setenv('LISTAS_ADMIN_POLITICA_ID',str(uuid4()))
    assert ejecutar(a,solicitud,aprobacion).status_code==409


@pytest.mark.parametrize('tipo',['original','esquema'])
def test_custodia_corrupta_no_activa(administracion,tipo):
    a=administracion; solicitud,aprobacion=aprobada(a)
    with a.sesiones() as sesion:
        version=sesion.get(VersionFuente,a.version)
        identificador=version.archivo_raiz_id if tipo=='original' else sesion.get(EsquemaFuente,version.esquema_id).archivo_id
        huella=sesion.get(ArchivoFuente,identificador).huella
    (a.custodia.directorio/huella).write_bytes(b'alterado')
    assert ejecutar(a,solicitud,aprobacion).status_code==503
    with a.sesiones() as sesion: assert sesion.get(FuenteVersionActiva,a.fuente).version_id is None


def test_revision_ajena_y_ruta_cuerpo(administracion):
    a=administracion; solicitud,aprobacion=aprobada(a)
    assert ejecutar(a,solicitud,str(uuid4())).status_code==409
    assert a.cliente.post(BASE+f'/solicitudes/{uuid4()}/decisiones',json={'solicitud_id':solicitud,'decision':'APROBADA','motivo':'Prueba','clave':'otra'}).status_code==422


def test_sql_rechaza_solicitud_y_decision_inmutables(administracion):
    a=administracion; solicitud,aprobacion=aprobada(a)
    with pytest.raises(DBAPIError),a.sesiones.begin() as sesion:
        sesion.execute(text('UPDATE solicitud_administrativa_lista SET motivo=\'otro\' WHERE id=:id'),{'id':solicitud})
    with pytest.raises(DBAPIError),a.sesiones.begin() as sesion:
        sesion.add(RevisionComparacion(solicitud_id=UUID(solicitud),comparacion_id=sesion.get(SolicitudAdministrativaLista,UUID(solicitud)).comparacion_id,
            decision='RECHAZADA',actor_emisor=a.app.state.config.keycloak.issuer,actor_sujeto='otro',motivo='Segundo resultado'))


def test_dos_ejecuciones_concurrentes_una_transicion(administracion):
    a=administracion; solicitud,aprobacion=aprobada(a)
    def una(clave):
        try:
            return servicio(a).ejecutar(EjecucionAdministrativa(solicitud_id=solicitud,aprobacion_id=aprobacion,revision_esperada=0,clave=clave))
        except ConflictoListas: return None
    with ThreadPoolExecutor(max_workers=2) as grupo: resultados=list(grupo.map(una,['uno','dos']))
    assert sum(r is not None for r in resultados)==1
    with a.sesiones() as sesion: assert sesion.scalar(select(func.count()).select_from(EventoActivacion))==1


def test_fallo_sql_revierte_y_respuesta_perdida_no_duplica(administracion):
    a=administracion; solicitud,aprobacion=aprobada(a)
    datos=EjecucionAdministrativa(solicitud_id=solicitud,aprobacion_id=aprobacion,revision_esperada=0,clave='fallo')
    def fallar(etapa,tipo):
        if etapa=='antes_commit': raise OperationalError('ensayo',{},Exception('fallo'))
    with pytest.raises(OperationalError): servicio(a,observador=fallar).ejecutar(datos)
    with a.sesiones() as sesion:
        assert sesion.get(FuenteVersionActiva,a.fuente).version_id is None
        assert sesion.scalar(select(func.count()).select_from(EventoActivacion))==0
    def perdida(etapa,tipo):
        if etapa=='despues_commit': raise ConnectionError('Respuesta perdida')
    with pytest.raises(ConnectionError): servicio(a,observador=perdida).ejecutar(datos)
    resultado=servicio(a).ejecutar(datos)
    assert resultado['revision']==1


def test_revisor_descarga_original_sin_ser_cargador(administracion):
    a=administracion
    identidad(a,'revisor',('listas_aprobador',))
    respuesta=a.cliente.get(BASE+f'/versiones/{a.version}/evidencias/original')
    assert respuesta.status_code==200,respuesta.text
    assert b'prueba_' in respuesta.content
    identidad(a,'ajeno',('listas_operador',))
    assert a.cliente.get(BASE+f'/versiones/{a.version}/evidencias/original').status_code==403


@pytest.mark.parametrize('mismo_usuario', [False, True])
def test_restauracion_con_dos_personas_cargador_historico_aprueba(administracion, mismo_usuario):
    a=administracion
    solicitud,aprobacion=aprobada(a)
    assert ejecutar(a,solicitud,aprobacion).status_code==200
    identidad(a)
    preparar(a,'v2.xml'); assert importador(a).ejecutar_uno()
    with a.sesiones() as sesion: segunda=sesion.scalar(select(VersionFuente.id).where(VersionFuente.id!=a.version))
    comparacion=comparar(a,segunda,1,'comparar-2')
    solicitud=solicitar(a,comparacion,clave='solicitar-2')
    identidad(a,'revisor',('listas_aprobador',))
    aprobacion=decidir(a,solicitud,clave='decidir-2').json()['revision_id']
    assert ejecutar(a,solicitud,aprobacion,1,'ejecutar-2').status_code==200
    comparacion=comparar(a,a.version,2,'comparar-3')
    solicitud=solicitar(a,comparacion,'REVERSION','restaurar')
    identidad(a,'revisor' if mismo_usuario else 'operador-local',('listas_aprobador',))
    respuesta=decidir(a,solicitud,clave='decidir-3')
    assert respuesta.status_code==201,respuesta.text
    respuesta=ejecutar(a,solicitud,respuesta.json()['revision_id'],2,'ejecutar-3')
    assert respuesta.status_code==200,respuesta.text
    with a.sesiones() as sesion:
        assert sesion.get(FuenteVersionActiva,a.fuente).version_id==a.version
        assert sesion.scalar(select(func.count()).select_from(EventoActivacion))==3


@pytest.mark.parametrize('operacion,etapa',[('comparar','antes_commit'),('comparar','despues_commit'),('ejecutar','antes_commit'),('ejecutar','despues_commit')])
def test_sigkill_reinicio_real_sin_duplicados(administracion,tmp_path,operacion,etapa):
    import json,os,signal,subprocess,sys,time
    from pathlib import Path
    a=administracion
    opciones={'custodia':str(a.custodia.directorio),'senal':str(tmp_path/'senal.json'),
              'detener':etapa,'operacion':operacion,'politica':str(a.politica_id),'emisor':a.app.state.config.keycloak.issuer}
    if operacion=='ejecutar':
        solicitud,aprobacion=aprobada(a)
        opciones['datos']={'solicitud_id':solicitud,'aprobacion_id':aprobacion,'revision_esperada':0,'clave':'proceso'}
    else:
        respuesta=a.cliente.post(BASE+'/comparaciones',json={'fuente_id':str(a.fuente),'destino_id':str(a.version),'revision_esperada':0,'clave':'proceso'})
        assert respuesta.status_code==202
    configuracion=tmp_path/'proceso.json';configuracion.write_text(json.dumps(opciones))
    comando=[sys.executable,str(Path(__file__).with_name('proceso_administracion_sintetica.py')),str(configuracion)]
    proceso=subprocess.Popen(comando)
    try:
        limite=time.monotonic()+15
        while not Path(opciones['senal']).exists() and time.monotonic()<limite:
            assert proceso.poll() is None
            time.sleep(.02)
        assert Path(opciones['senal']).exists()
        proceso.kill();proceso.wait(timeout=5)
        assert proceso.returncode==-signal.SIGKILL
        with a.sesiones() as sesion:
            cantidad=sesion.scalar(select(func.count()).select_from(EventoActivacion))
            assert cantidad==(1 if operacion=='ejecutar' and etapa=='despues_commit' else 0)
        evidencia=json.loads(Path(opciones['senal']).read_text())
        opciones['detener']=None;configuracion.write_text(json.dumps(opciones))
        reinicio=subprocess.run(comando,capture_output=True,text=True,timeout=20)
        assert reinicio.returncode==0,reinicio.stderr
        with a.sesiones() as sesion:
            assert sesion.scalar(select(TrabajoComparacionLista.estado))=='COMPLETADO'
            assert sesion.scalar(select(func.count()).select_from(EventoActivacion))==(1 if operacion=='ejecutar' else 0)
        evidencia.update(resultado='RECUPERADO_SIN_DUPLICADOS',senal='SIGKILL')
        Path(os.environ['LISTAS_EVIDENCIAS_DIRECTORIO'],f'administracion-{operacion}-{etapa}.json').write_text(json.dumps(evidencia,indent=2))
    finally:
        if proceso.poll() is None: proceso.kill();proceso.wait(timeout=5)


@pytest.mark.parametrize('operacion',['revocar','bloquear'])
def test_carrera_ejecucion_y_revocacion_o_bloqueo(administracion,operacion):
    a=administracion; solicitud,aprobacion=aprobada(a)
    datos=EjecucionAdministrativa(solicitud_id=solicitud,aprobacion_id=aprobacion,revision_esperada=0,clave='carrera')
    def ejecutar_una():
        try: return servicio(a).ejecutar(datos)
        except ConflictoListas: return None
    def impedir():
        try:
            if operacion=='revocar':
                return servicio(a).revocar(OperacionMotivada(objeto_id=aprobacion,motivo='Incidente sintético',clave='incidente'))
            return servicio(a,roles=('listas_incidentes',)).bloquear(OperacionMotivada(objeto_id=a.version,motivo='Incidente sintético',clave='incidente'))
        except ConflictoListas: return None
    with ThreadPoolExecutor(max_workers=2) as grupo:
        uno=grupo.submit(ejecutar_una);dos=grupo.submit(impedir)
        ejecucion,incidente=uno.result(),dos.result()
    with a.sesiones() as sesion:
        eventos=sesion.scalar(select(func.count()).select_from(EventoActivacion))
        assert eventos==int(ejecucion is not None)
        if operacion=='revocar': assert (ejecucion is None)!=(incidente is None)
        else: assert sesion.get(VersionFuente,a.version).estado=='BLOQUEADA'


def test_comparacion_alta_baja_modificacion_y_paginacion(administracion):
    a=administracion;solicitud,aprobacion=aprobada(a)
    assert ejecutar(a,solicitud,aprobacion).status_code==200
    identidad(a);preparar(a,'v2.xml');assert importador(a).ejecutar_uno()
    with a.sesiones() as sesion: segunda=sesion.scalar(select(VersionFuente.id).where(VersionFuente.id!=a.version))
    comparacion=comparar(a,segunda,1,'v2')
    informe=a.cliente.get(BASE+f'/comparaciones/{comparacion}?limite=1').json()
    assert informe['informe']['conteos']=={'ALTA':1,'BAJA':1,'MODIFICACION':1,'SIN_CAMBIOS':0}
    assert len(informe['cambios'])==1 and informe['total_cambios']==3
    assert a.cliente.get(BASE+f'/comparaciones/{comparacion}?limite=101').status_code==422


def test_clave_con_cuerpo_distinto_y_fuente_ajena(administracion):
    a=administracion
    datos={'fuente_id':str(a.fuente),'destino_id':str(a.version),'revision_esperada':0,'clave':'igual'}
    respuesta=a.cliente.post(BASE+'/comparaciones',json=datos)
    assert respuesta.status_code==202
    assert a.cliente.post(BASE+'/comparaciones',json=datos).json()==respuesta.json()
    assert a.cliente.post(BASE+'/comparaciones',json={**datos,'revision_esperada':1}).status_code==409
    assert a.cliente.post(BASE+'/comparaciones',json={**datos,'fuente_id':str(uuid4()),'clave':'ajena'}).status_code==404


def test_sesion_vencida_al_confirmar_revierte(administracion):
    a=administracion;solicitud,aprobacion=aprobada(a)
    def vencida(): raise PermissionError('Sesión vencida')
    with pytest.raises(PermissionError):
        servicio(a,validar_identidad=vencida).ejecutar(EjecucionAdministrativa(solicitud_id=solicitud,aprobacion_id=aprobacion,revision_esperada=0,clave='vencida'))
    with a.sesiones() as sesion: assert sesion.get(FuenteVersionActiva,a.fuente).version_id is None


def test_migracion_conserva_f2_y_rechaza_downgrade_con_historial(administracion):
    from alembic import command
    from alembic.config import Config
    from pathlib import Path
    a=administracion;solicitar(a)
    config=Config(str(Path(__file__).resolve().parents[2]/'backend/alembic.ini'))
    with pytest.raises(RuntimeError,match='historial'): command.downgrade(config,'d54e67f890a1')


def test_historial_y_pdf_no_cambian_al_activar_y_restaurar(administracion):
    from .test_flujo_http import finalizar
    a=administracion
    identidad(a,'operador-local',('acceso_clientes','listas_revisor'))
    consulta=finalizar(a)['consulta']
    consulta_id=consulta['consulta_id'];evidencia=consulta['evidencias'][0]
    ruta=f'/api/consultas-listas/{consulta_id}/evidencias/{evidencia["id"]}'
    anterior=a.cliente.get(ruta)
    assert anterior.status_code==200
    identidad(a)
    test_restauracion_con_dos_personas_cargador_historico_aprueba(a, False)
    identidad(a,'operador-local',('acceso_clientes','listas_revisor'))
    assert a.cliente.get(ruta).content==anterior.content
    assert a.cliente.get(f'/api/consultas-listas/{consulta_id}').json()['consulta']==consulta


def test_comparador_no_confunde_reordenamiento_ni_normalizador():
    from types import SimpleNamespace
    from services.listas.comparacion_versiones import contenido_canonico,comparar_registros
    contenido={'uid':'sintetico','clase':'PERSONA','campos':[{'tipo':'nombre','texto':'Ficticio','atributos':{}},
        {'tipo':'alias','texto':'Alias','atributos':{}}]}
    assert contenido_canonico(contenido)==contenido_canonico({**contenido,'campos':list(reversed(contenido['campos']))})
    base=SimpleNamespace(formato='SINTETICO_XML_V1',version_normalizador='otro',version_importador='sintetico-v1')
    destino=SimpleNamespace(formato='SINTETICO_XML_V1',version_normalizador='nfc-v1',version_importador='sintetico-v1')
    with pytest.raises(ConflictoListas): comparar_registros(None,base,destino)


def test_sql_no_omite_solicitud_para_version_f54(administracion):
    a=administracion;comparacion=comparar(a)
    with pytest.raises(DBAPIError,match='exige solicitud'),a.sesiones.begin() as sesion:
        sesion.add(RevisionComparacion(comparacion_id=UUID(comparacion),decision='APROBADA',
            actor_emisor=a.app.state.config.keycloak.issuer,actor_sujeto='revisor',motivo='Sin solicitud'))


def test_dos_solicitudes_aprobadas_revision_vieja_no_ejecuta(administracion):
    a=administracion;comparacion=comparar(a)
    primera=solicitar(a,comparacion,clave='primera');segunda=solicitar(a,comparacion,clave='segunda')
    identidad(a,'revisor',('listas_aprobador',))
    uno=decidir(a,primera,clave='uno').json()['revision_id'];dos=decidir(a,segunda,clave='dos').json()['revision_id']
    assert ejecutar(a,primera,uno).status_code==200
    assert ejecutar(a,segunda,dos,clave='otra').status_code==409


def test_flag_entorno_y_jwt_vencido(administracion):
    from datetime import datetime,timedelta,timezone
    a=administracion
    datos={'fuente_id':str(a.fuente),'destino_id':str(a.version),'revision_esperada':0,'clave':'uno'}
    a.cliente.headers['Authorization']='Bearer '+a.token(['listas_aprobador'],exp=datetime.now(timezone.utc)-timedelta(seconds=10))
    assert a.cliente.post(BASE+'/comparaciones',json=datos).status_code==401
    identidad(a)
    a.app.state.config.entorno='staging'
    assert a.cliente.post(BASE+'/comparaciones',json=datos).status_code==403
    a.app.state.config.entorno='development'
    from infrastructure.config.configuracion import SagrilaftListasConfig
    a.app.state.config.listas_cautela=SagrilaftListasConfig(proveedor='deshabilitado')
    assert a.cliente.post(BASE+'/comparaciones',json=datos).status_code==409


def test_comparacion_corrupta_no_publica_informe(administracion):
    a=administracion
    respuesta=a.cliente.post(BASE+'/comparaciones',json={'fuente_id':str(a.fuente),'destino_id':str(a.version),'revision_esperada':0,'clave':'corrupto'})
    identificador=respuesta.json()['comparacion_id']
    with a.sesiones() as sesion:
        version=sesion.get(VersionFuente,a.version);archivo=sesion.get(ArchivoFuente,version.archivo_raiz_id)
    (a.custodia.directorio/archivo.huella).write_bytes(b'corrupto')
    assert TrabajadorComparacionListas(a.sesiones,a.custodia,'development',True).ejecutar_uno()
    assert a.cliente.get(BASE+'/comparaciones/'+identificador).json()['estado']=='FALLIDO'
    respuesta=a.cliente.post(BASE+'/solicitudes',json={'comparacion_id':identificador,'politica_id':str(a.politica_id),'tipo':'ACTIVACION','motivo':'No debe solicitar','clave':'falla'})
    assert respuesta.status_code==404


def test_modelos_y_migracion_f55_coinciden(administracion_bd):
    from sqlalchemy import inspect,CheckConstraint
    from infrastructure.persistencia.modelos_administracion_listas import OperacionAdministrativaLista
    inspector=inspect(administracion_bd)
    for modelo in (SolicitudAdministrativaLista,TrabajoComparacionLista,OperacionAdministrativaLista,EventoAdministrativoLista):
        tabla=modelo.__table__
        columnas={c['name']:c for c in inspector.get_columns(tabla.name)}
        assert set(columnas)==set(tabla.columns.keys())
        assert all(columnas[c.name]['nullable']==c.nullable for c in tabla.columns)
        assert {r['name'] for r in inspector.get_check_constraints(tabla.name)}=={c.name for c in tabla.constraints if isinstance(c,CheckConstraint)}


def test_comparacion_respeta_cupo_global(administracion):
    a=administracion
    respuesta=a.cliente.post(BASE+'/comparaciones',json={'fuente_id':str(a.fuente),'destino_id':str(a.version),'revision_esperada':0,'clave':'cupo'})
    assert respuesta.status_code==202
    with a.sesiones.begin() as sesion:
        sesion.execute(text('SELECT pg_advisory_xact_lock(523003)'))
        assert not TrabajadorComparacionListas(a.sesiones,a.custodia,'development',True).ejecutar_uno()
    assert TrabajadorComparacionListas(a.sesiones,a.custodia,'development',True).ejecutar_uno()


def test_cli_y_trabajador_local_usando_api_real(administracion,tmp_path,monkeypatch,capsys):
    import importlib.util,os,subprocess,sys,threading,time,socket
    from pathlib import Path
    import uvicorn
    a=administracion
    raiz=Path(__file__).resolve().parents[2]
    especificacion=importlib.util.spec_from_file_location('cliente_administrativo',raiz/'scripts/listas/administrar_sintetico.py')
    cliente=importlib.util.module_from_spec(especificacion);especificacion.loader.exec_module(cliente)
    datos=tmp_path/'comparacion.json'
    import json
    datos.write_text(json.dumps({'fuente_id':str(a.fuente),'destino_id':str(a.version),'revision_esperada':0,'clave':'cli'}))
    with socket.socket() as conexion:
        conexion.bind(('127.0.0.1',0));puerto=conexion.getsockname()[1]
    servidor=uvicorn.Server(uvicorn.Config(a.app,host='127.0.0.1',port=puerto,log_level='error'))
    hilo=threading.Thread(target=servidor.run,daemon=True);hilo.start()
    try:
        limite=time.monotonic()+10
        while not servidor.started and time.monotonic()<limite: time.sleep(.02)
        assert servidor.started
        monkeypatch.setattr(cliente.getpass,'getpass',lambda _:a.token(['listas_cargador']))
        monkeypatch.setattr(sys,'argv',['administrar_sintetico.py','comparar','--datos',str(datos),'--url',f'http://127.0.0.1:{puerto}'])
        cliente.principal()
        identificador=json.loads(capsys.readouterr().out)['comparacion_id']
        entorno={**os.environ,'LISTAS_CUSTODIA_DIRECTORIO':str(a.custodia.directorio),'LISTAS_ADMIN_HABILITADA':'true'}
        resultado=subprocess.run([sys.executable,str(raiz/'scripts/validacion/ejecutar_comparacion_listas.py')],env=entorno,capture_output=True,text=True,timeout=20)
        assert resultado.returncode==0,resultado.stderr
        assert a.cliente.get(BASE+'/comparaciones/'+identificador).json()['estado']=='COMPLETADO'
    finally:
        servidor.should_exit=True;hilo.join(timeout=10)
        assert not hilo.is_alive()


def test_upgrade_f55_conserva_version_y_aprobacion_f2(escenario,administracion_bd):
    from alembic import command
    from alembic.config import Config
    from pathlib import Path
    from .conftest import crear_version,preparar_comparacion,activar_version
    configuracion=Config(str(Path(__file__).resolve().parents[2]/'backend/alembic.ini'))
    version,_=crear_version(escenario)
    comparacion,aprobacion=preparar_comparacion(escenario,version)
    activar_version(escenario,comparacion,aprobacion)
    with escenario.sesiones() as sesion:
        original=sesion.get(VersionFuente,version).manifiesto
        revision=sesion.get(FuenteVersionActiva,escenario.fuente).revision
    command.downgrade(configuracion,'d54e67f890a1')
    command.upgrade(configuracion,'head')
    with administracion_bd.begin() as conexion:
        conexion.execute(text('GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA public TO aplicacion_listas'))
    with escenario.sesiones() as sesion:
        assert sesion.get(VersionFuente,version).manifiesto==original
        assert sesion.get(FuenteVersionActiva,escenario.fuente).revision==revision
        assert sesion.scalar(select(func.count()).select_from(SolicitudAdministrativaLista))==0


def test_catalogo_y_limite_metadatos(administracion):
    a=administracion
    fuentes=a.cliente.get(BASE+'/fuentes').json()
    assert len(fuentes)==1 and fuentes[0]['fuente_id']==str(a.fuente)
    versiones=a.cliente.get(BASE+f'/fuentes/{a.fuente}/versiones').json()
    assert versiones['revision']==0 and versiones['activa_id'] is None
    assert versiones['versiones'][0]['version_id']==str(a.version)
    assert a.cliente.get(BASE+f'/fuentes/{uuid4()}/versiones').status_code==404
    assert a.cliente.post(BASE+'/comparaciones',content=b' '*16385,headers={'Content-Type':'application/json'}).status_code==413


def test_comparacion_aba_no_se_reutiliza(administracion):
    a=administracion
    solicitud,aprobacion=aprobada(a);assert ejecutar(a,solicitud,aprobacion).status_code==200
    identidad(a);preparar(a,'v2.xml');assert importador(a).ejecutar_uno()
    with a.sesiones() as sesion: segunda=sesion.scalar(select(VersionFuente.id).where(VersionFuente.id!=a.version))
    comparacion=comparar(a,segunda,1,'v2')
    solicitud=solicitar(a,comparacion,clave='v2')
    identidad(a,'revisor',('listas_aprobador',))
    aprobacion=decidir(a,solicitud,clave='v2').json()['revision_id']
    assert ejecutar(a,solicitud,aprobacion,1,'v2').status_code==200
    vuelta=comparar(a,a.version,2,'vuelta')
    solicitud=solicitar(a,vuelta,'REVERSION','vuelta')
    identidad(a,'operador-local',('listas_aprobador',))
    aprobacion=decidir(a,solicitud,clave='vuelta').json()['revision_id']
    assert ejecutar(a,solicitud,aprobacion,2,'vuelta').status_code==200
    respuesta=a.cliente.post(BASE+'/solicitudes',json={'comparacion_id':comparacion,'politica_id':str(a.politica_id),
        'tipo':'ACTIVACION','motivo':'Comparación antigua inválida','clave':'aba'})
    assert respuesta.status_code==409


def test_bloquear_antes_de_ejecutar_no_cambia_puntero(administracion):
    a=administracion;solicitud,aprobacion=aprobada(a)
    servicio(a,roles=('listas_incidentes',)).bloquear(OperacionMotivada(objeto_id=a.version,motivo='Bloqueo preventivo',clave='bloquear'))
    assert ejecutar(a,solicitud,aprobacion).status_code==409
    with a.sesiones() as sesion: assert sesion.get(FuenteVersionActiva,a.fuente).version_id is None


def test_sql_impide_ejecutor_distinto_aunque_posea_aprobacion(administracion):
    a=administracion;solicitud,aprobacion=aprobada(a)
    with pytest.raises(DBAPIError,match='Ejecución incompatible'),a.sesiones.begin() as sesion:
        s=sesion.get(SolicitudAdministrativaLista,UUID(solicitud))
        sesion.add(EventoActivacion(solicitud_id=s.id,fuente_id=a.fuente,anterior_id=None,destino_id=a.version,
            comparacion_id=s.comparacion_id,aprobacion_id=UUID(aprobacion),revision_anterior=0,revision_nueva=1,
            tipo='ACTIVACION',actor_emisor=a.app.state.config.keycloak.issuer,actor_sujeto='intruso',motivo='Prueba SQL',
            clave_idempotencia='sql',huella_peticion='a'*64,politica_id=a.politica_id))


def test_informe_completo_determinista_y_dos_trabajadores(administracion):
    a=administracion
    datos={'fuente_id':str(a.fuente),'destino_id':str(a.version),'revision_esperada':0,'clave':'uno'}
    primero=a.cliente.post(BASE+'/comparaciones',json=datos).json()['comparacion_id']
    def uno(_): return TrabajadorComparacionListas(a.sesiones,a.custodia,'development',True).ejecutar_uno()
    with ThreadPoolExecutor(max_workers=2) as grupo: assert sorted(grupo.map(uno,range(2)))==[False,True]
    segundo=comparar(a,clave='dos')
    informe_uno=a.cliente.get(BASE+'/comparaciones/'+primero).json()
    informe_dos=a.cliente.get(BASE+'/comparaciones/'+segundo).json()
    assert informe_uno['huella']==informe_dos['huella']
    assert informe_uno['cambios']==informe_dos['cambios']


def test_descarga_cierra_copia_si_commit_auditoria_falla(administracion,monkeypatch):
    from infrastructure.listas import recepcion_archivo
    a=administracion;copias=[]
    original=recepcion_archivo.original_verificado
    def registrar(*argumentos):
        copia=original(*argumentos);copias.append(copia);return copia
    monkeypatch.setattr(recepcion_archivo,'original_verificado',registrar)
    administrador=servicio(a)
    evento=administrador._evento
    def romper_confirmacion(sesion,fuente,tipo,detalle):
        evento(sesion,fuente,tipo,detalle)
        puntero=sesion.get(FuenteVersionActiva,fuente)
        # Restricción diferida real: un cambio de puntero sin evento falla al commit.
        puntero.version_id=a.version;puntero.revision=1
    monkeypatch.setattr(administrador,'_evento',romper_confirmacion)
    with pytest.raises(DBAPIError): administrador.evidencia(a.version,'original')
    assert len(copias)==1 and copias[0].closed
    with a.sesiones() as sesion:
        assert sesion.get(FuenteVersionActiva,a.fuente).version_id is None
        assert sesion.scalar(select(func.count()).select_from(EventoAdministrativoLista))==0


def test_migracion_mismo_usuario_reversible_sin_borrar_historial(administracion_bd):
    import importlib.util
    from pathlib import Path
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    ruta = Path(__file__).resolve().parents[2] / 'backend/alembic/versions/k21f34a567b8_aprobacion_mismo_usuario.py'
    especificacion = importlib.util.spec_from_file_location('migracion_mismo_usuario', ruta)
    migracion = importlib.util.module_from_spec(especificacion)
    especificacion.loader.exec_module(migracion)
    with administracion_bd.begin() as conexion:
        contexto = MigrationContext.configure(conexion)
        conteo = conexion.execute(text('SELECT count(*) FROM revision_comparacion')).scalar_one()
        with Operations.context(contexto):
            migracion.downgrade()
            anterior = conexion.execute(text("SELECT pg_get_functiondef('listas_validar_solicitud()'::regprocedure)")).scalar_one()
            assert 'El solicitante no puede decidir' in anterior
            migracion.upgrade()
        vigente = conexion.execute(text("SELECT pg_get_functiondef('listas_validar_solicitud()'::regprocedure)")).scalar_one()
        assert 'El solicitante no puede decidir' not in vigente
        assert 'Ejecución incompatible con solicitud y aprobador' in vigente
        assert conexion.execute(text('SELECT count(*) FROM revision_comparacion')).scalar_one() == conteo
