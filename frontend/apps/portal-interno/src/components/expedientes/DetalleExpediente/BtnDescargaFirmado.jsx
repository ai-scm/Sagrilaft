import { useState } from 'react';
import { api } from '../../../services/api';

export default function BtnDescargaFirmado({ formularioId }) {
  const [descargando, setDescargando] = useState(false);

  async function handleDescargar() {
    setDescargando(true);
    try {
      await api.descargarDocumentoFirmado(formularioId);
    } finally {
      setDescargando(false);
    }
  }

  return (
    <button
      onClick={handleDescargar}
      disabled={descargando}
      className="btn-firma btn-firma-color-firmado"
      type="button"
    >
      {descargando ? 'Descargando\u2026' : 'Descargar firmado'}
    </button>
  );
}
