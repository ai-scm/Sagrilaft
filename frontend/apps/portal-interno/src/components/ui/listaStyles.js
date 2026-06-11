/**
 * Estilos compartidos para bandejas del portal interno.
 *
 * Objetivo: evitar duplicación entre listas como "Accesos manuales" y
 * "Formularios recibidos", manteniendo una estética consistente.
 */


export const estilosBandeja = {
  contenedor: {
    display:       'flex',
    flexDirection: 'column',
    gap:           '12px',
  },
  encabezado: {
    display:        'flex',
    justifyContent: 'space-between',
    alignItems:     'center',
    marginBottom:   '4px',
  },
  btnActualizar: {
    padding:      '6px 14px',
    background:   'transparent',
    color:        'var(--primary-600, #2563eb)',
    border:       '1.5px solid var(--primary-200, #bfdbfe)',
    borderRadius: 'var(--radius-sm, 6px)',
    fontSize:     '0.8rem',
    fontWeight:   '600',
    cursor:       'pointer',
  },
  barraFiltros: {
    display:    'flex',
    gap:        '8px',
    flexWrap:   'wrap',
    alignItems: 'center',
  },
  selectFiltro: {
    padding:      '6px 10px',
    border:       '1.5px solid var(--gray-200, #e2e8f0)',
    borderRadius: 'var(--radius-sm, 6px)',
    fontSize:     '0.8rem',
    color:        'var(--gray-700, #334155)',
    background:   '#fff',
    cursor:       'pointer',
  },
  estadoVacio: {
    textAlign: 'center',
    padding:   '48px 0',
    color:     'var(--gray-400, #94a3b8)',
    fontSize:  '0.9rem',
  },
};
