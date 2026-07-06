import { useState } from 'react';
import { api } from '../../services/api';
import {
  CAUSAL_CIERRE_INFORME_FINAL,
  CAUSAL_CIERRE_NO_CONTINUACION_DIALOGOS,
  CAUSALES_CIERRE_EXPEDIENTE,
} from '../../config/constantes';

const LONGITUD_MAXIMA_JUSTIFICACION = 1000;

// ── Estilos ───────────────────────────────────────────────────────────────────

const s = {
  fondo: {
    position:       'fixed',
    inset:          0,
    background:     'rgba(15, 23, 42, 0.5)',
    display:        'flex',
    alignItems:     'center',
    justifyContent: 'center',
    zIndex:         200,
    padding:        '16px',
  },
  modal: {
    background:    '#fff',
    borderRadius:  'var(--radius-md, 10px)',
    boxShadow:     '0 20px 60px rgba(0,0,0,0.2)',
    width:         '100%',
    maxWidth:      '520px',
    maxHeight:     '90vh',
    overflowY:     'auto',
    display:       'flex',
    flexDirection: 'column',
  },
  encabezado: {
    padding: '24px 24px 0',
  },
  titulo: {
    fontSize:   '1.15rem',
    fontWeight: '800',
    color:      'var(--gray-900, #0f172a)',
    margin:     '0 0 8px',
  },
  descripcion: {
    fontSize:   '0.85rem',
    color:      'var(--gray-500, #64748b)',
    margin:     '0 0 24px',
    lineHeight: 1.5,
  },
  cuerpo: {
    padding: '0 24px',
    flex:    1,
  },
  etiqueta: {
    display:       'block',
    fontSize:      '0.8rem',
    fontWeight:    '700',
    color:         'var(--gray-700, #334155)',
    marginBottom:  '4px',
    letterSpacing: '0.03em',
  },
  descripcionCampo: {
    fontSize:     '0.78rem',
    color:        'var(--gray-500, #64748b)',
    margin:       '0 0 8px',
    lineHeight:   1.4,
  },
  textarea: {
    width:        '100%',
    padding:      '10px 12px',
    borderWidth:  '1.5px',
    borderStyle:  'solid',
    borderColor:  'var(--gray-300, #cbd5e1)',
    borderRadius: 'var(--radius-sm, 6px)',
    fontSize:     '0.88rem',
    lineHeight:   1.6,
    color:        'var(--gray-900, #0f172a)',
    resize:       'vertical',
    fontFamily:   'inherit',
    boxSizing:    'border-box',
    outline:      'none',
    transition:   'border-color 0.15s',
  },
  inputFile: {
    width:        '100%',
    padding:      '10px',
    border:       '1px dashed var(--gray-300, #cbd5e1)',
    borderRadius: 'var(--radius-sm, 6px)',
    cursor:       'pointer',
    marginBottom: '20px',
  },
  select: {
    width:        '100%',
    padding:      '10px 12px',
    borderWidth:  '1.5px',
    borderStyle:  'solid',
    borderColor:  'var(--gray-300, #cbd5e1)',
    borderRadius: 'var(--radius-sm, 6px)',
    fontSize:     '0.88rem',
    color:        'var(--gray-900, #0f172a)',
    background:   '#fff',
    marginBottom: '16px',
    boxSizing:    'border-box',
  },
  contadorCaracteres: {
    display:        'flex',
    justifyContent: 'space-between',
    alignItems:     'center',
    marginTop:      '4px',
    fontSize:       '0.75rem',
    color:          'var(--gray-400, #94a3b8)',
  },
  avisoInformativo: {
    marginTop:    '20px',
    padding:      '12px 14px',
    background:   '#fef2f2',
    border:       '1px solid #fca5a5',
    borderRadius: 'var(--radius-sm, 6px)',
    fontSize:     '0.83rem',
    color:        '#dc2626',
    lineHeight:   1.5,
  },
  bannerError: {
    marginTop:    '16px',
    padding:      '10px 14px',
    background:   '#fef2f2',
    border:       '1px solid #fca5a5',
    borderRadius: 'var(--radius-sm, 6px)',
    fontSize:     '0.85rem',
    color:        '#dc2626',
  },
  pie: {
    display:        'flex',
    justifyContent: 'flex-end',
    gap:            '10px',
    padding:        '20px 24px 24px',
    borderTop:      '1px solid var(--gray-100, #f1f5f9)',
    marginTop:      '20px',
  },
  btnCancelar: {
    padding:      '9px 20px',
    background:   '#fff',
    color:        'var(--gray-600, #475569)',
    border:       '1.5px solid var(--gray-300, #cbd5e1)',
    borderRadius: 'var(--radius-sm, 6px)',
    fontSize:     '0.88rem',
    fontWeight:   '600',
    cursor:       'pointer',
  },
  btnConfirmar: {
    padding:      '9px 20px',
    background:   '#0f172a',
    color:        '#fff',
    border:       'none',
    borderRadius: 'var(--radius-sm, 6px)',
    fontSize:     '0.88rem',
    fontWeight:   '700',
    cursor:       'pointer',
    transition:   'opacity 0.15s',
  },
  btnDeshabilitado: {
    opacity: 0.5,
    cursor:  'not-allowed',
  },
};

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
      onCargado(); // refrescar expediente
    } catch (err) {
      setError(err.message || 'Error al cargar el reporte final. Intente nuevamente.');
    } finally {
      setEnviando(false);
    }
  }

  if (!visible) return null;

  return (
    <div style={s.fondo} role="dialog" aria-modal="true" aria-labelledby="titulo-modal-carga-reporte">
      <div style={s.modal}>
        
        {/* Encabezado */}
        <div style={s.encabezado}>
          <h2 style={s.titulo} id="titulo-modal-carga-reporte">
            Cerrar expediente
          </h2>
          <p style={s.descripcion}>
            Seleccione la causal de cierre. El informe final en PDF es obligatorio, excepto cuando el proceso termina por no continuación de diálogos.
          </p>
        </div>

        {/* Cuerpo */}
        <div style={s.cuerpo}>

          <label style={s.etiqueta} htmlFor="campo-causal-cierre">
            Causal de cierre
          </label>
          <select
            id="campo-causal-cierre"
            value={causalCierre}
            onChange={e => {
              setCausalCierre(e.target.value);
              setError(null);
            }}
            disabled={enviando}
            style={s.select}
          >
            {CAUSALES_CIERRE_EXPEDIENTE.map(causal => (
              <option key={causal.valor} value={causal.valor}>{causal.etiqueta}</option>
            ))}
          </select>

          <label style={s.etiqueta} htmlFor="campo-archivo">
            Informe final PDF {permiteCierreSinPdf ? '(Opcional)' : '(Obligatorio)'}
          </label>
          <input
            id="campo-archivo"
            type="file"
            accept="application/pdf"
            onChange={e => setArchivo(e.target.files[0])}
            disabled={enviando}
            style={s.inputFile}
          />

          <label style={s.etiqueta} htmlFor="campo-justificacion">
            Comentario (Opcional)
          </label>
          <p style={s.descripcionCampo}>
            Añada un comentario o justificación para la auditoría.
          </p>
          <textarea
            id="campo-justificacion"
            style={s.textarea}
            value={justificacion}
            onChange={e => setJustificacion(e.target.value)}
            placeholder="Comentarios de cierre..."
            rows={4}
            maxLength={LONGITUD_MAXIMA_JUSTIFICACION}
            disabled={enviando}
          />
          <div style={s.contadorCaracteres}>
            <span>{justificacion.trim().length} / {LONGITUD_MAXIMA_JUSTIFICACION}</span>
          </div>

          <div style={s.avisoInformativo}>
            <strong>Atención.</strong> Esta acción cambiará el estado de la carpeta a <strong>Cerrado</strong>. Si es una actualización periódica, podrá reabrirse luego conservando el historial.
          </div>

          {error && <div style={s.bannerError}>{error}</div>}

        </div>

        {/* Pie */}
        <div style={s.pie}>
          <button
            style={s.btnCancelar}
            onClick={limpiarYCerrar}
            disabled={enviando}
            type="button"
          >
            Cancelar
          </button>
          <button
            style={{
              ...s.btnConfirmar,
              ...(!formularioValido || enviando ? s.btnDeshabilitado : {}),
            }}
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
