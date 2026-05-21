"""
Entidades de dominio del formulario SAGRILAFT.

Una entidad encapsula identidad y comportamiento: sabe en qué estado está
y cómo puede transicionar, lanzando excepciones de dominio si la operación
no es válida según las reglas de negocio.

Sin ORM, sin HTTP, sin frameworks — solo stdlib Python.
Los adaptadores de persistencia (Fase 3) convertirán entre el modelo ORM
y estas entidades.
"""

from __future__ import annotations

from dataclasses import dataclass

from domain.excepciones import FormularioNoEditableError
from domain.formulario.tipos import EstadoFormulario


@dataclass
class FormularioDominio:
    """
    Entidad de dominio que representa un formulario SAGRILAFT.

    Encapsula la máquina de estados y garantiza que solo ocurran
    transiciones válidas según las reglas de negocio.

    Máquina de estados:
        BORRADOR ──────────────────────────────────────────────┐
        EN_CORRECCION ─────── enviar() ──────────────────── ENVIADO
                                                              │
                         ┌── aprobar() ──────────────────── VALIDADO ──┐
                         │   rechazar() ─────────────────── RECHAZADO  │
                         │   devolver_para_correccion() ── EN_CORRECCION
                         │                                  (ciclo)
                         └── iniciar_firma() ────── PENDIENTE_FIRMA
                                                        │
                              completar_firma() ──── FIRMADO
                              cancelar_firma()  ──── VALIDADO (retorno)
    """

    id: str
    estado: EstadoFormulario
    numero_correccion: int = 0

    # ── Predicados ─────────────────────────────────────────────────────────────

    def es_borrador(self) -> bool:
        return self.estado == EstadoFormulario.BORRADOR

    def es_editable(self) -> bool:
        """True si la contraparte puede modificar y reenviar el formulario."""
        return self.estado in (EstadoFormulario.BORRADOR, EstadoFormulario.EN_CORRECCION)

    # ── Transiciones ───────────────────────────────────────────────────────────

    def enviar(self) -> None:
        """BORRADOR | EN_CORRECCION → ENVIADO."""
        if not self.es_editable():
            raise FormularioNoEditableError(
                f"El formulario debe estar en estado 'borrador' o 'en_correccion' "
                f"para enviarse (estado actual: '{self.estado.value}')."
            )
        self.estado = EstadoFormulario.ENVIADO

    def aprobar(self) -> None:
        """ENVIADO → VALIDADO."""
        if self.estado != EstadoFormulario.ENVIADO:
            raise FormularioNoEditableError(
                f"Solo se puede aprobar un formulario en estado 'enviado' "
                f"(actual: '{self.estado.value}')."
            )
        self.estado = EstadoFormulario.VALIDADO

    def rechazar(self) -> None:
        """ENVIADO | VALIDADO → RECHAZADO."""
        if self.estado not in (EstadoFormulario.ENVIADO, EstadoFormulario.VALIDADO):
            raise FormularioNoEditableError(
                f"Solo se puede rechazar un formulario en estado 'enviado' o 'validado' "
                f"(actual: '{self.estado.value}')."
            )
        self.estado = EstadoFormulario.RECHAZADO

    def devolver_para_correccion(self) -> None:
        """ENVIADO | VALIDADO → EN_CORRECCION. Incrementa numero_correccion."""
        _DEVOLVIBLES = {EstadoFormulario.ENVIADO, EstadoFormulario.VALIDADO}
        if self.estado not in _DEVOLVIBLES:
            raise FormularioNoEditableError(
                f"Solo se puede devolver un formulario en estado 'enviado' o 'validado' "
                f"(actual: '{self.estado.value}')."
            )
        self.estado = EstadoFormulario.EN_CORRECCION
        self.numero_correccion += 1

    def iniciar_firma(self) -> None:
        """VALIDADO → PENDIENTE_FIRMA."""
        if self.estado != EstadoFormulario.VALIDADO:
            raise FormularioNoEditableError(
                f"El formulario debe estar en estado 'validado' para enviarse a firma "
                f"(estado actual: '{self.estado.value}')."
            )
        self.estado = EstadoFormulario.PENDIENTE_FIRMA

    def completar_firma(self) -> None:
        """PENDIENTE_FIRMA → FIRMADO. Idempotente si ya está FIRMADO (webhook duplicado)."""
        if self.estado == EstadoFormulario.FIRMADO:
            return
        if self.estado != EstadoFormulario.PENDIENTE_FIRMA:
            raise FormularioNoEditableError(
                f"Solo se puede completar la firma cuando el formulario está en estado "
                f"'pendiente_firma' (estado actual: '{self.estado.value}')."
            )
        self.estado = EstadoFormulario.FIRMADO

    def cancelar_firma(self) -> None:
        """PENDIENTE_FIRMA → VALIDADO."""
        if self.estado != EstadoFormulario.PENDIENTE_FIRMA:
            raise FormularioNoEditableError(
                f"Solo se puede cancelar la firma cuando el formulario está en estado "
                f"'pendiente_firma' (estado actual: '{self.estado.value}')."
            )
        self.estado = EstadoFormulario.VALIDADO
