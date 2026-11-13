"""Recepción local en dos pasos. No valida ni importa el contenido."""
import asyncio
import json
import logging
from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import StreamingResponse
from starlette.background import BackgroundTask
from starlette.requests import ClientDisconnect
from domain.listas.administracion import RecepcionPropuesta
from api.routers.consultas_listas import RutaListas
from api.dependencias_listas import sesiones_listas, custodia_listas
from api.middleware.autenticacion import portal_interno, _decodificar_jwt, UsuarioPortalInterno
from services.listas.politica_v2 import ActorListas, PoliticaListasV2
from services.listas.recepcion import ServicioRecepcionListas
from infrastructure.listas.recepcion_archivo import ArchivoEnRecepcion, LimiteCarga
from domain.listas.errores import ErrorIntegridadEvidencia
from domain.utils.seguridad import sanitizar_log


def servicio_recepcion(request: Request, usuario: UsuarioPortalInterno = Depends(portal_interno),
                       sesiones=Depends(sesiones_listas), custodia=Depends(custodia_listas)):
    configuracion = request.app.state.config
    actor = ActorListas.desde_identidad_validada(configuracion.keycloak.issuer, usuario.sub, tuple(usuario.roles))
    request.state.actor_recepcion = (actor.issuer, actor.sub)
    return ServicioRecepcionListas(sesiones, custodia,
        PoliticaListasV2(configuracion.listas_cautela, configuracion.entorno), actor, configuracion.entorno)


class RutaRecepcionAuditada(RutaListas):
    """Conserva los errores HTTP y registra accesos rechazados sin revelar el original."""
    def get_route_handler(self):
        manejador = super().get_route_handler()

        async def ejecutar(solicitud):
            correlacion = getattr(solicitud.state, 'request_id', None) or str(uuid4())
            try:
                return await manejador(solicitud)
            except HTTPException as error:
                if error.status_code in {401, 403, 404}:
                    emisor, sujeto = getattr(solicitud.state, 'actor_recepcion',
                                             ('IDENTIDAD_NO_VERIFICADA', 'IDENTIDAD_NO_VERIFICADA'))
                    logging.getLogger(__name__).warning(
                        'LISTAS_RECEPCION_DENEGADA codigo=%s correlacion=%s emisor=%s actor=%s recurso=%s',
                        error.status_code, sanitizar_log(correlacion), sanitizar_log(emisor),
                        sanitizar_log(sujeto), sanitizar_log(solicitud.url.path))
                raise

        return ejecutar


enrutador = APIRouter(prefix='/api/administracion-listas', route_class=RutaRecepcionAuditada)


@enrutador.post('/recepciones', status_code=201)
async def reservar(request: Request, clave: str = Header(alias='Idempotency-Key', min_length=1, max_length=128),
                   servicio=Depends(servicio_recepcion)):
    servicio._autorizar()
    contenido = bytearray()
    try:
        async with asyncio.timeout(30):
            async for bloque in request.stream():
                if len(contenido) + len(bloque) > servicio.perfil.campos_bytes:
                    raise HTTPException(413, 'Metadatos demasiado grandes')
                contenido.extend(bloque)
    except TimeoutError:
        raise HTTPException(408, 'Tiempo de recepción agotado')
    datos = json.loads(contenido)
    if not isinstance(datos, dict) or 'clave' in datos:
        raise HTTPException(422, 'Metadatos inválidos; use Idempotency-Key')
    solicitud = RecepcionPropuesta.model_validate({**datos, 'clave': clave})
    identificador = servicio.reservar(solicitud)
    return {'recepcion_id': identificador, 'estado': servicio.consultar(identificador)['estado']}


@enrutador.get('/recepciones/{identificador}')
def consultar(identificador: UUID, servicio=Depends(servicio_recepcion)):
    return servicio.consultar(identificador)


@enrutador.put('/recepciones/{identificador}/contenido', status_code=202)
async def cargar(identificador: UUID, request: Request, servicio=Depends(servicio_recepcion)):
    if request.headers.get('content-type') != 'application/octet-stream':
        raise HTTPException(415, 'Envíe el original como application/octet-stream')
    servicio.preparar_perfil(identificador)
    longitud = request.headers.get('content-length')
    if longitud is not None:
        try:
            declarada = int(longitud)
        except ValueError:
            raise HTTPException(400, 'Content-Length inválido')
        if declarada < 0:
            raise HTTPException(400, 'Content-Length inválido')
        if declarada > servicio.perfil.recibido_bytes:
            raise HTTPException(413, 'Archivo demasiado grande')
    concesion = servicio.reclamar(identificador)
    if concesion is None:
        return servicio.consultar(identificador)
    control, metadatos = concesion
    archivo = None
    try:
        archivo = ArchivoEnRecepcion(servicio.custodia, servicio.perfil.recibido_bytes)
        async with asyncio.timeout(servicio.perfil.carga_segundos):
            async for bloque in request.stream():
                archivo.escribir(bloque)
        if longitud is not None and archivo.tamano != declarada:
            raise HTTPException(400, 'Longitud recibida no coincide')
        # Revalidar al confirmar; nunca conservar JWT en la reserva o el trabajo.
        autorizacion = request.headers.get('authorization', '')
        if not autorizacion.lower().startswith('bearer '):
            raise HTTPException(401, 'Se requiere identidad vigente')
        usuario = await _decodificar_jwt(autorizacion[7:], request.app.state.config.keycloak, request)
        nuevo = ActorListas.desde_identidad_validada(request.app.state.config.keycloak.issuer, usuario.sub, tuple(usuario.roles))
        if (nuevo.issuer, nuevo.sub) != (servicio.actor.issuer, servicio.actor.sub):
            raise HTTPException(403, 'La identidad cambió durante la carga')
        servicio.politica.administracion(nuevo, 'cargar')
        objeto = archivo.confirmar(metadatos['huella_declarada'])
        servicio.confirmar(identificador, control, objeto)
        return servicio.consultar(identificador)
    except BaseException as error:
        servicio.interrumpir(identificador, control, type(error).__name__)
        if isinstance(error, LimiteCarga):
            raise HTTPException(413, 'Archivo demasiado grande') from error
        if isinstance(error, ErrorIntegridadEvidencia):
            raise HTTPException(422, 'El original no coincide con la huella declarada') from error
        if isinstance(error, TimeoutError):
            raise HTTPException(408, 'Tiempo de carga agotado') from error
        if isinstance(error, ClientDisconnect):
            raise HTTPException(400, 'Transferencia interrumpida') from error
        if isinstance(error, OSError):
            raise HTTPException(503, 'Custodia temporalmente no disponible') from error
        raise
    finally:
        if archivo:
            archivo.cerrar()


@enrutador.get('/recepciones/{identificador}/original')
def descargar(identificador: UUID, servicio=Depends(servicio_recepcion)):
    try:
        copia = servicio.original(identificador)
    except PermissionError:
        raise
    except OSError as error:
        raise HTTPException(503, 'Original no disponible') from error
    def bloques():
        try:
            while bloque := copia.read(65536):
                yield bloque
        finally:
            copia.close()
    return StreamingResponse(bloques(), media_type='application/octet-stream',
        headers={'Content-Disposition': f'attachment; filename="original_{identificador}.bin"',
                 'Cache-Control':'private, no-store', 'X-Content-Type-Options':'nosniff'},
        background=BackgroundTask(copia.close))


@enrutador.get('/conciliacion')
def conciliar(servicio=Depends(servicio_recepcion)):
    return servicio.conciliar()


@enrutador.get('/intentos/{identificador}')
def progreso(identificador: UUID, servicio=Depends(servicio_recepcion)):
    from domain.listas.administracion import ProgresoImportacion
    from infrastructure.persistencia.modelos_listas import IntentoImportacion
    servicio._autorizar('ver')
    with servicio.sesiones() as sesion:
        intento = sesion.get(IntentoImportacion, identificador)
        if intento is None:
            raise LookupError('Intento no disponible')
        servicio._reserva(sesion, intento.recepcion_id)
        return ProgresoImportacion(intento_id=intento.id, estado=intento.estado, fase=intento.fase,
            registros_confirmados=intento.punto_reanudacion.get('registros_confirmados', 0), codigo_error=intento.error)


@enrutador.get('/recepciones/{identificador}/validacion')
def informe_validacion(identificador: UUID, servicio=Depends(servicio_recepcion)):
    from sqlalchemy import select
    from infrastructure.persistencia.modelos_recepcion_listas import EventoRecepcionLista
    from infrastructure.persistencia.modelos_listas import ArchivoFuente, IntentoImportacion
    from infrastructure.listas.recepcion_archivo import original_verificado
    servicio._autorizar('ver')
    with servicio.sesiones() as sesion:
        reserva = servicio._reserva(sesion, identificador)
        evento = sesion.scalar(select(EventoRecepcionLista).where(
            EventoRecepcionLista.recepcion_id == identificador,
            EventoRecepcionLista.tipo == 'VALIDACION_FINALIZADA'))
        if evento is None:
            intento = sesion.get(IntentoImportacion, reserva.intento_importacion_id) if reserva.intento_importacion_id else None
            if intento and intento.error:
                return {'resultado': 'NO_COMPLETADA', 'codigo': intento.error}
            return {'resultado': 'NO_EJECUTADA_O_EN_CURSO'}
        archivo = sesion.get(ArchivoFuente, UUID(evento.detalle['informe_id']))
        try:
            with original_verificado(servicio.custodia, archivo.huella, archivo.tamano_bytes) as copia:
                return json.load(copia)
        except OSError as error:
            raise HTTPException(503, 'Informe no disponible') from error
