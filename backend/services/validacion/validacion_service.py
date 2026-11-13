"""
Servicio de validación de formularios SAGRILAFT.

Orquesta la validación completa desacoplada de la capa HTTP:
  1. Contraste de documentos adjuntos vs datos diligenciados (vía IA).
  Las consultas de listas se ejecutan por separado mediante el servicio común v2.

SRP: cada método privado tiene una responsabilidad única y delimitada.
OCP: agregar nuevos tipos de validación no requiere modificar ejecutar_validacion_completa.
DIP: depende del orquestador y del servicio de listas vía sus interfaces,
     y no conoce ningún detalle HTTP (sin HTTPException, sin Request).
"""

from typing import Any

from domain.contratos import HallazgoValidacion
from domain.puertos.repositorios import RepositorioValidacion
from domain.validacion.resultado import ResultadoValidacionDominio
from domain.excepciones import FormularioNoEncontradoError
from services.validacion.orquestador import OrquestadorValidacionDocumentos


class ValidacionService:
    """
    Orquesta la validación completa de un formulario SAGRILAFT.

    No conoce detalles HTTP: el router traduce FormularioNoEncontradoError → 404.
    Puede ser invocado desde routers, tareas cron o comandos CLI sin duplicar código.
    """

    def __init__(
        self,
        repo: RepositorioValidacion,
        orquestador: OrquestadorValidacionDocumentos,
    ) -> None:
        self._repo = repo
        self._orquestador = orquestador

    # ── API pública ──────────────────────────────────────────────────────────────

    async def ejecutar_validacion_completa(
        self, formulario_id: str
    ) -> list[ResultadoValidacionDominio]:
        """
        Ejecuta el flujo completo de validación y retorna los resultados persistidos.

        Raises:
            FormularioNoEncontradoError: si el formulario no existe en la BD.
        """
        formulario = self._obtener_o_error(formulario_id)
        self._limpiar_validaciones_previas(formulario_id)

        datos_validaciones: list[dict[str, Any]] = []
        datos_validaciones += await self._validar_documentos(formulario_id, formulario)

        return self._repo.guardar_validaciones(datos_validaciones)

    # ── Helpers de orquestación ──────────────────────────────────────────────────

    def _obtener_o_error(self, formulario_id: str):
        formulario = self._repo.obtener_formulario(formulario_id)
        if not formulario:
            raise FormularioNoEncontradoError(formulario_id)
        return formulario

    def _limpiar_validaciones_previas(self, formulario_id: str) -> None:
        self._repo.limpiar_validaciones(formulario_id)

    async def _validar_documentos(
        self,
        formulario_id: str,
        formulario,
    ) -> list[dict[str, Any]]:
        """
        Valida los documentos adjuntos vía IA y prepara los datos para persistir.

        Retorna dicts listos para pasar a guardar_validaciones.
        """
        datos_formulario = self._extraer_datos_relevantes(formulario)
        lista_documentos = [
            {"ruta_archivo": doc.ruta_archivo, "tipo_documento": doc.tipo_documento}
            for doc in formulario.documentos
        ]

        hallazgos_individuales, hallazgos_cruzados = (
            await self._orquestador.validar_todos_documentos(
                documentos=lista_documentos,
                datos_formulario=datos_formulario,
            )
        )

        datos: list[dict[str, Any]] = []
        for tipo, grupo in [
            ("documento",        hallazgos_individuales),
            ("cruce_documentos", hallazgos_cruzados),
        ]:
            for hallazgo in grupo:
                datos.append(self._hallazgo_a_datos(formulario_id, tipo, hallazgo))

        return datos

    # ── Helpers de transformación ────────────────────────────────────────────────

    @staticmethod
    def _extraer_datos_relevantes(formulario) -> dict[str, Any]:
        return {
            "razon_social":             formulario.razon_social,
            "numero_identificacion":    formulario.numero_identificacion,
            "nombre_representante":     formulario.nombre_representante,
            "numero_doc_representante": formulario.numero_doc_representante,
            "total_activos":            formulario.total_activos,
            "total_pasivos":            formulario.total_pasivos,
            "patrimonio":               formulario.patrimonio,
            "ingresos_mensuales":       formulario.ingresos_mensuales,
            "egresos_mensuales":        formulario.egresos_mensuales,
            "codigo_ciiu":              formulario.codigo_ciiu,
        }

    @staticmethod
    def _hallazgo_a_datos(
        formulario_id: str,
        tipo: str,
        hallazgo: HallazgoValidacion,
    ) -> dict[str, Any]:
        return {
            "formulario_id":    formulario_id,
            "tipo":             tipo,
            "campo":            hallazgo.campo,
            "resultado":        hallazgo.resultado,
            "detalle":          hallazgo.detalle,
            "valor_formulario": hallazgo.valor_formulario,
            "valor_documento":  hallazgo.valor_documento,
        }
