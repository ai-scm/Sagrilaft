/**
 * Utilidades compartidas para comparar valores del formulario durante la corrección.
 *
 * La normalización se usa para que inputs, selects simples, react-select y arrays
 * puedan compararse contra su valor original sin duplicar lógica por componente.
 */

export function normalizarValorComparable(valor) {
  if (valor === null || valor === undefined) return '';
  if (typeof valor === 'string') return valor.trim().replace(/\s+/g, ' ');
  if (Array.isArray(valor)) {
    return `[${valor.map(item => normalizarValorComparable(item)).join(',')}]`;
  }
  if (typeof valor === 'object') {
    if (valor && Object.prototype.hasOwnProperty.call(valor, 'value')) {
      return normalizarValorComparable(valor.value);
    }
    const entradas = Object.keys(valor)
      .sort()
      .map(clave => `${clave}:${normalizarValorComparable(valor[clave])}`);
    return `{${entradas.join(',')}}`;
  }
  return String(valor).trim();
}

export function fueValorModificado(valorActual, valorOriginal) {
  const actualNormalizado = normalizarValorComparable(valorActual);
  const originalNormalizado = normalizarValorComparable(valorOriginal);
  const tieneValor = actualNormalizado !== '';
  return tieneValor && actualNormalizado !== originalNormalizado;
}
