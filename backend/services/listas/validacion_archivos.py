"""Consume solo validación pendiente. No crea versiones ni ejecuta F5.4."""
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
from uuid import uuid4

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from domain.listas.administracion import PerfilEnsayo, InformeValidacionArchivo
from domain.listas.errores import ConflictoListas
from infrastructure.listas.recepcion_archivo import original_verificado, ArchivoEnRecepcion
from infrastructure.listas.adaptadores_archivos import obtener_adaptador, exigir_adaptador_habilitado
from infrastructure.persistencia.modelos_listas import ArchivoFuente, IntentoImportacion, RecepcionFuente, EsquemaFuente
from infrastructure.persistencia.modelos_recepcion_listas import ReservaRecepcionLista, EventoRecepcionLista
from services.listas.autorizacion_administrativa import exigir_entorno_sintetico


class TrabajadorValidacionArchivos:
    def __init__(self, sesiones, custodia, entorno, habilitado=False, perfil=None):
        exigir_entorno_sintetico(entorno)
        if not habilitado:
            raise PermissionError('Administración de listas deshabilitada')
        self.sesiones, self.custodia = sesiones, custodia
        self.perfil = perfil or PerfilEnsayo()
        self.perfil_explicito = perfil

    def _reclamar(self):
        with self.sesiones.begin() as sesion:
            sesion.execute(text('SELECT pg_advisory_xact_lock(523003)'))
            sesion.execute(text('SELECT pg_advisory_xact_lock(523001)'))
            ocupado = 0
            for ruta in self.custodia.directorio.rglob('*'):
                try:
                    if ruta.is_file(): ocupado += ruta.stat().st_size
                except FileNotFoundError:
                    continue
            reserva_disco = 2 * self.perfil.expandido_bytes + 4 * self.perfil.recibido_bytes
            if ocupado + reserva_disco > self.perfil.disco_temporal_bytes:
                raise ConflictoListas('Cuota insuficiente para validar; revisar custodia')
            ahora = datetime.now(timezone.utc)
            activos = sesion.scalar(select(IntentoImportacion.id).where(
                IntentoImportacion.estado == 'EN_CURSO', IntentoImportacion.concesion_hasta > ahora).limit(1))
            if activos:
                return None
            intento = sesion.scalar(select(IntentoImportacion).join(ReservaRecepcionLista,
                ReservaRecepcionLista.intento_importacion_id == IntentoImportacion.id).where(
                IntentoImportacion.fase == 'VALIDACION', IntentoImportacion.estado.in_(['PENDIENTE', 'EN_CURSO']),
                IntentoImportacion.informe.is_(None)).order_by(IntentoImportacion.creado_en).with_for_update(of=IntentoImportacion).limit(1))
            if intento is None:
                return None
            if intento.numero_control >= self.perfil.recuperaciones:
                intento.estado, intento.error = 'FALLIDO', 'REINTENTOS_AGOTADOS'
                intento.concesion_hasta = None
                self._evento(sesion, intento, 'VALIDACION_AGOTADA', {'codigo': intento.error})
                return None
            reserva = sesion.get(ReservaRecepcionLista, intento.recepcion_id)
            recepcion = sesion.get(RecepcionFuente, intento.recepcion_id)
            archivo = sesion.get(ArchivoFuente, recepcion.archivo_id)
            adaptador = obtener_adaptador(reserva.metadatos['formato'])
            exigir_adaptador_habilitado(adaptador)
            self.perfil = self.perfil_explicito or adaptador.perfil
            intento.numero_control += 1
            intento.estado = 'EN_CURSO'
            intento.concesion_hasta = ahora + timedelta(seconds=self.perfil.concesion_segundos)
            self._evento(sesion, intento, 'VALIDACION_INICIADA', {'control': intento.numero_control})
            return dict(id=intento.id, control=intento.numero_control, archivo_id=archivo.id,
                        huella=archivo.huella, tamano=archivo.tamano_bytes,
                        formato=reserva.metadatos['formato'], fuente_id=recepcion.fuente_id)

    def _evento(self, sesion, intento, tipo, detalle):
        sesion.add(EventoRecepcionLista(recepcion_id=intento.recepcion_id, actor_emisor='servicio-local',
            actor_sujeto='validador-archivos-v1', tipo=tipo, detalle=detalle))

    def _archivo(self, sesion, objeto, nombre, padre=None):
        sesion.execute(insert(ArchivoFuente).values(id=uuid4(), clave=objeto.clave, huella=objeto.huella,
            tamano_bytes=objeto.tamano_bytes, nombre_recibido=nombre, tipo_contenido='application/octet-stream',
            archivo_padre_id=padre).on_conflict_do_nothing(index_elements=['clave']))
        archivo = sesion.scalar(select(ArchivoFuente).where(ArchivoFuente.clave == objeto.clave))
        if (archivo.huella, archivo.tamano_bytes) != (objeto.huella, objeto.tamano_bytes):
            raise ConflictoListas('Objeto de validación incompatible')
        return archivo.id

    def _custodiar(self, ruta, huella, limite):
        escritura = ArchivoEnRecepcion(self.custodia, limite)
        try:
            with ruta.open('rb') as entrada:
                while bloque := entrada.read(65536): escritura.escribir(bloque)
            return escritura.confirmar(huella)
        finally:
            escritura.cerrar()

    def _procesar(self, directorio, trabajo):
        (directorio / 'solicitud.json').write_text(json.dumps({'formato': trabajo['formato'],
            'perfil': self.perfil.model_dump()}))
        # Sin credenciales ni conexiones de BD en el hijo.
        entorno = {'PATH': os.defpath, 'PYTHONPATH': str(Path(__file__).resolve().parents[2]),
                   'LANG': 'C.UTF-8', 'PYTHONDONTWRITEBYTECODE': '1'}
        self._renovar(trabajo)
        proceso = subprocess.Popen([sys.executable, '-m', 'infrastructure.listas.proceso_validacion', str(directorio)],
            env=entorno, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        vencimiento = time.monotonic() + self.perfil.validacion_segundos
        try:
            while True:
                restante = vencimiento - time.monotonic()
                if restante <= 0:
                    return {'resultado': 'INVALIDO', 'codigo': 'LIMITE_TIEMPO'}
                try:
                    proceso.wait(timeout=min(restante, self.perfil.latido_segundos))
                    break
                except subprocess.TimeoutExpired:
                    self._renovar(trabajo)
            if proceso.returncode:
                return {'resultado': 'INVALIDO', 'codigo': 'PROCESO_VALIDACION_FALLIDO'}
            return json.loads((directorio / 'informe.json').read_text())
        finally:
            if proceso.poll() is None:
                proceso.kill()
            proceso.wait()

    def _renovar(self, trabajo):
        with self.sesiones.begin() as sesion:
            intento = sesion.scalar(select(IntentoImportacion).where(IntentoImportacion.id == trabajo['id']).with_for_update())
            ahora = datetime.now(timezone.utc)
            if (intento.numero_control != trabajo['control'] or intento.concesion_hasta is None
                    or intento.concesion_hasta <= ahora or intento.informe is not None):
                raise ConflictoListas('Concesión de validación vencida')
            intento.concesion_hasta = ahora + timedelta(seconds=self.perfil.concesion_segundos)

    def ejecutar_uno(self):
        trabajo = self._reclamar()
        if trabajo is None:
            return False
        adaptador = obtener_adaptador(trabajo['formato'])
        # Los errores de custodia/SQL se propagan. La concesión permite recuperarlos.
        with tempfile.TemporaryDirectory(prefix='validacion-', dir=self.custodia.directorio) as temporal:
            directorio = Path(temporal)
            with original_verificado(self.custodia, trabajo['huella'], trabajo['tamano']) as original:
                with (directorio / 'original.bin').open('wb') as destino:
                    shutil.copyfileobj(original, destino, length=65536)
            informe = self._procesar(directorio, trabajo)
            informe.update(original_sha256=trabajo['huella'], formato=trabajo['formato'],
                version_validador=adaptador.version_validador, esquema_sha256=adaptador.huella_esquema,
                perfil=self.perfil.codigo, oficial=adaptador.oficial)
            informe = InformeValidacionArchivo.model_validate(informe).model_dump(mode='json')
            contenido = None
            if informe['resultado'] == 'VALIDO':
                ruta = directorio / ('contenido.xml' if trabajo['formato'] != adaptador.formato else 'original.bin')
                contenido = self._custodiar(ruta, informe['contenido_sha256'], self.perfil.expandido_bytes)
            esquema = self._custodiar(adaptador.esquema, adaptador.huella_esquema, self.perfil.expandido_bytes)
            informe_objeto = self.custodia.guardar(json.dumps(informe, sort_keys=True, ensure_ascii=False).encode())
            self._confirmar(trabajo, informe, informe_objeto, contenido, esquema)
        return True

    def _confirmar(self, trabajo, informe, informe_objeto, contenido, esquema):
        adaptador = obtener_adaptador(trabajo['formato'])
        with self.sesiones.begin() as sesion:
            intento = sesion.scalar(select(IntentoImportacion).where(IntentoImportacion.id == trabajo['id']).with_for_update())
            if (intento.numero_control != trabajo['control'] or intento.informe is not None
                    or intento.concesion_hasta is None or intento.concesion_hasta <= datetime.now(timezone.utc)):
                raise ConflictoListas('Concesión de validación vencida')
            informe_id = self._archivo(sesion, informe_objeto, 'informe-validacion.json', trabajo['archivo_id'])
            esquema_archivo = self._archivo(sesion, esquema, adaptador.esquema.name)
            # Paquete aprobado por código, no suministrado por quien carga el XML.
            esquema_id = sesion.scalar(select(EsquemaFuente).where(EsquemaFuente.fuente_id == trabajo['fuente_id'],
                EsquemaFuente.archivo_id == esquema_archivo, EsquemaFuente.version == adaptador.version_esquema))
            if esquema_id is not None:
                if not esquema_id.aprobado:
                    raise ConflictoListas('El esquema registrado no está aprobado')
                esquema_id = esquema_id.id
            if esquema_id is None:
                registro = EsquemaFuente(fuente_id=trabajo['fuente_id'], archivo_id=esquema_archivo,
                    formato=adaptador.formato, version=adaptador.version_esquema, aprobado=True)
                sesion.add(registro); sesion.flush(); esquema_id = registro.id
            vinculos = {'informe_id': str(informe_id), 'informe_sha256': informe_objeto.huella,
                        'esquema_id': str(esquema_id), 'archivo_raiz_id': str(trabajo['archivo_id'])}
            if contenido:
                vinculos['archivo_contenido_id'] = str(self._archivo(sesion, contenido, 'contenido.xml', trabajo['archivo_id']))
            intento.informe = {**informe, **vinculos}
            intento.concesion_hasta = None
            if informe['resultado'] == 'VALIDO':
                intento.fase = 'IMPORTACION'
                # No COMPLETADO: el contrato reserva ese estado al sellado de F5.4.
            else:
                intento.estado, intento.error = 'FALLIDO', informe['codigo']
            self._evento(sesion, intento, 'VALIDACION_FINALIZADA', intento.informe)
