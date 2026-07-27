import { useState, useEffect, useMemo } from 'react';
import FormField from './FormField';
import { obtenerLocaleMoneda } from '../../../../shared/utils/formatoMoneda';

/**
 * Formatea un valor a string con separadores de miles según el locale dado.
 * Elimina todo carácter no numérico antes de formatear.
 * Retorna '' para valores vacíos o no numéricos.
 */
function formatearNumero(rawNum, locale) {
  if (rawNum === undefined || rawNum === null || rawNum === '') return '';
  const cleanNum = String(rawNum).replace(/\D/g, '');
  if (!cleanNum) return '';
  return new Intl.NumberFormat(locale).format(Number(cleanNum));
}

/**
 * CurrencyInput
 *
 * Envuelve FormField para campos monetarios. Muestra el valor formateado
 * con separadores de miles según la moneda seleccionada, pero propaga
 * al estado del formulario el valor numérico puro (sin separadores).
 *
 * Props:
 *   value    — valor numérico puro (string o number) desde el estado del formulario.
 *   onChange — handler del formulario (recibirá el valor numérico puro como e.target.value).
 *   name     — nombre del campo.
 *   label    — etiqueta visible.
 *   symbol   — símbolo de la moneda (ej. "$", "US$", "€").
 *   currency — código ISO de la moneda (ej. "COP", "USD"). Determina el locale de formato.
 */
export default function CurrencyInput({
  value,
  onChange,
  name,
  label,
  symbol = '$',
  currency,
  ...rest
}) {
  const [displayValue, setDisplayValue] = useState('');

  // Derivar el locale del código de moneda; fallback a es-CO si no está mapeado.
  const locale = useMemo(
    () => obtenerLocaleMoneda(currency),
    [currency],
  );

  // Sincronizar la visualización cuando el valor externo o la moneda cambian.
  // Depende de [value, locale] para re-formatear al cambiar de moneda.
  useEffect(() => {
    setDisplayValue(formatearNumero(value, locale));
  }, [value, locale]);

  const handleChange = (e) => {
    const rawValue = e.target.value;

    // Extraer solo dígitos: valor real que se persiste en el estado del formulario.
    const numericValue = rawValue.replace(/\D/g, '');

    // Actualizar la representación visual con el formato correcto.
    setDisplayValue(formatearNumero(numericValue, locale));

    // Propagar el valor numérico puro al formulario padre.
    if (onChange) {
      e.target.value = numericValue;
      onChange(e);
    }
  };

  return (
    <div className="currency-input-wrapper">
      <FormField
        label={label}
        name={name}
        type="text"
        value={displayValue}
        comparisonValue={value}
        onChange={handleChange}
        className="currency-input-field"
        inputMode="numeric"
        renderInputWrapper={(inputElement) => (
          <div className="currency-input-group">
            {symbol && (
              <span className="currency-prefix" aria-hidden="true">
                {symbol}
              </span>
            )}
            {inputElement}
          </div>
        )}
        {...rest}
      />
    </div>
  );
}
