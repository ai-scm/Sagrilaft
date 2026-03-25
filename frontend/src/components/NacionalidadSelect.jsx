/**
 * NacionalidadSelect
 *
 * Dropdown con buscador para seleccionar nacionalidad.
 * - Muestra nombres de países en español (i18n-iso-countries).
 * - Guarda el código ISO 3166-1 alpha-2 en el estado del formulario.
 * - Emite un evento sintético compatible con onChange de FormField.
 *
 * Interfaz idéntica a FormField: value (código ISO) + onChange ({ target }).
 */

import { useMemo } from 'react';
import Select from 'react-select';
import countries from 'i18n-iso-countries';
import esLocale from 'i18n-iso-countries/langs/es.json';
import { HelpIcon } from './HelpPanel';
import helpTexts from '../data/helpTexts';
import { buildSelectStyles } from '../utils/selectStyles';

countries.registerLocale(esLocale);

/** Lista de países ordenada alfabéticamente en español. */
const PAISES_OPTIONS = Object.entries(countries.getNames('es', { select: 'official' }))
  .map(([code, name]) => ({ value: code, label: name }))
  .sort((a, b) => a.label.localeCompare(b.label, 'es'));

export default function NacionalidadSelect({
  name = 'nacionalidad',
  required = false,
  value,
  onChange,
  onOpenHelp,
  error,
  placeholder = 'Seleccione un país...',
}) {
  const hasHelp = !!helpTexts[name];

  // Convierte el código ISO almacenado en el option que react-select necesita
  const selectedOption = useMemo(
    () => PAISES_OPTIONS.find((o) => o.value === value) ?? null,
    [value],
  );

  const handleChange = (option) => {
    onChange({ target: { name, value: option?.value ?? '', type: 'text' } });
  };

  return (
    <div className="form-group">
      <label className="form-label">
        Nacionalidad
        {required && <span className="required-mark">*</span>}
        {hasHelp && <HelpIcon fieldKey={name} onOpenHelp={onOpenHelp} />}
      </label>

      <Select
        inputId={name}
        name={name}
        value={selectedOption}
        onChange={handleChange}
        options={PAISES_OPTIONS}
        isClearable
        placeholder={placeholder}
        noOptionsMessage={() => 'Sin resultados'}
        styles={buildSelectStyles(!!error, !!value)}
      />

      {error && <div className="field-error">{error}</div>}
    </div>
  );
}
