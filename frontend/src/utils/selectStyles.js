/**
 * Estilos react-select alineados al Design System SAGRILAFT.
 * Fuente única de verdad para todos los componentes basados en react-select.
 *
 * hasError  → borde rojo + sombra roja
 * hasValue  → borde verde cuando hay valor válido
 */
export const buildSelectStyles = (hasError, hasValue) => ({
  control: (base, state) => ({
    ...base,
    minHeight: '40px',
    padding: '0 2px',
    fontSize: '0.9rem',
    fontFamily: 'inherit',
    color: '#1e293b',
    backgroundColor: state.isDisabled ? '#f8fafc' : 'white',
    border: `1.5px solid ${
      state.isFocused ? '#818cf8'
      : hasError       ? '#ef4444'
      : hasValue       ? '#10b981'
      : '#cbd5e1'
    }`,
    borderRadius: '6px',
    boxShadow: state.isFocused
      ? '0 0 0 3px #eef2ff'
      : hasError
        ? '0 0 0 3px #fee2e2'
        : 'none',
    transition: 'all 0.2s ease',
    cursor: state.isDisabled ? 'not-allowed' : 'default',
    opacity: state.isDisabled ? 0.6 : 1,
    '&:hover': { borderColor: state.isFocused ? '#818cf8' : '#94a3b8' },
  }),
  valueContainer: (base) => ({ ...base, padding: '2px 10px' }),
  placeholder: (base) => ({
    ...base,
    color: '#94a3b8',
    fontWeight: 400,
    fontSize: '0.9rem',
  }),
  singleValue: (base) => ({ ...base, color: '#1e293b', fontSize: '0.9rem' }),
  menu: (base) => ({
    ...base,
    borderRadius: '6px',
    boxShadow: '0 4px 6px -1px rgba(0,0,0,0.1), 0 2px 4px -1px rgba(0,0,0,0.06)',
    border: '1px solid #e2e8f0',
    zIndex: 50,
  }),
  menuList: (base) => ({ ...base, padding: '4px' }),
  option: (base, state) => ({
    ...base,
    fontSize: '0.9rem',
    borderRadius: '4px',
    padding: '8px 12px',
    backgroundColor: state.isSelected ? '#4f46e5' : state.isFocused ? '#eef2ff' : 'white',
    color: state.isSelected ? 'white' : '#334155',
    cursor: 'pointer',
    '&:active': { backgroundColor: '#e0e7ff' },
  }),
  indicatorSeparator: () => ({ display: 'none' }),
  dropdownIndicator: (base, state) => ({
    ...base,
    color: state.isDisabled ? '#cbd5e1' : '#94a3b8',
    padding: '0 8px',
    transition: 'transform 0.2s ease',
    transform: state.selectProps.menuIsOpen ? 'rotate(180deg)' : 'rotate(0deg)',
  }),
  clearIndicator: (base) => ({
    ...base,
    color: '#94a3b8',
    padding: '0 4px',
    '&:hover': { color: '#ef4444' },
  }),
  noOptionsMessage: (base) => ({ ...base, fontSize: '0.875rem', color: '#94a3b8' }),
  loadingMessage:   (base) => ({ ...base, fontSize: '0.875rem', color: '#94a3b8' }),
});
