/**
 * Hook: useFormValidacion
 *
 * Gestiona el estado de errores y la lógica de validación por paso.
 * SRP: única responsabilidad = saber qué campos son válidos en cada paso.
 */
import { useState, useCallback } from 'react';
import textosAyudaCampos from '../../data/helpTexts';
import { CAMPOS_REQUERIDOS, CAMPOS_CONDICIONALES } from '../../data/formularioConfig';
import { validarReglasEspeciales } from '../../utils/inputValidation';

/**
 * Determina si un valor de campo está vacío o sin seleccionar.
 * Soporta cadenas de texto, arreglos (selects multi-valor) y valores nulos.
 */
function esCampoVacio(valor) {
  if (valor === null || valor === undefined) return true;
  if (typeof valor === 'string') return !valor.trim();
  if (Array.isArray(valor)) return valor.length === 0;
  return false;
}

/** Genera el mensaje de error predeterminado para un campo obligatorio vacío. */
function mensajeObligatorio(campo, mensajesPersonalizados) {
  return mensajesPersonalizados[campo]
    ?? `${textosAyudaCampos[campo]?.titulo || campo} es obligatorio`;
}

export function useFormValidacion(formData) {
  const [errors, setErrors] = useState({});

  /** Valida los campos requeridos de un paso. Retorna el mapa de errores (sin mutar estado). */
  const validarPaso = useCallback((stepNum) => {
    const camposRequeridos = CAMPOS_REQUERIDOS[stepNum] || [];
    const errores = {};

    for (const campo of camposRequeridos) {
      if (esCampoVacio(formData[campo])) {
        errores[campo] = mensajeObligatorio(campo, {});
      }
    }

    // Reglas especiales: longitud exacta, solo numéricos, formato correo, etc.
    const reglasErr = validarReglasEspeciales(formData, camposRequeridos);
    for (const [campo, mensaje] of Object.entries(reglasErr)) {
      if (!errores[campo]) errores[campo] = mensaje;
    }

    // Campos condicionales: declarados en formularioConfig — agregar nuevos allá sin tocar aquí.
    for (const { condicion, campos: camposCondicionados, mensajes = {} } of (CAMPOS_CONDICIONALES[stepNum] || [])) {
      if (condicion(formData)) {
        for (const campo of camposCondicionados) {
          if (esCampoVacio(formData[campo])) {
            errores[campo] = mensajeObligatorio(campo, mensajes);
          }
        }
      }
    }

    return errores;
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
