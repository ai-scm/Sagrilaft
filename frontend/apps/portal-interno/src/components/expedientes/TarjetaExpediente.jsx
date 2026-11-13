/**
 * TarjetaExpediente — Tarjeta reutilizable de expediente para listas/buscadores.
 *
 * Usada tanto por la bandeja de "Formularios recibidos" como por el buscador
 * de "Verificar SAGRILAFT", para mantener una única presentación visual.
 */

import BadgeEstadoFormulario from '../badges/BadgeEstadoFormulario';
import { ETIQUETA_TIPO_CONTRAPARTE, formatearFechaCorta } from '../../config/constantes';

const s = {
  tarjeta: {
    background:    '#fff',
    borderRadius:  'var(--radius-md, 8px)',
    border:        '1px solid var(--gray-200, #e2e8f0)',
    padding:       '14px 18px',
    cursor:        'pointer',
    transition:    'border-color 0.15s, box-shadow 0.15s',
    display:       'flex',
    flexDirection: 'column',
    gap:           '6px',
  },
  filaSuperior: {
    display:        'flex',
    alignItems:     'flex-start',
    justifyContent: 'space-between',
    gap:            '8px',
  },
  razonSocial: {
    fontSize:   '0.92rem',
    fontWeight: '700',
    color:      'var(--gray-900, #0f172a)',
    margin:     0,
    lineHeight: 1.3,
  },
  codigo: {
    fontSize:      '0.75rem',
    color:         'var(--gray-400, #94a3b8)',
    fontFamily:    'monospace',
    letterSpacing: '0.04em',
  },
  metadatos: {
    display:    'flex',
    gap:        '8px',
    flexWrap:   'wrap',
    alignItems: 'center',
  },
  chip: {
    fontSize:     '0.72rem',
    color:        'var(--gray-500, #64748b)',
    background:   'var(--gray-50, #f8fafc)',
    border:       '1px solid var(--gray-200, #e2e8f0)',
    borderRadius: '999px',
    padding:      '2px 9px',
    whiteSpace:   'nowrap',
  },
  chipDocs: (cantidad) => ({
    fontSize:     '0.72rem',
    color:        cantidad > 0 ? '#15803d' : 'var(--gray-400, #94a3b8)',
    background:   cantidad > 0 ? '#f0fdf4' : 'var(--gray-50, #f8fafc)',
    border:       `1px solid ${cantidad > 0 ? '#bbf7d0' : 'var(--gray-200, #e2e8f0)'}`,
    borderRadius: '999px',
    padding:      '2px 9px',
    whiteSpace:   'nowrap',
  }),
};

export default function TarjetaExpediente({ expediente, onClick }) {
  const tipoLabel  = ETIQUETA_TIPO_CONTRAPARTE[expediente.tipo_contraparte] ?? expediente.tipo_contraparte ?? '—';
  const cantidadDocs = expediente.cantidad_documentos ?? 0;

  return (
    <div
      style={s.tarjeta}
      onClick={() => onClick(expediente)}
      onMouseEnter={e => {
        e.currentTarget.style.borderColor = 'var(--primary-300, #93c5fd)';
        e.currentTarget.style.boxShadow   = '0 2px 8px rgba(37,99,235,0.08)';
      }}
      onMouseLeave={e => {
        e.currentTarget.style.borderColor = 'var(--gray-200, #e2e8f0)';
        e.currentTarget.style.boxShadow   = 'none';
      }}
    >
      <div style={s.filaSuperior}>
        <div>
          <p style={s.razonSocial}>{expediente.razon_social ?? '(Sin razón social)'}</p>
          <span style={s.codigo}>{expediente.codigo_peticion}</span>
        </div>
        <BadgeEstadoFormulario
          estado={expediente.estado}
          overrides={{ fontSize: '0.7rem', padding: '2px 10px' }}
        />
      </div>

      <div style={s.metadatos}>
        <span style={s.chip}>{tipoLabel}</span>
        {expediente.numero_identificacion && (
          <span style={s.chip}>NIT {expediente.numero_identificacion}</span>
        )}
        <span style={s.chipDocs(cantidadDocs)}>
          {cantidadDocs} doc{cantidadDocs !== 1 ? 's' : ''}
        </span>
        <span style={{ ...s.chip, marginLeft: 'auto' }}>
          {formatearFechaCorta(expediente.updated_at)}
        </span>
      </div>
    </div>
  );
}
