"""Entradas autenticadas del servicio común de listas."""
from uuid import UUID
from fastapi import APIRouter, Depends, Header, Query, HTTPException
from fastapi.responses import Response
from fastapi.routing import APIRoute
from pydantic import ValidationError
from domain.listas.contratos import CrearConsultaV2
from domain.listas.contratos_busqueda import CrearConsultaBusqueda
from domain.listas.errores import ConflictoListas, ErrorIntegridadEvidencia
from domain.excepciones import SinPermisoError
from domain.listas.puertos import ListasNoDisponibles
from api.dependencias_listas import servicio_listas
from api.schemas.listas_v2 import SolicitudConsultaLista, SolicitudConsultaArchivos, RevisionLista, AdmisionLista, DetalleConsultaLista, AdmisionGrupo, DisponibilidadListas, RevisionRegistrada, HistorialListas
from services.listas.modalidades import modalidad_disponible
from services.listas.servicio_comun import ServicioComunListas


class RutaListas(APIRoute):
    def get_route_handler(self):
        manejador = super().get_route_handler()
        async def ejecutar(solicitud):
            try:
                respuesta = await manejador(solicitud)
                respuesta.headers["Cache-Control"] = "private, no-store"
                return respuesta
            except (PermissionError, SinPermisoError) as error:
                raise HTTPException(403, str(error)) from error
            except LookupError as error:
                raise HTTPException(404, str(error)) from error
            except (ConflictoListas, ListasNoDisponibles) as error:
                raise HTTPException(409, str(error)) from error
            except ErrorIntegridadEvidencia as error:
                raise HTTPException(503, "Evidencia no disponible: fallo de integridad") from error
            except (ValueError, ValidationError) as error:
                raise HTTPException(422, "Datos de consulta no válidos") from error
        return ejecutar


enrutador = APIRouter(prefix="/api", tags=["consultas de listas v2"], route_class=RutaListas)


@enrutador.get("/listas/disponibilidad", response_model=DisponibilidadListas)
def disponibilidad(servicio: ServicioComunListas = Depends(servicio_listas)):
    permisos = servicio.actor.permisos
    modalidad = modalidad_disponible(servicio.politica.config, servicio.entorno)
    return {"consultar": modalidad is not None and "listas.consultar" in permisos,
            "historial": "listas.ver_evidencias" in permisos, "revisar": "listas.revisar" in permisos,
            "implementacion": servicio.politica.config.implementacion,
            "version_contrato": modalidad.version_contrato if modalidad else None}


@enrutador.post("/expedientes/{expediente_id}/consultas-listas", status_code=202, response_model=AdmisionLista)
def crear(expediente_id: str, datos: SolicitudConsultaLista | SolicitudConsultaArchivos,
          clave: str = Header(alias="Idempotency-Key", min_length=1, max_length=128),
          servicio: ServicioComunListas = Depends(servicio_listas)):
    modelo = CrearConsultaBusqueda if isinstance(datos, SolicitudConsultaArchivos) else CrearConsultaV2
    solicitud = modelo(version_contrato="2.1" if isinstance(datos, SolicitudConsultaArchivos) else "2.0", contexto={"tipo": "EXPEDIENTE", "expediente_id": expediente_id,
        "sujeto_rol": datos.sujeto_rol, "motivo": datos.motivo}, criterio=datos.criterio)
    identificador = servicio.crear(expediente_id, solicitud, clave)
    return {"consulta_id": identificador, "ubicacion": f"/api/consultas-listas/{identificador}"}


@enrutador.post("/expedientes/{expediente_id}/consultas-listas/grupos", status_code=202, response_model=AdmisionGrupo)
def grupo(expediente_id: str, clave: str = Header(alias="Idempotency-Key", min_length=1, max_length=128),
          servicio: ServicioComunListas = Depends(servicio_listas)):
    return servicio.crear_grupo(expediente_id, clave)


@enrutador.get("/expedientes/{expediente_id}/consultas-listas", response_model=HistorialListas)
def historial(expediente_id: str, antes: UUID | None = None, limite: int = Query(20, ge=1, le=100),
              servicio: ServicioComunListas = Depends(servicio_listas)):
    return servicio.historial(expediente_id, antes, limite)


@enrutador.get("/consultas-listas/{consulta_id}", response_model=DetalleConsultaLista)
def detalle(consulta_id: UUID, servicio: ServicioComunListas = Depends(servicio_listas)):
    return servicio.detalle(consulta_id)


@enrutador.get("/consultas-listas/{consulta_id}/evidencias/{evidencia_id}")
def evidencia(consulta_id: UUID, evidencia_id: UUID, servicio: ServicioComunListas = Depends(servicio_listas)):
    contenido = servicio.evidencia(consulta_id, evidencia_id)
    return Response(contenido, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="listas_{consulta_id}.pdf"',
                                                                    "Cache-Control": "private, no-store"})


@enrutador.post("/consultas-listas/{consulta_id}/revisiones", status_code=201, response_model=RevisionRegistrada)
def revisar(consulta_id: UUID, datos: RevisionLista, servicio: ServicioComunListas = Depends(servicio_listas)):
    return {"revision_id": servicio.revisar(consulta_id, **datos.model_dump())}
