/**
 * ModalRechazo — panel para rechazar un formulario SAGRILAFT de forma definitiva.
 *
 * El operador documenta dos cosas con propósitos distintos:
 *   1. Motivo interno (obligatorio): justificación de compliance, solo visible en auditoría.
 *   2. Mensaje al destinatario (opcional): lo que la contraparte recibirá por correo.
 *
 * La separación garantiza que el razonamiento interno de compliance nunca
 * llegue al exterior.
 */

import { useState } from 'react';
import { api } from '../../services/api';

const LONGITUD_MINIMA_MOTIVO              = 20;
const LONGITUD_MAXIMA_MOTIVO              = 1000;
const LONGITUD_MINIMA_MENSAJE_DESTINATARIO = 10;
const LONGITUD_MAXIMA_MENSAJE_DESTINATARIO = 500;

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
  separador: {
    borderTop:  '1px dashed var(--gray-200, #e2e8f0)',
    margin:     '20px 0',
  },
  etiqueta: {
    display:       'block',
    fontSize:      '0.8rem',
    fontWeight:    '700',
    color:         'var(--gray-700, #334155)',
    marginBottom:  '4px',
    letterSpacing: '0.03em',
  },
  etiquetaOpcional: {
    fontSize:      '0.75rem',
    fontWeight:    '400',
    color:         'var(--gray-400, #94a3b8)',
    marginLeft:    '6px',
    letterSpacing: '0',
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
  textareaActivo: {
    borderColor: 'var(--primary-500, #3b82f6)',
  },
  contadorCaracteres: {
    display:        'flex',
    justifyContent: 'space-between',
    alignItems:     'center',
    marginTop:      '4px',
    fontSize:       '0.75rem',
    color:          'var(--gray-400, #94a3b8)',
  },
  avisoMinimo: {
    color: 'var(--orange-600, #ea580c)',
  },
  avisoDefinitivo: {
    marginTop:    '20px',
    padding:      '12px 14px',
    background:   '#fef2f2',
    border:       '1px solid #fca5a5',
    borderRadius: 'var(--radius-sm, 6px)',
    fontSize:     '0.83rem',
    color:        '#991b1b',
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
    background:   '#991b1b',
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

// ── Sub-componente reutilizable ───────────────────────────────────────────────

function CampoTextarea({
  id,
  label,
  descripcion,
  esOpcional,
  valor,
  onChange,
  longitudMinima,
  longitudMaxima,
  placeholder,
  filas = 4,
  deshabilitado = false,
}) {
  const [enfocado, setEnfocado] = useState(false);
  const longitudActual = valor.trim().length;
  const cumpleMinimo   = longitudActual === 0 || longitudActual >= longitudMinima;

  return (
    <div>
      <label style={s.etiqueta} htmlFor={id}>
        {label}
        {esOpcional && <span style={s.etiquetaOpcional}>(opcional)</span>}
      </label>
      {descripcion && <p style={s.descripcionCampo}>{descripcion}</p>}
      <textarea
        id={id}
        style={{ ...s.textarea, ...(enfocado ? s.textareaActivo : {}) }}
        value={valor}
        onChange={e => onChange(e.target.value)}
        onFocus={() => setEnfocado(true)}
        onBlur={() => setEnfocado(false)}
        placeholder={placeholder}
        rows={filas}
        maxLength={longitudMaxima}
        disabled={deshabilitado}
      />
      <div style={s.contadorCaracteres}>
        <span>{longitudActual} / {longitudMaxima}</span>
        {!cumpleMinimo && longitudActual > 0 && (
          <span style={s.avisoMinimo}>Mínimo {longitudMinima} caracteres</span>
        )}
      </div>
    </div>
  );
}

// ── Componente principal ──────────────────────────────────────────────────────

export default function ModalRechazo({ visible, formularioId, onRechazado, onCancelar }) {
  const [motivoInterno, setMotivoInterno]                       = useState('');
  const [mensajeParaDestinatario, setMensajeParaDestinatario]   = useState('');
  const [enviando, setEnviando]                                 = useState(false);
  const [error, setError]                                       = useState(null);

  function resetearEstado() {
    setMotivoInterno('');
    setMensajeParaDestinatario('');
    setError(null);
  }

  function limpiarYCerrar() {
    resetearEstado();
    onCancelar();
  }

  const motivoValido = motivoInterno.trim().length >= LONGITUD_MINIMA_MOTIVO;
  const mensajeParaDestinatarioValido = (
    mensajeParaDestinatario.trim().length === 0 ||
    mensajeParaDestinatario.trim().length >= LONGITUD_MINIMA_MENSAJE_DESTINATARIO
  );
  const formularioValido = motivoValido && mensajeParaDestinatarioValido;

  async function handleConfirmar() {
    if (!formularioValido) return;

    setEnviando(true);
    setError(null);

    try {
      await api.rechazarExpediente(formularioId, {
        motivo:                    motivoInterno.trim(),
        mensaje_para_destinatario: mensajeParaDestinatario.trim() || null,
      });
      resetearEstado();
      onRechazado();
    } catch (errorRechazo) {
      setError(errorRechazo.message || 'Error al procesar el rechazo. Intente nuevamente.');
    } finally {
      setEnviando(false);
    }
  }

  if (!visible) return null;

  return (
    <div style={s.fondo} role="dialog" aria-modal="true" aria-labelledby="titulo-modal-rechazo">
      <div style={s.modal}>

        {/* Encabezado */}
        <div style={s.encabezado}>
          <h2 style={s.titulo} id="titulo-modal-rechazo">
            Rechazar formulario
          </h2>
          <p style={s.descripcion}>
            Documente el motivo internamente y, si lo considera necesario,
            redacte un mensaje para notificar al destinatario.
          </p>
        </div>

        {/* Cuerpo */}
        <div style={s.cuerpo}>

          {/* Campo 1: motivo interno — queda en auditoría, no sale al exterior */}
          <CampoTextarea
            id="campo-motivo-interno"
            label="Motivo del rechazo"
            descripcion="Uso interno — queda en la auditoría del expediente. No se envía al destinatario."
            esOpcional={false}
            valor={motivoInterno}
            onChange={setMotivoInterno}
            longitudMinima={LONGITUD_MINIMA_MOTIVO}
            longitudMaxima={LONGITUD_MAXIMA_MOTIVO}
            placeholder="Describa la razón de compliance por la que se rechaza este formulario…"
            filas={4}
            deshabilitado={enviando}
          />

          <div style={s.separador} />

          {/* Campo 2: mensaje al destinatario — opcional, va en el correo */}
          <CampoTextarea
            id="campo-mensaje-destinatario"
            label="Mensaje para el destinatario"
            descripcion="Si lo completa, se enviará al destinatario por correo. No incluya el motivo interno."
            esOpcional={true}
            valor={mensajeParaDestinatario}
            onChange={setMensajeParaDestinatario}
            longitudMinima={LONGITUD_MINIMA_MENSAJE_DESTINATARIO}
            longitudMaxima={LONGITUD_MAXIMA_MENSAJE_DESTINATARIO}
            placeholder="Ej: Su formulario no pudo ser procesado. Comuníquese con su ejecutivo de cuenta…"
            filas={3}
            deshabilitado={enviando}
          />

          <div style={s.avisoDefinitivo}>
            Esta acción es definitiva. El formulario pasará a estado <strong>Rechazado</strong> y
            no podrá retomarse sin crear un nuevo link de diligenciamiento.
          </div>

          {error && <div style={s.bannerError}>{error}</div>}

        </div>

        {/* Pie con acciones */}
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
            {enviando ? 'Rechazando…' : 'Confirmar rechazo'}
          </button>
        </div>

      </div>
    </div>
  );
}
