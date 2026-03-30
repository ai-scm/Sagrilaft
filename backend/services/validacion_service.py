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

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from models import Formulario, ResultadoValidacion
from services.contracts import HallazgoValidacion
from services.document_orchestrator import OrquestadorValidacionDocumentos
from services.lista_cautela_service import ListaCautelaService


class FormularioNoEncontradoError(Exception):
    """Excepción de dominio: el formulario solicitado no existe."""

    def __init__(self, formulario_id: str) -> None:
        self.formulario_id = formulario_id
        super().__init__(f"Formulario '{formulario_id}' no encontrado")


class ValidacionService:
    """
    Orquesta la validación completa de un formulario SAGRILAFT.

    No conoce detalles HTTP: el router traduce FormularioNoEncontradoError → 404.
    Puede ser invocado desde routers, tareas cron o comandos CLI sin duplicar código.
    """

    def __init__(
        self,
        sesion: Session,
        orquestador: OrquestadorValidacionDocumentos,
        servicio_listas: ListaCautelaService,
    ) -> None:
        self._sesion = sesion
        self._orquestador = orquestador
        self._servicio_listas = servicio_listas

    # ── API pública ──────────────────────────────────────────────────────────────

    async def ejecutar_validacion_completa(
        self, formulario_id: str
    ) -> List[ResultadoValidacion]:
        """
        Ejecuta el flujo completo de validación y retorna los resultados persistidos.

        Raises:
            FormularioNoEncontradoError: si el formulario no existe en la BD.
        """
        formulario = self._obtener_o_error(formulario_id)
        self._limpiar_validaciones_previas(formulario_id)

        hallazgos: List[ResultadoValidacion] = []
        hallazgos += await self._validar_documentos(formulario_id, formulario)
        hallazgos += self._validar_listas_cautela(formulario_id, formulario)

        self._sesion.commit()
        for hallazgo in hallazgos:
            self._sesion.refresh(hallazgo)

        return hallazgos

    # ── Helpers de orquestación ──────────────────────────────────────────────────

    def _obtener_o_error(self, formulario_id: str) -> Formulario:
        """Recupera el formulario o lanza FormularioNoEncontradoError."""
        formulario = (
            self._sesion.query(Formulario)
            .filter(Formulario.id == formulario_id)
            .first()
        )
        if not formulario:
            raise FormularioNoEncontradoError(formulario_id)
        return formulario

    def _limpiar_validaciones_previas(self, formulario_id: str) -> None:
        """Elimina todos los resultados de validaciones anteriores del formulario."""
        self._sesion.query(ResultadoValidacion).filter(
            ResultadoValidacion.formulario_id == formulario_id
        ).delete()

    async def _validar_documentos(
        self,
        formulario_id: str,
        formulario: Formulario,
    ) -> List[ResultadoValidacion]:
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

        resultados: List[ResultadoValidacion] = []

        for hallazgo in hallazgos_individuales:
            resultado = self._hallazgo_a_resultado(formulario_id, "documento", hallazgo)
            self._sesion.add(resultado)
            resultados.append(resultado)

        for hallazgo in hallazgos_cruzados:
            resultado = self._hallazgo_a_resultado(formulario_id, "cruce_documentos", hallazgo)
            self._sesion.add(resultado)
            resultados.append(resultado)

        return resultados

    def _validar_listas_cautela(
        self,
        formulario_id: str,
        formulario: Formulario,
    ) -> List[ResultadoValidacion]:
        """
        Busca la empresa y el representante en todas las listas de cautela
        y prepara los resultados para persistir.
        """
        resultados: List[ResultadoValidacion] = []

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
        numero_identificacion: Optional[str],
        sufijo_campo: Optional[str],
    ) -> List[ResultadoValidacion]:
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
        nuevos: List[ResultadoValidacion] = []

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
            self._sesion.add(resultado)
            nuevos.append(resultado)

        return nuevos

    # ── Helpers de transformación ────────────────────────────────────────────────

    @staticmethod
    def _extraer_datos_relevantes(formulario: Formulario) -> Dict[str, Any]:
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
        tipo: str,
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
