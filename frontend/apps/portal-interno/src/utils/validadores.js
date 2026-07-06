/**
 * Validadores reutilizables para formularios.
 * Encapsulan regex y lógica de validación compartida entre componentes.
 */

// Regex de validación de correo: admite formato básico name@domain.extension
export const REGEX_CORREO = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

/**
 * Valida si un correo tiene formato válido.
 * @param {string} correo - Correo a validar (se hace trim internamente)
 * @returns {boolean} true si el formato es válido
 */
export function esCorreoValido(correo) {
  return REGEX_CORREO.test(correo.trim());
}

/**
 * Normaliza un correo: trim y lowercase.
 * @param {string} correo - Correo a normalizar
 * @returns {string} Correo normalizado
 */
export function normalizarCorreo(correo) {
  return correo.trim().toLowerCase();
}
