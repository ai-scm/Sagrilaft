"""El adaptador OFAC usa recepción, lotes, custodia y administración comunes."""
from datetime import datetime, timezone
import hashlib
from pathlib import Path
from uuid import UUID
import pytest
from sqlalchemy import select, func
from infrastructure.persistencia.modelos_listas import (FuenteLista, VersionFuente, IntentoImportacion,
    RegistroLista, RelacionRegistro, FuenteVersionActiva)
from services.listas.validacion_archivos import TrabajadorValidacionArchivos
from services.listas.importacion_archivos import TrabajadorImportacionArchivos
from services.listas.integridad_administrativa import verificar_version
from services.listas.comparacion_versiones import comparar_registros
from .test_flujo_http import portal
from .test_recepcion_f52 import carga, BASE

FIJO=Path(__file__).resolve().parents[1]/'fixtures/ofac_advanced/dos_entidades.xml'


def metadatos(contenido):
    return dict(fuente='ofac_sdn',formato='OFAC_ADVANCED_XML_V3',nombre_original='SDN_ADVANCED.XML',
        procedencia='https://sanctionslist.ofac.treas.gov/Home/SdnList',
        descargado_en=datetime.now(timezone.utc).isoformat(),huella_declarada=hashlib.sha256(contenido).hexdigest())


def test_ofac_deshabilitado_por_defecto(carga):
    respuesta=carga.cliente.post(BASE,json=metadatos(FIJO.read_bytes()),headers={'Idempotency-Key':'ofac'})
    assert respuesta.status_code==403


def test_carga_importa_sella_deduplica_y_conserva_fecha(carga,monkeypatch):
    monkeypatch.setenv('LISTAS_OFAC_LOCAL_HABILITADA','true')
    with carga.sesiones.begin() as sesion:
        sesion.add(FuenteLista(codigo='ofac_sdn',nombre='OFAC SDN ensayo aislado',organismo='OFAC',
            url_oficial='https://sanctionslist.ofac.treas.gov/Home/SdnList'))
    contenido=FIJO.read_bytes();datos=metadatos(contenido)
    versiones=[]
    for clave in ['primera','segunda']:
        respuesta=carga.cliente.post(BASE,json=datos,headers={'Idempotency-Key':clave})
        assert respuesta.status_code==201,respuesta.text
        recepcion=respuesta.json()['recepcion_id']
        exceso=carga.cliente.put(BASE+'/'+recepcion+'/contenido',content=b'',headers={'Content-Type':'application/octet-stream','Content-Length':'268435457'})
        assert exceso.status_code==413
        respuesta=carga.cliente.put(BASE+'/'+recepcion+'/contenido',content=contenido,headers={'Content-Type':'application/octet-stream'})
        assert respuesta.status_code==202,respuesta.text
        validador=TrabajadorValidacionArchivos(carga.sesiones,carga.custodia,'development',habilitado=True)
        assert validador.ejecutar_uno()
        with carga.sesiones() as sesion:
            intento=sesion.scalar(select(IntentoImportacion).where(IntentoImportacion.recepcion_id==UUID(recepcion)))
            assert intento.informe['resultado']=='VALIDO',intento.informe
        trabajador=TrabajadorImportacionArchivos(carga.sesiones,carga.custodia,'development',habilitado=True)
        assert trabajador.ejecutar_uno()
        with carga.sesiones() as sesion:
            version=sesion.scalar(select(VersionFuente))
            assert version.estado=='VALIDA' and version.cantidad_registros==2
            assert version.publicada_en=='2026-11-06' and version.origen_fecha=='DATE_OF_ISSUE'
            assert version.manifiesto['publicada_en']==version.publicada_en
            assert verificar_version(sesion,carga.custodia,version)==version.manifiesto['huella_manifiesto']
            assert sesion.scalar(select(func.count()).select_from(RegistroLista))==2
            assert sesion.scalar(select(RelacionRegistro)).registro_destino_id is not None
            assert sesion.scalar(select(FuenteVersionActiva.version_id)) is None
            comparacion=comparar_registros(sesion,None,version)
            assert comparacion['conteos']['ALTA']==2
            versiones.append(version.id)
        original=carga.cliente.get(BASE+'/'+recepcion+'/original')
        assert original.status_code==200 and original.content==contenido
    assert versiones[0]==versiones[1]

    # El mismo servicio administrativo revisa esta fuente, sin un circuito OFAC paralelo.
    from uuid import uuid4
    from api.routers import administracion_versiones
    from infrastructure.persistencia.modelos_listas import PoliticaListas
    from services.listas.informes import calcular_huella
    from .test_administracion_f55 import solicitar, decidir, ejecutar, identidad
    carga.app.include_router(administracion_versiones.enrutador)
    with carga.sesiones.begin() as sesion:
        version=sesion.get(VersionFuente,versiones[0])
        carga.version,carga.fuente=version.id,version.fuente_id
        carga.politica_id=uuid4(); parametros={'uso_local':True}
        sesion.add(PoliticaListas(id=carga.politica_id,codigo='ofac-local',version=1,
            parametros=parametros,huella=calcular_huella(parametros),
            aprobador_emisor=carga.app.state.config.keycloak.issuer,aprobador_sujeto='revisor'))
    monkeypatch.setenv('LISTAS_ADMIN_POLITICA_ID',str(carga.politica_id))
    solicitud=solicitar(carga)
    identidad(carga,'operador-local',('listas_aprobador',))
    assert decidir(carga,solicitud).status_code==403
    identidad(carga,'revisor',('listas_aprobador',))
    aprobacion=decidir(carga,solicitud)
    assert aprobacion.status_code==201,aprobacion.text
    revision=aprobacion.json()['revision_id']
    respuesta=ejecutar(carga,solicitud,revision)
    assert respuesta.status_code==200,respuesta.text
    assert ejecutar(carga,solicitud,revision).json()==respuesta.json()
    with carga.sesiones() as sesion:
        assert sesion.get(FuenteVersionActiva,carga.fuente).version_id==versiones[0]

    with carga.sesiones() as sesion:
        primero=sesion.get(VersionFuente,versiones[0])
        manifiesto_anterior=dict(primero.manifiesto)
        registro=sesion.scalar(select(RegistroLista).where(RegistroLista.version_id==primero.id))
        ruta=f'/api/administracion-listas/versiones/{primero.id}/registros/{registro.id}'
        esperado=registro.contenido_original
    detalle=carga.cliente.get(ruta)
    assert detalle.status_code==200 and detalle.json()['contenido']==esperado
    identidad(carga,'sin-permiso',('listas_operador',))
    assert carga.cliente.get(ruta).status_code==403
    identidad(carga)
    nuevo=contenido.replace(b'EMPRESA FICTICIA 1',b'EMPRESA FICTICIA MODIFICADA')
    respuesta=carga.cliente.post(BASE,json=metadatos(nuevo),headers={'Idempotency-Key':'actualizacion'})
    recepcion=respuesta.json()['recepcion_id']
    assert carga.cliente.put(BASE+'/'+recepcion+'/contenido',content=nuevo,headers={'Content-Type':'application/octet-stream'}).status_code==202
    assert TrabajadorValidacionArchivos(carga.sesiones,carga.custodia,'development',True).ejecutar_uno()
    assert TrabajadorImportacionArchivos(carga.sesiones,carga.custodia,'development',True).ejecutar_uno()
    from .test_administracion_f55 import comparar
    with carga.sesiones() as sesion:
        nueva=sesion.scalar(select(VersionFuente).where(VersionFuente.id!=versiones[0]))
        carga.version=nueva.id
    for revision_actual,destino,tipo in [(1,carga.version,'ACTIVACION'),(2,versiones[0],'REVERSION')]:
        identidad(carga)
        comparacion=comparar(carga,destino,revision_actual,'comparar-'+tipo)
        solicitud=solicitar(carga,comparacion,tipo,'solicitar-'+tipo)
        identidad(carga,'revisor',('listas_aprobador',))
        aprobacion=decidir(carga,solicitud,clave='decidir-'+tipo).json()['revision_id']
        respuesta=ejecutar(carga,solicitud,aprobacion,revision_actual,'ejecutar-'+tipo)
        assert respuesta.status_code==200,respuesta.text
    with carga.sesiones() as sesion:
        assert sesion.get(FuenteVersionActiva,carga.fuente).version_id==versiones[0]
        assert sesion.get(FuenteVersionActiva,carga.fuente).revision==3
        assert sesion.get(VersionFuente,versiones[0]).manifiesto==manifiesto_anterior
    assert carga.cliente.get(ruta).json()['contenido']==esperado


def test_cierre_sql_conserva_limite_sintetico(carga):
    """SQL debe rechazar >100 MiB aun si la aplicación anuncia un límite incorrecto."""
    from domain.listas.administracion import RecepcionPropuesta
    from infrastructure.listas.recepcion_archivo import ArchivoEnRecepcion
    from infrastructure.persistencia.modelos_listas import RecepcionFuente
    from sqlalchemy.exc import DBAPIError
    escritura=ArchivoEnRecepcion(carga.custodia,104857601)
    resumen=hashlib.sha256()
    try:
        bloque=b'x'*1048576
        for _ in range(100):escritura.escribir(bloque);resumen.update(bloque)
        escritura.escribir(b'x');resumen.update(b'x')
        objeto=escritura.confirmar(resumen.hexdigest())
        datos=RecepcionPropuesta(fuente='ofac_sdn_prueba',formato='SINTETICO_XML_V1',
            nombre_original='ensayo-limite.xml',procedencia='FIXTURE_LOCAL',
            huella_declarada=resumen.hexdigest(),clave='comprobar-limite-sql')
        recepcion=carga.servicio.reservar(datos)
        carga.servicio.perfil=carga.servicio.perfil.model_copy(update={'recibido_bytes':104857601})
        control,_=carga.servicio.reclamar(recepcion)
        with pytest.raises(DBAPIError,match='Cierre de recepción incompleto'):
            carga.servicio.confirmar(recepcion,control,objeto)
        with carga.sesiones() as sesion:
            assert sesion.get(RecepcionFuente,recepcion).estado=='PENDIENTE'
            assert sesion.scalar(select(func.count()).select_from(IntentoImportacion))==0
    finally:escritura.cerrar()
