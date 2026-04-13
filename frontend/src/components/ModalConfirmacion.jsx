import React from 'react';

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
    fontSize: '2.5rem',
    marginBottom: '16px',
    textAlign: 'center',
  },
  titulo: {
    fontSize: '1.2rem',
    fontWeight: '700',
    color: 'var(--gray-900)',
    marginBottom: '12px',
    textAlign: 'center',
  },
  descripcion: {
    fontSize: '0.95rem',
    color: 'var(--gray-600)',
    lineHeight: '1.5',
    marginBottom: '32px',
    textAlign: 'center',
  },
  acciones: {
    display: 'flex',
    gap: '12px',
    justifyContent: 'flex-end',
  },
  btnPrimario: {
    flex: 1,
    padding: '11px 0',
    background: '#ef4444', // Red for destructive action
    color: '#fff',
    border: 'none',
    borderRadius: 'var(--radius-md)',
    fontSize: '0.95rem',
    fontWeight: '600',
    cursor: 'pointer',
    transition: 'background 0.15s',
  },
  btnSecundario: {
    flex: 1,
    padding: '11px 0',
    background: 'transparent',
    color: 'var(--gray-600)',
    border: '1.5px solid var(--gray-200)',
    borderRadius: 'var(--radius-md)',
    fontSize: '0.95rem',
    fontWeight: '600',
    cursor: 'pointer',
    transition: 'color 0.15s, border-color 0.15s',
  },
};

export default function ModalConfirmacion({
  visible,
  titulo = '¿Está seguro?',
  mensaje = 'Esta acción no se puede deshacer.',
  onConfirm,
  onCancel,
}) {
  if (!visible) return null;

  return (
    <div style={estilos.overlay} role="dialog" aria-modal="true" aria-labelledby="modal-confirmacion-titulo">
      <div style={estilos.tarjeta}>
        <div style={estilos.icono}>⚠️</div>

        <h2 id="modal-confirmacion-titulo" style={estilos.titulo}>
          {titulo}
        </h2>

        <p style={estilos.descripcion}>
          {mensaje}
        </p>

        <div style={estilos.acciones}>
          <button
            type="button"
            style={estilos.btnSecundario}
            onClick={onCancel}
          >
            Cancelar
          </button>
          <button
            type="button"
            style={estilos.btnPrimario}
            onClick={onConfirm}
          >
            Confirmar
          </button>
        </div>
      </div>
    </div>
  );
}
