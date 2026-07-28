/**
 * Validadores reutilizables para formularios.
 * Encapsulan regex y lógica de validación compartida entre componentes.
 */

import { REGEX_CORREO } from '@shared/utils/constantes';

/**
 * Valida si un correo tiene formato válido.
 *
 * Usa REGEX_CORREO de @shared/utils/constantes — única fuente de verdad,
 * también usada por el formulario público (inputValidation.js). Antes este
 * módulo definía su propia regex, más permisiva, lo que permitía que el
 * portal interno aceptara correos que el formulario público rechazaría.
 *
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
