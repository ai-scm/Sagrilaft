import { useState } from 'react';
import { api } from '../../services/api';

const s = {
  contenedor: {
    background: '#fff',
    borderRadius: 'var(--radius-md, 8px)',
    border: '1px solid var(--gray-200, #e2e8f0)',
    marginBottom: '16px',
    overflow: 'hidden',
  },
  encabezado: {
    display: 'flex',
    justifyContent: 'space-between',
    gap: '12px',
    alignItems: 'center',
    padding: '12px 20px',
    background: 'var(--gray-50, #f8fafc)',
  },
  titulo: {
    fontSize: '0.8rem',
    fontWeight: '700',
    color: 'var(--gray-500, #64748b)',
    textTransform: 'uppercase',
    letterSpacing: '0.06em',
    margin: 0,
  },
  btnReporte: {
    padding: '5px 12px',
    background: '#fff',
    color: '#1d4ed8',
    border: '1px solid #bfdbfe',
    borderRadius: 'var(--radius-sm, 6px)',
    fontSize: '0.78rem',
    fontWeight: '700',
    cursor: 'pointer',
    whiteSpace: 'nowrap',
  },
  error: {
    padding: '12px 20px',
    color: '#dc2626',
    background: '#fef2f2',
    fontSize: '0.85rem',
    borderTop: '1px solid #fecaca',
  },
};

export default function HistorialExpediente({ formularioId }) {
  const [descargandoReporte, setDescargandoReporte] = useState(false);
  const [error, setError] = useState(null);

  async function handleDescargarReporte() {
    setDescargandoReporte(true);
    setError(null);
    try {
      await api.descargarReporteAuditoria(formularioId);
    } catch (err) {
      setError(err.message || 'No se pudo descargar el reporte de auditoría.');
    } finally {
      setDescargandoReporte(false);
    }
  }

  return (
    <div style={s.contenedor}>
      <div style={s.encabezado}>
        <p style={s.titulo}>Historial del expediente</p>
        <button
          type="button"
          style={{ ...s.btnReporte, opacity: descargandoReporte ? 0.6 : 1 }}
          disabled={descargandoReporte}
          onClick={handleDescargarReporte}
        >
          {descargandoReporte ? 'Descargando...' : 'Reporte auditoría'}
        </button>
      </div>
      {error && <div style={s.error}>{error}</div>}
    </div>
  );
}
