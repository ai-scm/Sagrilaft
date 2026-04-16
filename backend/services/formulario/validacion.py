"""
Validador de campos requeridos para envío de formulario.
"""

import json
from typing import List, Tuple

from models import Formulario
from schemas import ErrorValidacion


class ValidadorEnvioFormulario:
    """
    Verifica que el formulario tenga todos los campos obligatorios diligenciados
    antes de permitir el envío final.

    SOLID - S: Responsabilidad única — validar la completitud del formulario.
    SOLID - O: Agregar o quitar campos requeridos solo modifica _CAMPOS_REQUERIDOS
               sin tocar FormularioService ni el router.
    """

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
        ("ciudad_funciones",        "Ciudad donde ejerce funciones"),
        ("actividad_economica",     "Actividad Económica Principal"),
        ("codigo_ciiu",             "Código CIIU"),
        ("ingresos_mensuales",      "Ingresos Mensuales"),
        ("egresos_mensuales",       "Egresos Mensuales"),
        ("total_activos",           "Total Activos"),
        ("total_pasivos",           "Total Pasivos"),
        ("patrimonio",              "Patrimonio"),
        ("realiza_operaciones_moneda_extranjera", "¿Realiza Operaciones en Moneda Extranjera?"),
        ("origen_fondos",           "Origen de Fondos"),
        ("nombre_firma",            "Nombre para Firma"),
        ("fecha_firma",             "Fecha de Firma"),
        ("ciudad_firma",            "Ciudad de Firma"),
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

    def validar(self, formulario: Formulario) -> List[ErrorValidacion]:
        """
        Valida que todos los campos requeridos estén diligenciados y que
        las declaraciones obligatorias estén aceptadas.

        Args:
            formulario: Instancia ORM del formulario a validar.

        Returns:
            Lista de ErrorValidacion. Vacía si el formulario está completo.
        """
        errores: List[ErrorValidacion] = []

        for campo, nombre in self._CAMPOS_REQUERIDOS:
            valor = getattr(formulario, campo, None)
            if valor is None or (isinstance(valor, str) and not valor.strip()):
                errores.append(ErrorValidacion(
                    campo=campo,
                    mensaje=f"El campo '{nombre}' es obligatorio",
                ))

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

        if self._es_persona_juridica(formulario):
            errores.extend(self._validar_clasificacion_tributaria(formulario))
            errores.extend(self._validar_junta_directiva(formulario))
            errores.extend(self._validar_accionistas(formulario))
            errores.extend(self._validar_beneficiarios(formulario))

        return errores

    def _validar_clasificacion_tributaria(self, formulario: Formulario) -> List[ErrorValidacion]:
        """
        Valida los campos obligatorios de la sección 8 (Clasificación de la Empresa
        y Régimen Tributario), que solo aplican a Persona Jurídica.
        """
        errores: List[ErrorValidacion] = []
        for campo, nombre in self._CAMPOS_CLASIFICACION_JURIDICA:
            valor = getattr(formulario, campo, None)
            if valor is None or (isinstance(valor, str) and not valor.strip()):
                errores.append(ErrorValidacion(
                    campo=campo,
                    mensaje=f"El campo '{nombre}' es obligatorio",
                ))
        return errores

    @staticmethod
    def _realiza_operaciones_en_moneda_extranjera(formulario: Formulario) -> bool:
        return (formulario.realiza_operaciones_moneda_extranjera or "").lower() == "si"

    def _validar_campos_moneda_extranjera(self, formulario: Formulario) -> List[ErrorValidacion]:
        """
        Valida los campos condicionales de la sección 'Operaciones en Moneda Extranjera'.

        Solo se evalúan cuando la empresa declara que sí realiza este tipo de operaciones.
        Espejar aquí las mismas reglas que aplica el frontend en useFormValidacion (paso 6)
        garantiza que la BD nunca reciba un formulario inconsistente.
        """
        if not self._realiza_operaciones_en_moneda_extranjera(formulario):
            return []

        errores: List[ErrorValidacion] = []

        if not (formulario.paises_operaciones or "").strip():
            errores.append(ErrorValidacion(
                campo="paises_operaciones",
                mensaje="El campo 'Países en los que realiza operaciones' es obligatorio",
            ))

        tipos = self._deserializar_lista(formulario.tipos_transaccion)
        if "otras" in tipos and not (formulario.tipos_transaccion_otros or "").strip():
            errores.append(ErrorValidacion(
                campo="tipos_transaccion_otros",
                mensaje="El campo '¿Cuáles?' es obligatorio cuando selecciona 'Otras'",
            ))

        return errores

    @staticmethod
    def _es_persona_juridica(formulario: Formulario) -> bool:
        """
        Determina si el formulario corresponde a una Persona Jurídica.

        Las tablas de Junta Directiva, Composición Accionaria y Beneficiario
        Final solo aplican a este tipo de persona. Centralizar esta guarda
        aquí evita repetir la comparación de string en múltiples métodos
        y hace explícita la regla de negocio en el dominio.
        """
        return (formulario.tipo_persona or "").lower() == "juridica"

    # ── Helper genérico (DRY) ────────────────────────────────────────────────

    @staticmethod
    def _deserializar_lista(valor) -> List[dict]:
        """Convierte un JSON string o lista a lista de dicts."""
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
        reglas_adicionales: List = None,
    ) -> List[ErrorValidacion]:
        """
        Motor genérico de validación de tablas.

        Verifica:
          - Al menos una fila con datos.
          - Todos los campos obligatorios completos en filas con datos.
          - Vínculos PEP obligatorio cuando es_pep == 'si'.
          - Reglas de negocio específicas por tabla (reglas_adicionales).

        OCP: nuevas tablas solo agregan entradas de configuración.
        DRY: no duplicar lógica entre junta, accionistas y beneficiarios.
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
                valor = fila.get(campo)
                if valor is None or str(valor).strip() == "":
                    errores.append(ErrorValidacion(
                        campo=f"{campo_formulario}[{i}].{campo}",
                        mensaje=f"{etiqueta} es obligatorio para '{nombre_fila}' en {nombre_tabla}",
                    ))

            if fila.get("es_pep") == "si" and not str(fila.get("vinculos_pep") or "").strip():
                errores.append(ErrorValidacion(
                    campo=f"{campo_formulario}[{i}].vinculos_pep",
                    mensaje=f"Vínculos PEP es obligatorio para '{nombre_fila}' cuando ¿PEP? es 'Sí'",
                ))

            for regla in (reglas_adicionales or []):
                resultado = regla(i, fila)
                if resultado:
                    errores.append(resultado)

        return errores

    # ── Helper de suma (DRY) ─────────────────────────────────────────────────

    @staticmethod
    def _sumar_porcentajes(filas: List[dict]) -> float:
        """Suma los porcentajes numéricos de un conjunto de filas con datos."""
        total = 0.0
        for fila in filas:
            try:
                valor = float(fila.get("porcentaje") or 0)
                total += valor
            except (ValueError, TypeError):
                pass
        return total

    # ── Validadores por tabla ─────────────────────────────────────────────────

    _CAMPOS_JUNTA: List[Tuple[str, str]] = [
        ("cargo",      "Cargo"),
        ("nombre",     "Nombre"),
        ("tipo_id",    "Tipo ID"),
        ("numero_id",  "Número ID"),
        ("es_pep",     "¿PEP?"),
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

    def _validar_junta_directiva(self, formulario: Formulario) -> List[ErrorValidacion]:
        filas = self._deserializar_lista(formulario.junta_directiva)
        return self._validar_filas_tabla(filas, "Junta Directiva y Representantes", "junta_directiva", self._CAMPOS_JUNTA)

    def _validar_accionistas(self, formulario: Formulario) -> List[ErrorValidacion]:
        def regla_porcentaje_participacion(i: int, fila: dict):
            porcentaje = fila.get("porcentaje")
            if porcentaje is None or not str(porcentaje).strip():
                return None
            try:
                valor = float(porcentaje)
            except (ValueError, TypeError):
                return None
            nombre = fila.get("nombre") or f"fila {i + 1}"
            if valor <= 5:
                return ErrorValidacion(
                    campo=f"accionistas[{i}].porcentaje",
                    mensaje=f"El accionista '{nombre}' debe tener participación mayor al 5%",
                )
            if valor >= 100:
                return ErrorValidacion(
                    campo=f"accionistas[{i}].porcentaje",
                    mensaje=f"El accionista '{nombre}' no puede tener participación del 100% o superior",
                )
            return None

        filas = self._deserializar_lista(formulario.accionistas)
        errores = self._validar_filas_tabla(
            filas, "Composición Accionaria", "accionistas",
            self._CAMPOS_ACCIONISTA, [regla_porcentaje_participacion],
        )

        total = self._sumar_porcentajes(filas)
        if total > 100:
            errores.append(ErrorValidacion(
                campo="accionistas.porcentaje_total",
                mensaje=(
                    f"La suma de participaciones accionarias es {total:.2f}%, "
                    "lo que excede el 100% permitido"
                ),
            ))

        return errores

    def _validar_beneficiarios(self, formulario: Formulario) -> List[ErrorValidacion]:
        def regla_porcentaje_control(i: int, fila: dict):
            porcentaje = fila.get("porcentaje")
            if porcentaje is None or not str(porcentaje).strip():
                return None
            try:
                valor = float(porcentaje)
            except (ValueError, TypeError):
                return None
            nombre = fila.get("nombre") or f"fila {i + 1}"
            if valor <= 25:
                return ErrorValidacion(
                    campo=f"beneficiario_final[{i}].porcentaje",
                    mensaje=f"El beneficiario '{nombre}' debe tener control mayor al 25%",
                )
            if valor >= 100:
                return ErrorValidacion(
                    campo=f"beneficiario_final[{i}].porcentaje",
                    mensaje=f"El beneficiario '{nombre}' no puede tener control del 100% o superior",
                )
            return None

        def regla_no_nit(i: int, fila: dict):
            if str(fila.get("tipo_id") or "").upper() == "NIT":
                return ErrorValidacion(
                    campo=f"beneficiario_final[{i}].tipo_id",
                    mensaje=f"El beneficiario '{fila.get('nombre') or f'fila {i + 1}'}' no puede tener NIT como Tipo ID (debe ser CC, CE o PAS)",
                )
            return None

        filas = self._deserializar_lista(formulario.beneficiario_final)
        errores = self._validar_filas_tabla(
            filas, "Beneficiario Final", "beneficiario_final",
            self._CAMPOS_BENEFICIARIO, [regla_porcentaje_control, regla_no_nit],
        )

        total = self._sumar_porcentajes(filas)
        if total > 100:
            errores.append(ErrorValidacion(
                campo="beneficiario_final.porcentaje_total",
                mensaje=(
                    f"La suma de porcentajes de control es {total:.2f}%, "
                    "lo que excede el 100% permitido"
                ),
            ))

        return errores
