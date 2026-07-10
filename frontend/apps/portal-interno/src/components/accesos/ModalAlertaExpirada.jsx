export default function ModalAlertaExpirada({ isOpen, onClose }) {
  if (!isOpen) return null;

  const estiloFondo = {
    position: 'fixed',
    top: 0,
    left: 0,
    width: '100%',
    height: '100%',
    backgroundColor: 'rgba(0, 0, 0, 0.5)',
    display: 'flex',
    justifyContent: 'center',
    alignItems: 'center',
    zIndex: 1000,
    padding: '20px',
    boxSizing: 'border-box'
  };

  const estiloModalContenedor = {
    width: '100%',
    maxWidth: '400px',
    border: '1px solid #E2E8F0',
    borderRadius: '12px',
    padding: '24px',
    fontFamily: 'sans-serif',
    boxShadow: '0 10px 25px rgba(0,0,0,0.1)',
    background: 'white',
    boxSizing: 'border-box',
    position: 'relative'
  };

  const estiloIcono = {
    background: '#F8FAFC',
    padding: '8px',
    borderRadius: '50%',
    color: '#64748B',
    fontSize: '1.2rem',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    border: '1px solid #E2E8F0',
    width: '24px',
    height: '24px'
  };

  return (
    <div style={estiloFondo} onClick={onClose}>
      <div style={estiloModalContenedor} onClick={(e) => e.stopPropagation()}>
        <button 
          onClick={onClose}
          style={{ position: 'absolute', top: '16px', right: '16px', background: 'transparent', border: 'none', fontSize: '1.4rem', cursor: 'pointer', color: '#94A3B8', padding: 0, lineHeight: 1 }}
          title="Cerrar"
        >
          &times;
        </button>

        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '16px' }}>
          <div style={estiloIcono}>
            <span role="img" aria-label="Reloj">⏱️</span>
          </div>
          <h3 style={{ margin: 0, color: '#0F172A', fontSize: '1.05rem', fontWeight: 600 }}>
            Ventana de gracia concluida
          </h3>
        </div>

        <p style={{ margin: '0 0 16px 0', color: '#475569', fontSize: '0.9rem', lineHeight: 1.5 }}>
          Las credenciales completas de este acceso ya no se encuentran disponibles.
        </p>

        <div style={{ background: '#FEFCE8', borderLeft: '3px solid #FDE047', padding: '10px 14px', borderRadius: '0 6px 6px 0', display: 'flex', flexDirection: 'column', gap: '4px', marginBottom: '24px' }}>
          <span style={{ color: '#854D0E', fontSize: '0.85rem', lineHeight: 1.4 }}>
            <strong>Por tu seguridad:</strong> El PIN ha sido descartado permanentemente del sistema. Genere un nuevo acceso para obtener un nuevo PIN y código de petición si aún necesitas que el destinatario acceda al formulario. (Recordar que las credenciales le llega al Correo electrónico representante legal *)
          </span>
        </div>

        <button 
          onClick={onClose}
          style={{ width: '100%', padding: '11px 0', background: 'var(--gray-100, #F1F5F9)', color: '#334155', border: 'none', borderRadius: '8px', fontSize: '0.9rem', fontWeight: 600, cursor: 'pointer', transition: 'background 0.15s' }}
          onMouseEnter={(e) => e.currentTarget.style.background = '#E2E8F0'}
          onMouseLeave={(e) => e.currentTarget.style.background = 'var(--gray-100, #F1F5F9)'}
        >
          Entendido
        </button>
      </div>
    </div>
  );
}
