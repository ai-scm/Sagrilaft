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
import textosAyudaCampos from '../data/helpTexts';
import { buildSelectStyles } from '../utils/selectStyles';
import { useCorreccion } from '../context/CorreccionContext';
import { fueValorModificado, normalizarValorComparable } from '../utils/comparacionCorreccion';

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
  const { esCampoConCorreccion } = useCorreccion();
  const marcado = esCampoConCorreccion(name);
  const { valorOriginalDeCampo } = useCorreccion();

  // Si `value` es un objeto de react-select ({ value, label }), comparar su `value`
  const valorParaComparar = (value && typeof value === 'object' && 'value' in value) ? value.value : value;
  const valorActualNormalizado = normalizarValorComparable(valorParaComparar);
  const valorOriginal = marcado ? valorOriginalDeCampo(name) : undefined;
  const tieneValor = valorActualNormalizado !== '' && !error;
  const fueModificado = fueValorModificado(valorParaComparar, valorOriginal);
  const correccionPendiente  = marcado && !fueModificado;
  const correccionCompletada = marcado && fueModificado;

  const tieneAyuda = !!textosAyudaCampos[name];

  const groupClasses = [
    'form-group',
    correccionPendiente  ? 'correccion-pendiente'  : '',
    correccionCompletada ? 'correccion-completada' : '',
  ].filter(Boolean).join(' ');

  return (
    <div className={groupClasses}>
      <label className="form-label">
        {label}
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
        value={value}
        onChange={onChange}
        options={options}
        isDisabled={disabled}
        isClearable
        placeholder={placeholder}
        noOptionsMessage={() => 'Sin opciones'}
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
