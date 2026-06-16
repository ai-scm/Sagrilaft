import { HelpIcon } from './HelpPanel';
import textosAyudaCampos from '../data/helpTexts';
import { getInputProps } from '../utils/inputValidation';
import { useCorreccion } from '../context/CorreccionContext';

/**
 * Campo de formulario reutilizable con tooltip de ayuda integrado.
 * Soporta input, select y textarea.
 *
 * Cuando el formulario está en estado EN_CORRECCION y el campo fue identificado
 * por el área, se aplica la clase CSS `requiere-correccion` que el tema resuelve
 * visualmente (borde rojo + ícono). No requiere prop adicional.
 */
export default function FormField({
  label, name, type = 'text', required = false,
  value, onChange, onOpenHelp, placeholder,
  error, options, children,
  className = '', renderInputWrapper, comparisonValue, ...rest
}) {
  const { esCampoConCorreccion, valorOriginalDeCampo } = useCorreccion();
  const marcadoParaCorreccion = esCampoConCorreccion(name);

  const valorParaComparar = comparisonValue ?? value;
  const valorActualNormalizado = normalizarValorComparable(valorParaComparar);
  const valorOriginal = marcadoParaCorreccion ? valorOriginalDeCampo(name) : undefined;
  const valorOriginalNormalizado = normalizarValorComparable(valorOriginal);
  const tieneValor = valorActualNormalizado !== '' && !error;
  const fueModificado = tieneValor && valorActualNormalizado !== valorOriginalNormalizado;
  const correccionPendiente  = marcadoParaCorreccion && !fueModificado;
  const correccionCompletada = marcadoParaCorreccion && fueModificado;

  const tieneAyuda = !!textosAyudaCampos[name];
  const placeholderText = placeholder || (textosAyudaCampos[name]?.ejemplo ? `Ej: ${textosAyudaCampos[name].ejemplo}` : '');
  const inputProps = type !== 'select' && type !== 'textarea' ? getInputProps(name) : {};

  const clasesCampo = [
    type === 'textarea' ? 'form-textarea' : (type === 'select' ? 'form-select' : 'form-input'),
    error ? 'error' : '',
    tieneValor ? 'valid' : '',
  ].filter(Boolean).join(' ');

  const clasesGrupo = [
    'form-group',
    correccionPendiente  ? 'correccion-pendiente'  : '',
    correccionCompletada ? 'correccion-completada' : '',
    className,
  ].filter(Boolean).join(' ');

  return (
    <div className={clasesGrupo}>
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

      {type === 'select' ? (
        <select name={name} className={clasesCampo} value={value ?? ''} onChange={onChange} {...rest}>
          <option value="">Seleccione...</option>
          {options?.map(opcion => (
            <option key={opcion.value} value={opcion.value}>{opcion.label}</option>
          ))}
        </select>
      ) : type === 'textarea' ? (
        <textarea
          name={name} className={clasesCampo} value={value ?? ''}
          onChange={onChange} placeholder={placeholderText} rows={3} {...rest}
        />
      ) : (
        (() => {
          const inputEl = (
            <input
              type={type} name={name} className={clasesCampo}
              value={value ?? ''} onChange={onChange} placeholder={placeholderText}
              {...inputProps} {...rest}
            />
          );
          return renderInputWrapper ? renderInputWrapper(inputEl) : inputEl;
        })()
      )}

      {correccionPendiente && !error && (
        <div className="correccion-aviso">Este campo requiere corrección</div>
      )}
      {correccionCompletada && (
        <div className="correccion-aviso correccion-aviso--ok">Corrección completada</div>
      )}
      {error && <div className="field-error">{error}</div>}
      {children}
    </div>
  );
}

function normalizarValorComparable(valor) {
  if (valor === null || valor === undefined) return '';
  if (typeof valor === 'string') return valor.trim().replace(/\s+/g, ' ');
  if (Array.isArray(valor)) {
    return `[${valor.map(item => normalizarValorComparable(item)).join(',')}]`;
  }
  if (typeof valor === 'object') {
    const entradas = Object.keys(valor).sort().map(clave => `${clave}:${normalizarValorComparable(valor[clave])}`);
    return `{${entradas.join(',')}}`;
  }
  return String(valor).trim();
}
