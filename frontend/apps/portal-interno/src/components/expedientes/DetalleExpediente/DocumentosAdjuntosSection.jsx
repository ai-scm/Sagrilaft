import { useState } from 'react';
import { Download } from 'lucide-react';
import { api } from '../../../services/api';
import FilaDocumento from './FilaDocumento';

export default function DocumentosAdjuntosSection({ documentos, formularioId }) {
  const [descargandoTodos, setDescargandoTodos] = useState(false);

  async function handleDescargarTodos() {
    if (documentos.length === 0 || descargandoTodos) return;

    setDescargandoTodos(true);
    try {
      for (const documento of documentos) {
        await api.descargarDocumento(formularioId, documento.id, documento.nombre_archivo);
        await new Promise(resolve => setTimeout(resolve, 300));
      }
    } catch (err) {
      console.error('Error al descargar todos:', err);
    } finally {
      setDescargandoTodos(false);
    }
  }

  return (
    <section className="section-block">
      <div className="section-header">
        <h2 className="section-title">Documentos Adjuntos ({documentos.length})</h2>
        {documentos.length > 0 && (
          <button
            className="btn-outline btn-outline-gray"
            onClick={handleDescargarTodos}
            disabled={descargandoTodos}
            type="button"
          >
            <Download size={14} /> {descargandoTodos ? 'Descargando...' : 'Descargar todos'}
          </button>
        )}
      </div>
      <div className="card table-card">
        {documentos.length === 0 ? (
          <div style={{ padding: '24px', textAlign: 'center', color: '#9CA3AF' }}>
            No hay documentos adjuntos en este formulario.
          </div>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Documento</th>
                <th>Tipo</th>
                <th>Tamaño</th>
                <th>Cargado por</th>
                <th>Fecha de carga</th>
                <th className="text-right">Acciones</th>
              </tr>
            </thead>
            <tbody>
              {documentos.map(documento => (
                <FilaDocumento key={documento.id} documento={documento} formularioId={formularioId} />
              ))}
            </tbody>
          </table>
        )}
      </div>
    </section>
  );
}
