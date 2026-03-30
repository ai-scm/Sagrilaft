/**
 * Normalizadores para comparación tolerante de campos del formulario
 * con valores extraídos de documentos adjuntos.
 *
 * DRY  : fuente única de todas las reglas de normalización del frontend.
 * Espeja la lógica de backend/services/alertas/normalizador_*.py.
 */

// ── Razón social y nombre de persona ─────────────────────────────────────────

const SIGLAS_SOCIETARIAS = [
  [/SOCIEDAD POR ACCIONES SIMPLIFICADA/g,  'SAS'],
  [/SOCIEDAD ANONIMA SIMPLIFICADA/g,       'SAS'],
  [/SOCIEDAD DE RESPONSABILIDAD LIMITADA/g,'LTDA'],
  [/EMPRESA UNIPERSONAL/g,                 'EU'],
  [/SOCIEDAD ANONIMA/g,                    'SA'],
  [/SOCIEDAD EN COMANDITA POR ACCIONES/g,  'SCA'],
  [/SOCIEDAD EN COMANDITA SIMPLE/g,        'SCS'],
  [/S\.A\.S\.?/g,  'SAS'],
  [/S\.A\.?/g,     'SA'],
  [/LTDA\.?/g,     'LTDA'],
  [/LIMITADA\.?/g, 'LTDA'],
  [/E\.U\.?/g,     'EU'],
  [/S\.R\.L\.?/g,  'SRL'],
  [/S\.C\.A\.?/g,  'SCA'],
  [/S\.C\.S\.?/g,  'SCS'],
  [/E\.S\.P\.?/g,  'ESP'],
  [/CÍA\.?/g,      'CIA'],
  [/CIA\.?/g,      'CIA'],
];

/**
 * Normaliza razón social o nombre de persona para comparación tolerante.
 * Elimina diacríticos, unifica mayúsculas, estandariza siglas societarias.
 *
 * @param {string | undefined} valor
 * @returns {string}
 */
export function normalizarNombre(valor) {
  if (!valor) return '';
  let texto = valor.normalize('NFD').replace(/[\u0300-\u036f]/g, '');
  texto = texto.toUpperCase();
  for (const [patron, canonica] of SIGLAS_SOCIETARIAS) {
    texto = texto.replace(patron, canonica);
  }
  return texto.replace(/\./g, '').replace(/\s+/g, ' ').trim();
}

// ── NIT ───────────────────────────────────────────────────────────────────────

const LONGITUD_NIT_BASE = 9;

/**
 * Normaliza un NIT para comparación tolerante.
 * Retiene solo dígitos y descarta el dígito de verificación si supera 9 dígitos.
 *
 * @param {string | undefined} valor
 * @returns {string}
 */
export function normalizarNit(valor) {
  if (!valor) return '';
  const soloDigitos = String(valor).replace(/\D/g, '');
  return soloDigitos.length > LONGITUD_NIT_BASE
    ? soloDigitos.slice(0, LONGITUD_NIT_BASE)
    : soloDigitos;
}

// ── Número de documento de identidad ─────────────────────────────────────────

/**
 * Normaliza un número de documento para comparación tolerante.
 * Elimina puntos, guiones, espacios y unifica capitalización.
 *
 * @param {string | undefined} valor
 * @returns {string}
 */
export function normalizarNumeroDoc(valor) {
  if (!valor) return '';
  return String(valor).toUpperCase().replace(/[^A-Z0-9]/g, '');
}

// ── Dirección ─────────────────────────────────────────────────────────────────

const TIPOS_VIALES = [
  [/\bCALLE\b/g,       'CL'],
  [/\bCARRERA\b/g,     'CR'],
  [/\bAVENIDA\b/g,     'AV'],
  [/\bDIAGONAL\b/g,   'DG'],
  [/\bTRANSVERSAL\b/g, 'TV'],
  [/\bCIRCULAR\b/g,   'CIC'],
  [/\bAUTOPISTA\b/g,  'AU'],
  [/\bVARIANTE\b/g,   'VT'],
  [/\bCLLE\b/g,  'CL'],
  [/\bCLL\b/g,   'CL'],
  [/\bCRRA\b/g,  'CR'],
  [/\bCRA\b/g,   'CR'],
  [/\bAVE\b/g,   'AV'],
  [/\bDIAG\b/g,  'DG'],
  [/\bTRANS\b/g, 'TV'],
  [/\bCIRC\b/g,  'CIC'],
];

/**
 * Normaliza una dirección para comparación tolerante.
 * Estandariza tipos viales, separadores de numeración y puntuación.
 *
 * @param {string | undefined} valor
 * @returns {string}
 */
export function normalizarDireccion(valor) {
  if (!valor) return '';
  let texto = valor.normalize('NFD').replace(/[\u0300-\u036f]/g, '');
  texto = texto.toUpperCase();
  for (const [patron, canonica] of TIPOS_VIALES) {
    texto = texto.replace(patron, canonica);
  }
  texto = texto
    .replace(/#/g, ' ')
    .replace(/\bNUMERO\b/g, ' ')
    .replace(/\bNRO\.?\b/g, ' ')
    .replace(/\bNO\.?\b/g, ' ');
  texto = texto.replace(/[.,]/g, '');
  return texto.replace(/\s+/g, ' ').trim();
}
