/**
 * Módulo: borradorStorage
 *
 * Funciones puras de persistencia del borrador en localStorage.
 *
 * SRP: única responsabilidad = serializar y deserializar snapshots del formulario.
 * Sin dependencias de React — completamente testeables en aislamiento.
 *
 * Regla de negocio crítica:
 *   Un formulario enviado (submitted === true) NO es un borrador recuperable.
 *   El flag `enviado` se persiste junto con el snapshot para que cualquier
 *   lectura posterior pueda detectar este estado sin consultar el backend.
 */

const CLAVE_BORRADOR = 'sagrilaft_autosave';

/**
 * Persiste un snapshot del formulario en localStorage.
 * @param {object} snapshot - Estado completo del formulario
 */
/**
 * Persiste un snapshot del formulario en localStorage.
 *
 * El flag `enviado` se incluye para que la capa de restauración pueda
 * distinguir un borrador activo de un formulario ya finalizado.
 *
 * @param {object} snapshot - Estado completo del formulario (incluye `submitted`)
 */
export function guardarBorradorEnStorage(snapshot) {
  localStorage.setItem(
    CLAVE_BORRADOR,
    JSON.stringify({
      ...snapshot,
      enviado: snapshot.submitted === true,
      guardadoEn: new Date().toISOString(),
    }),
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
 * Determina si un borrador corresponde a un formulario ya enviado.
 *
 * Un borrador enviado NO debe presentarse al usuario como recuperable;
 * hacerlo inducirá a intentar un reenvío inválido (el backend rechazará
 * cualquier modificación de un formulario en estado ENVIADO).
 *
 * @param {object} borrador - Borrador deserializado del storage
 * @returns {boolean} true si el formulario ya fue enviado
 */
export function borradorEsFormularioEnviado(borrador) {
  return borrador?.enviado === true;
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
