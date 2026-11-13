// Solo formato. Las clasificaciones y las explicaciones proceden del servicio común.
export const etiquetasListas = {
  PENDIENTE: 'Pendiente', EN_CURSO: 'En curso', COMPLETADA: 'Completada', PARCIAL: 'Parcial',
  FALLIDA: 'Fallida', INDETERMINADA: 'Indeterminada', CON_CANDIDATOS: 'Candidatos para revisión humana',
  SIN_CANDIDATOS: 'Sin candidatos en las fuentes consultadas', NO_CONCLUYENTE: 'Resultado no concluyente',
  PERSONA: 'Persona natural', ENTIDAD: 'Empresa', NO_DETERMINADO: 'No determinado',
  CONTRAPARTE: 'Contraparte', REPRESENTANTE: 'Representante',
  COINCIDE: 'Coincide', COMPATIBLE: 'Compatible', DIFERENTE: 'Diferente', AUSENTE: 'Dato faltante', NO_APLICADO: 'No aplicado',
  CONFIRMADO: 'Confirmado', REPORTADO: 'Reportado', DESCONOCIDO: 'Desconocido', FALSO: 'Falso',
  CONSULTADA: 'Consultada', NO_DISPONIBLE: 'No disponible', DISPONIBLE: 'Disponible', ERROR_INTEGRIDAD: 'Error de integridad',
  nombre: 'Nombre', nombres_adicionales: 'Nombres adicionales', identificadores: 'Documentos e identificadores',
  tipo_sujeto: 'Tipo de sujeto', fecha_nacimiento: 'Fecha de nacimiento', fecha_expedicion: 'Fecha de expedición',
  nacionalidades: 'Nacionalidades', ciudadanias: 'Ciudadanías', ubicacion: 'Ubicación', ubicaciones: 'Ubicaciones',
  campos_exigidos: 'Criterios exigidos', observacion: 'Observación',
};

export function etiquetaLista(valor) {
  return etiquetasListas[valor] ?? String(valor ?? 'No informado').replaceAll('_', ' ');
}

// Convierte el JSON heredado de un DatePeriod OFAC a una fecha legible.
export function fechaOriginalLegible(original) {
  if (typeof original !== 'string' || !original.startsWith('{')) return original;
  let nodo;
  try { nodo = JSON.parse(original); } catch { return original; }
  if (!nodo || nodo.etiqueta !== 'DatePeriod') return original;
  const puntos = [];
  const bordes = (nodo.hijos || []).filter(b => b.etiqueta === 'Start' || b.etiqueta === 'End');
  for (const borde of bordes) {
    for (const punto of (borde.hijos || []).filter(p => p.etiqueta === 'From' || p.etiqueta === 'To')) {
      const c = Object.fromEntries((punto.hijos || []).map(h => [h.etiqueta, h.texto || '']));
      if (!c.Year) continue;
      const partes = [c.Year.padStart(4, '0')];
      if (c.Month) {
        partes.push(c.Month.padStart(2, '0'));
        if (c.Day) partes.push(c.Day.padStart(2, '0'));
      }
      puntos.push(partes.join('-'));
    }
  }
  if (!puntos.length) return original;
  const unicos = [...new Set(puntos)];
  const aprox = bordes.some(b => ['true', '1'].includes(b.atributos?.Approximate)) ? '~' : '';
  return unicos.length === 1 ? `${aprox}${unicos[0]}` : `${aprox}${unicos[0]} a ${unicos[unicos.length - 1]}`;
}

export function valorLista(valor) {
  if (valor === null || valor === undefined || valor === '') return 'No informado';
  if (typeof valor === 'boolean') return valor ? 'Sí' : 'No';
  if (Array.isArray(valor)) return valor.map(valorLista).join('; ') || 'No informado';
  if (typeof valor === 'object') {
    if ('anio' in valor) return ['anio', 'mes', 'dia'].filter(k => valor[k] != null).map(k => String(valor[k]).padStart(k === 'anio' ? 4 : 2, '0')).join('-');
    if ('original' in valor) return `${fechaOriginalLegible(valor.original)} · Precisión: ${valor.precision} · Aproximada: ${valor.aproximada ? 'Sí' : 'No'}`;
    return ['tipo', 'valor', 'pais_emisor', 'digito_verificacion', 'rol', 'texto', 'pais', 'historica']
      .filter(k => valor[k] != null).map(k => `${etiquetaLista(k)}: ${valorLista(valor[k])}`).join('; ') || 'No interpretado';
  }
  return String(valor);
}
