"""
Servicio de validación de formularios SAGRILAFT.

Orquesta la validación completa desacoplada de la capa HTTP:
  1. Contraste de documentos adjuntos vs datos diligenciados (vía IA).
  2. Búsqueda en listas de cautela para la empresa y el representante legal.

SRP: cada método privado tiene una responsabilidad única y delimitada.
OCP: agregar nuevos tipos de validación no requiere modificar ejecutar_validacion_completa.
DIP: depende del orquestador y del servicio de listas vía sus interfaces,
     y no conoce ningún detalle HTTP (sin HTTPException, sin Request).
"""

from typing import Any, Literal

from infrastructure.persistencia.models import ResultadoValidacion
from core.contratos import HallazgoValidacion
from domain.puertos.repositorios import RepositorioValidacion
from services.validacion.orquestador import OrquestadorValidacionDocumentos
from services.listas.servicio_listas_cautela import ListaCautelaService
from domain.excepciones import FormularioNoEncontradoError


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
        servicio_listas: ListaCautelaService,
    ) -> None:
        self._repo = repo
        self._orquestador = orquestador
        self._servicio_listas = servicio_listas

    # ── API pública ──────────────────────────────────────────────────────────────

    async def ejecutar_validacion_completa(
        self, formulario_id: str
    ) -> list[ResultadoValidacion]:
        """
        Ejecuta el flujo completo de validación y retorna los resultados persistidos.

        Raises:
            FormularioNoEncontradoError: si el formulario no existe en la BD.
        """
        formulario = self._obtener_o_error(formulario_id)
        self._limpiar_validaciones_previas(formulario_id)

        resultados: list[ResultadoValidacion] = []
        resultados += await self._validar_documentos(formulario_id, formulario)
        resultados += self._validar_listas_cautela(formulario_id, formulario)

        self._repo.confirmar()
        for resultado in resultados:
            self._repo.refrescar(resultado)

        return resultados

    # ── Helpers de orquestación ──────────────────────────────────────────────────

    def _obtener_o_error(self, formulario_id: str):
        """Recupera el formulario o lanza FormularioNoEncontradoError."""
        formulario = self._repo.obtener_formulario(formulario_id)
        if not formulario:
            raise FormularioNoEncontradoError(formulario_id)
        return formulario

    def _limpiar_validaciones_previas(self, formulario_id: str) -> None:
        """Elimina todos los resultados de validaciones anteriores del formulario."""
        self._repo.limpiar_validaciones(formulario_id)

    async def _validar_documentos(
        self,
        formulario_id: str,
        formulario,
    ) -> list[ResultadoValidacion]:
        """
        Valida los documentos adjuntos vía IA y prepara los hallazgos para persistir.

        Retorna los ResultadoValidacion añadidos a sesión (sin commit, para atomicidad).
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

        resultados: list[ResultadoValidacion] = []

        for tipo, grupo in [
            ("documento",        hallazgos_individuales),
            ("cruce_documentos", hallazgos_cruzados),
        ]:
            for hallazgo in grupo:
                resultado = self._hallazgo_a_resultado(formulario_id, tipo, hallazgo)
                self._repo.agregar_validacion(resultado)
                resultados.append(resultado)

        return resultados

    def _validar_listas_cautela(
        self,
        formulario_id: str,
        formulario,
    ) -> list[ResultadoValidacion]:
        """
        Busca la empresa y el representante en todas las listas de cautela
        y prepara los resultados para persistir.
        """
        resultados: list[ResultadoValidacion] = []

        if formulario.razon_social:
            resultados += self._registrar_busqueda_en_listas(
                formulario_id=formulario_id,
                nombre=formulario.razon_social,
                numero_identificacion=formulario.numero_identificacion,
                sufijo_campo=None,
            )

        if formulario.nombre_representante:
            resultados += self._registrar_busqueda_en_listas(
                formulario_id=formulario_id,
                nombre=formulario.nombre_representante,
                numero_identificacion=formulario.numero_doc_representante,
                sufijo_campo="(Rep. Legal)",
            )

        return resultados

    def _registrar_busqueda_en_listas(
        self,
        formulario_id: str,
        nombre: str,
        numero_identificacion: str | None,
        sufijo_campo: str | None,
    ) -> list[ResultadoValidacion]:
        """
        Ejecuta la búsqueda en listas de cautela para un sujeto y registra
        cada resultado en la sesión.

        Args:
            sufijo_campo: Texto para distinguir empresa de representante en el
                          nombre del campo (ej. "(Rep. Legal)"). None para empresa.
        """
        resultados_listas = self._servicio_listas.buscar_todas_listas(
            nombre, numero_identificacion
        )
        resultados: list[ResultadoValidacion] = []

        for resultado_lista in resultados_listas:
            nombre_campo = (
                f"{resultado_lista.lista} {sufijo_campo}"
                if sufijo_campo
                else resultado_lista.lista
            )
            resultado = ResultadoValidacion(
                formulario_id=formulario_id,
                tipo="lista_cautela",
                campo=nombre_campo,
                resultado="error" if resultado_lista.encontrado else "ok",
                detalle=resultado_lista.detalle,
            )
            self._repo.agregar_validacion(resultado)
            resultados.append(resultado)

        return resultados

    # ── Helpers de transformación ────────────────────────────────────────────────

    @staticmethod
    def _extraer_datos_relevantes(formulario) -> dict[str, Any]:
        """Extrae los campos del formulario necesarios para la validación documental."""
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
    def _hallazgo_a_resultado(
        formulario_id: str,
        tipo: Literal["documento", "cruce_documentos"],
        hallazgo: HallazgoValidacion,
    ) -> ResultadoValidacion:
        """Convierte un HallazgoValidacion en un ResultadoValidacion persistible en BD."""
        return ResultadoValidacion(
            formulario_id=formulario_id,
            tipo=tipo,
            campo=hallazgo.campo,
            resultado=hallazgo.resultado,
            detalle=hallazgo.detalle,
            valor_formulario=hallazgo.valor_formulario,
            valor_documento=hallazgo.valor_documento,
        )

