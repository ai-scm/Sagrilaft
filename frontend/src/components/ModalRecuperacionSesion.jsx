/**
 * ModalRecuperacionSesion
 *
 * Diálogo de recuperación de sesión. Permite al usuario identificarse con
 * código de petición + PIN para retomar un formulario SAGRILAFT generado
 * mediante acceso manual, desde cualquier dispositivo.
 *
 * Props:
 *   visible        {boolean}  Controla la visibilidad del modal.
 *   error          {string}   Mensaje de error de la última búsqueda (o null).
 *   cargando       {boolean}  Indica que la búsqueda está en curso.
 *   fechaBorrador  {string}   ISO timestamp del borrador local detectado (o null).
 *   onRecuperar    {Function} Callback (codigoPeticion, pin) => void.
 *   onDescartar    {Function} Callback sin parámetros; cierra y descarta el borrador.
 */

import { useState, useEffect, useRef } from 'react';

const estilos = {
  overlay: {
    position: 'fixed', inset: 0,
    background: 'rgba(15, 23, 42, 0.6)',
    backdropFilter: 'blur(4px)',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    zIndex: 9999,
    padding: '16px',
  },
  tarjeta: {
    background: '#fff',
    borderRadius: 'var(--radius-lg)',
    boxShadow: 'var(--shadow-xl)',
    padding: '36px 40px',
    width: '100%',
    maxWidth: '440px',
  },
  icono: {
    fontSize: '2rem',
    marginBottom: '12px',
  },
  titulo: {
    fontSize: '1.2rem',
    fontWeight: '700',
    color: 'var(--gray-900)',
    marginBottom: '8px',
  },
  descripcion: {
    fontSize: '0.88rem',
    color: 'var(--gray-500)',
    lineHeight: '1.5',
    marginBottom: '24px',
  },
  label: {
    display: 'block',
    fontSize: '0.82rem',
    fontWeight: '600',
    color: 'var(--gray-700)',
    marginBottom: '6px',
  },
  input: {
    width: '100%',
    padding: '10px 14px',
    borderWidth: '1.5px',
    borderStyle: 'solid',
    borderColor: 'var(--gray-200)',
    borderRadius: 'var(--radius-md)',
    fontSize: '0.9rem',
    color: 'var(--gray-800)',
    outline: 'none',
    marginBottom: '16px',
    transition: 'border-color 0.15s',
    fontFamily: 'monospace',
    letterSpacing: '0.05em',
  },
  inputFocus: {
    borderColor: 'var(--primary-500)',
  },
  error: {
    fontSize: '0.82rem',
    color: 'var(--error)',
    background: 'var(--error-light)',
    borderRadius: 'var(--radius-sm)',
    padding: '8px 12px',
    marginBottom: '16px',
  },
  btnPrimario: {
    width: '100%',
    padding: '11px 0',
    background: 'var(--primary-600)',
    color: '#fff',
    border: 'none',
    borderRadius: 'var(--radius-md)',
    fontSize: '0.9rem',
    fontWeight: '600',
    cursor: 'pointer',
    marginBottom: '12px',
    transition: 'background 0.15s',
  },
  btnSecundario: {
    width: '100%',
    padding: '9px 0',
    background: 'transparent',
    color: 'var(--gray-500)',
    border: '1.5px solid var(--gray-200)',
    borderRadius: 'var(--radius-md)',
    fontSize: '0.85rem',
    cursor: 'pointer',
    transition: 'color 0.15s, border-color 0.15s',
  },
  chip: {
    display: 'inline-block',
    fontSize: '0.78rem',
    color: 'var(--primary-700)',
    background: 'var(--primary-50)',
    borderRadius: 'var(--radius-sm)',
    padding: '3px 10px',
    marginBottom: '20px',
    fontWeight: '600',
  },
};

export default function ModalRecuperacionSesion({
  visible, error, cargando, fechaBorrador, codigoInicial,
  onRecuperar, onDescartar,
}) {
  const [codigoPeticion, setCodigoPeticion] = useState('');
  const [pin, setPin]                       = useState('');
  const [codigoFocus, setCodigoFocus]       = useState(false);
  const [pinFocus, setPinFocus]             = useState(false);
  const pinRef                              = useRef(null);

  // Sincroniza el input de código cuando el modal se abre con un código conocido
  // (post-refresh o sesión expirada). Resetea ambos campos al cerrar.
  useEffect(() => {
    if (visible) {
      if (codigoInicial) {
        setCodigoPeticion(codigoInicial);
        // Código ya conocido: enfocar directamente el PIN
        setTimeout(() => pinRef.current?.focus(), 50);
      }
    } else {
      setCodigoPeticion('');
      setPin('');
    }
  }, [visible, codigoInicial]);

  if (!visible) return null;

  const fechaLegible = fechaBorrador
    ? new Date(fechaBorrador).toLocaleString('es-CO', {
      day: '2-digit', month: 'short', year: 'numeric',
      hour: '2-digit', minute: '2-digit',
    })
    : null;

  const puedeEnviar = codigoPeticion.trim() && pin.trim() && !cargando;

  const handleSubmit = (e) => {
    e.preventDefault();
    if (puedeEnviar) onRecuperar(codigoPeticion.trim().toUpperCase(), pin.trim().toUpperCase());
  };

  return (
    <div style={estilos.overlay} role="dialog" aria-modal="true" aria-labelledby="modal-recuperacion-titulo">
      <div style={estilos.tarjeta}>
        <div style={estilos.icono}>🔐</div>

        <h2 id="modal-recuperacion-titulo" style={estilos.titulo}>
          Recuperar Formulario en Curso
        </h2>

        {fechaLegible ? (
          <>
            <div style={estilos.chip}>Borrador guardado: {fechaLegible}</div>
            <p style={estilos.descripcion}>
              {codigoInicial
                ? 'Por seguridad, ingrese su PIN para continuar donde lo dejó.'
                : 'Encontramos un formulario guardado en este dispositivo. Ingrese sus credenciales de acceso para retomar donde lo dejó.'}
            </p>
          </>
        ) : (
          <p style={estilos.descripcion}>
            {codigoInicial
              ? 'Su sesión ha expirado. Ingrese su PIN para continuar.'
              : 'Ingrese el código de petición y PIN que recibió por correo electrónico para recuperar su formulario desde cualquier dispositivo.'}
          </p>
        )}

        <form onSubmit={handleSubmit}>
          <label style={estilos.label} htmlFor="rec-codigo">
            Código de petición
          </label>
          <input
            id="rec-codigo"
            type="text"
            autoComplete="off"
            placeholder="Ej. SAG-3A7F2B1C"
            value={codigoPeticion}
            onChange={e => setCodigoPeticion(e.target.value)}
            onFocus={() => setCodigoFocus(true)}
            onBlur={() => setCodigoFocus(false)}
            style={{
              ...estilos.input,
              ...(codigoFocus ? estilos.inputFocus : {}),
              ...(codigoInicial ? { background: 'var(--gray-50)', color: 'var(--gray-500)' } : {}),
            }}
            disabled={cargando}
            readOnly={!!codigoInicial}
          />

          <label style={estilos.label} htmlFor="rec-pin">
            PIN de acceso
          </label>
          <input
            id="rec-pin"
            ref={pinRef}
            type="password"
            autoComplete="off"
            placeholder="PIN de 8 caracteres"
            value={pin}
            onChange={e => setPin(e.target.value)}
            onFocus={() => setPinFocus(true)}
            onBlur={() => setPinFocus(false)}
            style={{ ...estilos.input, ...(pinFocus ? estilos.inputFocus : {}) }}
            disabled={cargando}
          />

          {error && <div style={estilos.error} role="alert">{error}</div>}

          <button
            type="submit"
            style={{
              ...estilos.btnPrimario,
              opacity: puedeEnviar ? 1 : 0.55,
              cursor: puedeEnviar ? 'pointer' : 'not-allowed',
            }}
            disabled={!puedeEnviar}
          >
            {cargando ? 'Verificando credenciales…' : 'Recuperar sesión'}
          </button>
        </form>

        <button
          type="button"
          style={estilos.btnSecundario}
          onClick={onDescartar}
          disabled={cargando}
        >
          Comenzar desde cero
        </button>
      </div>
    </div>
  );
}
