"""
Validador de campos requeridos para envío de formulario.
"""

import json
import re
from typing import Any, Callable, List, Optional, Tuple

from domain.constantes import PORCENTAJE_MAXIMO_PERMITIDO
from domain.contratos import ErrorCampoFormulario
from domain.formulario.entidades import FormularioDatos

_REGEX_TELEFONO = re.compile(r'^\d{10}$')
_REGEX_CORREO   = re.compile(r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$')
UMBRAL_MINIMO_PARTICIPACION_ACCIONISTA   = 5
UMBRAL_MINIMO_CONTROL_BENEFICIARIO_FINAL = 25

def _esta_vacio(valor: Any) -> bool:
    """Fuente única de verdad para detectar un campo sin diligenciar."""
    return valor is None or (isinstance(valor, str) and not valor.strip())


ErrorValidacion = ErrorCampoFormulario


class ValidadorEnvioFormulario:
    """
    Verifica que el formulario tenga todos los campos obligatorios diligenciados
    antes de permitir el envío final.

    SOLID-S: única responsabilidad — validar la completitud del formulario.
    SOLID-O: agregar o quitar campos solo modifica las listas _CAMPOS_*.
    """

    # ── Declaraciones de campos requeridos ────────────────────────────────────

    _CAMPOS_REQUERIDOS: List[Tuple[str, str]] = [
        ("tipo_contraparte",        "Tipo de Contraparte"),
        ("tipo_persona",            "Tipo de Persona"),
        ("tipo_solicitud",          "Tipo de Solicitud"),
        ("clasificacion_actividad", "Clasificación de Actividad"),
        ("razon_social",            "Nombre o Razón Social"),
        ("tipo_identificacion",     "Tipo de Identificación"),
        ("numero_identificacion",   "Número de Identificación"),
        ("digito_verificacion",     "Dígito de Verificación (DV)"),
        ("direccion",               "Dirección"),
        ("departamento",            "Departamento"),
        ("ciudad",                  "Ciudad"),
        ("telefono",                "Teléfono"),
        ("fax",                     "Fax"),
        ("correo",                  "Correo Electrónico"),
        ("pagina_web",              "Página Web"),
        ("nombre_representante",    "Nombres y Apellidos del Representante"),
        ("tipo_doc_representante",  "Tipo de Documento del Representante"),
        ("numero_doc_representante","Número de Documento del Representante"),
        ("fecha_expedicion",        "Fecha de Expedición"),
        ("ciudad_expedicion",       "Ciudad de Expedición"),
        ("nacionalidad",            "Nacionalidad"),
        ("fecha_nacimiento",        "Fecha de Nacimiento"),
        ("ciudad_nacimiento",       "Ciudad de Nacimiento"),
        ("profesion",               "Profesión"),
        ("correo_representante",    "Correo del Representante"),
        ("telefono_representante",  "Teléfono del Representante"),
        ("direccion_funciones",     "Dirección donde ejerce funciones"),
        ("pais_funciones",          "País donde ejerce funciones"),
        ("departamento_funciones",  "Departamento donde ejerce funciones"),
        ("ciudad_funciones",        "Ciudad donde ejerce funciones"),
        ("actividad_economica",     "Actividad Económica Principal"),
        ("codigo_ciiu",             "Código CIIU"),
        ("ingresos_mensuales",      "Ingresos Mensuales"),
        ("egresos_mensuales",       "Egresos Mensuales"),
        ("total_activos",           "Total Activos"),
        ("total_pasivos",           "Total Pasivos"),
        ("patrimonio",              "Patrimonio"),
        ("realiza_operaciones_moneda_extranjera", "¿Realiza Operaciones en Moneda Extranjera?"),
        ("contacto_ordenes_nombre",   "Nombre (Órdenes de Compra)"),
        ("contacto_ordenes_cargo",    "Cargo (Órdenes de Compra)"),
        ("contacto_ordenes_telefono", "Teléfono (Órdenes de Compra)"),
        ("contacto_ordenes_correo",   "Correo (Órdenes de Compra)"),
        ("contacto_pagos_nombre",     "Nombre (Reportes de Pago)"),
        ("contacto_pagos_cargo",      "Cargo (Reportes de Pago)"),
        ("contacto_pagos_telefono",   "Teléfono (Reportes de Pago)"),
        ("contacto_pagos_correo",     "Correo (Reportes de Pago)"),
        ("origen_fondos",  "Origen de Fondos"),
        ("dia_firma",      "Día de Firma"),
        ("mes_firma",      "Mes de Firma"),
        ("year_firma",     "Año de Firma"),
        ("ciudad_firma",   "Ciudad de Firma"),
    ]

    _CAMPOS_PERSONA_NATURAL: List[Tuple[str, str]] = [
        ('direccion_residencia', "Dirección de Residencia"),
        ('ciudad_residencia', "Ciudad de Residencia"),
    ]

    _CAMPOS_CLASIFICACION_JURIDICA: List[Tuple[str, str]] = [
        ("actividad_clasificacion", "Actividad"),
        ("actividad_especifica",    "¿Cuál? Especifique"),
        ("sector",                  "Sector"),
        ("superintendencia",        "Vigilado por la Superintendencia de"),
        ("responsabilidades_renta", "Responsabilidades Impuesto sobre la Renta"),
        ("autorretenedor",          "Autorretenedor"),
        ("responsabilidades_iva",   "Responsabilidades en el IVA"),
        ("regimen_iva",             "Régimen IVA"),
        ("gran_contribuyente",      "¿Es Gran Contribuyente?"),
        ("entidad_sin_animo_lucro", "Entidad sin Ánimo de Lucro"),
        ("retencion_ica",           "Retención de Industria y Comercio"),
        ("impuesto_ica",            "Impuesto de Industria y Comercio"),
        ("entidad_oficial",         "Entidad Oficial"),
        ("exento_retencion_fuente", "Exento de Retención en la Fuente"),
    ]

    _CAMPOS_FORMATO_TELEFONO: List[Tuple[str, str]] = [
        ("telefono",                  "Teléfono"),
        ("telefono_representante",    "Teléfono del Representante"),
        ("contacto_ordenes_telefono", "Teléfono (Órdenes de Compra)"),
        ("contacto_pagos_telefono",   "Teléfono (Reportes de Pago)"),
    ]

    _CAMPOS_FORMATO_CORREO: List[Tuple[str, str]] = [
        ("correo",                  "Correo Electrónico"),
        ("correo_representante",    "Correo del Representante"),
        ("contacto_ordenes_correo", "Correo (Órdenes de Compra)"),
        ("contacto_pagos_correo",   "Correo (Reportes de Pago)"),
    ]

    _CAMPOS_JUNTA: List[Tuple[str, str]] = [
        ("cargo",     "Cargo"),
        ("nombre",    "Nombre"),
        ("tipo_id",   "Tipo ID"),
        ("numero_id", "Número ID"),
        ("es_pep",    "¿PEP?"),
    ]

    _CAMPOS_ACCIONISTA: List[Tuple[str, str]] = [
        ("nombre",     "Nombre"),
        ("porcentaje", "% Participación"),
        ("tipo_id",    "Tipo ID"),
        ("numero_id",  "Número ID"),
        ("es_pep",     "¿PEP?"),
    ]

    _CAMPOS_BENEFICIARIO: List[Tuple[str, str]] = [
        ("nombre",     "Nombre"),
        ("porcentaje", "% Control"),
        ("tipo_id",    "Tipo ID"),
        ("numero_id",  "Número ID"),
        ("es_pep",     "¿PEP?"),
    ]

    # ── Orquestador principal ─────────────────────────────────────────────────

    def validar(self, formulario: FormularioDatos) -> List[ErrorValidacion]:
        """
        Valida que todos los campos requeridos estén diligenciados y que
        las declaraciones obligatorias estén aceptadas.

        Returns:
            Lista de ErrorValidacion. Vacía si el formulario está completo.
        """
        errores = self._errores_presencia(formulario, self._CAMPOS_REQUERIDOS)

        if not formulario.autorizacion_datos:
            errores.append(ErrorValidacion(
                campo="autorizacion_datos",
                mensaje="Debe aceptar la autorización de tratamiento de datos",
            ))
        if not formulario.declaracion_origen_fondos:
            errores.append(ErrorValidacion(
                campo="declaracion_origen_fondos",
                mensaje="Debe aceptar la declaración de origen de fondos",
            ))

        errores.extend(self._validar_campos_moneda_extranjera(formulario))
        errores.extend(self._validar_campos_fecha_firma(formulario))
        errores.extend(self._validar_formatos(formulario))

        if not self._es_persona_juridica(formulario):
            errores.extend(self._validar_campos_persona_natural(formulario))

        if self._es_persona_juridica(formulario):
            errores.extend(self._validar_clasificacion_tributaria(formulario))
            errores.extend(self._validar_junta_directiva(formulario))
            errores.extend(self._validar_accionistas(formulario))
            errores.extend(self._validar_beneficiarios(formulario))

        return errores

    # ── Validadores por sección ───────────────────────────────────────────────

    def _validar_campos_persona_natural(self, formulario: FormularioDatos) -> List[ErrorValidacion]:
        return self._errores_presencia(formulario, self._CAMPOS_PERSONA_NATURAL)

    def _validar_clasificacion_tributaria(self, formulario: FormularioDatos) -> List[ErrorValidacion]:
        return self._errores_presencia(formulario, self._CAMPOS_CLASIFICACION_JURIDICA)

    def _validar_campos_fecha_firma(self, formulario: FormularioDatos) -> List[ErrorValidacion]:
        """Valida rangos de día (1-31), mes (1-12) y año (2000-2100) de la firma."""
        errores: List[ErrorValidacion] = []

        dia = formulario.dia_firma
        if dia is not None and not (1 <= int(dia) <= 31):
            errores.append(ErrorValidacion(
                campo="dia_firma",
                mensaje="El día de la firma debe estar entre 1 y 31",
            ))

        mes = formulario.mes_firma
        if mes is not None and not (1 <= int(mes) <= 12):
            errores.append(ErrorValidacion(
                campo="mes_firma",
                mensaje="El mes de la firma debe estar entre 1 y 12",
            ))

        year = formulario.year_firma
        if year is not None and not (2000 <= int(year) <= 2100):
            errores.append(ErrorValidacion(
                campo="year_firma",
                mensaje="El año de la firma debe estar entre 2000 y 2100",
            ))

        return errores

    def _validar_campos_moneda_extranjera(self, formulario: FormularioDatos) -> List[ErrorValidacion]:
        """
        Valida los campos condicionales de operaciones en moneda extranjera.
        Solo se evalúan cuando la empresa declara que sí realiza este tipo de operaciones.
        Espejar aquí las reglas del frontend garantiza que la BD nunca reciba datos inconsistentes.
        """
        if not self._realiza_operaciones_en_moneda_extranjera(formulario):
            return []

        errores: List[ErrorValidacion] = []

        if _esta_vacio(formulario.paises_operaciones):
            errores.append(ErrorValidacion(
                campo="paises_operaciones",
                mensaje="El campo 'Países en los que realiza operaciones' es obligatorio",
            ))

        tipos = self._deserializar_lista(formulario.tipos_transaccion)
        if "otras" in tipos and _esta_vacio(formulario.tipos_transaccion_otros):
            errores.append(ErrorValidacion(
                campo="tipos_transaccion_otros",
                mensaje="El campo '¿Cuáles?' es obligatorio cuando selecciona 'Otras'",
            ))

        return errores

    def _validar_formatos(self, formulario: FormularioDatos) -> List[ErrorValidacion]:
        """
        Valida que teléfonos y correos tengan el formato correcto.
        Solo corre en envío final — los borradores aceptan valores parciales.
        """
        errores = [
            *self._errores_formato(
                formulario, self._CAMPOS_FORMATO_TELEFONO, _REGEX_TELEFONO,
                "El campo '{nombre}' debe tener exactamente 10 dígitos numéricos",
            ),
            *self._errores_formato(
                formulario, self._CAMPOS_FORMATO_CORREO, _REGEX_CORREO,
                "El campo '{nombre}' debe ser un correo electrónico válido (ej: nombre@dominio.com)",
            ),
        ]

        for i, fila in enumerate(self._deserializar_lista(formulario.referencias_comerciales)):
            tel = str(fila.get("telefono") or "").strip()
            if tel and not _REGEX_TELEFONO.match(tel):
                errores.append(ErrorValidacion(
                    campo=f"referencias_comerciales[{i}].telefono",
                    mensaje=f"El teléfono de la referencia comercial {i + 1} debe tener exactamente 10 dígitos numéricos",
                ))

        return errores

    def _validar_junta_directiva(self, formulario: FormularioDatos) -> List[ErrorValidacion]:
        filas = self._deserializar_lista(formulario.junta_directiva)
        return self._validar_filas_tabla(
            filas, "Junta Directiva y Representantes", "junta_directiva", self._CAMPOS_JUNTA,
        )

    def _validar_accionistas(self, formulario: FormularioDatos) -> List[ErrorValidacion]:
        filas = self._deserializar_lista(formulario.accionistas)
        errores = self._validar_filas_tabla(
            filas, "Composición Accionaria", "accionistas",
            self._CAMPOS_ACCIONISTA,
            [self._crear_regla_porcentaje("accionistas", UMBRAL_MINIMO_PARTICIPACION_ACCIONISTA, "El accionista", "participación")],
        )
        error_total = self._error_porcentaje_excedido(
            self._sumar_porcentajes(filas),
            "accionistas.porcentaje_total",
            "participaciones accionarias",
        )
        if error_total:
            errores.append(error_total)
        return errores

    def _validar_beneficiarios(self, formulario: FormularioDatos) -> List[ErrorValidacion]:
        filas = self._deserializar_lista(formulario.beneficiario_final)
        errores = self._validar_filas_tabla(
            filas, "Beneficiario Final", "beneficiario_final",
            self._CAMPOS_BENEFICIARIO,
            [
                self._crear_regla_porcentaje("beneficiario_final", UMBRAL_MINIMO_CONTROL_BENEFICIARIO_FINAL, "El beneficiario", "control")
            ],
        )
        error_total = self._error_porcentaje_excedido(
            self._sumar_porcentajes(filas),
            "beneficiario_final.porcentaje_total",
            "porcentajes de control",
        )
        if error_total:
            errores.append(error_total)
        return errores

    # ── Helpers de presencia ──────────────────────────────────────────────────

    @staticmethod
    def _errores_presencia(
        formulario: FormularioDatos, campos: List[Tuple[str, str]]
    ) -> List[ErrorValidacion]:
        return [
            ErrorValidacion(campo=campo, mensaje=f"El campo '{nombre}' es obligatorio")
            for campo, nombre in campos
            if _esta_vacio(getattr(formulario, campo, None))
        ]

    # ── Helpers de formato ────────────────────────────────────────────────────

    @staticmethod
    def _errores_formato(
        formulario: FormularioDatos,
        campos: List[Tuple[str, str]],
        regex: re.Pattern,
        mensaje: str,
    ) -> List[ErrorValidacion]:
        errores = []
        for campo, nombre in campos:
            valor = str(getattr(formulario, campo, None) or "").strip()
            if valor and not regex.match(valor):
                errores.append(ErrorValidacion(campo=campo, mensaje=mensaje.format(nombre=nombre)))
        return errores

    # ── Helpers de porcentaje ─────────────────────────────────────────────────

    @staticmethod
    def _crear_regla_porcentaje(
        campo_base: str,
        umbral_minimo: float,
        etiqueta_entidad: str,
        nombre_porcentaje: str,
    ) -> Callable[[int, dict], Optional[ErrorValidacion]]:
        """Fábrica de reglas de validación de porcentaje para tablas dinámicas."""
        def regla(i: int, fila: dict) -> Optional[ErrorValidacion]:
            raw = fila.get("porcentaje")
            if raw is None or not str(raw).strip():
                return None
            try:
                valor = float(raw)
            except (ValueError, TypeError):
                return None
            nombre = fila.get("nombre") or f"fila {i + 1}"
            if valor <= umbral_minimo:
                return ErrorValidacion(
                    campo=f"{campo_base}[{i}].porcentaje",
                    mensaje=f"{etiqueta_entidad} '{nombre}' debe tener {nombre_porcentaje} mayor al {umbral_minimo:.0f}%",
                )
            if valor >= PORCENTAJE_MAXIMO_PERMITIDO:
                return ErrorValidacion(
                    campo=f"{campo_base}[{i}].porcentaje",
                    mensaje=f"{etiqueta_entidad} '{nombre}' no puede tener {nombre_porcentaje} del {PORCENTAJE_MAXIMO_PERMITIDO}% o superior",
                )
            return None
        return regla

    @staticmethod
    def _sumar_porcentajes(filas: List[dict]) -> float:
        total = 0.0
        for fila in filas:
            try:
                total += float(fila.get("porcentaje") or 0)
            except (ValueError, TypeError):
                pass
        return total

    @staticmethod
    def _error_porcentaje_excedido(
        total: float, campo: str, descripcion: str
    ) -> Optional[ErrorValidacion]:
        if total > PORCENTAJE_MAXIMO_PERMITIDO:
            return ErrorValidacion(
                campo=campo,
                mensaje=f"La suma de {descripcion} es {total:.2f}%, lo que excede el {PORCENTAJE_MAXIMO_PERMITIDO}% permitido",
            )
        return None
    
    # ── Helpers de estado del formulario ─────────────────────────────────────

    @staticmethod
    def _es_persona_juridica(formulario: FormularioDatos) -> bool:
        """
        Determina si el formulario corresponde a una Persona Jurídica.
        Centralizar esta guarda evita repetir la comparación de string
        y hace explícita la regla de negocio en el dominio.
        """
        return (formulario.tipo_persona or "").lower() == "juridica"

    @staticmethod
    def _realiza_operaciones_en_moneda_extranjera(formulario: FormularioDatos) -> bool:
        return (formulario.realiza_operaciones_moneda_extranjera or "").lower() == "si"

    # ── Helpers de deserialización ────────────────────────────────────────────

    @staticmethod
    def _deserializar_lista(valor: Any) -> List[dict]:
        """Convierte un JSON string o lista Python a lista de dicts."""
        if isinstance(valor, list):
            return valor
        if isinstance(valor, str):
            try:
                resultado = json.loads(valor)
                return resultado if isinstance(resultado, list) else []
            except (json.JSONDecodeError, TypeError):
                return []
        return []

    @staticmethod
    def _validar_filas_tabla(
        filas: List[dict],
        nombre_tabla: str,
        campo_formulario: str,
        campos_obligatorios: List[Tuple[str, str]],
        reglas_adicionales: Optional[List[Callable]] = None,
    ) -> List[ErrorValidacion]:
        """
        Motor genérico de validación de tablas dinámicas.

        Verifica:
          - Al menos una fila con datos.
          - Todos los campos obligatorios completos en filas con datos.
          - Vínculos PEP obligatorio cuando es_pep == 'si'.
          - Reglas de negocio adicionales por tabla (reglas_adicionales).

        OCP: nuevas tablas solo agregan entradas de configuración.
        DRY: lógica compartida entre junta, accionistas y beneficiarios.
        """
        errores: List[ErrorValidacion] = []
        campos = [c for c, _ in campos_obligatorios]

        def fila_tiene_datos(fila: dict) -> bool:
            return any(
                fila.get(c) is not None and str(fila.get(c)).strip()
                for c in campos
            )

        filas_con_datos = [f for f in filas if fila_tiene_datos(f)]

        if not filas_con_datos:
            errores.append(ErrorValidacion(
                campo=campo_formulario,
                mensaje=f"Debe registrar al menos un registro en {nombre_tabla}",
            ))
            return errores

        for i, fila in enumerate(filas):
            if not fila_tiene_datos(fila):
                continue

            nombre_fila = fila.get("nombre") or fila.get("cargo") or f"fila {i + 1}"

            for campo, etiqueta in campos_obligatorios:
                if _esta_vacio(fila.get(campo)):
                    errores.append(ErrorValidacion(
                        campo=f"{campo_formulario}[{i}].{campo}",
                        mensaje=f"{etiqueta} es obligatorio para '{nombre_fila}' en {nombre_tabla}",
                    ))

            if fila.get("es_pep") == "si" and _esta_vacio(fila.get("vinculos_pep")):
                errores.append(ErrorValidacion(
                    campo=f"{campo_formulario}[{i}].vinculos_pep",
                    mensaje=f"Vínculos PEP es obligatorio para '{nombre_fila}' cuando ¿PEP? es 'Sí'",
                ))

            for regla in (reglas_adicionales or []):
                resultado = regla(i, fila)
                if resultado:
                    errores.append(resultado)

        return errores
