import React from 'react';

const estilos = {
  textAlign: 'center',
  color:     'var(--gray-400, #94a3b8)',
  padding:   '48px 0',
  fontSize:  '0.9rem',
};

export default function Spinner({ texto = 'Cargando...', style = {} }) {
  return (
    <div style={{ ...estilos, ...style }}>
      {texto}
    </div>
  );
}
