import { useState } from 'react';
import { Download } from 'lucide-react';
import { api } from '../../../services/api';
import { formatearBytes, formatearFechaHora } from '../../../config/constantes';

export default function DocumentoResumenCard({
  documento,
  formularioId,
  titulo,
  icono,
  botonClassName = 'btn-icon',
  tituloDescarga = 'Descargar',
}) {
  const [descargando, setDescargando] = useState(false);
  const tamano = documento.tamano ? formatearBytes(documento.tamano) : '';
  const fecha = documento.created_at ? formatearFechaHora(documento.created_at) : null;

  async function handleDescargar() {
    setDescargando(true);
    try {
      await api.descargarDocumento(formularioId, documento.id, documento.nombre_archivo);
    } finally {
      setDescargando(false);
    }
  }

  return (
    <div className="card summary-card">
      {icono}
      <div className="card-content">
        <h3 className="doc-title">{titulo}</h3>
        <div className="doc-meta">
          <span>{documento.nombre_archivo}</span>
          {fecha && (
            <>
              <span className="separator">•</span>
              <span>{fecha}</span>
            </>
          )}
          {tamano && (
            <>
              <span className="separator">•</span>
              <span>{tamano}</span>
            </>
          )}
        </div>
      </div>
      <button
        className={botonClassName}
        onClick={handleDescargar}
        disabled={descargando}
        title={tituloDescarga}
        style={{ opacity: descargando ? 0.5 : 1 }}
        type="button"
      >
        <Download size={botonClassName === 'btn-icon' ? 18 : 16} />
      </button>
    </div>
  );
}
