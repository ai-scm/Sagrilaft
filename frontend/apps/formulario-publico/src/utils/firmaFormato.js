/**
 * Utilidades para la sección "Firma del Representante Legal".
 *
 * Fuente única de verdad para:
 *  - Opciones del selector de mes
 *  - Composición del texto narrativo (frontend y backend comparten la lógica)
 */

export const MESES_ES = [
  'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
  'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre',
];

export const OPCIONES_MES = MESES_ES.map((nombre, i) => ({
  value: String(i + 1),
  label: nombre.charAt(0).toUpperCase() + nombre.slice(1),
}));

/**
 * Devuelve las partes del texto narrativo con los valores ingresados.
 * Los campos vacíos quedan como cadena vacía para que el componente
 * decida cómo representarlos (línea en blanco, placeholder, etc.).
 *
 * @param {{ diaFirma, mesFirma, yearFirma, ciudadFirma }} campos
 * @returns {{ dia: string, mes: string, year: string, ciudad: string }}
 */
export function componerPartesFirma({ diaFirma, mesFirma, yearFirma, ciudadFirma }) {
  return {
    dia:    diaFirma  ? String(diaFirma)                      : '',
    mes:    mesFirma  ? (MESES_ES[Number(mesFirma) - 1] ?? '') : '',
    year:   yearFirma ? String(yearFirma)                     : '',
    ciudad: ciudadFirma?.trim() ?? '',
  };
}
