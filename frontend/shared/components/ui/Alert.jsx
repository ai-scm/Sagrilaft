import React from 'react';

const estilos = {
  background:   '#fef2f2',
  border:       '1px solid #fca5a5',
  borderRadius: 'var(--radius-md, 8px)',
  color:        '#dc2626',
  padding:      '12px 16px',
  fontSize:     '0.85rem',
  textAlign:    'center',
};

export default function Alert({ mensaje, style = {} }) {
  if (!mensaje) return null;
  return (
    <div style={{ ...estilos, ...style }} role="alert">
      {mensaje}
    </div>
  );
}
