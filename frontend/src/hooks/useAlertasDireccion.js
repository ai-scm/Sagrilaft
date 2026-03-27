/**
 * Hook: useAlertasDireccion
 *
 * Gestiona el estado de inconsistencias de dirección entre el formulario y
 * los documentos adjuntos.
 *
 * Responsabilidades:
 *  1. Almacenar la dirección extraída por IA de cada documento.
 *  2. Calcular reactivamente las alertas activas cada vez que cambia
 *     formData.direccion o se sube/elimina un documento.
 *  3. Limpiar la extracción cuando el usuario elimina un documento.
 *
 * El bloqueo de navegación es responsabilidad de useFormulario (SRP).
 * Este hook solo decide SI hay inconsistencias — no cómo reaccionar a ellas.
 *
 * SRP : única responsabilidad — computar qué documentos tienen una dirección
 *       distinta a la del formulario.
 * DRY : normalización centralizada aquí; espeja
 *       backend/services/alertas/normalizador_direccion.py.
 *
 * Nota de diseño: no existe "descartar alerta". El usuario debe corregir el
 * campo en el formulario o reemplazar el archivo adjunto.
 */

import { useCallback, useState } from 'react';

// ── Configuración de documentos monitoreados ──────────────────────────────────

const CONFIG_DOCUMENTOS_DIRECCION = {
  certificado_existencia: {
    nombreLegible:    'Certificado de Existencia y Representación Legal',
    seccionReferencia: 'Dirección del domicilio principal',
  },
  rut: {
    nombreLegible:    'RUT (Registro Único Tributario)',
    seccionReferencia: 'Sección UBICACIÓN → campo 41. Dirección principal',
  },
};

// ── Normalización (espejo de backend/services/alertas/normalizador_direccion.py) ─
// DRY dentro del frontend: una sola función usada en calcularAlertasDireccion.

const TIPOS_VIALES = [
  [/\bCALLE\b/g,       'CL'],
  [/\bCARRERA\b/g,     'CR'],
  [/\bAVENIDA\b/g,     'AV'],
  [/\bDIAGONAL\b/g,   'DG'],
  [/\bTRANSVERSAL\b/g, 'TV'],
  [/\bCIRCULAR\b/g,   'CIC'],
  [/\bAUTOPISTA\b/g,  'AU'],
  [/\bVARIANTE\b/g,   'VT'],
  [/\bCLLE\b/g,  'CL'],
  [/\bCLL\b/g,   'CL'],
  [/\bCRRA\b/g,  'CR'],
  [/\bCRA\b/g,   'CR'],
  [/\bAVE\b/g,   'AV'],
  [/\bDIAG\b/g,  'DG'],
  [/\bTRANS\b/g, 'TV'],
  [/\bCIRC\b/g,  'CIC'],
];

function normalizarDireccion(valor) {
  if (!valor) return '';

  // 1. Quitar diacríticos
  let texto = valor.normalize('NFD').replace(/[\u0300-\u036f]/g, '');

  // 2. Mayúsculas
  texto = texto.toUpperCase();

  // 3. Normalizar tipos viales
  for (const [patron, canonica] of TIPOS_VIALES) {
    texto = texto.replace(patron, canonica);
  }

  // 4. Normalizar separadores de numeración
  texto = texto
    .replace(/#/g, ' ')
    .replace(/\bNUMERO\b/g, ' ')
    .replace(/\bNRO\.?\b/g, ' ')
    .replace(/\bNO\.?\b/g, ' ');

  // 5. Eliminar puntuación residual
  texto = texto.replace(/[.,]/g, '');

  // 6. Colapsar espacios
  return texto.replace(/\s+/g, ' ').trim();
}

// ── Hook ──────────────────────────────────────────────────────────────────────

/**
 * @typedef {{
 *   tipoDoc:          string,
 *   nombreDocumento:  string,
 *   seccionReferencia: string,
 *   valorFormulario:  string,
 *   valorDocumento:   string,
 * }} AlertaInconsistenciaDireccion
 */

export function useAlertasDireccion() {
  /** Dirección extraída por IA, indexada por tipo de documento. */
  const [direccionPorDocumento, setDireccionPorDocumento] = useState({});

  /**
   * Registra la dirección extraída tras cada carga de documento.
   * Llamar desde handleFileChange después de recibir direccion_extraida.
   */
  const registrarExtraccionDireccion = useCallback((tipoDoc, direccionExtraida) => {
    if (!direccionExtraida) return;
    setDireccionPorDocumento(prev => ({ ...prev, [tipoDoc]: direccionExtraida }));
  }, []);

  /**
   * Calcula las alertas activas comparando cada dirección extraída con la
   * dirección actual del formulario. Invocado en cada render desde useFormulario.
   *
   * @param {string | undefined} direccionFormulario
   * @returns {AlertaInconsistenciaDireccion[]}
   */
  const calcularAlertasDireccion = useCallback(
    (direccionFormulario) => {
      if (!direccionFormulario) return [];

      const normForm = normalizarDireccion(direccionFormulario);
      if (!normForm) return [];

      return Object.entries(direccionPorDocumento)
        .map(([tipoDoc, direccionDoc]) => {
          const normDoc = normalizarDireccion(direccionDoc);
          if (!normDoc || normForm === normDoc) return null;

          const config = CONFIG_DOCUMENTOS_DIRECCION[tipoDoc];
          return {
            tipoDoc,
            nombreDocumento:   config?.nombreLegible    ?? tipoDoc,
            seccionReferencia: config?.seccionReferencia ?? '',
            valorFormulario:   direccionFormulario,
            valorDocumento:    direccionDoc,
          };
        })
        .filter(Boolean);
    },
    [direccionPorDocumento],
  );

  /**
   * Elimina la dirección almacenada de un documento.
   * Llamar desde handleRemoveFile cuando el usuario borra un adjunto.
   */
  const limpiarExtraccionDireccion = useCallback((tipoDoc) => {
    setDireccionPorDocumento(prev => {
      const siguiente = { ...prev };
      delete siguiente[tipoDoc];
      return siguiente;
    });
  }, []);

  return { registrarExtraccionDireccion, calcularAlertasDireccion, limpiarExtraccionDireccion };
}
