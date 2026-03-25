/**
 * Hook: useFormValidacion
 *
 * Gestiona el estado de errores y la lógica de validación por paso.
 * SRP: única responsabilidad = saber qué campos son válidos en cada paso.
 */
import { useState, useCallback } from 'react';
import helpTexts from '../data/helpTexts';
import { CAMPOS_REQUERIDOS } from '../data/formularioConfig';
import { validarReglasEspeciales } from '../utils/inputValidation';

export function useFormValidacion(formData) {
  const [errors, setErrors] = useState({});

  /** Valida los campos requeridos de un paso. Retorna el mapa de errores (sin mutar estado). */
  const validarPaso = useCallback((stepNum) => {
    const campos = CAMPOS_REQUERIDOS[stepNum] || [];
    const camposErr = {};

    for (const field of campos) {
      const valor = formData[field];
      if (!valor || (typeof valor === 'string' && !valor.trim())) {
        camposErr[field] = `${helpTexts[field]?.titulo || field} es obligatorio`;
      }
    }

    // Reglas especiales: longitud exacta, solo numéricos, etc.
    const reglasErr = validarReglasEspeciales(formData, campos);
    for (const [campo, mensaje] of Object.entries(reglasErr)) {
      if (!camposErr[campo]) camposErr[campo] = mensaje;
    }

    // Campos condicionales: solo obligatorios según el tipo de persona
    if (stepNum === 3 && formData.tipo_persona === 'natural') {
      if (!formData.ciudad_residencia) {
        camposErr.ciudad_residencia = 'Ciudad de Residencia es obligatoria';
      }
    }

    return camposErr;
  }, [formData]);

  /** Aplica un mapa de errores al estado (usado por handleNext y handleSubmit). */
  const aplicarErrores = useCallback((mapaErrores) => {
    setErrors(mapaErrores);
  }, []);

  /** Limpia el error de un campo específico (usado por handleChange). */
  const limpiarError = useCallback((nombre) => {
    setErrors(prev => {
      if (!prev[nombre]) return prev;
      return { ...prev, [nombre]: null };
    });
  }, []);

  return { errors, validarPaso, aplicarErrores, limpiarError };
}
