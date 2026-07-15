import { useState } from 'react';
import { api } from '../../services/api';
import './Modals.css';

const LONGITUD_MINIMA_JUSTIFICACION = 20;
const LONGITUD_MAXIMA_JUSTIFICACION = 1000;

export default function ModalCargaManual({ visible, formularioId, onCargado, onCancelar }) {
  const [justificacion, setJustificacion] = useState('');
  const [archivo, setArchivo]             = useState(null);
  const [enviando, setEnviando]           = useState(false);
  const [error, setError]                 = useState(null);

  function resetearEstado() {
    setJustificacion('');
    setArchivo(null);
    setError(null);
  }

  function limpiarYCerrar() {
    resetearEstado();
    onCancelar();
  }

  const justificacionValida = justificacion.trim().length >= LONGITUD_MINIMA_JUSTIFICACION;
  const archivoValido = archivo && archivo.type === 'application/pdf';
  const formularioValido = justificacionValida && archivoValido;

  async function handleConfirmar() {
    if (!formularioValido) return;

    setEnviando(true);
    setError(null);

    try {
      await api.cargarFormularioManual(formularioId, archivo, justificacion.trim());
      resetearEstado();
      onCargado();
    } catch (err) {
      setError(err.message || 'Error al cargar el formulario. Intente nuevamente.');
    } finally {
      setEnviando(false);
    }
  }

  if (!visible) return null;

  return (
    <div className="modal-overlay" role="dialog" aria-modal="true" aria-labelledby="titulo-modal-carga">
      <div className="modal-container">
        
        <div className="modal-header">
          <h2 className="modal-title" id="titulo-modal-carga">
            Cargar Formulario Manualmente
          </h2>
          <p className="modal-desc">
            Suba un documento PDF y documente la justificación. Esta acción creará
            una nueva versión y reanudará el flujo de revisión del expediente automáticamente.
          </p>
        </div>

        <div className="modal-body">
          <div className="form-group">
            <label className="form-label" htmlFor="campo-archivo">Archivo PDF</label>
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
            <label className="form-label" htmlFor="campo-justificacion">Justificación del cargue manual</label>
            <p className="form-help">
              Uso interno — requerido por compliance para la trazabilidad (mín. 20 caracteres).
            </p>
            <textarea
              id="campo-justificacion"
              className="form-input form-textarea"
              value={justificacion}
              onChange={e => setJustificacion(e.target.value)}
              placeholder="Describa el motivo por el cual está subiendo el formulario manualmente..."
              rows={4}
              maxLength={LONGITUD_MAXIMA_JUSTIFICACION}
              disabled={enviando}
            />
            <div className="char-counter">
              <span>{justificacion.trim().length} / {LONGITUD_MAXIMA_JUSTIFICACION}</span>
              {!justificacionValida && justificacion.trim().length > 0 && (
                <span className="text-error">Mínimo {LONGITUD_MINIMA_JUSTIFICACION} caracteres</span>
              )}
            </div>
          </div>

          <div className="alert-info">
            Al confirmar, el formulario pasará a estado <strong>Enviado</strong> para su respectiva validación y alertas.
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
            {enviando ? 'Cargando...' : 'Confirmar Carga'}
          </button>
        </div>

      </div>
    </div>
  );
}
