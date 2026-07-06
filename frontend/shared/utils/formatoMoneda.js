/**
 * Utilidades de presentación para valores monetarios.
 *
 * Se usan en formularios y en vistas de auditoría para mantener una salida
 * consistente sin alterar el valor real que viaja por la API.
 */

const MONEDA_POR_CODIGO = {
  COP: { simbolo: '$', locale: 'es-CO' },
  USD: { simbolo: 'US$', locale: 'en-US' },
  EUR: { simbolo: '€', locale: 'de-DE' },
  PEN: { simbolo: 'S/', locale: 'es-PE' },
  BRL: { simbolo: 'R$', locale: 'pt-BR' },
  CLP: { simbolo: 'CL$', locale: 'es-CL' },
  ARS: { simbolo: 'AR$', locale: 'es-AR' },
  MXN: { simbolo: 'MX$', locale: 'es-MX' },
  GBP: { simbolo: '£', locale: 'en-GB' },
  JPY: { simbolo: '¥', locale: 'ja-JP' },
  CHF: { simbolo: 'CHF', locale: 'de-CH' },
  AUD: { simbolo: 'A$', locale: 'en-AU' },
  CAD: { simbolo: 'C$', locale: 'en-CA' },
  NZD: { simbolo: 'NZ$', locale: 'en-NZ' },
  CNY: { simbolo: '¥', locale: 'zh-CN' },
  HKD: { simbolo: 'HK$', locale: 'zh-HK' },
  SGD: { simbolo: 'S$', locale: 'en-SG' },
  OTRA: { simbolo: '', locale: 'es-CO' },
};

const MONEDA_PERSONALIZADA = 'OTRA';
const MONEDA_PREDETERMINADA = 'COP';

const CAMPOS_MONETARIOS = new Set([
  'ingresos_mensuales',
  'otros_ingresos',
  'egresos_mensuales',
  'total_activos',
  'total_pasivos',
  'patrimonio',
]);

function extraerEntero(valor) {
  if (valor === null || valor === undefined || valor === '') return null;
  if (typeof valor === 'boolean') return null;
  if (typeof valor === 'number') return Number.isFinite(valor) ? Math.trunc(valor) : null;

  const texto = String(valor).trim();
  if (!texto) return null;

  if (/^-?\d+(?:[.,]\d+)?$/.test(texto)) {
    const normalizado = texto.replace(',', '.');
    const numero = Number(normalizado);
    return Number.isFinite(numero) ? Math.trunc(numero) : null;
  }

  const soloDigitos = texto.replace(/\D/g, '');
  if (!soloDigitos) return null;
  const numero = Number(soloDigitos);
  return Number.isFinite(numero) ? numero : null;
}

export function obtenerLocaleMoneda(moneda = 'COP') {
  const codigo = String(moneda || 'COP').trim().toUpperCase();
  return MONEDA_POR_CODIGO[codigo]?.locale ?? MONEDA_POR_CODIGO[MONEDA_PREDETERMINADA].locale;
}

export function obtenerSimboloMoneda(moneda = 'COP') {
  const codigo = String(moneda || 'COP').trim().toUpperCase();
  return MONEDA_POR_CODIGO[codigo]?.simbolo ?? '';
}

export function obtenerCodigoIsoMoneda(valor) {
  const codigo = String(valor || '').trim().toUpperCase();
  return /^[A-Z]{3}$/.test(codigo) && MONEDA_POR_CODIGO[codigo] ? codigo : null;
}

export function resolverMonedaParaFormato(monedaDeclaracion = 'COP', monedaDeclaracionOtra = '') {
  const codigoDeclaracion = String(monedaDeclaracion || '').trim().toUpperCase();

  if (codigoDeclaracion === MONEDA_PERSONALIZADA) {
    return obtenerCodigoIsoMoneda(monedaDeclaracionOtra) ?? MONEDA_PREDETERMINADA;
  }

  return obtenerCodigoIsoMoneda(codigoDeclaracion) ?? MONEDA_PREDETERMINADA;
}

export function esCampoMonetario(campo) {
  return CAMPOS_MONETARIOS.has(campo);
}

export function formatearMontoMoneda(valor, moneda = 'COP') {
  const numero = extraerEntero(valor);
  if (numero === null) return valor === null || valor === undefined || valor === '' ? 'Sin información' : String(valor);

  const simbolo = obtenerSimboloMoneda(moneda);
  const locale = obtenerLocaleMoneda(moneda);
  const separadorMiles = new Intl.NumberFormat(locale).format(1000).includes(',') ? ',' : '.';
  const monto = new Intl.NumberFormat(locale, {
    maximumFractionDigits: 0,
    minimumFractionDigits: 0,
  }).format(numero).replace(/[\u202f\u00a0]/g, ' ');

  if (monto.includes(',') || monto.includes('.')) {
    return `${simbolo} ${monto}`.trim();
  }

  const montosConSeparador = `${numero}`.replace(/\B(?=(\d{3})+(?!\d))/g, separadorMiles);
  return `${simbolo} ${montosConSeparador}`.trim();
}
