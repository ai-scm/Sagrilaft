/**
 * Constantes de validación compartidas — fuente única de verdad del frontend.
 *
 * Sincronizadas con las constantes homólogas en:
 *   backend/services/formulario/validacion.py
 *   backend/services/utils/coercion.py
 *
 * Al cambiar cualquier valor aquí, actualizar el equivalente en el backend.
 */

// ─── Porcentajes de participación y control ───────────────────────────────────

export const UMBRAL_MINIMO_PARTICIPACION_ACCIONISTA   = 5;
export const UMBRAL_MINIMO_CONTROL_BENEFICIARIO_FINAL = 25;
export const PORCENTAJE_MAXIMO_PERMITIDO               = 100;

// ─── Longitudes de campos de formato estricto ─────────────────────────────────

export const LONGITUD_TELEFONO  = 10;
export const LONGITUD_MAXIMA_ID = 10;

// ─── Expresiones regulares ────────────────────────────────────────────────────

export const REGEX_CORREO = /^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$/;

