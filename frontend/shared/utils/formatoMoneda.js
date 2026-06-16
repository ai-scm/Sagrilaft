/**
 * Utilidades de presentación para valores monetarios.
 *
 * Se usan en formularios y en vistas de auditoría para mantener una salida
 * consistente sin alterar el valor real que viaja por la API.
 */

const SIMBOLO_POR_MONEDA = {
  COP: '$',
  USD: 'US$',
  EUR: '€',
  PEN: 'S/',
  BRL: 'R$',
  CLP: 'CL$',
  ARS: 'AR$',
};

const LOCALE_POR_MONEDA = {
  COP: 'es-CO',
  USD: 'en-US',
  EUR: 'de-DE',
  PEN: 'es-PE',
  BRL: 'pt-BR',
  CLP: 'es-CL',
  ARS: 'es-AR',
};

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
  return LOCALE_POR_MONEDA[codigo] ?? 'es-CO';
}

export function obtenerSimboloMoneda(moneda = 'COP') {
  const codigo = String(moneda || 'COP').trim().toUpperCase();
  return SIMBOLO_POR_MONEDA[codigo] ?? '$';
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
    return `${simbolo} ${monto}`;
  }

  const montosConSeparador = `${numero}`.replace(/\B(?=(\d{3})+(?!\d))/g, separadorMiles);
  return `${simbolo} ${montosConSeparador}`;
}
