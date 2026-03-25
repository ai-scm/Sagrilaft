/**
 * LocationSelect
 *
 * Wrapper presentacional de react-select que replica exactamente los estilos
 * del sistema de diseño SAGRILAFT (variables CSS de index.css).
 *
 * Acepta la misma interfaz visual que FormField para uso intercambiable:
 * label, name, required, value, onChange, options, error, disabled, onOpenHelp.
 *
 * SRP : solo renderiza — sin lógica de negocio ni estado.
 * OCP : los estilos se calculan a partir de props; no requiere modificación.
 */

import Select from 'react-select';
import { HelpIcon } from './HelpPanel';
import helpTexts from '../data/helpTexts';
import { buildSelectStyles } from '../utils/selectStyles';

// ── Componente ────────────────────────────────────────────────────────────────

export default function LocationSelect({
  label,
  name,
  required = false,
  value,
  onChange,
  options = [],
  error,
  disabled = false,
  placeholder = 'Seleccione...',
  onOpenHelp,
}) {
  const hasHelp = !!helpTexts[name];

  return (
    <div className="form-group">
      <label className="form-label">
        {label}
        {required && <span className="required-mark">*</span>}
        {hasHelp && <HelpIcon fieldKey={name} onOpenHelp={onOpenHelp} />}
      </label>

      <Select
        inputId={name}
        name={name}
        value={value}
        onChange={onChange}
        options={options}
        isDisabled={disabled}
        isClearable
        placeholder={placeholder}
        noOptionsMessage={() => 'Sin opciones'}
        styles={buildSelectStyles(!!error, !!value)}
      />

      {error && <div className="field-error">{error}</div>}
    </div>
  );
}
