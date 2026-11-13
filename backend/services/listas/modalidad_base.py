"""Piezas comunes a las modalidades de consulta (contrato del registro y grupos del expediente)."""
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Protocol
from uuid import UUID, uuid4


@dataclass(frozen=True)
class ConsultaAdmitida:
    """Lo que el trabajador leyó de una consulta ya admitida, antes de ejecutarla."""
    id: UUID
    implementacion: str
    version_contrato: str
    manifiesto: dict
    criterio: dict
    admitida_en: datetime
    tiene_borrador: bool


class ModalidadListas(Protocol):
    implementacion: str
    version_contrato: str

    def disponible(self, entorno: str) -> bool: ...
    def recuperar_reintento(self, servicio, solicitud, clave: str) -> UUID | None: ...
    def crear(self, servicio, solicitud, clave: str) -> UUID: ...
    def crear_grupo(self, servicio, expediente_id: str, clave: str, sesion) -> dict: ...
    def reconoce(self, consulta: ConsultaAdmitida) -> bool: ...
    def ejecutar(self, trabajador, concesion, consulta: ConsultaAdmitida) -> None: ...


def crear_grupo_por_documento(servicio, expediente_id, clave, sesion, *, proveedor: str,
                              criterio_para: Callable[[str, object], tuple[dict | None, str]],
                              manifiesto_para: Callable[[dict], dict]) -> dict:
    """Admite en una transacción la consulta de la contraparte y la de su representante.

    `criterio_para(rol, expediente)` devuelve (criterio, motivo): criterio None omite al
    sujeto con ese motivo. El grupo se inserta ya completo y cada hijo lo referencia.
    """
    from sqlalchemy import text
    from domain.listas.contratos import CrearConsultaV2, SolicitudIdempotente
    from infrastructure.persistencia.models import Formulario
    from infrastructure.persistencia.modelos_grupos_listas import GrupoConsultaLista
    from services.listas.informes import calcular_huella
    huella = calcular_huella({"expediente": expediente_id, "operacion": "ambos_sujetos_v1"})
    expediente = sesion.get(Formulario, expediente_id)
    grupo_id = uuid4()
    solicitudes, omitidos = [], []
    for rol in ("CONTRAPARTE", "REPRESENTANTE"):
        criterio, motivo = criterio_para(rol, expediente)
        if criterio is None:
            omitidos.append({"sujeto_rol": rol, "motivo": motivo})
            continue
        solicitudes.append(CrearConsultaV2(version_contrato="2.0", contexto={"tipo": "EXPEDIENTE",
            "expediente_id": expediente_id, "sujeto_rol": rol}, criterio=criterio))
    respuesta = {"grupo_id": str(grupo_id), "consultas": [], "no_consultados": omitidos}
    grupo = GrupoConsultaLista(id=grupo_id, actor_emisor=servicio.actor.issuer, actor_sujeto=servicio.actor.sub,
        expediente_id=expediente_id, clave=clave, huella=huella, respuesta={})
    # Diferir FK para poder insertar el grupo ya completo al final.
    sesion.execute(text("SET CONSTRAINTS fk_consulta_grupo DEFERRED"))
    for solicitud in solicitudes:
        identificador = servicio.repositorio.admitir(servicio.actor,
            SolicitudIdempotente(clave=f"grupo:{grupo_id}:{solicitud.contexto.sujeto_rol}", solicitud=solicitud),
            proveedor, manifiesto_para(solicitud.criterio.model_dump(mode="json")), grupo_id=grupo_id, sesion_actual=sesion)
        respuesta["consultas"].append({"consulta_id": str(identificador), "sujeto_rol": solicitud.contexto.sujeto_rol})
    grupo.respuesta = respuesta
    sesion.add(grupo)
    return respuesta


def datos_sujeto(rol: str, expediente) -> tuple[str | None, str | None, str | None]:
    """(nombre, tipo de documento, número) del sujeto del expediente."""
    if rol == "CONTRAPARTE":
        return expediente.razon_social, expediente.tipo_identificacion, expediente.numero_identificacion
    return expediente.nombre_representante, expediente.tipo_doc_representante, expediente.numero_doc_representante
