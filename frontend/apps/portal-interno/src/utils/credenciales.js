export const CLAVE_CREDENCIALES = 'credenciales_recientes';
export const VENTANA_GRACIA_MS = 10 * 60 * 1000; // 10 minutos

/**
 * Guarda las credenciales recién creadas en el sessionStorage.
 * @param {Object} acceso - Objeto con los datos del acceso creado (incluyendo PIN).
 */
export function guardarCredenciales(acceso) {
  try {
    const almacenadas = JSON.parse(sessionStorage.getItem(CLAVE_CREDENCIALES) || '{}');
    almacenadas[acceso.codigo_peticion] = {
      ...acceso,
      guardado_en: Date.now()
    };
    sessionStorage.setItem(CLAVE_CREDENCIALES, JSON.stringify(almacenadas));
  } catch (error) {
    console.error('Error al guardar credenciales en sessionStorage', error);
  }
}

/**
 * Recupera las credenciales si están dentro de la ventana de gracia.
 * @param {string} codigoPeticion - El código de petición del acceso.
 * @returns {Object|null} Las credenciales o null si no existen o ya expiraron.
 */
export function obtenerCredencialesRecientes(codigoPeticion) {
  try {
    const almacenadas = JSON.parse(sessionStorage.getItem(CLAVE_CREDENCIALES) || '{}');
    const credencial = almacenadas[codigoPeticion];
    
    if (!credencial) return null;

    if (Date.now() - credencial.guardado_en <= VENTANA_GRACIA_MS) {
      return credencial;
    }

    // Si expiró, se limpia por seguridad
    delete almacenadas[codigoPeticion];
    sessionStorage.setItem(CLAVE_CREDENCIALES, JSON.stringify(almacenadas));
    return null;
  } catch (error) {
    return null;
  }
}
