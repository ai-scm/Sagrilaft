/**
 * Hook: useEstadoCorreccionGlobal
 *
 * Determina en tiempo real qué campos marcados para corrección ya fueron
 * subsanados y si la corrección global está completa.
 *
 * Separa campos simples (en formData) de campos-tabla (junta, accionistas,
 * referencias, etc.) para aplicar la estrategia de comparación adecuada:
 *   - Campo simple   : corregido si el valor actual difiere del valor original.
 *   - Campo tabla    : corregido si el array actual difiere del snapshot original.
 *
 * SRP : única responsabilidad = derivar el avance de la corrección.
 * OCP : agregar nuevos tipos de campo-tabla solo requiere extender CAMPOS_TABLA
 *       y CLAVE_TABLA_POR_CAMPO; no modifica la lógica central.
 * DIP : recibe datos como parámetros; no conoce ni al contexto ni a los componentes.
 */

import { useMemo } from 'react';

// IDs del catálogo que corresponden a tablas dinámicas (no viven en formData)
const CAMPOS_TABLA = new Set([
  'junta_directiva',
  'accionistas',
  'beneficiario_final',
  'referencias_comerciales',
  'referencias_bancarias',
  'informacion_bancaria_pagos',
]);

// Mapea ID del catálogo → clave del objeto tablasActuales / tablasOriginales
const CLAVE_TABLA_POR_CAMPO = {
  junta_directiva:            'juntaDirectiva',
  accionistas:                'accionistas',
  beneficiario_final:         'beneficiarios',
  referencias_comerciales:    'referenciasComerciales',
  referencias_bancarias:      'referenciasBancarias',
  informacion_bancaria_pagos: 'infoBancariaPagos',
};

/**
 * Compara dos snapshots de tabla usando serialización JSON.
 * Retorna false cuando no existe original (formulario sin snapshot previo),
 * evitando falsos positivos de "corrección completada".
 */
function _tablaFueModificada(actual, original) {
  if (!original) return false;
  return JSON.stringify(actual) !== JSON.stringify(original);
}

/**
 * @param {object} params
 * @param {Set<string>}  params.camposIdentificados  - campos marcados por el portal
 * @param {object}       params.formDataActual        - valores actuales de campos simples
 * @param {object}       params.formDataOriginal      - snapshot de campos simples al cargar
 * @param {object|null}  params.tablasActuales        - { juntaDirectiva, accionistas, ... }
 * @param {object|null}  params.tablasOriginales      - snapshot de tablas al cargar
 *
 * @returns {{
 *   camposCorregidos:             Set<string>,
 *   camposPendientes:             Set<string>,
 *   todasCorreccionesCompletadas: boolean,
 * }}
 */
export function useEstadoCorreccionGlobal({
  camposIdentificados,
  formDataActual,
  formDataOriginal,
  tablasActuales,
  tablasOriginales,
}) {
  return useMemo(() => {
    if (camposIdentificados.size === 0) {
      return {
        camposCorregidos:             new Set(),
        camposPendientes:             new Set(),
        todasCorreccionesCompletadas: false,
      };
    }

    const corregidos = new Set();
    const pendientes = new Set();

    for (const campo of camposIdentificados) {
      if (CAMPOS_TABLA.has(campo)) {
        const claveTabla  = CLAVE_TABLA_POR_CAMPO[campo];
        const actual      = tablasActuales?.[claveTabla];
        const original    = tablasOriginales?.[claveTabla];
        if (_tablaFueModificada(actual, original)) {
          corregidos.add(campo);
        } else {
          pendientes.add(campo);
        }
      } else {
        // Campo simple: corregido si tiene valor Y difiere del original
        const valorActual   = formDataActual?.[campo]   ?? '';
        const valorOriginal = formDataOriginal?.[campo]  ?? '';
        if (valorActual !== '' && valorActual !== valorOriginal) {
          corregidos.add(campo);
        } else {
          pendientes.add(campo);
        }
      }
    }

    return {
      camposCorregidos:             corregidos,
      camposPendientes:             pendientes,
      todasCorreccionesCompletadas: pendientes.size === 0,
    };
  }, [camposIdentificados, formDataActual, formDataOriginal, tablasActuales, tablasOriginales]);
}
