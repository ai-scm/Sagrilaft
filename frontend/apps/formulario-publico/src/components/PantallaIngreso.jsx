import { useState } from 'react';
import { useDiligenciamiento } from '../context/DiligenciamientoContext';

const estilos = {
  container: {
    minHeight: '100vh',
    display: 'flex', 
    flexDirection: 'column',
    alignItems: 'center', 
    justifyContent: 'center',
    background: 'var(--gray-50)',
    padding: '20px',
  },
  tarjeta: {
    background: '#fff',
    borderRadius: 'var(--radius-lg)',
    boxShadow: 'var(--shadow-xl)',
    padding: '40px',
    width: '100%',
    maxWidth: '480px',
  },
  header: {
    textAlign: 'center',
    marginBottom: '30px',
  },
  tituloLogo: {
    fontSize: '1.5rem',
    fontWeight: '800',
    color: 'var(--primary-700)',
    marginBottom: '4px',
    letterSpacing: '-0.02em',
  },
  subtituloLogo: {
    fontSize: '0.85rem',
    color: 'var(--gray-500)',
    textTransform: 'uppercase',
    letterSpacing: '0.05em',
  },
  icono: {
    fontSize: '2.5rem',
    marginBottom: '16px',
    textAlign: 'center',
  },
  titulo: {
    fontSize: '1.3rem',
    fontWeight: '700',
    color: 'var(--gray-900)',
    marginBottom: '10px',
    textAlign: 'center',
  },
  descripcion: {
    fontSize: '0.95rem',
    color: 'var(--gray-600)',
    lineHeight: '1.5',
    marginBottom: '24px',
    textAlign: 'center',
  },
  label: {
    display: 'block',
    fontSize: '0.85rem',
    fontWeight: '600',
    color: 'var(--gray-700)',
    marginBottom: '8px',
  },
  input: {
    width: '100%',
    padding: '12px 16px',
    borderWidth: '1.5px',
    borderStyle: 'solid',
    borderColor: 'var(--gray-200)',
    borderRadius: 'var(--radius-md)',
    fontSize: '1rem',
    color: 'var(--gray-800)',
    outline: 'none',
    marginBottom: '20px',
    transition: 'border-color 0.15s',
    fontFamily: 'monospace',
    letterSpacing: '0.05em',
  },
  inputFocus: {
    borderColor: 'var(--primary-500)',
  },
  error: {
    fontSize: '0.85rem',
    color: 'var(--error)',
    background: 'var(--error-light)',
    borderRadius: 'var(--radius-sm)',
    padding: '10px 14px',
    marginBottom: '20px',
  },
  btnPrimario: {
    width: '100%',
    padding: '14px 0',
    background: 'var(--primary-600)',
    color: '#fff',
    border: 'none',
    borderRadius: 'var(--radius-md)',
    fontSize: '1rem',
    fontWeight: '600',
    cursor: 'pointer',
    marginBottom: '16px',
    transition: 'background 0.15s',
  },
  btnSecundario: {
    width: '100%',
    padding: '12px 0',
    background: 'transparent',
    color: 'var(--gray-500)',
    border: '1.5px solid var(--gray-200)',
    borderRadius: 'var(--radius-md)',
    fontSize: '0.9rem',
    cursor: 'pointer',
    transition: 'color 0.15s, border-color 0.15s',
  },
  chip: {
    display: 'inline-block',
    fontSize: '0.8rem',
    color: 'var(--primary-700)',
    background: 'var(--primary-50)',
    borderRadius: 'var(--radius-sm)',
    padding: '4px 12px',
    marginBottom: '20px',
    fontWeight: '600',
  },
  loader: {
    textAlign: 'center',
    padding: '40px',
    color: 'var(--gray-500)',
    fontSize: '1.1rem',
  }
};

export default function PantallaIngreso() {
  const { 
    ingresarConCredenciales, 
    cargando, 
    error, 
    borradorLocal, 
    descartarBorrador 
  } = useDiligenciamiento();
  
  const [codigoPeticion, setCodigoPeticion] = useState(borradorLocal?.codigoPeticion || '');
  const [pin, setPin] = useState('');
  const [codigoFocus, setCodigoFocus] = useState(false);
  const [pinFocus, setPinFocus] = useState(false);

  if (cargando) {
    return (
      <div style={estilos.container}>
        <div style={estilos.loader}>Validando acceso seguro...</div>
      </div>
    );
  }

  const fechaLegible = borradorLocal?.guardadoEn
    ? new Date(borradorLocal.guardadoEn).toLocaleString('es-CO', {
      day: '2-digit', month: 'short', year: 'numeric',
      hour: '2-digit', minute: '2-digit',
    })
    : null;

  const puedeEnviar = codigoPeticion.trim() && pin.trim() && !cargando;

  const handleSubmit = (e) => {
    e.preventDefault();
    if (puedeEnviar) ingresarConCredenciales(codigoPeticion.trim().toUpperCase(), pin.trim().toUpperCase());
  };

  return (
    <div style={estilos.container}>
      <div style={estilos.header}>
        <div style={estilos.tituloLogo}>SAGRILAFT</div>
        <div style={estilos.subtituloLogo}>Portal de Diligenciamiento</div>
      </div>

      <div style={estilos.tarjeta}>
        <div style={estilos.icono}>🔐</div>

        <h2 style={estilos.titulo}>
          Acceso Seguro
        </h2>

        {fechaLegible ? (
          <div style={{ textAlign: 'center' }}>
            <div style={estilos.chip}>Borrador guardado: {fechaLegible}</div>
            <p style={estilos.descripcion}>
              Encontramos un formulario guardado en este dispositivo. Ingrese su PIN para retomar donde lo dejó.
            </p>
          </div>
        ) : (
          <p style={estilos.descripcion}>
            Para iniciar o continuar, ingrese el código de petición y PIN que recibió por correo electrónico.
          </p>
        )}

        <form onSubmit={handleSubmit}>
          <label style={estilos.label} htmlFor="ingreso-codigo">
            Código de petición
          </label>
          <input
            id="ingreso-codigo"
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
            }}
            disabled={cargando}
          />

          <label style={estilos.label} htmlFor="ingreso-pin">
            PIN de acceso
          </label>
          <input
            id="ingreso-pin"
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
            {cargando ? 'Verificando...' : 'Ingresar'}
          </button>
        </form>

        {borradorLocal && (
          <button
            type="button"
            style={estilos.btnSecundario}
            onClick={descartarBorrador}
            disabled={cargando}
          >
            Ingresar con otras credenciales
          </button>
        )}
      </div>
    </div>
  );
}
