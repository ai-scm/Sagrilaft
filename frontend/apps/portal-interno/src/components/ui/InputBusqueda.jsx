/**
 * InputBusqueda — Componente de búsqueda reutilizable.
 *
 * Entrada de búsqueda consistente para aplicarse en diferentes contextos
 * (formularios, accesos, etc.). Mantiene estilo uniforme y comportamiento.
 */

const s = {
  input: {
    flex:         1,
    minWidth:     '160px',
    padding:      '7px 12px',
    border:       '1.5px solid var(--gray-200, #e2e8f0)',
    borderRadius: 'var(--radius-sm, 6px)',
    fontSize:     '0.82rem',
    color:        'var(--gray-800, #1e293b)',
    outline:      'none',
  },
};

export default function InputBusqueda({
  valor,
  onChange,
  placeholder = 'Buscar…',
  estiloPersonalizado = {}
}) {
  return (
    <input
      type="search"
      placeholder={placeholder}
      value={valor}
      onChange={e => onChange(e.target.value)}
      style={{ ...s.input, ...estiloPersonalizado }}
    />
  );
}
