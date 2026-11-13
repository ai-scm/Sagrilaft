"""Puerto común; ningún adaptador selecciona versiones activas ni decide cumplimiento."""
from typing import Protocol
from pydantic import AwareDatetime, Field, StringConstraints
from typing import Annotated
from uuid import UUID

from .contratos import Codigo, Criterio, DTO, Implementacion, ResultadoProveedorV2


class Capacidades(DTO):
    proveedor: Codigo
    adaptador_version: Codigo
    algoritmo_version: Codigo
    criterios_busqueda: tuple[Codigo, ...]
    tipos_identificador: tuple[Codigo, ...]
    version_explicita: bool
    evidencia_nativa: bool
    seleccion_fuentes: bool


class VersionFijada(DTO):
    fuente_codigo: Codigo
    version_id: UUID
    revision: int = Field(ge=0)
    hash_contenido: Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")]


class SolicitudProveedorV2(DTO):
    consulta_id: UUID
    correlacion_id: UUID
    criterio: Criterio
    implementacion: Implementacion
    proveedor: Codigo
    adaptador_version: Codigo
    algoritmo_version: Codigo
    parametros: dict
    admitida_en: AwareDatetime
    huella_configuracion: Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")]
    criterio_normalizado: Criterio | None = None
    politica_version: Codigo | None = None
    versiones: tuple[VersionFijada, ...] = ()


class DocumentoProveedor(DTO):
    """Bytes obtenidos del proveedor, antes de su custodia interna en F2."""
    referencia_origen: Codigo
    tipo_media: Codigo
    contenido: bytes


class ConsultorListasV2(Protocol):
    def capacidades(self) -> Capacidades: ...
    def consultar(self, solicitud: SolicitudProveedorV2) -> ResultadoProveedorV2: ...
    def obtener_evidencia(self, referencia: str) -> DocumentoProveedor: ...


class ListasNoDisponibles(RuntimeError):
    """Deshabilitado o adaptador pendiente; nunca equivale a ausencia de candidatos."""
