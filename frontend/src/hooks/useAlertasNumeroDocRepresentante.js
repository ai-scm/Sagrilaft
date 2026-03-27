/**
 * Hook: useAlertasNumeroDocRepresentante
 *
 * Gestiona el estado de inconsistencias del número de documento del representante
 * legal entre el formulario y los documentos adjuntos.
 *
 * Responsabilidades:
 *  1. Almacenar el número de documento del representante extraído por IA de cada
 *     documento.
 *  2. Calcular reactivamente las alertas activas cada vez que cambia
 *     formData.numero_doc_representante o se sube/elimina un documento.
 *  3. Limpiar la extracción cuando el usuario elimina un documento.
 *
 * El bloqueo de navegación es responsabilidad de useFormulario (SRP).
 * Este hook solo decide SI hay inconsistencias — no cómo reaccionar a ellas.
 *
 * SRP : única responsabilidad — computar qué documentos tienen número de
 *       documento del representante distinto.
 * DRY : normalización centralizada aquí; espeja
 *       backend/services/alertas/normalizador_numero_doc.py.
 *
 * Nota de diseño: no existe "descartar alerta". El usuario debe corregir el
 * campo en el formulario o reemplazar el archivo adjunto.
 */

import { useCallback, useState } from 'react';

// ── Configuración de documentos monitoreados ──────────────────────────────────

const CONFIG_DOCUMENTOS_NUMERO_DOC = {
  cedula_representante: {
    nombreLegible:    'Cédula del Representante Legal',
    seccionReferencia: 'Número del documento de identidad del titular',
  },
  certificado_existencia: {
    nombreLegible:    'Certificado de Existencia y Representación Legal',
    seccionReferencia: 'NOMBRAMIENTOS → REPRESENTANTES LEGALES → IDENTIFICACIÓN',
  },
  rut: {
    nombreLegible:    'RUT (Registro Único Tributario)',
    seccionReferencia: 'Representación → 101. Número de identificación',
  },
  estados_financieros: {
    nombreLegible:    'Estados Financieros',
    seccionReferencia: 'Número de documento del representante legal o firmante del documento',
  },
};

// ── Normalización (espejo de backend/services/alertas/normalizador_numero_doc.py) ─
// DRY: una sola función usada en calcularAlertasNumeroDocRepresentante.
// Tolera puntos, guiones, espacios y diferencias de capitalización.

function normalizarNumeroDoc(valor) {
  if (!valor) return '';
  return String(valor).toUpperCase().replace(/[^A-Z0-9]/g, '');
}

// ── Hook ──────────────────────────────────────────────────────────────────────

/**
 * @typedef {{
 *   tipoDoc:          string,
 *   nombreDocumento:  string,
 *   seccionReferencia: string,
 *   valorFormulario:  string,
 *   valorDocumento:   string,
 * }} AlertaInconsistenciaNumeroDocRepresentante
 */

export function useAlertasNumeroDocRepresentante() {
  /** Número de documento del representante extraído por IA, indexado por tipo de doc. */
  const [numeroDocPorDocumento, setNumeroDocPorDocumento] = useState({});

  /**
   * Registra el número de documento del representante extraído tras cada carga.
   * Llamar desde handleFileChange después de recibir numero_doc_representante_extraido.
   */
  const registrarExtraccionNumeroDocRepresentante = useCallback((tipoDoc, numeroDocExtraido) => {
    if (!numeroDocExtraido) return;
    setNumeroDocPorDocumento(prev => ({ ...prev, [tipoDoc]: numeroDocExtraido }));
  }, []);

  /**
   * Calcula las alertas activas comparando cada número de documento extraído con el
   * número de documento del representante actual del formulario.
   * Invocado en cada render desde useFormulario.
   *
   * @param {string | undefined} numeroDocRepresentanteFormulario
   * @returns {AlertaInconsistenciaNumeroDocRepresentante[]}
   */
  const calcularAlertasNumeroDocRepresentante = useCallback(
    (numeroDocRepresentanteFormulario) => {
      if (!numeroDocRepresentanteFormulario) return [];

      const normForm = normalizarNumeroDoc(numeroDocRepresentanteFormulario);
      if (!normForm) return [];

      return Object.entries(numeroDocPorDocumento)
        .map(([tipoDoc, numeroDocDoc]) => {
          const normDoc = normalizarNumeroDoc(numeroDocDoc);
          if (!normDoc || normForm === normDoc) return null;

          const config = CONFIG_DOCUMENTOS_NUMERO_DOC[tipoDoc];
          return {
            tipoDoc,
            nombreDocumento:   config?.nombreLegible    ?? tipoDoc,
            seccionReferencia: config?.seccionReferencia ?? '',
            valorFormulario:   numeroDocRepresentanteFormulario,
            valorDocumento:    numeroDocDoc,
          };
        })
        .filter(Boolean);
    },
    [numeroDocPorDocumento],
  );

  /**
   * Elimina el número de documento almacenado de un documento.
   * Llamar desde handleRemoveFile cuando el usuario borra un adjunto.
   */
  const limpiarExtraccionNumeroDocRepresentante = useCallback((tipoDoc) => {
    setNumeroDocPorDocumento(prev => {
      const siguiente = { ...prev };
      delete siguiente[tipoDoc];
      return siguiente;
    });
  }, []);

  return {
    registrarExtraccionNumeroDocRepresentante,
    calcularAlertasNumeroDocRepresentante,
    limpiarExtraccionNumeroDocRepresentante,
  };
}
