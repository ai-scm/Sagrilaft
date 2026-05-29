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

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from domain.contratos import DocumentoDatos
from domain.excepciones import FormularioNoEditableError
from domain.formulario.tipos import EstadoFormulario


@dataclass
class FormularioDatos:
    """
    Snapshot de todos los datos de un formulario SAGRILAFT.

    Entidad de dominio libre de SQLAlchemy — reemplaza el modelo ORM Formulario
    en la capa de aplicación. Los repositorios hacen el mapping internamente.

    Los campos JSON (junta_directiva, accionistas, etc.) se entregan ya
    deserializados como listas Python. Los campos documentos/validaciones solo
    se populan cuando se necesita snapshot completo (obtener_por_codigo).
    """

    # ── Identificadores (siempre presentes) ───────────────────────────────────
    id: str
    codigo_peticion: str
    estado: str
    numero_correccion: int = 0

    # ── Metadata ──────────────────────────────────────────────────────────────
    pagina_actual: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    # ── Clasificación ─────────────────────────────────────────────────────────
    tipo_contraparte: Optional[str] = None
    tipo_persona: Optional[str] = None
    tipo_solicitud: Optional[str] = None
    clasificacion_actividad: Optional[str] = None

    # ── Información Básica ────────────────────────────────────────────────────
    razon_social: Optional[str] = None
    tipo_identificacion: Optional[str] = None
    numero_identificacion: Optional[str] = None
    digito_verificacion: Optional[str] = None
    direccion: Optional[str] = None
    pais: Optional[str] = None
    departamento: Optional[str] = None
    ciudad: Optional[str] = None
    telefono: Optional[str] = None
    fax: Optional[str] = None
    correo: Optional[str] = None
    codigo_ica: Optional[str] = None
    pagina_web: Optional[str] = None

    # ── Representante Legal ───────────────────────────────────────────────────
    nombre_representante: Optional[str] = None
    tipo_doc_representante: Optional[str] = None
    numero_doc_representante: Optional[str] = None
    fecha_expedicion: Optional[str] = None
    ciudad_expedicion: Optional[str] = None
    nacionalidad: Optional[str] = None
    fecha_nacimiento: Optional[str] = None
    ciudad_nacimiento: Optional[str] = None
    profesion: Optional[str] = None
    correo_representante: Optional[str] = None
    telefono_representante: Optional[str] = None
    direccion_funciones: Optional[str] = None
    pais_funciones: Optional[str] = None
    departamento_funciones: Optional[str] = None
    ciudad_funciones: Optional[str] = None
    direccion_residencia: Optional[str] = None
    ciudad_residencia: Optional[str] = None

    # ── Información Financiera ────────────────────────────────────────────────
    actividad_economica: Optional[str] = None
    codigo_ciiu: Optional[str] = None
    ingresos_mensuales: Optional[float] = None
    otros_ingresos: Optional[float] = None
    egresos_mensuales: Optional[float] = None
    total_activos: Optional[float] = None
    total_pasivos: Optional[float] = None
    patrimonio: Optional[float] = None

    # ── Moneda Extranjera ─────────────────────────────────────────────────────
    realiza_operaciones_moneda_extranjera: Optional[str] = None
    paises_operaciones: Optional[str] = None
    tipos_transaccion: Optional[Any] = None          # lista Python (ya deserializada)
    tipos_transaccion_otros: Optional[str] = None

    # ── Clasificación Tributaria ──────────────────────────────────────────────
    actividad_clasificacion: Optional[str] = None
    actividad_especifica: Optional[str] = None
    sector: Optional[str] = None
    superintendencia: Optional[str] = None
    responsabilidades_renta: Optional[str] = None
    autorretenedor: Optional[str] = None
    responsabilidades_iva: Optional[str] = None
    regimen_iva: Optional[str] = None
    gran_contribuyente: Optional[str] = None
    entidad_sin_animo_lucro: Optional[str] = None
    retencion_ica: Optional[str] = None
    impuesto_ica: Optional[str] = None
    entidad_oficial: Optional[str] = None
    exento_retencion_fuente: Optional[str] = None

    # ── Contactos ─────────────────────────────────────────────────────────────
    contacto_ordenes_nombre: Optional[str] = None
    contacto_ordenes_cargo: Optional[str] = None
    contacto_ordenes_telefono: Optional[str] = None
    contacto_ordenes_correo: Optional[str] = None
    contacto_pagos_nombre: Optional[str] = None
    contacto_pagos_cargo: Optional[str] = None
    contacto_pagos_telefono: Optional[str] = None
    contacto_pagos_correo: Optional[str] = None

    # ── Autorizaciones ────────────────────────────────────────────────────────
    autorizacion_datos: Optional[bool] = None
    declaracion_origen_fondos: Optional[bool] = None
    origen_fondos: Optional[str] = None

    # ── Firma ─────────────────────────────────────────────────────────────────
    dia_firma: Optional[int] = None
    mes_firma: Optional[int] = None
    year_firma: Optional[int] = None
    ciudad_firma: Optional[str] = None

    # ── Corrección ────────────────────────────────────────────────────────────
    campos_a_corregir: Optional[str] = None

    # ── ZohoSign ──────────────────────────────────────────────────────────────
    zoho_request_id: Optional[str] = None
    ruta_documento_firmado: Optional[str] = None

    # ── Campos dinámicos JSON (ya deserializados como listas Python) ──────────
    junta_directiva: Optional[Any] = None
    accionistas: Optional[Any] = None
    beneficiario_final: Optional[Any] = None
    referencias_comerciales: Optional[Any] = None
    referencias_bancarias: Optional[Any] = None
    informacion_bancaria_pagos: Optional[Any] = None
    clasificaciones: Optional[Any] = None

    # ── Relaciones (populadas solo en snapshot completo) ──────────────────────
    documentos: List[DocumentoDatos] = field(default_factory=list)
    validaciones: List[Dict[str, Any]] = field(default_factory=list)


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

    # ── Factory ────────────────────────────────────────────────────────────────

    @classmethod
    def desde_snapshot(cls, datos: "FormularioDatos") -> "FormularioDominio":
        """Construye la entidad rica desde un snapshot de persistencia."""
        return cls(
            id=datos.id,
            estado=EstadoFormulario(datos.estado),
            numero_correccion=datos.numero_correccion or 0,
        )

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
