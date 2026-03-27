/**
 * Hook: useAlertasNit
 *
 * Gestiona el estado de inconsistencias de NIT entre el formulario y los
 * documentos adjuntos.
 *
 * Responsabilidades:
 *  1. Almacenar el NIT extraído por IA de cada documento.
 *  2. Calcular reactivamente las alertas activas cada vez que cambia
 *     formData.numero_identificacion o se sube/elimina un documento.
 *  3. Solo emitir alertas cuando tipo_identificacion === 'NIT'.
 *  4. Limpiar la extracción cuando el usuario elimina un documento.
 *
 * El bloqueo de navegación es responsabilidad de useFormulario (SRP).
 * Este hook solo decide SI hay inconsistencias — no cómo reaccionar a ellas.
 *
 * SRP : única responsabilidad — computar qué documentos tienen NIT distinto.
 * DRY : normalización centralizada aquí; espeja
 *       backend/services/alertas/normalizador_nit.py.
 *
 * Nota de diseño: no existe "descartar alerta". El usuario debe corregir el
 * NIT en el formulario o reemplazar el archivo adjunto.
 */

import { useCallback, useState } from 'react';

// ── Configuración de documentos monitoreados ──────────────────────────────────

const CONFIG_DOCUMENTOS_NIT = {
  certificado_existencia: {
    nombreLegible:    'Revisa los documentos adjuntos',
    seccionReferencia: 'NOMBRE, IDENTIFICACIÓN Y DOMICILIO → Nit',
  },
  rut: {
    nombreLegible:    'RUT (Registro Único Tributario)',
    seccionReferencia: 'IDENTIFICACIÓN → campo 5. Número de Identificación Tributaria (NIT)',
  },
  estados_financieros: {
    nombreLegible:    'Estados Financieros',
    seccionReferencia: 'Encabezado o membrete del documento (NIT del emisor)',
  },
  declaracion_renta: {
    nombreLegible:    'Declaración de Renta',
    seccionReferencia: 'IDENTIFICACIÓN → campo 5. Número de Identificación Tributaria (NIT)',
  },
  referencias_bancarias: {
    nombreLegible:    'Referencias Bancarias',
    seccionReferencia: 'NIT del titular de la cuenta (si aparece en el documento)',
  },
};

// ── Normalización (espejo de backend/services/alertas/normalizador_nit.py) ────
// DRY dentro del frontend: una sola función usada en calcularAlertasNit.

const LONGITUD_NIT_BASE = 9;

function normalizarNit(valor) {
  if (!valor) return '';
  const soloDigitos = String(valor).replace(/\D/g, '');
  if (soloDigitos.length > LONGITUD_NIT_BASE) {
    return soloDigitos.slice(0, LONGITUD_NIT_BASE);
  }
  return soloDigitos;
}

// ── Hook ──────────────────────────────────────────────────────────────────────

/**
 * @typedef {{
 *   tipoDoc:          string,
 *   nombreDocumento:  string,
 *   seccionReferencia: string,
 *   valorFormulario:  string,
 *   valorDocumento:   string,
 * }} AlertaInconsistenciaNit
 */

export function useAlertasNit() {
  /** NIT extraído por IA, indexado por tipo de documento. */
  const [nitPorDocumento, setNitPorDocumento] = useState({});

  /**
   * Registra el NIT extraído tras cada carga de documento.
   * Llamar desde handleFileChange después de recibir nit_extraido.
   */
  const registrarExtraccionNit = useCallback((tipoDoc, nitExtraido) => {
    if (!nitExtraido) return;
    setNitPorDocumento(prev => ({ ...prev, [tipoDoc]: nitExtraido }));
  }, []);

  /**
   * Calcula las alertas activas comparando cada NIT extraído con el NIT
   * actual del formulario. Solo aplica cuando tipoIdentificacion === 'NIT'.
   * Invocado en cada render desde useFormulario.
   *
   * @param {string | undefined} numeroIdentificacion
   * @param {string | undefined} tipoIdentificacion
   * @returns {AlertaInconsistenciaNit[]}
   */
  const calcularAlertasNit = useCallback(
    (numeroIdentificacion, tipoIdentificacion) => {
      // Solo valida NIT
      if ((tipoIdentificacion || '').toUpperCase() !== 'NIT') return [];
      if (!numeroIdentificacion) return [];

      const normForm = normalizarNit(numeroIdentificacion);
      if (!normForm) return [];

      return Object.entries(nitPorDocumento)
        .map(([tipoDoc, nitDoc]) => {
          const normDoc = normalizarNit(nitDoc);
          if (!normDoc || normForm === normDoc) return null;

          const config = CONFIG_DOCUMENTOS_NIT[tipoDoc];
          return {
            tipoDoc,
            nombreDocumento:   config?.nombreLegible    ?? tipoDoc,
            seccionReferencia: config?.seccionReferencia ?? '',
            valorFormulario:   numeroIdentificacion,
            valorDocumento:    nitDoc,
          };
        })
        .filter(Boolean);
    },
    [nitPorDocumento],
  );

  /**
   * Elimina el NIT almacenado de un documento.
   * Llamar desde handleRemoveFile cuando el usuario borra un adjunto.
   */
  const limpiarExtraccionNit = useCallback((tipoDoc) => {
    setNitPorDocumento(prev => {
      const siguiente = { ...prev };
      delete siguiente[tipoDoc];
      return siguiente;
    });
  }, []);

  return { registrarExtraccionNit, calcularAlertasNit, limpiarExtraccionNit };
}
