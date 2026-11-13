"""Recepción durable de fixtures. No crea versiones ni activa listas."""
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from domain.listas.administracion import PerfilEnsayo
from infrastructure.listas.adaptadores_archivos import obtener_adaptador, exigir_adaptador_habilitado
from domain.listas.errores import ConflictoListas, ErrorIntegridadEvidencia
from services.listas.autorizacion_administrativa import exigir_entorno_sintetico
from services.listas.informes import calcular_huella
from infrastructure.persistencia.modelos_listas import FuenteLista, RecepcionFuente, ArchivoFuente, IntentoImportacion
from infrastructure.persistencia.modelos_recepcion_listas import ReservaRecepcionLista, EventoRecepcionLista
from infrastructure.listas.recepcion_archivo import original_verificado


class ServicioRecepcionListas:
    def __init__(self, sesiones, custodia, politica, actor, entorno, perfil=None):
        exigir_entorno_sintetico(entorno)
        self.sesiones, self.custodia, self.politica, self.actor = sesiones, custodia, politica, actor
        self.perfil = perfil or PerfilEnsayo()

    def _autorizar(self, operacion='cargar'):
        self.politica.administracion(self.actor, operacion)

    def _reserva(self, sesion, identificador, bloquear=False):
        sentencia = select(ReservaRecepcionLista).where(ReservaRecepcionLista.recepcion_id == identificador)
        if bloquear:
            sentencia = sentencia.with_for_update()
        reserva = sesion.scalar(sentencia)
        # El catálogo local de cargas es privado del cargador en F5.2.
        if reserva is None or (reserva.actor_emisor, reserva.actor_sujeto) != (self.actor.issuer, self.actor.sub):
            raise LookupError('Recepción no disponible')
        return reserva

    def _evento(self, sesion, identificador, tipo, **detalle):
        sesion.add(EventoRecepcionLista(recepcion_id=identificador, actor_emisor=self.actor.issuer,
            actor_sujeto=self.actor.sub, tipo=tipo, detalle=detalle))

    def reservar(self, datos):
        self._autorizar()
        adaptador = obtener_adaptador(datos.formato)
        exigir_adaptador_habilitado(adaptador)
        if adaptador.fuente != datos.fuente:
            raise ValueError('Fuente incompatible con el adaptador')
        metadatos = datos.model_dump(mode='json', exclude={'clave'})
        huella = calcular_huella(metadatos)
        with self.sesiones.begin() as sesion:
            sesion.execute(text('SELECT pg_advisory_xact_lock(523001)'))
            fuente = sesion.scalar(select(FuenteLista).where(FuenteLista.codigo == datos.fuente))
            if fuente is None:
                raise LookupError('Fuente no registrada por administración')
            anterior = sesion.scalar(select(ReservaRecepcionLista).where(
                ReservaRecepcionLista.actor_emisor == self.actor.issuer,
                ReservaRecepcionLista.actor_sujeto == self.actor.sub,
                ReservaRecepcionLista.fuente_id == fuente.id, ReservaRecepcionLista.clave == datos.clave))
            if anterior:
                if anterior.huella_peticion != huella:
                    raise ConflictoListas('Clave usada con otros metadatos')
                return anterior.recepcion_id
            identificador = uuid4()
            sesion.add(RecepcionFuente(id=identificador, fuente_id=fuente.id, actor_emisor=self.actor.issuer,
                actor_sujeto=self.actor.sub, url_declarada=datos.procedencia, descargado_en=datos.descargado_en,
                estado='PENDIENTE'))
            sesion.flush()
            sesion.add(ReservaRecepcionLista(recepcion_id=identificador, fuente_id=fuente.id,
                actor_emisor=self.actor.issuer, actor_sujeto=self.actor.sub, clave=datos.clave,
                huella_peticion=huella, metadatos=metadatos))
            self._evento(sesion, identificador, 'RESERVADA')
            return identificador

    def consultar(self, identificador):
        self._autorizar('ver')
        with self.sesiones() as sesion:
            reserva = self._reserva(sesion, identificador)
            recepcion = sesion.get(RecepcionFuente, identificador)
            evento = sesion.scalar(select(EventoRecepcionLista).where(
                EventoRecepcionLista.recepcion_id == identificador, EventoRecepcionLista.tipo == 'VALIDACION_FINALIZADA'))
            intento = sesion.get(IntentoImportacion, reserva.intento_importacion_id) if reserva.intento_importacion_id else None
            validacion = evento.detalle['resultado'] if evento else ('FALLIDA' if intento and intento.error else 'EN_CURSO' if intento and intento.estado == 'EN_CURSO' else 'NO_EJECUTADA')
            return {'recepcion_id': identificador, 'estado': recepcion.estado,
                'intento_id': reserva.intento_importacion_id, 'validacion': validacion,
                'nombre_original': reserva.metadatos['nombre_original'], 'intentos_carga': reserva.intentos}

    def preparar_perfil(self, identificador):
        self._autorizar('cargar')
        with self.sesiones() as sesion:
            reserva = self._reserva(sesion, identificador)
            adaptador = obtener_adaptador(reserva.metadatos['formato'])
            exigir_adaptador_habilitado(adaptador)
            if adaptador.oficial:
                self.perfil = adaptador.perfil

    def reclamar(self, identificador):
        self.preparar_perfil(identificador)
        self._autorizar()
        with self.sesiones.begin() as sesion:
            sesion.execute(text('SELECT pg_advisory_xact_lock(523001)'))
            reserva = self._reserva(sesion, identificador, True)
            ahora = datetime.now(timezone.utc)
            if reserva.intento_importacion_id:
                return None
            if reserva.concesion_hasta and reserva.concesion_hasta > ahora:
                raise ConflictoListas('La carga ya está en curso')
            if reserva.intentos >= self.perfil.recuperaciones:
                raise ConflictoListas('Presupuesto de transferencia agotado; registrar otra recepción')
            activas = list(sesion.scalars(select(ReservaRecepcionLista).where(ReservaRecepcionLista.concesion_hasta > ahora)))
            if len(activas) >= self.perfil.cargas_globales or any((r.actor_emisor, r.actor_sujeto) == (self.actor.issuer, self.actor.sub) for r in activas):
                raise ConflictoListas('Límite de cargas simultáneas')
            ocupado = 0
            for ruta in self.custodia.directorio.iterdir():
                try:
                    ocupado += ruta.lstat().st_size
                except FileNotFoundError:
                    # Otra transferencia puede haber retirado su temporal.
                    continue
            if ocupado + self.perfil.cargas_globales * self.perfil.recibido_bytes > self.perfil.disco_temporal_bytes:
                raise ConflictoListas('Cuota de custodia local insuficiente; revisar objetos retenidos')
            reserva.numero_control += 1
            reserva.intentos += 1
            reserva.concesion_hasta = ahora + timedelta(seconds=self.perfil.carga_segundos + 30)
            self._evento(sesion, identificador, 'TRANSFERENCIA_INICIADA', control=reserva.numero_control)
            return reserva.numero_control, dict(reserva.metadatos)

    def interrumpir(self, identificador, control, codigo):
        with self.sesiones.begin() as sesion:
            reserva = self._reserva(sesion, identificador, True)
            if reserva.numero_control == control and reserva.intento_importacion_id is None:
                reserva.concesion_hasta = None
                self._evento(sesion, identificador, 'TRANSFERENCIA_INTERRUMPIDA', control=control, codigo=codigo)

    def confirmar(self, identificador, control, objeto):
        self._autorizar()
        with self.sesiones() as sesion:
            reserva = self._reserva(sesion, identificador)
            if reserva.intento_importacion_id:
                return reserva.intento_importacion_id
        if objeto.clave != objeto.huella:
            raise ValueError("La clave del original debe coincidir con su hash")
        with original_verificado(self.custodia, objeto.huella, objeto.tamano_bytes):
            pass
        with self.sesiones.begin() as sesion:
            reserva = self._reserva(sesion, identificador, True)
            if reserva.intento_importacion_id:
                return reserva.intento_importacion_id
            if reserva.numero_control != control or reserva.concesion_hasta is None or reserva.concesion_hasta <= datetime.now(timezone.utc):
                raise ConflictoListas('La concesión de carga venció')
            if objeto.huella != reserva.metadatos['huella_declarada'] or not 0 < objeto.tamano_bytes <= self.perfil.recibido_bytes:
                raise ValueError('Objeto no corresponde a la recepción')
            archivo_id = uuid4()
            sesion.execute(insert(ArchivoFuente).values(id=archivo_id, clave=objeto.clave, huella=objeto.huella,
                tamano_bytes=objeto.tamano_bytes, nombre_recibido=reserva.metadatos['nombre_original'],
                tipo_contenido='application/octet-stream').on_conflict_do_nothing(index_elements=['clave']))
            archivo = sesion.scalar(select(ArchivoFuente).where(ArchivoFuente.clave == objeto.clave))
            if archivo.huella != objeto.huella or archivo.tamano_bytes != objeto.tamano_bytes:
                raise ConflictoListas('Metadatos de custodia incompatibles')
            recepcion = sesion.get(RecepcionFuente, identificador)
            recepcion.archivo_id, recepcion.estado = archivo.id, 'RECIBIDA'
            intento = IntentoImportacion(recepcion_id=identificador, estado='PENDIENTE', fase='VALIDACION')
            sesion.add(intento)
            sesion.flush()
            reserva.intento_importacion_id = intento.id
            reserva.concesion_hasta = None
            self._evento(sesion, identificador, 'RECIBIDA', archivo_id=str(archivo.id), intento_id=str(intento.id),
                         sha256=objeto.huella, tamano=objeto.tamano_bytes)
            return intento.id

    def original(self, identificador):
        self._autorizar('ver')
        with self.sesiones() as sesion:
            self._reserva(sesion, identificador)
            recepcion = sesion.get(RecepcionFuente, identificador)
            if recepcion.estado != 'RECIBIDA':
                raise ConflictoListas('Original todavía no recibido')
            archivo = sesion.get(ArchivoFuente, recepcion.archivo_id)
            huella, tamano = archivo.huella, archivo.tamano_bytes
        try:
            copia = original_verificado(self.custodia, huella, tamano)
        except (OSError, ErrorIntegridadEvidencia):
            with self.sesiones.begin() as sesion:
                self._evento(sesion, identificador, 'ORIGINAL_NO_DISPONIBLE')
            raise
        try:
            with self.sesiones.begin() as sesion:
                self._evento(sesion, identificador, 'DESCARGA_AUTORIZADA', sha256=huella)
            return copia
        except BaseException:
            copia.close()
            raise

    def conciliar(self):
        """Inventario de solo lectura; nunca elimina originales ni temporales."""
        self._autorizar('ver')
        self.actor.exigir('listas.bloquear_version')
        with self.sesiones() as sesion:
            referenciados = set(sesion.scalars(select(ArchivoFuente.clave)))
        existentes = {p.name for p in self.custodia.directorio.iterdir() if p.is_file()}
        temporales = {nombre for nombre in existentes if nombre.startswith('recepcion-')}
        return {'objetos_referenciados_presentes': len((existentes - temporales) & referenciados),
                'objetos_sin_referencia': len((existentes - temporales) - referenciados),
                'temporales_para_revision': len(temporales),
                'referencias_sin_objeto_local': len(referenciados - existentes),
                'eliminados': 0}
