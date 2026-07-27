import { useState } from 'react';
import { Download, FileText } from 'lucide-react';
import { api } from '../../../services/api';
import { formatearBytes, formatearFechaHora } from '../../../config/constantes';
import { formatTipoDocumento } from '../../../utils/formateadores';

export default function FilaDocumento({ documento, formularioId }) {
  const [descargando, setDescargando] = useState(false);

  async function handleDescargar() {
    setDescargando(true);
    try {
      await api.descargarDocumento(formularioId, documento.id, documento.nombre_archivo);
    } finally {
      setDescargando(false);
    }
  }

  const sinDato = '\u2014';
  const tamano = documento.tamano ? formatearBytes(documento.tamano) : sinDato;
  const fecha = documento.created_at ? formatearFechaHora(documento.created_at) : sinDato;

  return (
    <tr>
      <td>
        <div className="cell-doc-name">
          <FileText size={16} className="text-gray-400" />
          <span title={documento.nombre_archivo}>{documento.nombre_archivo}</span>
        </div>
      </td>
      <td>{formatTipoDocumento(documento.tipo_documento)}</td>
      <td>{tamano}</td>
      <td>{documento.subido_por || sinDato}</td>
      <td>{fecha}</td>
      <td className="text-right">
        <button
          className="btn-icon-small"
          onClick={handleDescargar}
          disabled={descargando}
          title="Descargar"
          style={{ opacity: descargando ? 0.5 : 1 }}
          type="button"
        >
          <Download size={16} />
        </button>
      </td>
    </tr>
  );
}
