/**
 * Constantes de validación compartidas — fuente única de verdad del frontend.
 *
 * Sincronizadas con:
 *   backend/services/formulario/validacion.py
 *   backend/services/utils/coercion.py
 *   backend/infrastructure/persistencia/models.py (enums como SectorEmpresa)
 *
 * Al cambiar cualquier valor aquí, actualizar el equivalente en el backend.
 */

// ─── Porcentajes de participación y control ───────────────────────────────────

export const UMBRAL_MINIMO_PARTICIPACION_ACCIONISTA   = 5;
export const UMBRAL_MINIMO_CONTROL_BENEFICIARIO_FINAL = 25;
export const PORCENTAJE_MAXIMO_PERMITIDO               = 100;

// ─── Longitudes de campos de formato estricto ─────────────────────────────────

export const LONGITUD_TELEFONO  = 10;
export const LONGITUD_MAXIMA_ID = 20;

// ─── Expresiones regulares ────────────────────────────────────────────────────

export const REGEX_CORREO = /^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$/;
// ─── Solo texto (letras, tildes, espacios, guiones, puntos) ──────────────────
export const REGEX_CHAR_TEXTO = /^[a-zA-ZáéíóúÁÉÍÓÚüÜñÑ\s'.\-,]$/;
// ─── Alfanumérico (letras, números, espacios, guiones, puntos) ────────────────
export const REGEX_CHAR_ALFANUMERICO = /^[a-zA-Z0-9áéíóúÁÉÍÓÚüÜñÑ\s'.\-,]$/;
// ─── Alfanumérico Estricto (solo letras A-Z, a-z y números 0-9) ───────────────
export const REGEX_CHAR_ALFANUMERICO_ESTRICTO = /^[a-zA-Z0-9]$/;

// ─── Opciones de dropdown — espejo de enums del backend (models.py) ───────────

/** Espeja SectorEmpresa en backend/infrastructure/persistencia/models.py */
export const SECTORES_EMPRESA = [
  { value: 'Público', label: 'Público' },
  { value: 'Privado', label: 'Privado' },
  { value: 'Mixto',   label: 'Mixto'   },
];

/** Espeja ActividadClasificacion en backend/domain/formulario/tipos.py */
export const OPCIONES_ACTIVIDAD_CLASIFICACION = [
  { value: 'Industrial',         label: 'Industrial'         },
  { value: 'Comercial',          label: 'Comercial'          },
  { value: 'Financiera',         label: 'Financiera'         },
  { value: 'Economia solidaria', label: 'Economía solidaria' },
  { value: 'Otra',               label: 'Otra'               },
];

/** Valor que habilita edición libre de 'actividad_especifica'; usado en PasoClasificacionContactoBancario.jsx y useFormulario.js */
export const VALOR_ACTIVIDAD_OTRA = 'Otra';

// ─── Tipos de Documentos del Sistema ──────────────────────────────────────────
export const TIPO_DOCUMENTO_FORMULARIO_PDF        = 'FORMULARIO_PDF';
export const TIPO_DOCUMENTO_CERTIFICADO_SAGRILAFT = 'CERTIFICADO_SAGRILAFT';
export const TIPO_DOCUMENTO_REPORTE_FINAL         = 'REPORTE_FINAL';

// Causales de cierre de expediente
export const CAUSAL_CIERRE_INFORME_FINAL = 'informe_final';
export const CAUSAL_CIERRE_NO_CONTINUACION_DIALOGOS = 'no_continuacion_dialogos';
export const CAUSAL_CIERRE_RECHAZADO_CON_INFORME_FINAL = 'rechazado_con_informe_final';

// ─── Estados de Dominio ───────────────────────────────────────────────────────

// Estados de Formulario / Expediente
export const ESTADO_FORM_ENVIADO         = 'enviado';
export const ESTADO_FORM_EN_CORRECCION   = 'en_correccion';
export const ESTADO_FORM_VALIDADO        = 'validado';
export const ESTADO_FORM_RECHAZADO       = 'rechazado';
export const ESTADO_FORM_PENDIENTE_FIRMA = 'pendiente_firma';
export const ESTADO_FORM_FIRMADO         = 'firmado';
export const ESTADO_FORM_CERRADO         = 'cerrado';

// Tipos de solicitud
export const TIPO_SOLICITUD_VINCULACION = 'vinculacion';
export const TIPO_SOLICITUD_ACTUALIZACION = 'actualizacion';

// Modos de trabajo editable
export const MODO_TRABAJO_CORRECCION = 'correccion';
export const MODO_TRABAJO_ACTUALIZACION_REABIERTA = 'actualizacion_reabierta';

// Estados de Acceso Manual
export const ESTADO_ACCESO_ACTIVO    = 'activo';
export const ESTADO_ACCESO_CONSUMIDO = 'consumido';
export const ESTADO_ACCESO_EXPIRADO  = 'expirado';

// Tipos de Contraparte
export const TIPO_CONTRAPARTE_CLIENTE   = 'cliente';
export const TIPO_CONTRAPARTE_PROVEEDOR = 'proveedor';
