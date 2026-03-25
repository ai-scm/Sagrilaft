/**
 * Hook: useUbicacion
 *
 * Encapsula la lógica de selección jerárquica País → Departamento → Ciudad
 * usando la librería `country-state-city` como fuente de datos.
 *
 * Acepta un objeto de opciones para configurar los nombres de los campos,
 * permitiendo su reutilización en múltiples secciones del formulario
 * (empresa, representante legal, etc.) sin duplicar lógica — DRY.
 *
 * SRP : única responsabilidad = gestionar la cascada de ubicación.
 * OCP : extensible sin modificar los componentes consumidores.
 * DIP : los componentes dependen de esta interfaz, no de country-state-city.
 */

import { useMemo } from 'react';
import { Country, State, City } from 'country-state-city';

// ── Helpers de conversión a formato react-select ─────────────────────────────

const toOption = (value, label) => ({ value, label });

const countriesToOptions = () =>
  Country.getAllCountries().map(c => toOption(c.isoCode, c.name));

const statesToOptions = (countryCode) =>
  State.getStatesOfCountry(countryCode).map(s => toOption(s.isoCode, s.name));

const citiesToOptions = (countryCode, stateCode) =>
  City.getCitiesOfState(countryCode, stateCode).map(c => toOption(c.name, c.name));

// ── Genera un evento sintético compatible con handleChange de useFormulario ──

const syntheticEvent = (name, value) => ({ target: { name, value, type: 'text' } });

// ── Hook ──────────────────────────────────────────────────────────────────────

/**
 * @param {object}   formData              - Estado global del formulario.
 * @param {function} onChange              - Manejador global de cambios de campo.
 * @param {object}   [options]             - Configuración de nombres de campo.
 * @param {string}   [options.paisKey]     - Campo del país      (default: 'pais').
 * @param {string}   [options.departamentoKey] - Campo del departamento (default: 'departamento').
 * @param {string}   [options.ciudadKey]   - Campo de la ciudad  (default: 'ciudad').
 * @param {string}   [options.defaultPais] - Código ISO de país por defecto cuando
 *                                           paisKey está vacío (ej. país de la empresa).
 */
export function useUbicacion(formData, onChange, {
  paisKey         = 'pais',
  departamentoKey = 'departamento',
  ciudadKey       = 'ciudad',
  defaultPais     = '',
} = {}) {
  // Valor efectivo del país: campo propio → fallback → vacío
  const paisValue         = formData[paisKey] || defaultPais || '';
  const departamentoValue = formData[departamentoKey] || '';

  // Opciones computadas solo cuando cambia el nivel padre
  const paisesOptions        = useMemo(() => countriesToOptions(), []);
  const departamentosOptions = useMemo(() => statesToOptions(paisValue), [paisValue]);
  const ciudadesOptions      = useMemo(
    () => citiesToOptions(paisValue, departamentoValue),
    [paisValue, departamentoValue],
  );

  // Reconstruye el objeto { value, label } que react-select necesita como `value`
  const selectedPais         = paisesOptions.find(o => o.value === paisValue)         ?? null;
  const selectedDepartamento = departamentosOptions.find(o => o.value === departamentoValue) ?? null;
  const selectedCiudad       = ciudadesOptions.find(o => o.value === formData[ciudadKey]) ?? null;

  // ── Handlers: reciben la opción seleccionada de react-select ────────────────

  const handlePaisChange = (option) => {
    onChange(syntheticEvent(paisKey,         option?.value ?? ''));
    onChange(syntheticEvent(departamentoKey, ''));
    onChange(syntheticEvent(ciudadKey,       ''));
  };

  const handleDepartamentoChange = (option) => {
    onChange(syntheticEvent(departamentoKey, option?.value ?? ''));
    onChange(syntheticEvent(ciudadKey,       ''));
  };

  const handleCiudadChange = (option) => {
    onChange(syntheticEvent(ciudadKey, option?.value ?? ''));
  };

  return {
    paisesOptions,
    departamentosOptions,
    ciudadesOptions,
    selectedPais,
    selectedDepartamento,
    selectedCiudad,
    handlePaisChange,
    handleDepartamentoChange,
    handleCiudadChange,
  };
}
