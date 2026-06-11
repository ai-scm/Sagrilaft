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
import textosAyudaCampos from '../data/helpTexts';
import { buildSelectStyles } from '../utils/selectStyles';
import { useCorreccion } from '../context/CorreccionContext';

countries.registerLocale(esLocale);

/** Lista de países ordenada alfabéticamente en español. */
const PAISES_OPCIONES = Object.entries(countries.getNames('es', { select: 'official' }))
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
  const { esCampoConCorreccion } = useCorreccion();
  const marcado = esCampoConCorreccion(name);
  const tieneValor = !!value;
  const correccionPendiente  = marcado && !tieneValor && !error;
  const correccionCompletada = marcado && tieneValor;

  const tieneAyuda = !!textosAyudaCampos[name];

  const groupClasses = [
    'form-group',
    correccionPendiente  ? 'correccion-pendiente'  : '',
    correccionCompletada ? 'correccion-completada' : '',
  ].filter(Boolean).join(' ');

  // Convierte el código ISO almacenado en el option que react-select necesita
  const opcionSeleccionada = useMemo(
    () => PAISES_OPCIONES.find((opcion) => opcion.value === value) ?? null,
    [value],
  );

  const handleChange = (opcionElegida) => {
    onChange({ target: { name, value: opcionElegida?.value ?? '', type: 'text' } });
  };

  return (
    <div className={groupClasses}>
      <label className="form-label">
        Nacionalidad
        {required && <span className="required-mark">*</span>}
        {correccionPendiente && (
          <span className="correccion-mark" title="Este campo requiere corrección" aria-label="Requiere corrección">
            ✎
          </span>
        )}
        {correccionCompletada && (
          <span className="correccion-ok-mark" title="Corrección completada" aria-label="Corregido">
            ✓
          </span>
        )}
        {tieneAyuda && <HelpIcon fieldKey={name} onOpenHelp={onOpenHelp} />}
      </label>

      <Select
        inputId={name}
        name={name}
        value={opcionSeleccionada}
        onChange={handleChange}
        options={PAISES_OPCIONES}
        isClearable
        placeholder={placeholder}
        noOptionsMessage={() => 'Sin resultados'}
        styles={buildSelectStyles(!!error, tieneValor, correccionPendiente)}
      />

      {correccionPendiente && !error && (
        <div className="correccion-aviso">Este campo requiere corrección</div>
      )}
      {correccionCompletada && (
        <div className="correccion-aviso correccion-aviso--ok">Corrección completada</div>
      )}
      {error && <div className="field-error">{error}</div>}
    </div>
  );
}
