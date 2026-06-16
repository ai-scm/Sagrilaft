/**
 * ModalCorreoDestinatario
 *
 * Modal bloqueante que solicita el correo electrónico al cliente/proveedor
 * antes de que pueda acceder al formulario de diligenciamiento.
 *
 * Comportamiento:
 *   - Se monta encima de toda la UI (z-index alto + overlay con blur).
 *   - No puede cerrarse sin ingresar un correo válido (no hay botón X, no
 *     se cierra al hacer clic en el overlay).
 *   - Valida el formato de correo en tiempo real antes de habilitar el botón.
 *   - Muestra estados de carga y error correctamente.
 *
 * Props:
 *   visible      {boolean}   Controla la visibilidad del modal.
 *   enviando     {boolean}   True mientras se persiste el correo en el backend.
 *   error        {string}    Mensaje de error de la última llamada (o null).
 *   onConfirmar  {Function}  Callback (correo: string) => void. Se llama al confirmar.
 */

import { useState, useRef, useEffect } from 'react';

const REGEX_CORREO = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

// ── Estilos ────────────────────────────────────────────────────────────────────

const estilos = {
  overlay: {
    position:       'fixed',
    inset:          0,
    background:     'rgba(15, 23, 42, 0.65)',
    backdropFilter: 'blur(6px)',
    display:        'flex',
    alignItems:     'center',
    justifyContent: 'center',
    zIndex:         9999,
    padding:        '16px',
  },
  tarjeta: {
    background:   '#fff',
    borderRadius: 'var(--radius-lg)',
    boxShadow:    'var(--shadow-xl)',
    padding:      '40px',
    width:        '100%',
    maxWidth:     '460px',
    textAlign:    'center',
  },
  icono: {
    fontSize:     '2.4rem',
    marginBottom: '12px',
    lineHeight:   1,
  },
  titulo: {
    fontSize:     '1.2rem',
    fontWeight:   '700',
    color:        'var(--gray-900)',
    marginBottom: '8px',
    marginTop:    0,
  },
  disclaimer: {
    fontSize:     '0.875rem',
    color:        'var(--gray-500)',
    lineHeight:   '1.6',
    marginBottom: '28px',
    textAlign:    'left',
  },
  label: {
    display:      'block',
    fontSize:     '0.82rem',
    fontWeight:   '600',
    color:        'var(--gray-700)',
    marginBottom: '6px',
    textAlign:    'left',
  },
  input: {
    width:         '100%',
    padding:       '11px 14px',
    borderWidth:   '1.5px',
    borderStyle:   'solid',
    borderColor:   'var(--gray-200)',
    borderRadius:  'var(--radius-md)',
    fontSize:      '0.9rem',
    color:         'var(--gray-800)',
    outline:       'none',
    marginBottom:  '8px',
    transition:    'border-color 0.15s',
    boxSizing:     'border-box',
  },
  inputFocus: {
    borderColor: 'var(--primary-500)',
  },
  inputError: {
    borderColor: 'var(--error)',
  },
  errorValidacion: {
    fontSize:     '0.8rem',
    color:        'var(--error)',
    textAlign:    'left',
    marginBottom: '12px',
    minHeight:    '18px',
  },
  errorApi: {
    fontSize:     '0.82rem',
    color:        'var(--error)',
    background:   'var(--error-light)',
    borderRadius: 'var(--radius-sm)',
    padding:      '8px 12px',
    marginBottom: '16px',
    textAlign:    'left',
  },
  btn: {
    width:        '100%',
    padding:      '12px 0',
    background:   'var(--primary-600)',
    color:        '#fff',
    border:       'none',
    borderRadius: 'var(--radius-md)',
    fontSize:     '0.9rem',
    fontWeight:   '600',
    cursor:       'pointer',
    transition:   'background 0.15s, opacity 0.15s',
    marginTop:    '4px',
  },
  notaSeguridad: {
    fontSize:   '0.75rem',
    color:      'var(--gray-400)',
    marginTop:  '14px',
    lineHeight: '1.5',
  },
};

// ── Componente ────────────────────────────────────────────────────────────────

export default function ModalCorreoDestinatario({ visible, enviando, error, onConfirmar }) {
  const [correo,    setCorreo]    = useState('');
  const [enfocado,  setEnfocado]  = useState(false);
  const [tocado,    setTocado]    = useState(false);

  const inputRef = useRef(null);

  // Enfocar el input al mostrarse el modal
  useEffect(() => {
    if (visible) {
      setTimeout(() => inputRef.current?.focus(), 60);
    }
  }, [visible]);

  if (!visible) return null;

  const correoValido  = REGEX_CORREO.test(correo.trim());
  const mostrarError  = tocado && !correoValido;
  const puedeEnviar   = correoValido && !enviando;

  const handleChange = (e) => {
    setCorreo(e.target.value);
    if (!tocado) setTocado(true);
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    setTocado(true);
    if (puedeEnviar) onConfirmar(correo.trim().toLowerCase());
  };

  const estiloInput = {
    ...estilos.input,
    ...(enfocado   ? estilos.inputFocus  : {}),
    ...(mostrarError ? estilos.inputError : {}),
  };

  const estiloBtn = {
    ...estilos.btn,
    opacity: puedeEnviar ? 1 : 0.55,
    cursor:  puedeEnviar ? 'pointer' : 'not-allowed',
  };

  return (
    <div style={estilos.overlay} role="dialog" aria-modal="true" aria-labelledby="modal-correo-titulo">
      <div style={estilos.tarjeta}>

        <div style={estilos.icono}>✉️</div>

        <h2 id="modal-correo-titulo" style={estilos.titulo}>
          Confirme su correo electrónico
        </h2>

        <p style={estilos.disclaimer}>
          Para continuar con el diligenciamiento y garantizar que reciba las notificaciones
          de su proceso, por favor confirme la dirección de correo electrónico a la que
          desea que lleguen las comunicaciones y el documento final.
        </p>

        <form onSubmit={handleSubmit} noValidate>
          <label style={estilos.label} htmlFor="correo-destinatario-input">
            Correo electrónico
          </label>
          <input
            id="correo-destinatario-input"
            ref={inputRef}
            type="email"
            autoComplete="email"
            placeholder="ejemplo@empresa.com"
            value={correo}
            onChange={handleChange}
            onFocus={() => setEnfocado(true)}
            onBlur={() => { setEnfocado(false); setTocado(true); }}
            style={estiloInput}
            disabled={enviando}
            required
          />
          <div style={estilos.errorValidacion}>
            {mostrarError && 'Ingrese un correo electrónico válido.'}
          </div>

          {error && (
            <div style={estilos.errorApi} role="alert">
              {error}
            </div>
          )}

          <button type="submit" style={estiloBtn} disabled={!puedeEnviar}>
            {enviando ? 'Guardando…' : 'Continuar al formulario →'}
          </button>
        </form>

        <p style={estilos.notaSeguridad}>
          🔒 Su información está protegida. Solo se usará para el proceso SAGRILAFT.
        </p>
      </div>
    </div>
  );
}
