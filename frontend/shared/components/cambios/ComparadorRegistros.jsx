export function esCampoComparableComoRegistro(campo, configuracionComparador = {}) {
  return Boolean(configuracionComparador[campo]);
}

/**
 * Estilos CSS-in-JS para el comparador de registros.
 */
const estilos = {
  contenedor: { display: 'flex', flexDirection: 'column', gap: '10px' },
  ficha: { border: '1px solid var(--gray-100,#f1f5f9)', borderRadius: 8, padding: 10, background: '#fff' },
  fichaEncabezado: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8, marginBottom: 8, fontWeight: 700, color: 'var(--gray-800,#1e293b)' },
  etiquetaIdentificador: { fontSize: '0.78rem', color: 'var(--gray-600,#475569)', fontWeight: 600 },
  tabla: { width: '100%', borderCollapse: 'collapse', tableLayout: 'fixed' },
  etiquetaCampo: { width: '36%', padding: '6px 8px', color: 'var(--gray-600,#475569)', fontSize: '0.86rem' },
  valor: { padding: '6px 8px', fontSize: '0.9rem', color: 'var(--gray-800,#1e293b)' },
  valorCambiadoAntes: { background: '#fff7ed' },
  valorCambiadoDespues: { background: '#f0fdf4' },
  mensaje: { padding: '8px', color: 'var(--gray-600,#475569)' },
  codigoRaw: { whiteSpace: 'pre-wrap', fontSize: '0.9rem', color: 'var(--gray-800,#1e293b)', background: 'var(--gray-50,#f8fafc)', padding: 8, borderRadius: 6 },
};

/**
 * Parsea un valor a arreglo de registros.
 * Maneja strings JSON, arrays directos y casos de error.
 * @param {any} valor - Valor a parsear
 * @returns {Array} Arreglo de registros o [] si falla
 */
function parseArreglo(valor) {
  if (!valor && valor !== 0) return [];
  if (Array.isArray(valor)) return valor;
  if (typeof valor === 'string') {
    try {
      const arregloParsado = JSON.parse(valor);
      if (Array.isArray(arregloParsado)) return arregloParsado;
    } catch (error) {
      return [];
    }
  }
  return [];
}

/**
 * Normaliza un valor para comparación.
 * Convierte a string en minúsculas y trimea whitespace.
 * @param {any} valor - Valor a normalizar
 * @returns {string} Valor normalizado
 */
function normalizarValor(valor) {
  return (valor === undefined || valor === null) ? '' : String(valor).trim().toLowerCase();
}

/**
 * Comprueba si dos valores son iguales tras normalización.
 * @param {any} a - Primer valor
 * @param {any} b - Segundo valor
 * @returns {boolean} True si son iguales
 */
function sonValoresIguales(a, b) {
  if (a === undefined && b === undefined) return true;
  return String(a ?? '').trim() === String(b ?? '').trim();
}

/**
 * Formatea un valor para mostrar según su tipo.
 * Especialmente útil para porcentajes.
 * @param {any} valor - Valor a formatear
 * @param {string} clave - Clave del campo para determinar formato
 * @returns {string} Valor formateado
 */
function formatearValor(valor, clave, etiquetasValores = null) {
  if (valor === null || valor === undefined) return '';
  if (etiquetasValores) {
    const texto = String(valor);
    return etiquetasValores[texto] || texto;
  }
  if (clave === 'porcentaje') {
    const numero = Number(valor);
    if (!Number.isNaN(numero)) return `${numero}%`;
    return String(valor);
  }
  return String(valor);
}

/**
 * Construye mapas de índices por llave normalizada.
 * Útil para búsquedas rápidas de coincidencias.
 */
function construirMapasIndices(registros, llaves) {
  const mapas = {};
  for (const llave of llaves) mapas[llave] = new Map();

  registros.forEach((registro, indice) => {
    for (const llave of llaves) {
      const valorNormalizado = normalizarValor(registro?.[llave]);
      if (!valorNormalizado) continue;
      const indices = mapas[llave].get(valorNormalizado) || [];
      indices.push(indice);
      mapas[llave].set(valorNormalizado, indices);
    }
  });

  return mapas;
}

/**
 * Busca emparejamiento por llaves prioritarias.
 */
function buscarPorLlaves(registroAntes, registrosDespues, llaves, mapas, indicesUsados) {
  for (const llave of llaves) {
    const valorNormalizado = normalizarValor(registroAntes?.[llave]);
    if (!valorNormalizado) continue;

    const indices = mapas[llave].get(valorNormalizado) || [];
    for (let i = 0; i < indices.length; i++) {
      if (!indicesUsados[indices[i]]) return indices[i];
    }
  }
  return null;
}

/**
 * Busca emparejamiento por nombre.
 */
function buscarPorNombre(registroAntes, registrosDespues, indicesUsados) {
  if (!registroAntes?.nombre) return null;
  const nombreNormalizado = normalizarValor(registroAntes.nombre);
  for (let j = 0; j < registrosDespues.length; j++) {
    if (indicesUsados[j]) continue;
    if (normalizarValor(registrosDespues[j]?.nombre) === nombreNormalizado) return j;
  }
  return null;
}

/**
 * Busca emparejamiento por cargo.
 */
function buscarPorCargo(registroAntes, registrosDespues, indicesUsados) {
  if (!registroAntes?.cargo) return null;
  const cargoNormalizado = normalizarValor(registroAntes.cargo);
  for (let j = 0; j < registrosDespues.length; j++) {
    if (indicesUsados[j]) continue;
    if (normalizarValor(registrosDespues[j]?.cargo) === cargoNormalizado) return j;
  }
  return null;
}

/**
 * Empareja registros anteriores con posteriores aplicando múltiples estrategias.
 */
function emparejarRegistros(registrosAntes, registrosDespues, llaves = ['numero_id', 'nombre']) {
  const pares = [];
  const indicesUsados = new Array(registrosDespues.length).fill(false);
  const mapas = construirMapasIndices(registrosDespues, llaves);

  registrosAntes.forEach((registroAntes, indiceAntes) => {
    let indiceEmparejado = buscarPorLlaves(registroAntes, registrosDespues, llaves, mapas, indicesUsados)
      || buscarPorNombre(registroAntes, registrosDespues, indicesUsados)
      || buscarPorCargo(registroAntes, registrosDespues, indicesUsados)
      || (indiceAntes < registrosDespues.length && !indicesUsados[indiceAntes] ? indiceAntes : null);

    if (indiceEmparejado !== null) {
      indicesUsados[indiceEmparejado] = true;
      pares.push({ antes: registroAntes, despues: registrosDespues[indiceEmparejado] });
    } else {
      pares.push({ antes: registroAntes, despues: null, eliminado: true });
    }
  });

  for (let j = 0; j < registrosDespues.length; j++) {
    if (!indicesUsados[j]) {
      pares.push({ antes: null, despues: registrosDespues[j], nuevo: true });
    }
  }

  return pares;
}

/**
 * Obtiene etiqueta descriptiva para valor de arreglo simple.
 * @param {string} valor - Valor a traducir
 * @param {Object} etiquetasValores - Mapa de valor -> etiqueta
 * @returns {string} Etiqueta o valor original
 */
function obtenerEtiquetaValor(valor, etiquetasValores = {}) {
  return etiquetasValores[valor] || valor;
}

/**
 * Renderiza comparación de arreglo simple (lista de strings).
 * Muestra items agregados/eliminados con color de cambio.
 * @param {Array} valoresAntes - Arreglo anterior
 * @param {Array} valoresDespues - Arreglo posterior
 * @param {Object} configuracion - Configuración del campo
 * @returns {JSX.Element} Componente con comparación
 */
function renderizarArregloSimple(valoresAntes, valoresDespues, configuracion) {
  const conjuntoAntes = new Set(valoresAntes);
  const conjuntoDespues = new Set(valoresDespues);
  
  const valoresEliminados = valoresAntes.filter(v => !conjuntoDespues.has(v));
  const valoresNuevos = valoresDespues.filter(v => !conjuntoAntes.has(v));
  const valoresIguales = valoresAntes.filter(v => conjuntoDespues.has(v));

  return (
    <div style={estilos.contenedor}>
      {valoresEliminados.length > 0 && (
        <div>
          <div style={{ fontWeight: 600, color: '#dc2626', marginBottom: 6, fontSize: '0.9rem' }}>
            Eliminados:
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {valoresEliminados.map(v => (
              <span
                key={`eliminado-${v}`}
                style={{
                  background: '#fff7ed',
                  border: '1px solid #fed7aa',
                  borderRadius: 4,
                  padding: '4px 8px',
                  fontSize: '0.9rem',
                  color: '#7c2d12',
                }}
              >
                {obtenerEtiquetaValor(v, configuracion.etiquetasValores)}
              </span>
            ))}
          </div>
        </div>
      )}

      {valoresIguales.length > 0 && (
        <div>
          <div style={{ fontWeight: 600, color: '#666', marginBottom: 6, fontSize: '0.9rem' }}>
            Sin cambios:
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {valoresIguales.map(v => (
              <span
                key={`igual-${v}`}
                style={{
                  background: '#f8fafc',
                  border: '1px solid #e2e8f0',
                  borderRadius: 4,
                  padding: '4px 8px',
                  fontSize: '0.9rem',
                  color: '#475569',
                }}
              >
                {obtenerEtiquetaValor(v, configuracion.etiquetasValores)}
              </span>
            ))}
          </div>
        </div>
      )}

      {valoresNuevos.length > 0 && (
        <div>
          <div style={{ fontWeight: 600, color: '#16a34a', marginBottom: 6, fontSize: '0.9rem' }}>
            Agregados:
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {valoresNuevos.map(v => (
              <span
                key={`nuevo-${v}`}
                style={{
                  background: '#f0fdf4',
                  border: '1px solid #bbf7d0',
                  borderRadius: 4,
                  padding: '4px 8px',
                  fontSize: '0.9rem',
                  color: '#166534',
                }}
              >
                {obtenerEtiquetaValor(v, configuracion.etiquetasValores)}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default function ComparadorRegistros({ campo, valorAnterior, valorCorregido, configuracionComparador = {} }) {
  const configuracion = configuracionComparador[campo] || { tipo: 'arregloObjetos', campos: [] };
  const registrosAntes = parseArreglo(valorAnterior);
  const registrosDespues = parseArreglo(valorCorregido);

  // Manejar arreglos simples (strings)
  if (configuracion.tipo === 'arregloSimple') {
    const valoresAntes = registrosAntes.filter(v => typeof v === 'string');
    const valoresDespues = registrosDespues.filter(v => typeof v === 'string');

    if (!valoresAntes.length && !valoresDespues.length) {
      return <div style={estilos.mensaje}>Sin datos para mostrar.</div>;
    }

    return renderizarArregloSimple(valoresAntes, valoresDespues, configuracion);
  }

  // Manejar arreglos de objetos (fichas)
  if (!registrosAntes.length && !registrosDespues.length) {
    if (valorAnterior || valorCorregido) {
      return (
        <div style={estilos.contenedor}>
          <div style={estilos.mensaje}>No se pudo parsear como lista. Mostrando contenido crudo:</div>
          <pre style={estilos.codigoRaw}>{`ANTES:\n${valorAnterior ?? ''}\n\nDESPUÉS:\n${valorCorregido ?? ''}`}</pre>
        </div>
      );
    }
    return <div style={estilos.mensaje}>Sin datos para mostrar.</div>;
  }

  const paresSinEmparejamientos = emparejarRegistros(registrosAntes, registrosDespues, configuracion.llaves || ['numero_id', 'nombre']);

  return (
    <div style={estilos.contenedor}>
      {paresSinEmparejamientos.map((parConEstatus, indiceIterador) => (
        <div key={indiceIterador} style={estilos.ficha}>
          <div style={estilos.fichaEncabezado}>
            <div>
              {parConEstatus.nuevo ? 'Registro nuevo' : parConEstatus.eliminado ? 'Registro eliminado' : `Registro ${indiceIterador + 1}`}
            </div>
            <div style={estilos.etiquetaIdentificador}>
              {parConEstatus.antes?.numero_id || parConEstatus.despues?.numero_id || ''}
            </div>
          </div>

          <table style={estilos.tabla}>
            <tbody>
              {configuracion.campos.map(({ clave, etiqueta, etiquetasValores }) => {
                const valorAntes = parConEstatus.antes ? parConEstatus.antes[clave] ?? '' : '';
                const valorDespues = parConEstatus.despues ? parConEstatus.despues[clave] ?? '' : '';
                const seModifico = !sonValoresIguales(valorAntes, valorDespues);
                return (
                  <tr key={clave}>
                    <td style={estilos.etiquetaCampo}>{etiqueta}</td>
                    <td style={{ ...estilos.valor, ...(seModifico && parConEstatus.antes ? estilos.valorCambiadoAntes : {}) }}>
                      {formatearValor(valorAntes, clave, etiquetasValores)}
                    </td>
                    <td style={{ ...estilos.valor, ...(seModifico && parConEstatus.despues ? estilos.valorCambiadoDespues : {}) }}>
                      {formatearValor(valorDespues, clave, etiquetasValores)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ))}
    </div>
  );
}
