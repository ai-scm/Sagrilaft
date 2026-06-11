/**
 * Textos legales parametrizables del formulario SAGRILAFT.
 *
 * Actualizar estos valores al desplegar para un nuevo cliente.
 * Variables de entorno opcionales (prefijo VITE_):
 *   VITE_RAZON_SOCIAL         — nombre completo de la empresa titular
 *   VITE_CORREO_DATOS         — correo para ejercer derechos HABEAS DATA
 */

export const RAZON_SOCIAL_EMPRESA    = import.meta.env.VITE_RAZON_SOCIAL    ?? 'HIGHTECH SOFTWARE CONTABLE SAS';
export const CORREO_DATOS_PERSONALES = import.meta.env.VITE_CORREO_DATOS    ?? 'info@hightechsoftware.com.co';
