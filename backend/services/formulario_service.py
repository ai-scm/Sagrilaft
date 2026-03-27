"""
FormularioService — lógica de negocio para formularios SAGRILAFT.

Organiza responsabilidades en capas claras:
  - Funciones de serialización JSON (sin estado, nivel módulo).
  - ValidadorEnvioFormulario: verifica completitud antes del envío final (SRP, OCP).
  - FormularioService: CRUD, gestión de documentos y pre-llenado IA (SRP, DIP).

SOLID:
- S (Responsabilidad Única): Cada clase/función tiene un propósito delimitado.
- O (Abierto/Cerrado): Agregar campos requeridos o tipos de documento no
  requiere modificar FormularioService, solo ValidadorEnvioFormulario o prellenado.py.
- D (Inversión de Dependencias): Depende de IExtractorIA y de prellenado.py,
  nunca de implementaciones concretas como ExtractorBedrock.

DRY: Consultas BD centralizadas en _buscar_formulario_o_404 y
     _buscar_documento_o_404. Serialización centralizada en funciones de módulo.
     Mapeo IA→formulario centralizado en services/prellenado.py.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException
from sqlalchemy.orm import Session

from models import DocumentoAdjunto, EstadoFormulario, Formulario
from schemas import (
    DocumentoResponse,
    ErrorValidacion,
    FormularioCreate,
    FormularioUpdate,
    ResultadoValidacionEnvio,
)
from services.alertas.detector_inconsistencias_nombre import (
    AlertaInconsistenciaNombre,
    DetectorInconsistenciasNombre,
)
from services.alertas.detector_inconsistencias_nit import (
    AlertaInconsistenciaNit,
    DetectorInconsistenciasNit,
)
from services.alertas.detector_inconsistencias_nombre_representante import (
    AlertaInconsistenciaNombreRepresentante,
    DetectorInconsistenciasNombreRepresentante,
)
from services.alertas.detector_inconsistencias_numero_doc_representante import (
    AlertaInconsistenciaNumeroDocRepresentante,
    DetectorInconsistenciasNumeroDocRepresentante,
)
from services.contracts import IExtractorIA
from services.prellenado import mapear_campos_para_formulario

DIRECTORIO_UPLOADS: Path = Path(__file__).parent.parent / "uploads"


# ═══════════════════════════════════════════════════════════════
# Serialización JSON (sin estado — funciones de módulo)
# ═══════════════════════════════════════════════════════════════

# Campos que se almacenan como JSON string en la BD
_CAMPOS_JSON_ESCRITURA: List[str] = [
    "junta_directiva", "accionistas", "beneficiario_final",
    "referencias_comerciales", "referencias_bancarias", "informacion_bancaria_pagos", "clasificaciones",
]
_CAMPOS_JSON_LECTURA: List[str] = [
    "junta_directiva", "accionistas", "beneficiario_final",
    "referencias_comerciales", "referencias_bancarias", "informacion_bancaria_pagos", "clasificaciones",
    "tipos_transaccion",
]


def serializar_campos_json(datos: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convierte listas y dicts a JSON strings para persistir en BD.

    Maneja tanto objetos Pydantic (con model_dump) como dicts planos.

    Args:
        datos: Diccionario con los campos del formulario a persistir.

    Returns:
        El mismo diccionario con los campos complejos convertidos a JSON string.
    """
    for campo in _CAMPOS_JSON_ESCRITURA:
        valor = datos.get(campo)
        if valor is None or not isinstance(valor, (list, dict)):
            continue
        elementos: List[Any] = valor if isinstance(valor, list) else [valor]
        serializados = [
            item.model_dump() if hasattr(item, "model_dump") else item
            for item in elementos
        ]
        datos[campo] = json.dumps(serializados, ensure_ascii=False)
    return datos


def deserializar_campos_json(formulario: Formulario) -> Dict[str, Any]:
    """
    Convierte los JSON strings de la BD a sus tipos Python originales.

    Args:
        formulario: Instancia ORM del formulario.

    Returns:
        Diccionario con todos los campos, con los complejos ya deserializados.
    """
    datos: Dict[str, Any] = {
        columna.name: getattr(formulario, columna.name)
        for columna in formulario.__table__.columns
    }
    for campo in _CAMPOS_JSON_LECTURA:
        valor = datos.get(campo)
        if valor is None:
            continue
        try:
            datos[campo] = json.loads(valor)
        except (json.JSONDecodeError, TypeError):
            pass
    return datos


# ═══════════════════════════════════════════════════════════════
# Validador de campos requeridos para envío
# ═══════════════════════════════════════════════════════════════

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
        ("razon_social",            "Nombre o Razón Social"),
        ("tipo_identificacion",     "Tipo de Identificación"),
        ("numero_identificacion",   "Número de Identificación"),
        ("direccion",               "Dirección"),
        ("departamento",            "Departamento"),
        ("ciudad",                  "Ciudad"),
        ("telefono",                "Teléfono"),
        ("correo",                  "Correo Electrónico"),
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
        ("origen_fondos",           "Origen de Fondos"),
        ("nombre_firma",            "Nombre para Firma"),
        ("fecha_firma",             "Fecha de Firma"),
        ("ciudad_firma",            "Ciudad de Firma"),
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

        errores.extend(self._validar_junta_directiva(formulario))
        errores.extend(self._validar_accionistas(formulario))
        errores.extend(self._validar_beneficiarios(formulario))

        return errores

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
        def regla_porcentaje(i: int, fila: dict):
            porcentaje = fila.get("porcentaje")
            if porcentaje is not None and str(porcentaje).strip():
                try:
                    if float(porcentaje) <= 5:
                        return ErrorValidacion(
                            campo=f"accionistas[{i}].porcentaje",
                            mensaje=f"El accionista '{fila.get('nombre', i + 1)}' debe tener participación mayor al 5%",
                        )
                except (ValueError, TypeError):
                    pass
            return None

        filas = self._deserializar_lista(formulario.accionistas)
        return self._validar_filas_tabla(filas, "Composición Accionaria", "accionistas", self._CAMPOS_ACCIONISTA, [regla_porcentaje])

    def _validar_beneficiarios(self, formulario: Formulario) -> List[ErrorValidacion]:
        def regla_no_nit(i: int, fila: dict):
            if str(fila.get("tipo_id") or "").upper() == "NIT":
                return ErrorValidacion(
                    campo=f"beneficiario_final[{i}].tipo_id",
                    mensaje=f"El beneficiario '{fila.get('nombre', i + 1)}' no puede tener NIT como Tipo ID (debe ser CC, CE o PAS)",
                )
            return None

        filas = self._deserializar_lista(formulario.beneficiario_final)
        return self._validar_filas_tabla(filas, "Beneficiario Final", "beneficiario_final", self._CAMPOS_BENEFICIARIO, [regla_no_nit])


# ═══════════════════════════════════════════════════════════════
# Resultado de guardado de documento (Value Object)
# ═══════════════════════════════════════════════════════════════

@dataclass
class ResultadoGuardadoDocumento:
    """
    Encapsula todo lo que produce guardar_documento en un único objeto.

    SRP: evita que el router tenga que desempaquetar tuplas con semántica implícita.

    Attributes:
        documento:             Entidad ORM del documento persistido.
        campos_sugeridos:      Campos del formulario sugeridos por la IA.
        razon_social_extraida: Nombre/razón social encontrada en el documento
                               (None si no aplica o no se extrajo).
        alerta_nombre:         Alerta de inconsistencia si el nombre del documento
                               no coincide con el formulario (None si no hay discrepancia).
        nit_extraido:          NIT encontrado en el documento
                               (None si no aplica o no se extrajo).
        alerta_nit:            Alerta de inconsistencia si el NIT del documento
                               no coincide con el formulario (None si no hay discrepancia).
        numero_doc_representante_extraido: Número de documento del representante
                               encontrado en el documento (None si no aplica o no
                               se extrajo).
        alerta_numero_doc_representante: Alerta de inconsistencia si el número de
                               documento del representante no coincide con el formulario
                               (None si no hay discrepancia).
    """

    documento: DocumentoAdjunto
    campos_sugeridos: Dict[str, Any]
    razon_social_extraida: Optional[str]
    alerta_nombre: Optional[AlertaInconsistenciaNombre]
    nit_extraido: Optional[str] = None
    alerta_nit: Optional[AlertaInconsistenciaNit] = None
    nombre_representante_extraido: Optional[str] = None
    alerta_nombre_representante: Optional[AlertaInconsistenciaNombreRepresentante] = None
    numero_doc_representante_extraido: Optional[str] = None
    alerta_numero_doc_representante: Optional[AlertaInconsistenciaNumeroDocRepresentante] = None


# ═══════════════════════════════════════════════════════════════
# Servicio principal
# ═══════════════════════════════════════════════════════════════

class FormularioService:
    """
    Servicio de negocio para la gestión de formularios SAGRILAFT.

    Coordina operaciones CRUD, gestión de documentos adjuntos y pre-llenado IA,
    manteniendo los routers libres de lógica de negocio.

    Compuesto con ValidadorEnvioFormulario (SRP, OCP).
    Depende de IExtractorIA, no de implementaciones concretas (DIP).
    Mapeo IA→formulario delegado a services/prellenado.py (DIP, DRY).
    """

    def __init__(self, sesion: Session, extractor: IExtractorIA) -> None:
        """
        Args:
            sesion:    Sesión de base de datos SQLAlchemy.
            extractor: Implementación del extractor IA (ej. ExtractorBedrock).
        """
        self._sesion = sesion
        self._extractor = extractor
        self._validador_envio = ValidadorEnvioFormulario()
        self._detector_nombres = DetectorInconsistenciasNombre()
        self._detector_nit = DetectorInconsistenciasNit()
        self._detector_nombre_representante = DetectorInconsistenciasNombreRepresentante()
        self._detector_numero_doc_representante = DetectorInconsistenciasNumeroDocRepresentante()

    # ─── CRUD de formulario ───────────────────────────────────────────────────

    def crear_borrador(self, datos: FormularioCreate) -> Dict[str, Any]:
        """
        Crea un nuevo formulario en estado borrador.

        Args:
            datos: Datos iniciales del formulario.

        Returns:
            Diccionario con los datos del formulario deserializados.
        """
        datos_dict = serializar_campos_json(datos.model_dump(exclude_unset=True))
        formulario = Formulario(**datos_dict)
        self._sesion.add(formulario)
        self._sesion.commit()
        self._sesion.refresh(formulario)
        return deserializar_campos_json(formulario)

    def obtener_por_codigo(self, codigo: str) -> Dict[str, Any]:
        """
        Obtiene un formulario por código de petición o ID, con documentos
        y validaciones deserializados.

        Args:
            codigo: Código de petición o UUID del formulario.

        Returns:
            Diccionario con los datos del formulario, documentos y validaciones.

        Raises:
            HTTPException 404 si el formulario no existe.
        """
        formulario = self._sesion.query(Formulario).filter(
            (Formulario.codigo_peticion == codigo) | (Formulario.id == codigo)
        ).first()
        if not formulario:
            raise HTTPException(status_code=404, detail="Formulario no encontrado")

        datos = deserializar_campos_json(formulario)
        datos["documentos"] = self._documentos_a_respuesta(formulario.documentos)
        datos["validaciones"] = self._validaciones_a_dict(formulario.validaciones)
        return datos

    def actualizar(self, formulario_id: str, datos: FormularioUpdate) -> Dict[str, Any]:
        """
        Actualiza un formulario en estado borrador (guardado parcial).

        Args:
            formulario_id: UUID del formulario.
            datos:         Campos a actualizar.

        Returns:
            Diccionario con los datos del formulario deserializados.

        Raises:
            HTTPException 404 si no se encuentra.
            HTTPException 400 si el formulario ya fue enviado.
        """
        formulario = self._buscar_formulario_o_404(formulario_id)
        self._verificar_estado_borrador(
            formulario,
            "No se puede modificar un formulario que ya fue enviado",
        )

        datos_actualizacion = serializar_campos_json(datos.model_dump(exclude_unset=True))
        for clave, valor in datos_actualizacion.items():
            setattr(formulario, clave, valor)

        self._sesion.commit()
        self._sesion.refresh(formulario)
        return deserializar_campos_json(formulario)

    def enviar(self, formulario_id: str) -> ResultadoValidacionEnvio:
        """
        Realiza el envío final del formulario: valida campos requeridos
        y bloquea ediciones posteriores.

        Args:
            formulario_id: UUID del formulario.

        Returns:
            Resultado indicando si el envío fue exitoso y los errores encontrados.

        Raises:
            HTTPException 404 si no se encuentra.
            HTTPException 400 si ya fue enviado previamente.
        """
        formulario = self._buscar_formulario_o_404(formulario_id)
        self._verificar_estado_borrador(formulario, "El formulario ya fue enviado previamente")

        errores = self._validador_envio.validar(formulario)
        if errores:
            return ResultadoValidacionEnvio(valido=False, errores=errores)

        formulario.estado = EstadoFormulario.ENVIADO
        self._sesion.commit()
        return ResultadoValidacionEnvio(valido=True, errores=[])

    # ─── Gestión de documentos adjuntos ──────────────────────────────────────

    async def guardar_documento(
        self,
        formulario_id: str,
        tipo_documento: str,
        contenido_bytes: bytes,
        nombre_archivo: str,
        content_type: str,
    ) -> ResultadoGuardadoDocumento:
        """
        Guarda un documento en disco y en BD, extrae datos con IA y detecta
        inconsistencias de nombre con respecto al formulario.

        Flujo event-driven: cada carga dispara UNA sola llamada al extractor
        para el tipo_documento recibido, sin iterar sobre otros documentos.

        Args:
            formulario_id:   UUID del formulario al que pertenece el documento.
            tipo_documento:  Tipo de documento (ej. "cedula_representante").
            contenido_bytes: Contenido binario del archivo.
            nombre_archivo:  Nombre original del archivo.
            content_type:    MIME type del archivo.

        Returns:
            ResultadoGuardadoDocumento con documento, campos_sugeridos,
            razon_social_extraida y alerta_nombre (si hay inconsistencia).

        Raises:
            HTTPException 404 si el formulario no existe.
            HTTPException 400 si el formulario ya fue enviado.
        """
        formulario = self._buscar_formulario_o_404(formulario_id)
        self._verificar_estado_borrador(
            formulario,
            "No se pueden agregar documentos a un formulario enviado",
        )

        ruta_archivo = self._guardar_archivo_en_disco(
            formulario_id, nombre_archivo, contenido_bytes
        )
        documento = self._registrar_documento_en_bd(
            formulario_id=formulario_id,
            tipo_documento=tipo_documento,
            nombre_archivo=nombre_archivo,
            ruta_archivo=ruta_archivo,
            content_type=content_type,
            tamano=len(contenido_bytes),
        )

        extraccion = await self._extractor.extraer(str(ruta_archivo), tipo_documento)

        campos_sugeridos: Dict[str, Any] = {}
        razon_social_extraida: Optional[str] = None
        alerta_nombre: Optional[AlertaInconsistenciaNombre] = None
        nit_extraido: Optional[str] = None
        alerta_nit: Optional[AlertaInconsistenciaNit] = None
        nombre_representante_extraido: Optional[str] = None
        alerta_nombre_representante: Optional[AlertaInconsistenciaNombreRepresentante] = None
        numero_doc_representante_extraido: Optional[str] = None
        alerta_numero_doc_representante: Optional[AlertaInconsistenciaNumeroDocRepresentante] = None

        if extraccion.extraido:
            campos_sugeridos = mapear_campos_para_formulario(
                tipo_documento, extraccion.datos
            )
            razon_social_extraida = self._detector_nombres.extraer_nombre_de_documento(
                tipo_documento, extraccion.datos
            )
            alerta_nombre = self._detector_nombres.detectar(
                tipo_documento=tipo_documento,
                datos_extraidos=extraccion.datos,
                razon_social_formulario=formulario.razon_social,
            )
            nit_extraido = self._detector_nit.extraer_nit_de_documento(
                tipo_documento, extraccion.datos
            )
            alerta_nit = self._detector_nit.detectar(
                tipo_documento=tipo_documento,
                datos_extraidos=extraccion.datos,
                numero_identificacion_formulario=formulario.numero_identificacion,
                tipo_identificacion_formulario=formulario.tipo_identificacion,
            )
            nombre_representante_extraido = (
                self._detector_nombre_representante.extraer_nombre_de_documento(
                    tipo_documento, extraccion.datos
                )
            )
            alerta_nombre_representante = self._detector_nombre_representante.detectar(
                tipo_documento=tipo_documento,
                datos_extraidos=extraccion.datos,
                nombre_representante_formulario=formulario.nombre_representante,
            )
            numero_doc_representante_extraido = (
                self._detector_numero_doc_representante.extraer_numero_doc_de_documento(
                    tipo_documento, extraccion.datos
                )
            )
            alerta_numero_doc_representante = self._detector_numero_doc_representante.detectar(
                tipo_documento=tipo_documento,
                datos_extraidos=extraccion.datos,
                numero_doc_representante_formulario=formulario.numero_doc_representante,
            )

        return ResultadoGuardadoDocumento(
            documento=documento,
            campos_sugeridos=campos_sugeridos,
            razon_social_extraida=razon_social_extraida,
            alerta_nombre=alerta_nombre,
            nit_extraido=nit_extraido,
            alerta_nit=alerta_nit,
            nombre_representante_extraido=nombre_representante_extraido,
            alerta_nombre_representante=alerta_nombre_representante,
            numero_doc_representante_extraido=numero_doc_representante_extraido,
            alerta_numero_doc_representante=alerta_numero_doc_representante,
        )

    def eliminar_documento(self, formulario_id: str, doc_id: str) -> None:
        """
        Elimina un documento adjunto de disco y de la BD.

        Args:
            formulario_id: UUID del formulario propietario.
            doc_id:        UUID del documento a eliminar.

        Raises:
            HTTPException 404 si el documento no existe.
        """
        documento = self._buscar_documento_o_404(formulario_id, doc_id)
        ruta = Path(documento.ruta_archivo)
        if ruta.exists():
            ruta.unlink()
        self._sesion.delete(documento)
        self._sesion.commit()

    def listar_documentos(self, formulario_id: str) -> List[DocumentoAdjunto]:
        """
        Lista todos los documentos adjuntos de un formulario.

        Args:
            formulario_id: UUID del formulario.

        Returns:
            Lista de instancias DocumentoAdjunto.
        """
        return self._sesion.query(DocumentoAdjunto).filter(
            DocumentoAdjunto.formulario_id == formulario_id
        ).all()

    # ─── Pre-llenado con IA ───────────────────────────────────────────────────

    async def prellenar_documento(
        self, formulario_id: str, doc_id: str
    ) -> Dict[str, Any]:
        """
        Escanea un documento con IA y retorna campos sugeridos para pre-llenado.

        Args:
            formulario_id: UUID del formulario propietario.
            doc_id:        UUID del documento a procesar.

        Returns:
            Diccionario con success, mensaje, confianza, datos_extraidos y
            campos_sugeridos.

        Raises:
            HTTPException 404 si el documento no existe.
        """
        documento = self._buscar_documento_o_404(formulario_id, doc_id)
        extraccion = await self._extractor.extraer(
            ruta_archivo=documento.ruta_archivo,
            tipo_documento=documento.tipo_documento,
        )

        if not extraccion.extraido:
            return {"success": False, "message": extraccion.mensaje, "campos_sugeridos": {}}

        return {
            "success": True,
            "message": extraccion.mensaje,
            "confianza": extraccion.confianza,
            "datos_extraidos": extraccion.datos,
            "campos_sugeridos": mapear_campos_para_formulario(
                documento.tipo_documento, extraccion.datos
            ),
        }

    async def prellenar_todos(self, formulario_id: str) -> Dict[str, Any]:
        """
        Escanea TODOS los documentos adjuntos con IA y retorna campos
        consolidados para pre-llenado completo del formulario.

        Los campos del primer documento que los provea tienen prioridad
        en campos_consolidados.

        Args:
            formulario_id: UUID del formulario.

        Returns:
            Diccionario con success, campos_consolidados y detalles_por_documento.

        Raises:
            HTTPException 404 si el formulario no existe.
        """
        formulario = self._buscar_formulario_o_404(formulario_id)

        campos_consolidados: Dict[str, Any] = {}
        detalles: List[Dict[str, Any]] = []

        for doc in formulario.documentos:
            extraccion = await self._extractor.extraer(
                ruta_archivo=doc.ruta_archivo,
                tipo_documento=doc.tipo_documento,
            )

            campos: Dict[str, Any] = {}
            if extraccion.extraido:
                campos = mapear_campos_para_formulario(doc.tipo_documento, extraccion.datos)
                for clave, valor in campos.items():
                    if clave not in campos_consolidados and valor is not None:
                        campos_consolidados[clave] = valor

            detalles.append({
                "documento":       doc.nombre_archivo,
                "tipo":            doc.tipo_documento,
                "extraido":        extraccion.extraido,
                "campos_sugeridos":campos,
                "confianza":       extraccion.confianza,
            })

        return {
            "success": True,
            "campos_consolidados":    campos_consolidados,
            "detalles_por_documento": detalles,
        }

    # ─── Helpers privados ─────────────────────────────────────────────────────

    def _buscar_formulario_o_404(self, formulario_id: str) -> Formulario:
        """
        Recupera un formulario por ID o lanza HTTP 404.

        DRY: centraliza la consulta repetida en crear_borrador, actualizar,
             enviar, guardar_documento y prellenar_todos.
        """
        formulario = self._sesion.query(Formulario).filter(
            Formulario.id == formulario_id
        ).first()
        if not formulario:
            raise HTTPException(status_code=404, detail="Formulario no encontrado")
        return formulario

    def _buscar_documento_o_404(
        self, formulario_id: str, doc_id: str
    ) -> DocumentoAdjunto:
        """
        Recupera un documento adjunto por ID y formulario, o lanza HTTP 404.

        DRY: centraliza la consulta repetida en eliminar_documento y
             prellenar_documento.
        """
        documento = self._sesion.query(DocumentoAdjunto).filter(
            DocumentoAdjunto.id == doc_id,
            DocumentoAdjunto.formulario_id == formulario_id,
        ).first()
        if not documento:
            raise HTTPException(status_code=404, detail="Documento no encontrado")
        return documento

    def _verificar_estado_borrador(
        self, formulario: Formulario, mensaje_error: str
    ) -> None:
        """
        Lanza HTTP 400 si el formulario no está en estado borrador.

        DRY: centraliza la verificación de estado repetida en actualizar,
             enviar y guardar_documento.
        """
        if formulario.estado != EstadoFormulario.BORRADOR:
            raise HTTPException(status_code=400, detail=mensaje_error)

    def _guardar_archivo_en_disco(
        self, formulario_id: str, nombre_archivo: str, contenido: bytes
    ) -> Path:
        """Persiste el contenido binario en el directorio de uploads."""
        directorio = DIRECTORIO_UPLOADS / formulario_id
        directorio.mkdir(parents=True, exist_ok=True)
        ruta = directorio / nombre_archivo
        ruta.write_bytes(contenido)
        return ruta

    def _registrar_documento_en_bd(
        self,
        formulario_id: str,
        tipo_documento: str,
        nombre_archivo: str,
        ruta_archivo: Path,
        content_type: str,
        tamano: int,
    ) -> DocumentoAdjunto:
        """Crea y persiste el registro de un documento adjunto en la BD."""
        documento = DocumentoAdjunto(
            formulario_id=formulario_id,
            tipo_documento=tipo_documento,
            nombre_archivo=nombre_archivo,
            ruta_archivo=str(ruta_archivo),
            content_type=content_type,
            tamano=tamano,
        )
        self._sesion.add(documento)
        self._sesion.commit()
        self._sesion.refresh(documento)
        return documento

    @staticmethod
    def _documentos_a_respuesta(
        documentos: List[DocumentoAdjunto],
    ) -> List[DocumentoResponse]:
        """Convierte una lista de DocumentoAdjunto a DocumentoResponse."""
        return [
            DocumentoResponse(
                id=d.id,
                tipo_documento=d.tipo_documento,
                nombre_archivo=d.nombre_archivo,
                content_type=d.content_type,
                tamano=d.tamano,
                created_at=d.created_at,
            )
            for d in documentos
        ]

    @staticmethod
    def _validaciones_a_dict(validaciones: List[Any]) -> List[Dict[str, Any]]:
        """Convierte una lista de ResultadoValidacion a dicts serializables."""
        return [
            {
                "id":              v.id,
                "tipo":            v.tipo,
                "campo":           v.campo,
                "resultado":       v.resultado,
                "detalle":         v.detalle,
                "valor_formulario":v.valor_formulario,
                "valor_documento": v.valor_documento,
                "created_at":      v.created_at,
            }
            for v in validaciones
        ]
