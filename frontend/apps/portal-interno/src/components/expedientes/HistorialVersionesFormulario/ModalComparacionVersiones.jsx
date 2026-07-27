import { useState, useEffect } from 'react';
import Spinner from '@shared/components/ui/Spinner';
import { esCampoMonetario, formatearMontoMoneda } from '@shared/utils/formatoMoneda';
import ComparadorRegistros, { esCampoComparableComoRegistro } from '@shared/components/cambios/ComparadorRegistros';
import { formatClasificacionActividad } from '../../../utils/formateadores';

const s = {
  fondo: {
    position: 'fixed',
    inset: 0,
    zIndex: 200,
    background: 'rgba(15, 23, 42, 0.46)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    padding: '24px',
  },
  modal: {
    width: 'min(980px, 100%)',
    maxHeight: 'min(760px, 92vh)',
    background: '#fff',
    borderRadius: '8px',
    border: '1px solid var(--gray-200, #e2e8f0)',
    boxShadow: '0 24px 80px rgba(15, 23, 42, 0.24)',
    display: 'flex',
    flexDirection: 'column',
    overflow: 'hidden',
  },
  encabezado: {
    padding: '18px 22px',
    borderBottom: '1px solid var(--gray-100, #f1f5f9)',
    display: 'flex',
    justifyContent: 'space-between',
    gap: '16px',
  },
  titulo: {
    margin: 0,
    color: 'var(--gray-900, #0f172a)',
    fontSize: '1rem',
    fontWeight: 800,
  },
  subtitulo: {
    margin: '4px 0 0',
    color: 'var(--gray-500, #64748b)',
    fontSize: '0.82rem',
  },
  cerrar: {
    width: '32px',
    height: '32px',
    borderRadius: '6px',
    border: '1px solid var(--gray-200, #e2e8f0)',
    background: '#fff',
    color: 'var(--gray-600, #475569)',
    fontSize: '1.1rem',
    cursor: 'pointer',
    flexShrink: 0,
  },
  acciones: {
    display: 'flex',
    gap: '8px',
    alignItems: 'center',
  },
  descargar: {
    padding: '7px 12px',
    borderRadius: '6px',
    border: '1px solid var(--primary-200, #bfdbfe)',
    background: 'var(--primary-50, #eff6ff)',
    color: 'var(--primary-700, #1d4ed8)',
    fontSize: '0.78rem',
    fontWeight: 700,
    cursor: 'pointer',
    whiteSpace: 'nowrap',
  },
  cuerpo: {
    overflow: 'auto',
    padding: '18px 22px 22px',
  },
  aviso: {
    padding: '14px 16px',
    background: 'var(--gray-50, #f8fafc)',
    border: '1px solid var(--gray-200, #e2e8f0)',
    borderRadius: '8px',
    color: 'var(--gray-600, #475569)',
    fontSize: '0.88rem',
  },
  tabla: {
    width: '100%',
    borderCollapse: 'collapse',
    tableLayout: 'fixed',
  },
  th: {
    textAlign: 'left',
    color: 'var(--gray-500, #64748b)',
    fontSize: '0.72rem',
    textTransform: 'uppercase',
    letterSpacing: '0.06em',
    padding: '10px 12px',
    borderBottom: '1px solid var(--gray-200, #e2e8f0)',
    background: 'var(--gray-50, #f8fafc)',
  },
  td: {
    verticalAlign: 'top',
    padding: '12px',
    borderBottom: '1px solid var(--gray-100, #f1f5f9)',
    color: 'var(--gray-800, #1e293b)',
    fontSize: '0.84rem',
    lineHeight: 1.45,
    overflowWrap: 'anywhere',
  },
  campo: {
    fontWeight: 700,
    color: 'var(--gray-900, #0f172a)',
  },
  antes: {
    background: '#fff7ed',
  },
  despues: {
    background: '#f0fdf4',
  },
};

export default function ModalComparacionVersiones({
  visible,
  comparacion,
  cargando,
  error,
  errorDescarga,
  descargandoReporte,
  onDescargarReporte,
  onCerrar,
  versiones,
  onCompararVersiones,
}) {
  const [baseSeleccionada, setBaseSeleccionada] = useState('');
  const [compararSeleccionada, setCompararSeleccionada] = useState('');

  useEffect(() => {
    if (comparacion) {
      setBaseSeleccionada(comparacion.version_anterior?.toString() || '');
      setCompararSeleccionada(comparacion.version_corregida?.toString() || '');
    }
  }, [comparacion]);

  function handleCambioComparacion(nuevaBase, nuevaComparar) {
    if (!versiones || !onCompararVersiones) return;
    
    const docBase = versiones.find(v => v.version_numero.toString() === nuevaBase);
    const docComparar = versiones.find(v => v.version_numero.toString() === nuevaComparar);
    
    if (docBase && docComparar) {
      onCompararVersiones(docBase.id, docComparar.id);
    }
  }

  if (!visible) return null;

  const camposComplejos = comparacion?.campos_complejos ?? {};

  function presentarCambio(cambio, moneda) {
    const valor = cambio.valor_anterior;
    if (cambio.campo === 'actividad_clasificacion' || cambio.campo === 'clasificacion_actividad') {
      return formatClasificacionActividad(valor);
    }
    if (!esCampoMonetario(cambio.campo)) return valor;
    return formatearMontoMoneda(valor, moneda);
  }

  function presentarCambioCorregido(cambio, moneda) {
    const valor = cambio.valor_corregido;
    if (cambio.campo === 'actividad_clasificacion' || cambio.campo === 'clasificacion_actividad') {
      return formatClasificacionActividad(valor);
    }
    if (!esCampoMonetario(cambio.campo)) return valor;
    return formatearMontoMoneda(valor, moneda);
  }

  return (
    <div style={s.fondo} role="dialog" aria-modal="true" aria-labelledby="titulo-comparacion-versiones">
      <div style={s.modal}>
        <div style={s.encabezado}>
          <div>
            <h2 id="titulo-comparacion-versiones" style={s.titulo}>Cambios corregidos</h2>
            {versiones && versiones.length > 0 ? (
              <div style={{ display: 'flex', gap: '8px', alignItems: 'center', marginTop: '6px' }}>
                <span style={{ fontSize: '0.82rem', color: 'var(--gray-500, #64748b)' }}>Comparando versión</span>
                <select 
                  value={compararSeleccionada}
                  onChange={e => handleCambioComparacion(baseSeleccionada, e.target.value)}
                  disabled={cargando}
                  style={{ fontSize: '0.8rem', padding: '2px 4px', borderRadius: '4px', border: '1px solid #cbd5e1', cursor: 'pointer' }}
                >
                  {versiones.map(v => (
                    <option key={`c-${v.id}`} value={v.version_numero.toString()}>v{v.version_numero}</option>
                  ))}
                </select>
                <span style={{ fontSize: '0.82rem', color: 'var(--gray-500, #64748b)' }}>contra versión base</span>
                <select
                  value={baseSeleccionada}
                  onChange={e => handleCambioComparacion(e.target.value, compararSeleccionada)}
                  disabled={cargando}
                  style={{ fontSize: '0.8rem', padding: '2px 4px', borderRadius: '4px', border: '1px solid #cbd5e1', cursor: 'pointer' }}
                >
                  <option value="">-</option>
                  {versiones.map(v => (
                    <option key={`b-${v.id}`} value={v.version_numero.toString()}>v{v.version_numero}</option>
                  ))}
                </select>
              </div>
            ) : (
              <p style={s.subtitulo}>
                {comparacion ? `v${comparacion.version_anterior || '-'} → v${comparacion.version_corregida}` : 'Comparando versiones'}
              </p>
            )}
          </div>
          <div style={s.acciones}>
            {comparacion?.disponible && (
              <button
                type="button"
                onClick={onDescargarReporte}
                disabled={descargandoReporte}
                style={{ ...s.descargar, opacity: descargandoReporte ? 0.6 : 1 }}
              >
                {descargandoReporte ? 'Descargando…' : 'Descargar evidencia'}
              </button>
            )}
            <button type="button" onClick={onCerrar} style={s.cerrar} aria-label="Cerrar">×</button>
          </div>
        </div>

        <div style={s.cuerpo}>
          {cargando && <Spinner texto="Comparando versiones…" style={{ padding: '42px 0' }} />}

          {!cargando && error && (
            <div style={s.aviso}>{error}</div>
          )}

          {!cargando && !error && errorDescarga && (
            <div style={s.aviso}>{errorDescarga}</div>
          )}

          {!cargando && !error && comparacion && !comparacion.disponible && (
            <div style={s.aviso}>{comparacion.motivo}</div>
          )}

          {!cargando && !error && comparacion?.disponible && comparacion.cambios.length === 0 && (
            <div style={s.aviso}>No se detectaron cambios en los campos comparables.</div>
          )}

          {!cargando && !error && comparacion?.disponible && comparacion.cambios.length > 0 && (
            <table style={s.tabla}>
              <colgroup>
                <col style={{ width: '24%' }} />
                <col style={{ width: '38%' }} />
                <col style={{ width: '38%' }} />
              </colgroup>
              <thead>
                <tr>
                  <th style={s.th}>Campo</th>
                  <th style={s.th}>Antes</th>
                  <th style={s.th}>Después</th>
                </tr>
              </thead>
                  <tbody>
                    {comparacion.cambios.map(cambio => {
                      if (esCampoComparableComoRegistro(cambio.campo, camposComplejos)) {
                        return (
                          <tr key={cambio.campo}>
                            <td style={{ ...s.td, ...s.campo }}>{cambio.etiqueta}</td>
                            <td style={{ ...s.td }} colSpan={2}>
                              <ComparadorRegistros
                                campo={cambio.campo}
                                valorAnterior={cambio.valor_anterior}
                                valorCorregido={cambio.valor_corregido}
                                configuracionComparador={camposComplejos}
                              />
                            </td>
                          </tr>
                        );
                      }

                      return (
                        <tr key={cambio.campo}>
                          <td style={{ ...s.td, ...s.campo }}>{cambio.etiqueta}</td>
                          <td style={{ ...s.td, ...s.antes }}>{presentarCambio(cambio, comparacion.moneda_anterior)}</td>
                          <td style={{ ...s.td, ...s.despues }}>{presentarCambioCorregido(cambio, comparacion.moneda_corregida)}</td>
                        </tr>
                      );
                    })}
                  </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}
