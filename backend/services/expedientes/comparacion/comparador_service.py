"""
ComparadorService — gestión de comparación de versiones de formularios.

Responsabilidades:
  - Buscar documentos anterior y corregido.
  - Comparar versiones de formularios.
  - Generar HTML y PDF de reportes de comparación.
"""

from typing import Any, Dict, List, Optional

from domain.excepciones import (
    DocumentoNoEncontradoError,
    FormularioNoEncontradoError,
    SinPermisoError,
)
from domain.constantes import TIPO_DOCUMENTO_FORMULARIO_PDF
from domain.formulario.tipos import EstadoFormulario
from domain.puertos.repositorios import RepositorioExpediente
from services.expedientes.comparacion_versiones import (
    comparar_versiones,
    comparacion_versiones_a_dict,
)
from services.expedientes.reportes import RendereadorReporteService


class ComparadorService:
    """
    Servicio de comparación de versiones de formularios.

    Responsabilidades:
      - Comparar documentos anterior y corregido.
      - Generar HTML y PDF de reportes de comparación.
    """

    def __init__(
        self,
        repo_expediente: RepositorioExpediente,
        documentos_service,
        rendereador: RendereadorReporteService,
    ) -> None:
        self._repo = repo_expediente
        self._documentos = documentos_service
        self._rendereador = rendereador
        self._estados_expediente = [
            EstadoFormulario.ENVIADO,
            EstadoFormulario.EN_CORRECCION,
            EstadoFormulario.VALIDADO,
            EstadoFormulario.RECHAZADO,
            EstadoFormulario.PENDIENTE_FIRMA,
            EstadoFormulario.FIRMADO,
            EstadoFormulario.CERRADO,
        ]

    def comparar_ultima_correccion(
        self,
        formulario_id: str,
        contrapartes_permitidas: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Compara la última versión de un formulario con su versión anterior."""
        self._buscar_formulario(formulario_id, contrapartes_permitidas)
        documento_corregido = self._documentos.obtener_ultimo_formulario_pdf(formulario_id)
        if not documento_corregido:
            raise DocumentoNoEncontradoError(formulario_id, TIPO_DOCUMENTO_FORMULARIO_PDF)

        documento_anterior = None
        if documento_corregido.version_anterior_id:
            documento_anterior = self._documentos.buscar_documento(
                formulario_id,
                documento_corregido.version_anterior_id,
            )

        comparacion = comparar_versiones(documento_corregido, documento_anterior)
        return comparacion_versiones_a_dict(comparacion)

    def generar_reporte_comparacion_pdf(
        self,
        formulario_id: str,
        contrapartes_permitidas: Optional[List[str]] = None,
    ) -> bytes:
        """Genera un PDF con el reporte de comparación de cambios."""
        formulario = self._buscar_formulario(formulario_id, contrapartes_permitidas)
        comparacion = self.comparar_ultima_correccion(formulario_id, contrapartes_permitidas)
        return self._rendereador.generar_reporte_pdf(formulario, comparacion)

    # ─── Privados ─────────────────────────────────────────────────────────────

    def _buscar_formulario(
        self,
        formulario_id: str,
        contrapartes_permitidas: Optional[List[str]] = None,
    ):
        """Busca un formulario y valida permisos de acceso."""
        formulario = self._repo.obtener(formulario_id, self._estados_expediente)
        if not formulario:
            raise FormularioNoEncontradoError(formulario_id)

        if contrapartes_permitidas is not None and formulario.tipo_contraparte not in contrapartes_permitidas:
            raise SinPermisoError(formulario.tipo_contraparte)

        return formulario
