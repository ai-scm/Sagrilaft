/**
 * Hook: useFormValidacion
 *
 * Gestiona el estado de errores y la lógica de validación por paso.
 * SRP: única responsabilidad = saber qué campos son válidos en cada paso.
 */
import { useState, useCallback } from 'react';
import textosAyudaCampos from '../data/helpTexts';
import { CAMPOS_REQUERIDOS, CAMPOS_CONDICIONALES } from '../data/formularioConfig';
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
        camposErr[field] = `${textosAyudaCampos[field]?.titulo || field} es obligatorio`;
      }
    }

    // Reglas especiales: longitud exacta, solo numéricos, etc.
    const reglasErr = validarReglasEspeciales(formData, campos);
    for (const [campo, mensaje] of Object.entries(reglasErr)) {
      if (!camposErr[campo]) camposErr[campo] = mensaje;
    }

    // Campos condicionales: declarados en formularioConfig — agregar nuevos allá sin tocar aquí
    for (const { condicion, campos: camposCondicionados, mensajes = {} } of (CAMPOS_CONDICIONALES[stepNum] || [])) {
      if (condicion(formData)) {
        for (const campo of camposCondicionados) {
          const valor = formData[campo];
          if (!valor || (typeof valor === 'string' && !valor.trim())) {
            camposErr[campo] = mensajes[campo] ?? `${textosAyudaCampos[campo]?.titulo || campo} es obligatorio`;
          }
        }
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
