/**
 * Módulo: borradorStorage
 *
 * Funciones puras de persistencia del borrador en localStorage.
 *
 * SRP: única responsabilidad = serializar y deserializar snapshots del formulario.
 * Sin dependencias de React — completamente testeables en aislamiento.
 */

const CLAVE_BORRADOR = 'sagrilaft_autosave';

/**
 * Persiste un snapshot del formulario en localStorage.
 * @param {object} snapshot - Estado completo del formulario
 */
export function guardarBorradorEnStorage(snapshot) {
  localStorage.setItem(
    CLAVE_BORRADOR,
    JSON.stringify({ ...snapshot, guardadoEn: new Date().toISOString() }),
  );
}

/**
 * Lee y deserializa el borrador almacenado.
 * @returns {object|null} El borrador o null si no existe o está corrupto
 */
export function leerBorradorDeStorage() {
  const raw = localStorage.getItem(CLAVE_BORRADOR);
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

/**
 * Elimina el borrador del almacenamiento local.
 * Debe invocarse tras un envío exitoso del formulario.
 */
export function eliminarBorradorDeStorage() {
  localStorage.removeItem(CLAVE_BORRADOR);
}

/**
 * Construye el mensaje de confirmación para el diálogo de recuperación.
 * Soporta el campo legado `savedAt` para compatibilidad con borradores previos.
 *
 * @param {object} borrador - Borrador deserializado del storage
 * @returns {string} Mensaje legible listo para window.confirm
 */
export function construirMensajeRecuperacion(borrador) {
  const identificador = borrador.codigoPeticion
    ? `Código: ${borrador.codigoPeticion}`
    : 'un borrador sin código';

  const fechaStr = borrador.guardadoEn ?? borrador.savedAt;
  const fechaFormateada = fechaStr
    ? ` (guardado: ${new Date(fechaStr).toLocaleString('es-CO')})`
    : '';

  return `Se encontró ${identificador}${fechaFormateada}.\n¿Desea retomar donde lo dejó?`;
}
