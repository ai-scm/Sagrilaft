/**
 * Hook: useUbicacion
 *
 * Encapsula la lógica de selección jerárquica País → Departamento → Ciudad
 * usando la librería `country-state-city` como fuente de datos.
 *
 * SRP : única responsabilidad = gestionar la cascada de ubicación.
 * OCP : extensible (ej. agregar subciudad) sin tocar PasoInfoBasica.
 * DIP : PasoInfoBasica depende de esta interfaz, no de country-state-city.
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

export function useUbicacion(formData, onChange) {
  const paisValue       = formData.pais        || '';
  const departamentoValue = formData.departamento || '';

  // Opciones computadas solo cuando cambia el nivel padre
  const paisesOptions        = useMemo(() => countriesToOptions(), []);
  const departamentosOptions = useMemo(() => statesToOptions(paisValue),                  [paisValue]);
  const ciudadesOptions      = useMemo(() => citiesToOptions(paisValue, departamentoValue), [paisValue, departamentoValue]);

  // Reconstruye el objeto { value, label } que react-select necesita como `value`
  const selectedPais        = paisesOptions.find(o => o.value === paisValue)         ?? null;
  const selectedDepartamento = departamentosOptions.find(o => o.value === departamentoValue) ?? null;
  const selectedCiudad      = ciudadesOptions.find(o => o.value === formData.ciudad) ?? null;

  // ── Handlers: reciben la opción seleccionada de react-select ────────────────

  const handlePaisChange = (option) => {
    onChange(syntheticEvent('pais',         option?.value ?? ''));
    onChange(syntheticEvent('departamento', ''));
    onChange(syntheticEvent('ciudad',       ''));
  };

  const handleDepartamentoChange = (option) => {
    onChange(syntheticEvent('departamento', option?.value ?? ''));
    onChange(syntheticEvent('ciudad',       ''));
  };

  const handleCiudadChange = (option) => {
    onChange(syntheticEvent('ciudad', option?.value ?? ''));
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
