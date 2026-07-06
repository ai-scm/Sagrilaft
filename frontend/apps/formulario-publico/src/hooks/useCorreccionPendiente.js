/**
 * Hook: useCorreccionPendiente
 *
 * Analiza el estado de corrección de un formulario EN_CORRECCION y expone
 * las primitivas que necesitan el formulario y sus campos para presentar
 * la información de forma contextualizada.
 *
 * SRP  : única responsabilidad = derivar el estado de corrección activa.
 * OCP  : extender campos no requiere cambiar este hook, solo el catálogo.
 * DIP  : consume CATALOGO_CORRECCIONES como abstracción; no conoce componentes.
 */

import { useMemo, useCallback } from 'react';
import { CATALOGO_CORRECCIONES } from '@shared/data/catalogoCorrecciones';
import { MODO_TRABAJO_ACTUALIZACION_REABIERTA } from '@shared/utils/constantes';

const ESTADO_EN_CORRECCION = 'en_correccion';

/**
 * @typedef {Object} CorreccionPendiente
 * @property {boolean}  activa                   - true cuando el formulario está en corrección
 * @property {string}   especificaciones          - texto libre con la descripción del área
 * @property {Set<string>} camposIdentificados    - IDs de campos que requieren corrección
 * @property {number|null} pasoInicialCorreccion  - paso donde se ubica el primer campo marcado
 * @property {function(string): boolean} esCampoConCorreccion - true si el campo está marcado
 */

/**
 * Parsea `campos_a_corregir` con compatibilidad hacia atrás:
 * - JSON nuevo: { tipo?, especificaciones, campos: [...] }
 * - Texto plano (registros pre-migración): se trata como especificación sin campos marcados
 */
function _parsearCorreccion(raw) {
  if (!raw) return { tipo: 'correccion', especificaciones: '', campos: [] };
  try {
    const parsed = JSON.parse(raw);
    return {
      tipo:             parsed.tipo ?? 'correccion',
      especificaciones: parsed.especificaciones ?? '',
      campos:           Array.isArray(parsed.campos) ? parsed.campos : [],
    };
  } catch {
    // Compatibilidad con el formato de texto plano anterior
    return { tipo: 'correccion', especificaciones: raw, campos: [] };
  }
}

/**
 * Determina el primer paso del formulario que contiene alguno de los campos marcados.
 * Retorna null si no hay campos identificados o ninguno coincide con el catálogo.
 */
function _calcularPasoInicial(camposIdentificados) {
  if (camposIdentificados.size === 0) return null;
  for (const grupo of CATALOGO_CORRECCIONES) {
    if (grupo.campos.some(c => camposIdentificados.has(c.id))) {
      return grupo.paso;
    }
  }
  return null;
}

/**
 * @param {string} estadoFormulario  - valor del enum EstadoFormulario del backend
 * @param {string|null} camposACorregirRaw - valor crudo de campos_a_corregir (JSON o texto)
 * @returns {CorreccionPendiente}
 */
export function useCorreccionPendiente(estadoFormulario, camposACorregirRaw) {
  const correccion = useMemo(() => {
    if (estadoFormulario !== ESTADO_EN_CORRECCION) {
      return { especificaciones: '', campos: [] };
    }
    return _parsearCorreccion(camposACorregirRaw);
  }, [estadoFormulario, camposACorregirRaw]);

  const camposIdentificados = useMemo(
    () => new Set(correccion.campos),
    [correccion.campos],
  );

  const pasoInicialCorreccion = useMemo(
    () => _calcularPasoInicial(camposIdentificados),
    [camposIdentificados],
  );

  const esCampoConCorreccion = useCallback(
    (nombreCampo) => camposIdentificados.has(nombreCampo),
    [camposIdentificados],
  );

  return {
    activa:                estadoFormulario === ESTADO_EN_CORRECCION,
    esActualizacionReabierta: correccion.tipo === MODO_TRABAJO_ACTUALIZACION_REABIERTA,
    especificaciones:      correccion.especificaciones,
    camposIdentificados,
    pasoInicialCorreccion,
    esCampoConCorreccion,
  };
}
