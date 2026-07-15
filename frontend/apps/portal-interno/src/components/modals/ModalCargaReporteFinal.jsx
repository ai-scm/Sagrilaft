import { useState } from 'react';
import { api } from '../../services/api';
import './Modals.css';
import {
  CAUSAL_CIERRE_INFORME_FINAL,
  CAUSAL_CIERRE_NO_CONTINUACION_DIALOGOS,
  CAUSALES_CIERRE_EXPEDIENTE,
} from '../../config/constantes';

const LONGITUD_MAXIMA_JUSTIFICACION = 1000;

export default function ModalCargaReporteFinal({ visible, formularioId, onCargado, onCancelar }) {
  const [justificacion, setJustificacion] = useState('');
  const [archivo, setArchivo]             = useState(null);
  const [causalCierre, setCausalCierre]   = useState(CAUSAL_CIERRE_INFORME_FINAL);
  const [enviando, setEnviando]           = useState(false);
  const [error, setError]                 = useState(null);

  function resetearEstado() {
    setJustificacion('');
    setArchivo(null);
    setCausalCierre(CAUSAL_CIERRE_INFORME_FINAL);
    setError(null);
  }

  function limpiarYCerrar() {
    resetearEstado();
    onCancelar();
  }

  const archivoValido = archivo && archivo.type === 'application/pdf';
  const permiteCierreSinPdf = causalCierre === CAUSAL_CIERRE_NO_CONTINUACION_DIALOGOS;
  const formularioValido = permiteCierreSinPdf ? (!archivo || archivoValido) : archivoValido;

  async function handleConfirmar() {
    if (!formularioValido) return;

    setEnviando(true);
    setError(null);

    try {
      await api.cargarReporteFinal(formularioId, archivo, justificacion.trim(), causalCierre);
      resetearEstado();
      onCargado();
    } catch (err) {
      setError(err.message || 'Error al cargar el reporte final. Intente nuevamente.');
    } finally {
      setEnviando(false);
    }
  }

  if (!visible) return null;

  return (
    <div className="modal-overlay" role="dialog" aria-modal="true" aria-labelledby="titulo-modal-carga-reporte">
      <div className="modal-container">
        
        <div className="modal-header">
          <h2 className="modal-title" id="titulo-modal-carga-reporte">
            Cerrar expediente
          </h2>
          <p className="modal-desc">
            Seleccione la causal de cierre. El informe final en PDF es obligatorio, excepto cuando el proceso termina por no continuación de diálogos.
          </p>
        </div>

        <div className="modal-body">
          <div className="form-group">
            <label className="form-label" htmlFor="campo-causal-cierre">Causal de cierre</label>
            <select
              id="campo-causal-cierre"
              value={causalCierre}
              onChange={e => {
                setCausalCierre(e.target.value);
                setError(null);
              }}
              disabled={enviando}
              className="form-input"
            >
              {CAUSALES_CIERRE_EXPEDIENTE.map(causal => (
                <option key={causal.valor} value={causal.valor}>{causal.etiqueta}</option>
              ))}
            </select>
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="campo-archivo">
              Informe final PDF {permiteCierreSinPdf ? '(Opcional)' : '(Obligatorio)'}
            </label>
            <input
              id="campo-archivo"
              type="file"
              accept="application/pdf"
              onChange={e => setArchivo(e.target.files[0])}
              disabled={enviando}
              className="file-dropzone"
            />
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="campo-justificacion">Comentario (Opcional)</label>
            <p className="form-help">Añada un comentario o justificación para la auditoría.</p>
            <textarea
              id="campo-justificacion"
              className="form-input form-textarea"
              value={justificacion}
              onChange={e => setJustificacion(e.target.value)}
              placeholder="Comentarios de cierre..."
              rows={3}
              maxLength={LONGITUD_MAXIMA_JUSTIFICACION}
              disabled={enviando}
            />
            <div className="char-counter">
              <span>{justificacion.trim().length} / {LONGITUD_MAXIMA_JUSTIFICACION}</span>
            </div>
          </div>

          <div className="alert-error" style={{ backgroundColor: '#FFFBEB', borderColor: '#FBBF24', color: '#92400E' }}>
            <strong>Atención.</strong> Esta acción cambiará el estado de la carpeta a <strong>Cerrado</strong>. Si es una actualización periódica, podrá reabrirse luego conservando el historial.
          </div>

          {error && <div className="alert-error">{error}</div>}
        </div>

        <div className="modal-footer">
          <button
            className="btn-modal btn-modal-secondary"
            onClick={limpiarYCerrar}
            disabled={enviando}
            type="button"
          >
            Cancelar
          </button>
          <button
            className="btn-modal btn-modal-primary"
            onClick={handleConfirmar}
            disabled={!formularioValido || enviando}
            type="button"
          >
            {enviando ? 'Procesando...' : 'Finalizar Proceso'}
          </button>
        </div>

      </div>
    </div>
  );
}
