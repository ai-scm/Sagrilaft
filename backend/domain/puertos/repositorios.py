"""
Puertos de repositorio — contratos que los adaptadores de persistencia deben cumplir.

Cada protocolo describe las operaciones de BD que un servicio de aplicación necesita,
sin mencionar SQLAlchemy, ORM ni ningún detalle de infraestructura.

SOLID:
- I (Segregación de Interfaces): un protocolo por servicio; cada uno expone solo
  lo que su consumidor necesita.
- D (Inversión de Dependencias): los servicios dependen de estos protocolos,
  no de SQLAlchemy ni de implementaciones concretas.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

from domain.contratos import (
    AccesoManualDatos,
    DocumentoDatos,
    ResultadoCreacionAcceso,
    SolicitudCreacionAcceso,
)
from domain.formulario.entidades import FormularioDatos
from domain.validacion.resultado import ResultadoValidacionDominio


@runtime_checkable
class RepositorioFormulario(Protocol):
    """Puerto de persistencia para FormularioService."""

    def obtener_por_id(self, formulario_id: str) -> Optional[FormularioDatos]: ...
    def obtener_por_codigo(self, codigo: str) -> Optional[FormularioDatos]: ...
    def crear(self, datos: Dict[str, Any]) -> FormularioDatos: ...
    def actualizar(self, formulario_id: str, campos: Dict[str, Any]) -> FormularioDatos: ...
    def guardar_alertas(self, formulario_id: str, alertas: List[Dict[str, Any]]) -> None: ...


@runtime_checkable
class RepositorioDocumento(Protocol):
    """Puerto de persistencia para DocumentoService."""

    def buscar(self, formulario_id: str, doc_id: str) -> Optional[DocumentoDatos]: ...
    def listar_activos(self, formulario_id: str) -> List[DocumentoDatos]: ...
    def crear(self, datos: Dict[str, Any]) -> DocumentoDatos: ...
    def actualizar_rutas(self, rutas: Dict[str, str]) -> None: ...
    def marcar_eliminado(self, doc_id: str) -> None: ...
    def actualizar_snapshot_datos(self, doc_id: str, snapshot_datos: str) -> None: ...
    def obtener_ultimo_formulario_pdf(self, formulario_id: str) -> Optional[DocumentoDatos]: ...
    """
    Retorna el PDF del formulario con el mayor version_numero activo.
    Es el punto de partida para construir la cadena de versiones al generar
    un nuevo PDF en cada envío o corrección.
    """


@runtime_checkable
class RepositorioValidacion(Protocol):
    """Puerto de persistencia para ValidacionService."""

    def obtener_formulario(self, formulario_id: str) -> Optional[FormularioDatos]: ...
    def limpiar_validaciones(self, formulario_id: str) -> None: ...
    def guardar_validaciones(self, datos: List[Dict[str, Any]]) -> List[ResultadoValidacionDominio]: ...


@runtime_checkable
class RepositorioExpediente(Protocol):
    """Puerto de persistencia para ExpedienteService."""

    def listar(
        self,
        estados: List[Any],
        tipo_contraparte: Optional[str] = None,
        busqueda: Optional[str] = None,
        contrapartes_permitidas: Optional[List[str]] = None,
    ) -> List[FormularioDatos]: ...

    def obtener(self, formulario_id: str, estados: List[Any], bloquear: bool = False) -> Optional[FormularioDatos]: ...

    def buscar_documento_descargable(
        self, formulario_id: str, doc_id: str, estados: List[Any]
    ) -> Optional[DocumentoDatos]: ...

    def listar_documentos(self, formulario_id: str) -> List[DocumentoDatos]: ...

    def contar_documentos(self, ids_formularios: List[str]) -> Dict[str, int]: ...

    def actualizar_sagrilaft_reporte_id(self, formulario_id: str, reporte_id: str) -> None: ...

    def actualizar_estado(self, formulario_id: str, estado: str) -> None: ...

    def actualizar_para_correccion(
        self,
        formulario_id: str,
        estado: str,
        numero_correccion: int,
        campos_a_corregir: str,
    ) -> None: ...

    def actualizar_para_deshacer_devolucion(
        self,
        formulario_id: str,
        estado: str,
        numero_correccion: int,
    ) -> None: ...

    def actualizar_para_reapertura_actualizacion(
        self,
        formulario_id: str,
        estado: str,
        campos_a_corregir: str,
    ) -> None: ...

    def actualizar_estado_alerta(
        self,
        formulario_id: str,
        alerta_id: str,
        estado_auditoria: str,
        actor_id: str,
    ) -> None: ...


@runtime_checkable
class RepositorioFirma(Protocol):
    """Puerto de persistencia para FirmaService."""

    def obtener_formulario(self, formulario_id: str, bloquear: bool = False) -> Optional[FormularioDatos]: ...
    def obtener_formulario_por_zoho_id(self, request_id: str, bloquear: bool = False) -> Optional[FormularioDatos]: ...
    def obtener_pdf(self, formulario_id: str) -> Optional[DocumentoDatos]: ...
    def obtener_acceso_manual(self, formulario_id: str) -> Optional[AccesoManualDatos]: ...
    def obtener_certificado(self, formulario_id: str) -> Optional[DocumentoDatos]: ...
    def crear_documento(self, datos: Dict[str, Any]) -> None: ...
    def actualizar_formulario(self, formulario_id: str, campos: Dict[str, Any]) -> None: ...
    def actualizar_certificado(self, doc_id: str, ruta_archivo: str, tamano: int, hash_sha256: str) -> None: ...


@runtime_checkable
class RepositorioAccesoManual(Protocol):
    """Puerto de persistencia para AccesoManualService."""

    def obtener_acceso_por_token(self, token: str) -> Optional[AccesoManualDatos]: ...
    def obtener_acceso_por_formulario_id(
        self, formulario_id: str, *, cargar_formulario: bool = False
    ) -> Optional[AccesoManualDatos]: ...
    def obtener_formulario_por_codigo(self, codigo_peticion: str) -> Optional[FormularioDatos]: ...
    def obtener_formulario_completo(self, formulario_id: str) -> Optional[FormularioDatos]: ...
    def listar_accesos(self) -> List[AccesoManualDatos]: ...
    def crear_formulario_y_acceso(
        self, solicitud: SolicitudCreacionAcceso, pin_hash: str, token: str
    ) -> ResultadoCreacionAcceso: ...
    def marcar_consumido(self, acceso_id: str, timestamp: datetime) -> None: ...
    def reactivar_acceso(
        self, acceso_id: str, nuevo_token: str, nuevo_expires_at: datetime
    ) -> None: ...
    def actualizar_correo_por_token(self, token: str, correo: str) -> None: ...
    def obtener_acceso_activo_por_correo(self, correo: str) -> Optional[AccesoManualDatos]: ...
    def reenviar_acceso(self, acceso_id: str, nuevo_pin_hash: str, nuevo_token: str, timestamp: datetime) -> None: ...
