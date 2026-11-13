"""Importación por adaptadores recuperable; el sellado nunca activa una lista."""
from datetime import datetime, timedelta, timezone
import hashlib
import fcntl
import os
import json
from uuid import UUID
from sqlalchemy import select, text, func
from domain.listas.administracion import PerfilEnsayo
from domain.listas.errores import ConflictoListas, ErrorIntegridadEvidencia
from infrastructure.listas.recepcion_archivo import original_verificado
from infrastructure.listas.adaptadores_archivos import obtener_adaptador, exigir_adaptador_habilitado
from infrastructure.listas.proyeccion_persistida import guardar_registro, TABLAS_PROYECCION
from infrastructure.persistencia.modelos_listas import (ArchivoFuente, EsquemaFuente, IntentoImportacion,
    RecepcionFuente, VersionFuente, RegistroLista, RelacionRegistro, EventoVersion)
from infrastructure.persistencia.modelos_recepcion_listas import EventoRecepcionLista, ReservaRecepcionLista
from infrastructure.persistencia.modelos_importacion_listas import (RecepcionVersionLista,
    ControlImportacionVersion, LoteImportacionLista)
from services.listas.autorizacion_administrativa import exigir_entorno_sintetico
from services.listas.informes import calcular_huella


class ImportacionInvalida(ValueError):
    pass


class TrabajadorImportacionArchivos:
    def __init__(self, sesiones, custodia, entorno, habilitado=False, perfil=None, observador=None):
        exigir_entorno_sintetico(entorno)
        if not habilitado:
            raise PermissionError('Administración de listas deshabilitada')
        self.sesiones, self.custodia = sesiones, custodia
        self.perfil = perfil or PerfilEnsayo()
        self.observador = observador or (lambda *_: None)

    def _evento(self, sesion, intento, tipo, **detalle):
        sesion.add(EventoRecepcionLista(recepcion_id=intento.recepcion_id, actor_emisor='servicio-local',
            actor_sujeto=self.adaptador.version_importador, tipo=tipo, detalle={'intento_id':str(intento.id), **detalle}))

    def _seleccionar(self):
        with self.sesiones() as sesion:
            intento = sesion.scalar(select(IntentoImportacion).join(ReservaRecepcionLista,
                ReservaRecepcionLista.recepcion_id==IntentoImportacion.recepcion_id).where(IntentoImportacion.estado=='EN_CURSO',
                IntentoImportacion.fase.in_(['IMPORTACION','COMPROBACION','SELLADO']))
                .order_by(IntentoImportacion.creado_en).limit(1))
            if intento is None:
                return None
            evento = sesion.scalar(select(EventoRecepcionLista).where(EventoRecepcionLista.recepcion_id==intento.recepcion_id,
                EventoRecepcionLista.tipo=='VALIDACION_FINALIZADA'))
            if evento is None or evento.detalle != intento.informe or evento.detalle.get('resultado')!='VALIDO':
                raise ImportacionInvalida('INFORME_VALIDACION_INCOMPATIBLE')
            datos = dict(evento.detalle)
            self.adaptador = obtener_adaptador(datos['formato'])
            exigir_adaptador_habilitado(self.adaptador)
            if self.adaptador.oficial:
                self.perfil = self.adaptador.perfil
            if datos['esquema_sha256']!=self.adaptador.huella_esquema or datos['version_validador']!=self.adaptador.version_validador:
                raise ImportacionInvalida('SOFTWARE_O_ESQUEMA_INCOMPATIBLE')
            recepcion = sesion.get(RecepcionFuente,intento.recepcion_id)
            return dict(intento_id=intento.id, recepcion_id=intento.recepcion_id,
                        fuente_id=recepcion.fuente_id, datos=datos)

    def _verificar_objetos(self, trabajo):
        """No mantiene bloqueos SQL durante la lectura. Devuelve copia verificada del XML."""
        datos = trabajo['datos']
        with self.sesiones() as sesion:
            esquema = sesion.get(EsquemaFuente,UUID(datos['esquema_id']))
            if not esquema.aprobado or esquema.fuente_id!=trabajo['fuente_id']:
                raise ImportacionInvalida('ESQUEMA_NO_APROBADO')
            ids = [datos['archivo_raiz_id'],datos['archivo_contenido_id'],datos['informe_id'],str(esquema.archivo_id)]
            objetos = [sesion.get(ArchivoFuente,UUID(identificador)) for identificador in ids]
            existente = sesion.scalar(select(VersionFuente).where(VersionFuente.fuente_id==trabajo['fuente_id'],
                VersionFuente.huella_contenido==datos['contenido_sha256'],VersionFuente.esquema_id==esquema.id,
                VersionFuente.formato==self.adaptador.formato,VersionFuente.version_importador==self.adaptador.version_importador,
                VersionFuente.version_normalizador==self.adaptador.version_normalizador,VersionFuente.generacion==0))
            raiz_previa = sesion.get(ArchivoFuente,existente.archivo_raiz_id) if existente else None
            if existente and existente.estado=='BLOQUEADA': raise ImportacionInvalida('VERSION_BLOQUEADA')
        ocupado = 0
        for ruta in self.custodia.directorio.rglob('*'):
            try:
                if ruta.is_file(): ocupado += ruta.stat().st_size
            except FileNotFoundError:
                continue
        reserva = 2 * max(objeto.tamano_bytes for objeto in objetos) + 2 * self.perfil.recibido_bytes
        if ocupado + reserva > self.perfil.disco_temporal_bytes:
            raise ConflictoListas('Cuota insuficiente para comprobar la importación')
        esperadas = [datos['original_sha256'],datos['contenido_sha256'],datos['informe_sha256'],datos['esquema_sha256']]
        copia = None
        try:
            if raiz_previa:
                with original_verificado(self.custodia,raiz_previa.huella,raiz_previa.tamano_bytes): pass
            for posicion, (objeto, huella) in enumerate(zip(objetos, esperadas)):
                if objeto.huella!=huella:
                    raise ErrorIntegridadEvidencia('Metadatos de importación alterados')
                verificado = original_verificado(self.custodia,huella,objeto.tamano_bytes)
                if posicion==1:
                    copia = verificado
                else:
                    if posicion==2:
                        informe = json.load(verificado)
                        if any(datos.get(clave)!=valor for clave,valor in informe.items()):
                            verificado.close()
                            raise ErrorIntegridadEvidencia('Informe de validación alterado')
                    verificado.close()
            return copia
        except BaseException:
            if copia: copia.close()
            raise

    def _contabilizar(self, control, ahora):
        if control.concesion_hasta:
            control.segundos_consumidos += max(0,(min(ahora,control.concesion_hasta)-control.ultima_actividad).total_seconds())
        control.ultima_actividad = ahora

    def _reclamar(self, trabajo):
        with self.sesiones.begin() as sesion:
            sesion.execute(text('SELECT pg_advisory_xact_lock(523003)'))
            sesion.execute(text('SELECT pg_advisory_xact_lock(523004)'))
            ahora = datetime.now(timezone.utc)
            if sesion.scalar(select(IntentoImportacion.id).where(IntentoImportacion.fase=='VALIDACION',
                    IntentoImportacion.concesion_hasta>ahora).limit(1)):
                return None
            if sesion.scalar(select(ControlImportacionVersion.version_id).where(ControlImportacionVersion.concesion_hasta>ahora).limit(1)):
                return None
            intento = sesion.scalar(select(IntentoImportacion).where(IntentoImportacion.id==trabajo['intento_id']).with_for_update())
            if intento.estado!='EN_CURSO': return None
            datos = trabajo['datos']
            version = sesion.scalar(select(VersionFuente).where(VersionFuente.fuente_id==trabajo['fuente_id'],
                VersionFuente.huella_contenido==datos['contenido_sha256'],VersionFuente.formato==self.adaptador.formato,
                VersionFuente.esquema_id==UUID(datos['esquema_id']),VersionFuente.version_importador==self.adaptador.version_importador,
                VersionFuente.version_normalizador==self.adaptador.version_normalizador,VersionFuente.generacion==0).with_for_update())
            if version is None:
                version = VersionFuente(fuente_id=trabajo['fuente_id'],recepcion_id=trabajo['recepcion_id'],
                    esquema_id=UUID(datos['esquema_id']),archivo_raiz_id=UUID(datos['archivo_raiz_id']),
                    archivo_contenido_id=UUID(datos['archivo_contenido_id']),formato=self.adaptador.formato,
                    version_importador=self.adaptador.version_importador,version_normalizador=self.adaptador.version_normalizador,
                    huella_contenido=datos['contenido_sha256'])
                sesion.add(version); sesion.flush()
            if version.estado=='BLOQUEADA': raise ImportacionInvalida('VERSION_BLOQUEADA')
            control = sesion.get(ControlImportacionVersion,version.id)
            previo = None
            if control and control.intento_id!=intento.id:
                anterior = sesion.get(IntentoImportacion,control.intento_id)
                if anterior.estado=='EN_CURSO':
                    return None
                if anterior.estado=='FALLIDO': previo = anterior.id
            if not sesion.scalar(select(RecepcionVersionLista.id).where(RecepcionVersionLista.intento_id==intento.id)):
                intento.version_id=version.id; sesion.flush()
                sesion.add(RecepcionVersionLista(intento_id=intento.id,intento_previo_id=previo,
                    fuente_id=trabajo['fuente_id'],recepcion_id=intento.recepcion_id,version_id=version.id))
                sesion.flush()
            if version.estado=='VALIDA':
                intento.estado,intento.fase='COMPLETADO','SELLADO'
                intento.punto_reanudacion={'registros_confirmados':version.cantidad_registros,'reutilizada':True}
                intento.concesion_hasta=None
                self._evento(sesion,intento,'VERSION_REUTILIZADA',version_id=str(version.id))
                return {'reutilizada':True,'version_id':version.id}
            if control is None:
                control=ControlImportacionVersion(version_id=version.id,intento_id=intento.id,
                    numero_control=intento.numero_control+1,reclamaciones=1,ordinal_confirmado=0,segundos_consumidos=0,ultima_actividad=ahora)
                sesion.add(control)
            else:
                self._contabilizar(control,ahora)
                if control.reclamaciones>=self.perfil.recuperaciones or control.segundos_consumidos>=self.perfil.intento_segundos:
                    intento.estado,intento.error='FALLIDO','PRESUPUESTO_IMPORTACION_AGOTADO'
                    intento.concesion_hasta=control.concesion_hasta=None
                    self._evento(sesion,intento,'IMPORTACION_AGOTADA',version_id=str(version.id))
                    return None
                control.numero_control=max(control.numero_control,intento.numero_control)+1; control.reclamaciones+=1; control.intento_id=intento.id
            control.concesion_hasta=ahora+timedelta(seconds=self.perfil.concesion_segundos)
            intento.numero_control=control.numero_control; intento.concesion_hasta=control.concesion_hasta
            self._evento(sesion,intento,'IMPORTACION_RECLAMADA',version_id=str(version.id),control=control.numero_control)
            return {**trabajo,'version_id':version.id,'control':control.numero_control,'ordinal':control.ordinal_confirmado}

    def _bloquear(self, sesion, trabajo, comprobar_presupuesto=True):
        version = sesion.scalar(select(VersionFuente).where(VersionFuente.id==trabajo['version_id']).with_for_update())
        control = sesion.scalar(select(ControlImportacionVersion).where(ControlImportacionVersion.version_id==version.id).with_for_update())
        ahora = datetime.now(timezone.utc)
        if (control.numero_control!=trabajo['control'] or control.intento_id!=trabajo['intento_id']
                or control.concesion_hasta is None or control.concesion_hasta<=ahora or version.estado!='EN_CONSTRUCCION'):
            raise ConflictoListas('Escritor de importación vencido')
        self._contabilizar(control,ahora)
        if comprobar_presupuesto and control.segundos_consumidos>=self.perfil.intento_segundos:
            raise ImportacionInvalida('TIEMPO_IMPORTACION_AGOTADO')
        sesion.execute(text("SELECT set_config('listas.intento',:intento,true),set_config('listas.control',:control,true)"),
            {'intento':str(trabajo['intento_id']),'control':str(trabajo['control'])})
        intento = sesion.get(IntentoImportacion,trabajo['intento_id'])
        if intento.estado!='EN_CURSO': raise ConflictoListas('Intento terminal')
        control.concesion_hasta=ahora+timedelta(seconds=self.perfil.concesion_segundos)
        intento.concesion_hasta=control.concesion_hasta
        return version, control, intento

    def _renovar(self, trabajo):
        with self.sesiones.begin() as sesion: self._bloquear(sesion,trabajo)

    def _lote(self, trabajo, desde, contenidos):
        with self.sesiones.begin() as sesion:
            version, control, intento = self._bloquear(sesion,trabajo)
            if control.ordinal_confirmado!=desde-1: raise ConflictoListas('Lote ya confirmado o discontinuo')
            for contenido in contenidos: guardar_registro(sesion,version.id,contenido,self.adaptador.proyeccion)
            sesion.flush()
            hasta=desde+len(contenidos)-1
            sesion.add(LoteImportacionLista(version_id=version.id,intento_id=intento.id,numero_control=control.numero_control,
                desde=desde,hasta=hasta,huella=calcular_huella(contenidos)))
            sesion.flush()
            control.ordinal_confirmado=hasta
            intento.punto_reanudacion={'registros_confirmados':hasta}
            self._evento(sesion,intento,'LOTE_CONFIRMADO',version_id=str(version.id),desde=desde,hasta=hasta)
            self.observador('antes_commit_lote',trabajo)
        self.observador('despues_commit_lote',trabajo)

    def _comparar(self, sesion, version, archivo, trabajo):
        """Compara todas las tablas proyectadas con el XML, no solo sus conteos."""
        acumulada=hashlib.sha256(); cantidad=0
        lotes=list(sesion.scalars(select(LoteImportacionLista).where(LoteImportacionLista.version_id==version.id).order_by(LoteImportacionLista.desde)))
        indice_lote=0; contenidos_lote=[]; latido=datetime.now(timezone.utc)
        for contenido in self.adaptador.registros(archivo):
            cantidad+=1
            if (datetime.now(timezone.utc)-latido).total_seconds()>=self.perfil.latido_segundos:
                self._renovar(trabajo); latido=datetime.now(timezone.utc)
            contenidos_lote.append(contenido)
            if indice_lote>=len(lotes): raise ImportacionInvalida('LOTES_INCOMPLETOS')
            lote=lotes[indice_lote]
            if cantidad==lote.hasta:
                if lote.desde!=cantidad-len(contenidos_lote)+1 or lote.huella!=calcular_huella(contenidos_lote):
                    raise ImportacionInvalida('HUELLA_LOTE_DISTINTA')
                indice_lote+=1; contenidos_lote=[]
            registro=sesion.scalar(select(RegistroLista).where(RegistroLista.version_id==version.id,RegistroLista.uid_original==contenido['uid']))
            if registro is None or registro.contenido_original!=contenido or registro.tipo_sujeto!=contenido['clase'] or registro.huella_semantica!=calcular_huella(contenido):
                raise ImportacionInvalida('REGISTRO_NO_COINCIDE')
            esperados=self.adaptador.proyeccion(contenido)
            for nombre,tabla in TABLAS_PROYECCION.items():
                filas=list(sesion.scalars(select(tabla).where(tabla.registro_id==registro.id).order_by(tabla.ordinal)))
                if len(filas)!=len(esperados[nombre]): raise ImportacionInvalida('PROYECCION_INCOMPLETA')
                for ordinal,(fila,esperado) in enumerate(zip(filas,esperados[nombre])):
                    if fila.ordinal!=ordinal or any(getattr(fila,clave)!=valor for clave,valor in esperado.items()):
                        raise ImportacionInvalida('PROYECCION_NO_COINCIDE')
            relaciones=list(sesion.scalars(select(RelacionRegistro).where(RelacionRegistro.registro_origen_id==registro.id)))
            esperadas=esperados['relaciones']
            if len(relaciones)!=len(esperadas): raise ImportacionInvalida('RELACIONES_INCOMPLETAS')
            actuales=[{clave:getattr(fila,clave) for clave in ('identificador_destino','ambito_destino','tipo','atributos')} for fila in relaciones]
            if sorted(actuales,key=calcular_huella)!=sorted(esperadas,key=calcular_huella): raise ImportacionInvalida('RELACIONES_NO_COINCIDEN')
            for relacion in relaciones:
                destino=sesion.scalar(select(RegistroLista.id).where(RegistroLista.version_id==version.id,RegistroLista.uid_original==relacion.identificador_destino))
                if destino is None: raise ImportacionInvalida('REFERENCIA_ROTA')
                if relacion.registro_destino_id!=destino: raise ImportacionInvalida('REFERENCIA_NO_RESUELTA')
            acumulada.update(bytes.fromhex(calcular_huella(contenido)))
        if contenidos_lote or indice_lote!=len(lotes): raise ImportacionInvalida('LOTES_INCOMPLETOS')
        if cantidad==0 or cantidad!=sesion.scalar(select(func.count()).select_from(RegistroLista).where(RegistroLista.version_id==version.id)):
            raise ImportacionInvalida('CONTEO_INCOMPLETO')
        return cantidad,acumulada.hexdigest()

    def _sellar(self, trabajo, archivo):
        # Revalidar custodia completa fuera de la transacción de sellado.
        with self._verificar_objetos(trabajo): pass
        with self.sesiones.begin() as sesion:
            version,control,intento=self._bloquear(sesion,trabajo)
            intento.fase='COMPROBACION'
            sesion.execute(text("""UPDATE relacion_registro r SET registro_destino_id=d.id FROM registro_lista d
                WHERE r.version_id=:version AND d.version_id=r.version_id AND d.uid_original=r.identificador_destino
                AND r.registro_destino_id IS DISTINCT FROM d.id"""), {'version':version.id})
        # Cotejo sin bloqueos de escritura. La revisión detecta cualquier cambio concurrente.
        with self.sesiones() as sesion:
            version=sesion.get(VersionFuente,trabajo['version_id'])
            revision=sesion.get(ControlImportacionVersion,version.id).revision_datos
            cantidad,huella=self._comparar(sesion,version,archivo,trabajo)
        with self.sesiones.begin() as sesion:
            version,control,intento=self._bloquear(sesion,trabajo)
            if control.revision_datos!=revision: raise ConflictoListas('La proyección cambió durante la comprobación')
            if cantidad!=trabajo['datos']['registros'] or control.ordinal_confirmado!=cantidad:
                raise ImportacionInvalida('CONTEO_VALIDACION_DISTINTO')
            intento.fase='SELLADO'; sesion.flush()
            version.cantidad_registros=cantidad
            original_version=sesion.get(ArchivoFuente,version.archivo_raiz_id)
            evento_validacion=sesion.scalar(select(EventoRecepcionLista).where(
                EventoRecepcionLista.recepcion_id==version.recepcion_id,EventoRecepcionLista.tipo=='VALIDACION_FINALIZADA'))
            recepcion_original=sesion.get(RecepcionFuente,version.recepcion_id)
            archivo_esquema=sesion.get(ArchivoFuente,sesion.get(EsquemaFuente,version.esquema_id).archivo_id)
            version.manifiesto={'registros':cantidad,'huella_proyeccion':huella,'algoritmo':'sha256-concatenacion-huellas-canonicas-v1',
                'importador':self.adaptador.version_importador,'normalizador':self.adaptador.version_normalizador,'perfil':self.perfil.model_dump(),
                'original_sha256':original_version.huella,'original_tamano':original_version.tamano_bytes,
                'contenido_tamano':trabajo['datos']['contenido_tamano'],'contenido_sha256':version.huella_contenido,
                'esquema_sha256':self.adaptador.huella_esquema,'generacion':version.generacion,'publicada_en':trabajo['datos'].get('publicada_en'),
                'origen_fecha':trabajo['datos'].get('origen_fecha', 'DESCONOCIDA'),'informe_validacion_id':evento_validacion.detalle['informe_id'],
                'intento_sellado_id':str(intento.id),'recepcion_sellado_id':str(intento.recepcion_id),
                'recepcion_original_id':str(version.recepcion_id),
                'descargado_en':recepcion_original.descargado_en.isoformat() if recepcion_original.descargado_en else None,
                'sellada_en':datetime.now(timezone.utc).isoformat(),'esquema_tamano':archivo_esquema.tamano_bytes,
                'version_validador':self.adaptador.version_validador,
                'lotes':[{'desde':l.desde,'hasta':l.hasta,'huella':l.huella} for l in sesion.scalars(
                    select(LoteImportacionLista).where(LoteImportacionLista.version_id==version.id).order_by(LoteImportacionLista.desde))]}
            version.publicada_en = trabajo['datos'].get('publicada_en')
            version.origen_fecha = trabajo['datos'].get('origen_fecha', 'DESCONOCIDA')
            version.manifiesto={**version.manifiesto,'huella_manifiesto':calcular_huella(version.manifiesto)}
            version.estado='VALIDA'; sesion.flush()
            sesion.add(EventoVersion(version_id=version.id,estado_anterior='EN_CONSTRUCCION',estado_nuevo='VALIDA',
                actor_emisor='servicio-local',actor_sujeto=self.adaptador.version_importador,motivo='Importación íntegra comprobada'))
            intento.estado='COMPLETADO'; intento.concesion_hasta=None
            control.concesion_hasta=None
            self._evento(sesion,intento,'IMPORTACION_SELLADA',version_id=str(version.id),manifiesto=version.manifiesto)
            self.observador('antes_commit_sellado',trabajo)
        self.observador('despues_commit_sellado',trabajo)

    def _fallar(self, trabajo, codigo):
        with self.sesiones.begin() as sesion:
            version,control,intento=self._bloquear(sesion,trabajo,comprobar_presupuesto=False)
            intento.estado,intento.error='FALLIDO',codigo
            intento.concesion_hasta=control.concesion_hasta=None
            self._evento(sesion,intento,'IMPORTACION_FALLIDA',version_id=str(version.id),codigo=codigo)

    def ejecutar_uno(self):
        # Evita copias simultáneas antes de reclamar; no mantiene una transacción SQL abierta.
        descriptor = os.open(self.custodia.directorio, os.O_RDONLY | os.O_DIRECTORY)
        try:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return False
            return self._ejecutar_uno()
        finally:
            os.close(descriptor)

    def _ejecutar_uno(self):
        trabajo=self._seleccionar()
        if trabajo is None: return False
        with self._verificar_objetos(trabajo) as archivo:
            trabajo=self._reclamar(trabajo)
            if trabajo is None: return False
            if trabajo.get('reutilizada'): return True
            try:
                lote=[]; desde=trabajo['ordinal']+1; latido=datetime.now(timezone.utc)
                for ordinal,contenido in enumerate(self.adaptador.registros(archivo),1):
                    if (datetime.now(timezone.utc)-latido).total_seconds()>=self.perfil.latido_segundos:
                        self._renovar(trabajo); latido=datetime.now(timezone.utc)
                    if ordinal<=trabajo['ordinal']: continue
                    lote.append(contenido)
                    if len(lote)>=self.perfil.lote_registros:
                        self._lote(trabajo,desde,lote); desde+=len(lote); lote=[]
                if lote: self._lote(trabajo,desde,lote)
                self._sellar(trabajo,archivo)
            except ImportacionInvalida as error:
                self._fallar(trabajo,str(error))
                raise
            except ValueError as error:
                self._fallar(trabajo, 'PROYECCION_INVALIDA')
                raise ImportacionInvalida('PROYECCION_INVALIDA') from error
        return True
