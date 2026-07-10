import React from 'react';

// ── Estilos ───────────────────────────────────────────────────────────────────
const s = {
  fondo: {
    position:       'fixed',
    inset:          0,
    background:     'rgba(15, 23, 42, 0.5)',
    display:        'flex',
    alignItems:     'center',
    justifyContent: 'center',
    zIndex:         300,
    padding:        '16px',
  },
  modal: {
    background:    '#fff',
    borderRadius:  'var(--radius-md, 10px)',
    boxShadow:     '0 20px 60px rgba(0,0,0,0.2)',
    width:         '100%',
    maxWidth:      '420px',
    padding:       '24px',
    display:       'flex',
    flexDirection: 'column',
  },
  titulo: {
    fontSize:   '1.15rem',
    fontWeight: '800',
    color:      'var(--gray-900, #0f172a)',
    margin:     '0 0 12px',
  },
  mensaje: {
    fontSize:   '0.9rem',
    color:      'var(--gray-600, #475569)',
    margin:     '0 0 24px',
    lineHeight: 1.5,
  },
  botones: {
    display:        'flex',
    justifyContent: 'flex-end',
    gap:            '12px',
  },
  btnCancelar: {
    padding:      '9px 18px',
    background:   '#fff',
    color:        'var(--gray-600, #475569)',
    border:       '1.5px solid var(--gray-300, #cbd5e1)',
    borderRadius: 'var(--radius-sm, 6px)',
    fontSize:     '0.88rem',
    fontWeight:   '600',
    cursor:       'pointer',
  },
  btnConfirmar: {
    padding:      '9px 18px',
    background:   'var(--primary-600, #2563eb)',
    color:        '#fff',
    border:       'none',
    borderRadius: 'var(--radius-sm, 6px)',
    fontSize:     '0.88rem',
    fontWeight:   '700',
    cursor:       'pointer',
    transition:   'opacity 0.15s',
  },
  btnDeshabilitado: {
    opacity: 0.6,
    cursor:  'not-allowed',
  },
};

export default function ModalConfirmacion({
  visible,
  titulo,
  mensaje,
  children,
  textoConfirmar = 'Confirmar',
  textoCancelar = 'Cancelar',
  onConfirmar,
  onCancelar,
  ocupado = false,
  colorConfirmar = 'var(--primary-600, #2563eb)',
}) {
  if (!visible) return null;

  return (
    <div style={s.fondo} role="dialog" aria-modal="true" aria-labelledby="titulo-modal-confirmacion">
      <div style={s.modal}>
        <h3 style={s.titulo} id="titulo-modal-confirmacion">{titulo}</h3>
        {children ?? <p style={s.mensaje}>{mensaje}</p>}
        <div style={s.botones}>
          <button
            style={s.btnCancelar}
            onClick={onCancelar}
            disabled={ocupado}
            type="button"
          >
            {textoCancelar}
          </button>
          <button
            style={{
              ...s.btnConfirmar,
              background: colorConfirmar,
              ...(ocupado ? s.btnDeshabilitado : {}),
            }}
            onClick={onConfirmar}
            disabled={ocupado}
            type="button"
          >
            {ocupado ? 'Procesando…' : textoConfirmar}
          </button>
        </div>
      </div>
    </div>
  );
}
