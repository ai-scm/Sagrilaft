"""F5.4 con PostgreSQL migrado, XML sintético e identidad real local."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID
from concurrent.futures import ThreadPoolExecutor
import pytest
from sqlalchemy import select, func, text
from sqlalchemy.exc import DBAPIError, OperationalError
from infrastructure.persistencia.modelos_listas import (VersionFuente, IntentoImportacion, RegistroLista,
    NombreRegistro, IdentificadorRegistro, RelacionRegistro, FuenteVersionActiva, ArchivoFuente)
from infrastructure.persistencia.modelos_importacion_listas import ControlImportacionVersion, LoteImportacionLista, RecepcionVersionLista
from services.listas.importacion_archivos import TrabajadorImportacionArchivos, ImportacionInvalida
from domain.listas.errores import ConflictoListas, ErrorIntegridadEvidencia
from .test_flujo_http import portal
from .test_recepcion_f52 import carga, BASE
from .test_validacion_f53 import recibir, trabajador as validador


def preparar(carga,archivo='v1.xml'):
    recepcion=recibir(carga,archivo)
    assert validador(carga).ejecutar_uno()
    return recepcion


def importador(carga,observador=None):
    trabajador=TrabajadorImportacionArchivos(carga.sesiones,carga.custodia,'development',habilitado=True,observador=observador)
    trabajador.perfil=trabajador.perfil.model_copy(update={'lote_registros':1})
    return trabajador


def test_importa_todos_los_campos_sella_y_no_activa(carga):
    recepcion=preparar(carga)
    assert importador(carga).ejecutar_uno()
    assert not importador(carga).ejecutar_uno()
    with carga.sesiones() as sesion:
        version=sesion.scalar(select(VersionFuente))
        assert version.estado=='VALIDA' and version.cantidad_registros==2
        assert sesion.scalar(select(FuenteVersionActiva.version_id)) is None
        assert sesion.scalar(select(func.count()).select_from(LoteImportacionLista))==2
        assert sesion.scalar(select(func.count()).select_from(NombreRegistro))==3
        assert sesion.scalar(select(IdentificadorRegistro.original))=='00001'
        relacion=sesion.scalar(select(RelacionRegistro))
        assert relacion.registro_destino_id is not None
        assert sesion.get(RegistroLista,relacion.registro_destino_id).uid_original=='prueba_empresa'
        intento=sesion.scalar(select(IntentoImportacion))
        respuesta=carga.cliente.get(f'/api/administracion-listas/intentos/{intento.id}')
        assert respuesta.status_code==200,respuesta.text
        assert respuesta.json()['estado']=='COMPLETADO' and respuesta.json()['registros_confirmados']==2
        assert version.recepcion_id==UUID(recepcion)


def test_deduplica_xml_y_zip_sin_cambiar_cargador(carga):
    primero=preparar(carga); assert importador(carga).ejecutar_uno()
    carga.cliente.headers['Authorization']='Bearer '+carga.token(['listas_cargador'],sub='otra-persona')
    segundo=preparar(carga,'v1.zip'); assert importador(carga).ejecutar_uno()
    assert primero!=segundo
    with carga.sesiones() as sesion:
        assert sesion.scalar(select(func.count()).select_from(VersionFuente))==1
        assert sesion.scalar(select(func.count()).select_from(RecepcionVersionLista))==2
        assert sesion.scalar(select(VersionFuente.recepcion_id))==UUID(primero)
        assert all(i.estado=='COMPLETADO' for i in sesion.scalars(select(IntentoImportacion)))
        assert sesion.scalar(select(func.count()).select_from(RegistroLista))==2


def test_un_escritor_concurrente(carga):
    preparar(carga)
    with ThreadPoolExecutor(max_workers=2) as grupo:
        resultados=list(grupo.map(lambda _:importador(carga).ejecutar_uno(),range(2)))
    assert sorted(resultados)==[False,True]


def test_fallo_sql_lote_revierte_filas_y_avance(carga,monkeypatch):
    preparar(carga)
    def fallar(etapa,_):
        if etapa=='antes_commit_lote': raise OperationalError('ensayo',{},Exception('fallo'))
    with pytest.raises(OperationalError): importador(carga,fallar).ejecutar_uno()
    with carga.sesiones.begin() as sesion:
        assert sesion.scalar(select(func.count()).select_from(RegistroLista))==0
        assert sesion.scalar(select(func.count()).select_from(LoteImportacionLista))==0
        control=sesion.scalar(select(ControlImportacionVersion))
        assert control.ordinal_confirmado==0
        control.concesion_hasta=datetime.now(timezone.utc)-timedelta(seconds=1)
    assert importador(carga).ejecutar_uno()


def test_postgres_rechaza_escritor_vencido_y_avance_inventado(carga):
    preparar(carga); servicio=importador(carga)
    trabajo=servicio._seleccionar(); trabajo=servicio._reclamar(trabajo)
    with pytest.raises(DBAPIError,match='Escritor'), carga.sesiones.begin() as sesion:
        sesion.add(RegistroLista(version_id=trabajo['version_id'],uid_original='ajeno',tipo_sujeto='PERSONA',contenido_original={},huella_semantica='a'*64))
    with pytest.raises(DBAPIError,match='Avance'), carga.sesiones.begin() as sesion:
        sesion.get(ControlImportacionVersion,trabajo['version_id']).ordinal_confirmado=8
    with carga.sesiones.begin() as sesion:
        sesion.get(ControlImportacionVersion,trabajo['version_id']).concesion_hasta=datetime.now(timezone.utc)-timedelta(seconds=1)
    nuevo=servicio._reclamar(servicio._seleccionar())
    with pytest.raises(ConflictoListas): servicio._lote(trabajo,1,[])
    assert nuevo['control']>trabajo['control']


def test_original_corrupto_no_importa(carga):
    preparar(carga)
    with carga.sesiones() as sesion:
        intento=sesion.scalar(select(IntentoImportacion))
        archivo=sesion.get(ArchivoFuente,UUID(intento.informe['archivo_raiz_id']))
    (carga.custodia.directorio/archivo.clave).write_bytes(b'alterado')
    with pytest.raises(ErrorIntegridadEvidencia): importador(carga).ejecutar_uno()
    with carga.sesiones() as sesion:
        assert sesion.scalar(select(func.count()).select_from(VersionFuente))==0


def test_proyeccion_alterada_impide_sellado(carga):
    preparar(carga)
    def alterar(etapa,trabajo):
        if etapa=='despues_commit_lote':
            with carga.sesiones.begin() as sesion:
                sesion.execute(text("SELECT set_config('listas.intento',:i,true),set_config('listas.control',:c,true)"),
                    {'i':str(trabajo['intento_id']),'c':str(trabajo['control'])})
                sesion.execute(text("UPDATE nombre_registro SET original='alterado'"))
    with pytest.raises(ImportacionInvalida,match='PROYECCION_NO_COINCIDE'): importador(carga,alterar).ejecutar_uno()
    with carga.sesiones() as sesion:
        assert sesion.scalar(select(VersionFuente.estado))=='EN_CONSTRUCCION'
        assert sesion.scalar(select(IntentoImportacion.estado))=='FALLIDO'


def test_sellada_y_lotes_inmutables(carga):
    preparar(carga); importador(carga).ejecutar_uno()
    for sentencia in ('DELETE FROM lote_importacion_lista','UPDATE recepcion_version_lista SET creado_en=now()',
                       'UPDATE control_importacion_version SET revision_datos=0',
                       "UPDATE intento_importacion SET estado='EN_CURSO'", "UPDATE nombre_registro SET original='alterado'"):
        with pytest.raises(DBAPIError), carga.sesiones.begin() as sesion: sesion.execute(text(sentencia))


def test_no_sella_vacia_por_sql(carga):
    preparar(carga); servicio=importador(carga); trabajo=servicio._reclamar(servicio._seleccionar())
    with pytest.raises(DBAPIError), carga.sesiones.begin() as sesion:
        servicio._bloquear(sesion,trabajo)
        version=sesion.get(VersionFuente,trabajo['version_id']); version.estado='VALIDA'; version.manifiesto={}; version.cantidad_registros=0


@pytest.mark.parametrize('etapa,confirmados,sellada',[
    ('antes_commit_lote',0,False),('despues_commit_lote',1,False),
    ('antes_commit_sellado',2,False),('despues_commit_sellado',2,True),
])
def test_sigkill_importacion_reinicio_real(carga,tmp_path,etapa,confirmados,sellada):
    import json, os, signal, subprocess, sys, time
    preparar(carga)
    senal=tmp_path/'senal.json'; configuracion=tmp_path/'proceso.json'
    opciones={'custodia':str(carga.custodia.directorio),'senal':str(senal),'detener':etapa}
    configuracion.write_text(json.dumps(opciones))
    comando=[sys.executable,str(Path(__file__).with_name('proceso_importacion_sintetica.py')),str(configuracion)]
    proceso=subprocess.Popen(comando)
    try:
        limite=time.monotonic()+15
        while not senal.exists() and time.monotonic()<limite:
            assert proceso.poll() is None
            time.sleep(.02)
        assert senal.exists(),'No alcanzó el punto de interrupción'
        evidencia=json.loads(senal.read_text())
        proceso.kill(); proceso.wait(timeout=5)
        assert proceso.returncode==-signal.SIGKILL
        with carga.sesiones() as sesion:
            control=sesion.scalar(select(ControlImportacionVersion))
            assert control.ordinal_confirmado==confirmados
            assert sesion.scalar(select(func.count()).select_from(RegistroLista))==confirmados
            assert sesion.scalar(select(VersionFuente.estado))==('VALIDA' if sellada else 'EN_CONSTRUCCION')
            vencimiento=control.concesion_hasta
        if vencimiento:
            while datetime.now(timezone.utc)<=vencimiento: time.sleep(.05)
        opciones['detener']=None; configuracion.write_text(json.dumps(opciones))
        reinicio=subprocess.run(comando,capture_output=True,text=True,timeout=20)
        assert reinicio.returncode==0,reinicio.stderr
        with carga.sesiones() as sesion:
            assert sesion.scalar(select(VersionFuente.estado))=='VALIDA'
            assert sesion.scalar(select(func.count()).select_from(RegistroLista))==2
            assert sesion.scalar(select(func.count()).select_from(LoteImportacionLista))==2
            assert sesion.scalar(select(IntentoImportacion.estado))=='COMPLETADO'
            assert sesion.scalar(select(FuenteVersionActiva.version_id)) is None
        evidencia.update(senal='SIGKILL',confirmados_al_morir=confirmados,estado_final='VALIDA',registros_finales=2,lotes_finales=2)
        Path(os.environ['LISTAS_EVIDENCIAS_DIRECTORIO'],f'importacion-{etapa}.json').write_text(json.dumps(evidencia,indent=2))
    finally:
        if proceso.poll() is None: proceso.kill(); proceso.wait(timeout=5)


def test_intento_nuevo_reutiliza_construccion_y_conserva_terminal(carga):
    preparar(carga)
    servicio=importador(carga)
    def fallar(etapa,_):
        if etapa=='despues_commit_lote': raise ImportacionInvalida('ENSAYO_TERMINAL')
    with pytest.raises(ImportacionInvalida): importador(carga,fallar).ejecutar_uno()
    with carga.sesiones() as sesion:
        anterior=sesion.scalar(select(IntentoImportacion)); anterior_id=anterior.id
        version_id=sesion.scalar(select(VersionFuente.id))
    preparar(carga,'v1.zip')
    assert servicio.ejecutar_uno()
    with carga.sesiones() as sesion:
        assert sesion.get(IntentoImportacion,anterior_id).estado=='FALLIDO'
        assert sesion.scalar(select(func.count()).select_from(VersionFuente))==1
        assert sesion.get(VersionFuente,version_id).estado=='VALIDA'
        nuevo=sesion.scalar(select(RecepcionVersionLista).where(RecepcionVersionLista.intento_previo_id==anterior_id))
        assert nuevo is not None
        original=sesion.get(ArchivoFuente,sesion.get(VersionFuente,version_id).archivo_raiz_id)
        assert sesion.get(VersionFuente,version_id).manifiesto['original_sha256']==original.huella


def test_esquema_corrupto_antes_sellado_no_sella(carga):
    preparar(carga)
    def corromper(etapa,trabajo):
        if etapa=='despues_commit_lote':
            (carga.custodia.directorio/trabajo['datos']['esquema_sha256']).write_bytes(b'alterado')
    with pytest.raises(ErrorIntegridadEvidencia): importador(carga,corromper).ejecutar_uno()
    with carga.sesiones() as sesion: assert sesion.scalar(select(VersionFuente.estado))=='EN_CONSTRUCCION'


def test_limite_tiempo_cierra_intento_sin_publicar(carga):
    preparar(carga); servicio=importador(carga)
    servicio.perfil=servicio.perfil.model_copy(update={'intento_segundos':0})
    with pytest.raises(ImportacionInvalida,match='TIEMPO'): servicio.ejecutar_uno()
    with carga.sesiones() as sesion:
        assert sesion.scalar(select(IntentoImportacion.estado))=='FALLIDO'
        assert sesion.scalar(select(VersionFuente.estado))=='EN_CONSTRUCCION'


def test_migracion_rechaza_downgrade_con_historial(carga):
    from alembic import command
    from alembic.config import Config
    preparar(carga); importador(carga).ejecutar_uno()
    configuracion=Config(str(Path(__file__).resolve().parents[2]/'backend/alembic.ini'))
    with pytest.raises(RuntimeError,match='historial'): command.downgrade(configuracion,'c43d56e78f90')
    with carga.sesiones() as sesion: assert sesion.scalar(select(VersionFuente.estado))=='VALIDA'


def test_mas_de_mil_registros_con_relacion_al_siguiente_lote(carga):
    from .test_recepcion_f52 import datos, enviar
    contenido=('<lista xmlns="urn:sagrilaft:pruebas:listas:v1" sintetica="true">'+''.join(
        f'<registro uid="prueba_{i}" clase="PERSONA"><nombre>Persona ficticia {i}</nombre>'+
        ('<relacion destino="prueba_1000"/>' if i==0 else '')+'</registro>' for i in range(1001))+'</lista>').encode()
    respuesta=carga.cliente.post(BASE,json=datos(contenido),headers={'Idempotency-Key':'volumen'})
    assert respuesta.status_code==201
    identificador=respuesta.json()['recepcion_id']
    assert enviar(carga,identificador,contenido).status_code==202
    assert validador(carga).ejecutar_uno()
    servicio=TrabajadorImportacionArchivos(carga.sesiones,carga.custodia,'development',habilitado=True)
    assert servicio.ejecutar_uno()
    with carga.sesiones() as sesion:
        assert sesion.scalar(select(VersionFuente.cantidad_registros))==1001
        lotes=list(sesion.scalars(select(LoteImportacionLista).order_by(LoteImportacionLista.desde)))
        assert [(l.desde,l.hasta) for l in lotes]==[(1,1000),(1001,1001)]
        relacion=sesion.scalar(select(RelacionRegistro))
        assert sesion.get(RegistroLista,relacion.registro_destino_id).uid_original=='prueba_1000'


def test_metadata_version_no_se_cambia_para_eludir_control(carga):
    preparar(carga); servicio=importador(carga)
    trabajo=servicio._reclamar(servicio._seleccionar())
    with pytest.raises(DBAPIError,match='Origen'), carga.sesiones.begin() as sesion:
        sesion.get(VersionFuente,trabajo['version_id']).version_importador='otro'


def test_cambio_entre_comprobacion_y_sellado_detectado(carga,monkeypatch):
    preparar(carga); servicio=importador(carga)
    comparar=servicio._comparar
    def alterar(sesion,version,archivo,trabajo):
        resultado=comparar(sesion,version,archivo,trabajo)
        with carga.sesiones.begin() as escritura:
            escritura.execute(text("SELECT set_config('listas.intento',:i,true),set_config('listas.control',:c,true)"),
                {'i':str(trabajo['intento_id']),'c':str(trabajo['control'])})
            escritura.execute(text("UPDATE nombre_registro SET original='cambio concurrente'"))
        return resultado
    monkeypatch.setattr(servicio,'_comparar',alterar)
    with pytest.raises(ConflictoListas,match='cambió'): servicio.ejecutar_uno()
    with carga.sesiones() as sesion: assert sesion.scalar(select(VersionFuente.estado))=='EN_CONSTRUCCION'


def test_upgrade_aditivo_conserva_version_f2(escenario,administracion_bd):
    from alembic import command
    from alembic.config import Config
    from .conftest import crear_version
    identificador,_=crear_version(escenario)
    with escenario.sesiones() as sesion:
        antes=sesion.get(VersionFuente,identificador).manifiesto
    configuracion=Config(str(Path(__file__).resolve().parents[2]/'backend/alembic.ini'))
    command.downgrade(configuracion,'c43d56e78f90')
    command.upgrade(configuracion,'head')
    with administracion_bd.begin() as conexion:
        conexion.execute(text('GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO aplicacion_listas'))
    with escenario.sesiones() as sesion:
        version=sesion.get(VersionFuente,identificador)
        assert version.estado=='VALIDA' and version.manifiesto==antes
        assert sesion.scalar(select(func.count()).select_from(ControlImportacionVersion))==0


def test_cli_importa_sin_activar(carga):
    import os, subprocess, sys
    preparar(carga)
    entorno=dict(os.environ,LISTAS_CUSTODIA_DIRECTORIO=str(carga.custodia.directorio),LISTAS_ADMIN_HABILITADA='true')
    respuesta=subprocess.run([sys.executable,'scripts/validacion/ejecutar_importacion_archivos.py'],env=entorno,
        capture_output=True,text=True,timeout=20)
    assert respuesta.returncode==0,respuesta.stderr
    with carga.sesiones() as sesion:
        assert sesion.scalar(select(VersionFuente.estado))=='VALIDA'
        assert sesion.scalar(select(FuenteVersionActiva.version_id)) is None


def test_validador_e_importador_comparten_limite_global(carga):
    preparar(carga)
    servicio=importador(carga); trabajo=servicio._reclamar(servicio._seleccionar())
    recibir(carga,'v2.xml')
    assert not validador(carga).ejecutar_uno()
    with carga.sesiones.begin() as sesion:
        sesion.get(ControlImportacionVersion,trabajo['version_id']).concesion_hasta=datetime.now(timezone.utc)-timedelta(seconds=1)
        sesion.get(IntentoImportacion,trabajo['intento_id']).concesion_hasta=datetime.now(timezone.utc)-timedelta(seconds=1)
    assert validador(carga)._reclamar() is not None
    assert servicio._reclamar(servicio._seleccionar()) is None


def test_campos_originales_exactos_y_versiones_separadas(carga):
    from infrastructure.persistencia.modelos_listas import DireccionRegistro, AtributoRegistro
    preparar(carga); importador(carga).ejecutar_uno()
    with carga.sesiones() as sesion:
        assert set(sesion.scalars(select(NombreRegistro.original)))=={'Persona ficticia Ámbar','Alias sintético Ω','Empresa ficticia Uno'}
        assert sesion.scalar(select(DireccionRegistro.original))=={'texto':'Dirección ficticia 1'}
        observacion=sesion.scalar(select(AtributoRegistro))
        assert observacion.valor=={'texto':'Sin datos reales ni fecha de nacimiento conocida.'}
        assert observacion.tipo=='observacion'
        identificador=sesion.scalar(select(IdentificadorRegistro))
        assert identificador.tipo=='PRUEBA' and identificador.pais_emisor=='ZZ' and identificador.original=='00001'
    preparar(carga,'v2.xml'); importador(carga).ejecutar_uno()
    with carga.sesiones() as sesion:
        assert sesion.scalar(select(func.count()).select_from(VersionFuente))==2
        assert sesion.scalar(select(func.count()).select_from(RegistroLista))==4
        assert sesion.scalar(select(FuenteVersionActiva.version_id)) is None


def test_cuota_y_entorno_rechazan_antes_de_importar(carga):
    preparar(carga); servicio=importador(carga)
    servicio.perfil=servicio.perfil.model_copy(update={'disco_temporal_bytes':1})
    with pytest.raises(ConflictoListas,match='Cuota'): servicio.ejecutar_uno()
    with pytest.raises(PermissionError): TrabajadorImportacionArchivos(carga.sesiones,carga.custodia,'production',habilitado=True)
    with pytest.raises(PermissionError): TrabajadorImportacionArchivos(carga.sesiones,carga.custodia,'development')
    with carga.sesiones() as sesion: assert sesion.scalar(select(func.count()).select_from(VersionFuente))==0


def test_no_toma_intentos_anteriores_fuera_del_circuito(carga):
    from infrastructure.persistencia.modelos_listas import RecepcionFuente, FuenteLista
    with carga.sesiones.begin() as sesion:
        recepcion=RecepcionFuente(fuente_id=sesion.scalar(select(FuenteLista.id)),actor_emisor='anterior',
            actor_sujeto='anterior',url_declarada='FIXTURE_LOCAL',estado='PENDIENTE')
        sesion.add(recepcion); sesion.flush()
        antiguo=IntentoImportacion(recepcion_id=recepcion.id,estado='EN_CURSO',fase='IMPORTACION')
        sesion.add(antiguo); sesion.flush(); anterior_id=antiguo.id
    preparar(carga)
    assert importador(carga).ejecutar_uno()
    with carga.sesiones() as sesion:
        assert sesion.get(IntentoImportacion,anterior_id).version_id is None
        assert sesion.get(IntentoImportacion,anterior_id).estado=='EN_CURSO'
        version=sesion.scalar(select(VersionFuente))
        from services.listas.informes import calcular_huella
        manifiesto=dict(version.manifiesto); huella=manifiesto.pop('huella_manifiesto')
        assert calcular_huella(manifiesto)==huella
        assert manifiesto['descargado_en'] is None and len(manifiesto['lotes'])==2


def test_reutilizacion_verifica_original_de_version_previa(carga):
    preparar(carga,'v1.zip'); importador(carga).ejecutar_uno()
    with carga.sesiones() as sesion:
        version=sesion.scalar(select(VersionFuente))
        archivo=sesion.get(ArchivoFuente,version.archivo_raiz_id)
    (carga.custodia.directorio/archivo.clave).write_bytes(b'zip alterado')
    preparar(carga,'v1.xml')
    with pytest.raises(ErrorIntegridadEvidencia): importador(carga).ejecutar_uno()
    with carga.sesiones() as sesion:
        assert sesion.scalar(select(func.count()).select_from(RecepcionVersionLista))==1


def test_registro_sin_lote_falla_al_confirmar(carga):
    """La optimización de conteos no permite insertar registros sin avance confirmado."""
    preparar(carga);trabajador=importador(carga)
    trabajo=trabajador._seleccionar()
    with trabajador._verificar_objetos(trabajo):trabajo=trabajador._reclamar(trabajo)
    with pytest.raises(DBAPIError,match='Avance y lotes no coinciden'),carga.sesiones.begin() as sesion:
        sesion.execute(text("SELECT set_config('listas.intento',:i,true),set_config('listas.control',:c,true)"),
            {'i':str(trabajo['intento_id']),'c':str(trabajo['control'])})
        sesion.add(RegistroLista(version_id=trabajo['version_id'],uid_original='sin-lote',tipo_sujeto='PERSONA',
            contenido_original={'ensayo':'sin lote'},huella_semantica='a'*64))
    with carga.sesiones() as sesion:
        assert sesion.scalar(select(func.count()).select_from(RegistroLista))==0
        assert sesion.get(ControlImportacionVersion,trabajo['version_id']).ordinal_confirmado==0
