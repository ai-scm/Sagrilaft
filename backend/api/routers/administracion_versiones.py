"""F5.5 local: toda operación administrativa recibe identidad JWT verificada."""
import asyncio
import logging
import os
from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, Request, Query, HTTPException
from fastapi.responses import StreamingResponse
from starlette.background import BackgroundTask
from api.routers.consultas_listas import RutaListas
from api.dependencias_listas import sesiones_listas, custodia_listas
from api.middleware.autenticacion import portal_interno, _decodificar_jwt, UsuarioPortalInterno
from domain.listas.administracion import (ComparacionPropuesta, SolicitudAdministrativa,
    DecisionAdministrativa, EjecucionAdministrativa, OperacionMotivada)
from services.listas.politica_v2 import ActorListas, PoliticaListasV2
from services.listas.administracion_versiones import ServicioAdministracionVersiones


class RutaAdministrativa(RutaListas):
    def get_route_handler(self):
        manejador = super().get_route_handler()
        async def ejecutar(solicitud):
            solicitud.state.correlacion_id = str(uuid4())
            try:
                if solicitud.method == 'POST':
                    contenido = bytearray()
                    async with asyncio.timeout(30):
                        async for bloque in solicitud.stream():
                            if len(contenido) + len(bloque) > 16384:
                                raise HTTPException(413, 'Metadatos administrativos demasiado grandes')
                            contenido.extend(bloque)
                    solicitud._body = bytes(contenido)
                return await manejador(solicitud)
            except TimeoutError as error:
                raise HTTPException(408, 'Tiempo de petición agotado') from error
            except Exception as error:
                # Solo código y clase; nunca JWT, cuerpos ni datos de las listas.
                logging.getLogger(__name__).warning('ADMINISTRACION_DENEGADA_O_FALLIDA codigo=%s clase=%s correlacion=%s actor=%s',
                    getattr(error, 'status_code', 500), type(error).__name__, solicitud.state.correlacion_id,
                    getattr(solicitud.state, 'actor_administrativo', 'IDENTIDAD_NO_VERIFICADA'))
                raise
        return ejecutar


def servicio_administrativo(request: Request, usuario: UsuarioPortalInterno = Depends(portal_interno),
                           sesiones=Depends(sesiones_listas), custodia=Depends(custodia_listas)):
    config = request.app.state.config
    actor = ActorListas.desde_identidad_validada(config.keycloak.issuer, usuario.sub, tuple(usuario.roles))
    request.state.actor_administrativo = (actor.issuer, actor.sub)
    autorizacion = request.headers.get('authorization', '')
    if not autorizacion.lower().startswith('bearer '):
        raise PermissionError('Administración exige JWT incluso en local')
    def identidad_vigente():
        nuevo = asyncio.run(_decodificar_jwt(autorizacion[7:], config.keycloak, request))
        if nuevo.sub != usuario.sub or set(nuevo.roles) != set(usuario.roles):
            raise PermissionError('La identidad cambió durante la operación')
    def politica_vigente():
        valor = os.environ.get('LISTAS_ADMIN_POLITICA_ID')
        if not valor:
            from domain.listas.errores import ConflictoListas
            raise ConflictoListas('Política administrativa local no configurada')
        return UUID(valor)
    servicio = ServicioAdministracionVersiones(sesiones, custodia, PoliticaListasV2(config.listas_cautela, config.entorno),
        actor, config.entorno, politica_vigente, validar_identidad=identidad_vigente)
    servicio.correlacion_id = request.state.correlacion_id
    return servicio


enrutador = APIRouter(prefix='/api/administracion-listas', route_class=RutaAdministrativa)


@enrutador.post('/comparaciones', status_code=202)
def comparar(datos: ComparacionPropuesta, servicio=Depends(servicio_administrativo)):
    return servicio.comparar(datos)


@enrutador.get('/comparaciones/{identificador}')
def informe(identificador: UUID, pagina: int = Query(0, ge=0), limite: int = Query(50, ge=1, le=100),
            servicio=Depends(servicio_administrativo)):
    return servicio.informe(identificador, pagina, limite)


@enrutador.post('/solicitudes', status_code=201)
def solicitar(datos: SolicitudAdministrativa, servicio=Depends(servicio_administrativo)):
    return servicio.solicitar(datos)


@enrutador.get('/solicitudes/{identificador}')
def consultar(identificador: UUID, servicio=Depends(servicio_administrativo)):
    return servicio.consultar_solicitud(identificador)


def exigir_correspondencia(identificador, recibido):
    if identificador != recibido:
        raise ValueError('El identificador de la ruta no coincide con el cuerpo')


@enrutador.post('/solicitudes/{identificador}/decisiones', status_code=201)
def decidir(identificador: UUID, datos: DecisionAdministrativa, servicio=Depends(servicio_administrativo)):
    exigir_correspondencia(identificador, datos.solicitud_id)
    return servicio.decidir(datos)


@enrutador.post('/solicitudes/{identificador}/ejecuciones')
def ejecutar(identificador: UUID, datos: EjecucionAdministrativa, servicio=Depends(servicio_administrativo)):
    exigir_correspondencia(identificador, datos.solicitud_id)
    return servicio.ejecutar(datos)


@enrutador.post('/revisiones/{identificador}/revocaciones', status_code=201)
def revocar(identificador: UUID, datos: OperacionMotivada, servicio=Depends(servicio_administrativo)):
    exigir_correspondencia(identificador, datos.objeto_id)
    return servicio.revocar(datos)


@enrutador.post('/versiones/{identificador}/bloqueos')
def bloquear(identificador: UUID, datos: OperacionMotivada, servicio=Depends(servicio_administrativo)):
    exigir_correspondencia(identificador, datos.objeto_id)
    return servicio.bloquear(datos)


@enrutador.get('/versiones/{identificador}/evidencias/{tipo}')
def evidencia(identificador: UUID, tipo: str, servicio=Depends(servicio_administrativo)):
    copia = servicio.evidencia(identificador, tipo)
    def bloques():
        try:
            while bloque := copia.read(65536):
                yield bloque
        finally:
            copia.close()
    return StreamingResponse(bloques(), media_type='application/octet-stream',
        headers={'Content-Disposition': 'attachment; filename="evidencia.bin"', 'X-Content-Type-Options': 'nosniff'},
        background=BackgroundTask(copia.close))


@enrutador.get('/fuentes')
def fuentes(servicio=Depends(servicio_administrativo)):
    return servicio.fuentes()


@enrutador.get('/fuentes/{identificador}/versiones')
def versiones(identificador: UUID, pagina: int = Query(0, ge=0), limite: int = Query(50, ge=1, le=100),
              servicio=Depends(servicio_administrativo)):
    return servicio.versiones(identificador, pagina, limite)


@enrutador.get('/versiones/{version_id}/registros/{registro_id}')
def registro_conservado(version_id: UUID, registro_id: UUID, servicio=Depends(servicio_administrativo)):
    return servicio.registro_conservado(version_id, registro_id)
