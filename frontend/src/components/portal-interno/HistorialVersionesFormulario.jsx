/**
 * HistorialVersionesFormulario — línea de tiempo de PDFs generados por el sistema.
 *
 * Cada vez que la contraparte envía o corrige el formulario, el sistema genera
 * un nuevo PDF versionado. Este componente los lista en orden cronológico,
 * con la versión activa destacada y todas las versiones anteriores descargables
 * para trazabilidad y auditoría SAGRILAFT.
 */

import { useState } from 'react';
import { api } from '../../services/api';
import {
  TIPO_DOCUMENTO_FORMULARIO_PDF,
  formatearFechaHora,
  formatearBytes,
} from './constantes';

// ── Estilos ───────────────────────────────────────────────────────────────────

const s = {
  contenedor: {
    background:   '#fff',
    borderRadius: 'var(--radius-md, 8px)',
    border:       '1px solid var(--gray-200, #e2e8f0)',
    marginBottom: '16px',
    overflow:     'hidden',
  },
  encabezado: {
    fontSize:      '0.8rem',
    fontWeight:    '700',
    color:         'var(--gray-500, #64748b)',
    textTransform: 'uppercase',
    letterSpacing: '0.06em',
    padding:       '12px 20px',
    background:    'var(--gray-50, #f8fafc)',
    borderBottom:  '1px solid var(--gray-100, #f1f5f9)',
    margin:        0,
  },
  filaVersion: {
    display:        'flex',
    alignItems:     'center',
    justifyContent: 'space-between',
    padding:        '12px 20px',
    borderBottom:   '1px solid var(--gray-50, #f8fafc)',
    gap:            '12px',
  },
  filaVersionActiva: {
    background: '#f0fdf4',
  },
  infoVersion: {
    display:       'flex',
    flexDirection: 'column',
    gap:           '3px',
    flex:          1,
    minWidth:      0,
  },
  nombreArchivo: {
    fontSize:     '0.88rem',
    fontWeight:   '500',
    color:        'var(--gray-800, #1e293b)',
    overflow:     'hidden',
    textOverflow: 'ellipsis',
    whiteSpace:   'nowrap',
  },
  metaVersion: {
    display:    'flex',
    gap:        '8px',
    alignItems: 'center',
    flexWrap:   'wrap',
  },
  fechaTamano: {
    fontSize: '0.75rem',
    color:    'var(--gray-400, #94a3b8)',
  },
  badgeVersionActiva: {
    fontSize:      '0.68rem',
    fontWeight:    '700',
    color:         '#166534',
    background:    '#dcfce7',
    border:        '1px solid #bbf7d0',
    borderRadius:  '999px',
    padding:       '2px 8px',
    letterSpacing: '0.03em',
    textTransform: 'uppercase',
    whiteSpace:    'nowrap',
  },
  badgeVersionAnterior: {
    fontSize:      '0.68rem',
    fontWeight:    '600',
    color:         'var(--gray-500, #64748b)',
    background:    'var(--gray-100, #f1f5f9)',
    border:        '1px solid var(--gray-200, #e2e8f0)',
    borderRadius:  '999px',
    padding:       '2px 8px',
    whiteSpace:    'nowrap',
  },
  btnDescargar: {
    padding:        '5px 14px',
    background:     'var(--primary-50, #eff6ff)',
    color:          'var(--primary-700, #1d4ed8)',
    border:         '1px solid var(--primary-200, #bfdbfe)',
    borderRadius:   'var(--radius-sm, 6px)',
    fontSize:       '0.78rem',
    fontWeight:     '600',
    cursor:         'pointer',
    textDecoration: 'none',
    whiteSpace:     'nowrap',
    flexShrink:     0,
  },
};

// ── Sub-componente ────────────────────────────────────────────────────────────

function FilaVersion({ documento, esVersionActiva, formularioId }) {
  const [descargando, setDescargando] = useState(false);

  async function handleDescargar() {
    setDescargando(true);
    try {
      await api.descargarDocumento(formularioId, documento.id, documento.nombre_archivo);
    } finally {
      setDescargando(false);
    }
  }

  const tamano    = documento.tamano ? formatearBytes(documento.tamano) : null;
  const fecha     = documento.created_at ? formatearFechaHora(documento.created_at) : null;
  const metaTexto = [fecha, tamano].filter(Boolean).join(' · ');

  return (
    <div style={{ ...s.filaVersion, ...(esVersionActiva ? s.filaVersionActiva : {}) }}>
      <div style={s.infoVersion}>
        <span style={s.nombreArchivo} title={documento.nombre_archivo}>
          {documento.nombre_archivo}
        </span>
        <div style={s.metaVersion}>
          {metaTexto && <span style={s.fechaTamano} title={documento.created_at ?? undefined}>{metaTexto}</span>}
          {esVersionActiva
            ? <span style={s.badgeVersionActiva}>Versión activa</span>
            : <span style={s.badgeVersionAnterior}>v{documento.version_numero}</span>
          }
        </div>
      </div>
      <button
        onClick={handleDescargar}
        disabled={descargando}
        style={{
          ...s.btnDescargar,
          opacity: descargando ? 0.6 : 1,
          cursor:  descargando ? 'not-allowed' : 'pointer',
        }}
        type="button"
      >
        {descargando ? 'Descargando…' : 'Descargar'}
      </button>
    </div>
  );
}

// ── Componente principal ──────────────────────────────────────────────────────

export default function HistorialVersionesFormulario({ documentos, formularioId }) {
  const versionesDelFormulario = documentos
    .filter(doc => doc.tipo_documento === TIPO_DOCUMENTO_FORMULARIO_PDF)
    .sort((a, b) => b.version_numero - a.version_numero);

  if (versionesDelFormulario.length === 0) return null;

  const numeroVersionMaxima = versionesDelFormulario[0].version_numero;

  return (
    <div style={s.contenedor}>
      <p style={s.encabezado}>
        Historial de versiones del formulario ({versionesDelFormulario.length})
      </p>

      {versionesDelFormulario.map(doc => (
        <FilaVersion
          key={doc.id}
          documento={doc}
          esVersionActiva={doc.version_numero === numeroVersionMaxima}
          formularioId={formularioId}
        />
      ))}
    </div>
  );
}
