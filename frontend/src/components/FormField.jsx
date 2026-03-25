import { HelpIcon } from './HelpPanel';
import helpTexts from '../data/helpTexts';
import { getInputProps } from '../utils/inputValidation';

/**
 * Campo de formulario reutilizable con tooltip de ayuda integrado.
 * Soporta input, select y textarea.
 */
export default function FormField({
  label, name, type = 'text', required = false,
  value, onChange, onOpenHelp, placeholder,
  error, options, children,
  className = '', ...rest
}) {
  const hasHelp = !!helpTexts[name];
  const placeholderText = placeholder || (helpTexts[name]?.ejemplo ? `Ej: ${helpTexts[name].ejemplo}` : '');
  const inputProps = type !== 'select' && type !== 'textarea' ? getInputProps(name) : {};

  const fieldClasses = [
    type === 'textarea' ? 'form-textarea' : (type === 'select' ? 'form-select' : 'form-input'),
    error ? 'error' : '',
    value && !error ? 'valid' : '',
  ].filter(Boolean).join(' ');

  return (
    <div className={`form-group ${className}`}>
      <label className="form-label">
        {label}
        {required && <span className="required-mark">*</span>}
        {hasHelp && <HelpIcon fieldKey={name} onOpenHelp={onOpenHelp} />}
      </label>

      {type === 'select' ? (
        <select name={name} className={fieldClasses} value={value || ''} onChange={onChange} {...rest}>
          <option value="">Seleccione...</option>
          {options?.map(opt => (
            <option key={opt.value} value={opt.value}>{opt.label}</option>
          ))}
        </select>
      ) : type === 'textarea' ? (
        <textarea
          name={name} className={fieldClasses} value={value || ''}
          onChange={onChange} placeholder={placeholderText} rows={3} {...rest}
        />
      ) : (
        <input
          type={type} name={name} className={fieldClasses}
          value={value || ''} onChange={onChange} placeholder={placeholderText}
          {...inputProps} {...rest}
        />
      )}

      {error && <div className="field-error">{error}</div>}
      {children}
    </div>
  );
}
