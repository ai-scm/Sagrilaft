/**
 * Hook: useAlertasRazonSocial
 *
 * Gestiona el estado de inconsistencias de nombre/razón social entre el
 * formulario y los documentos adjuntos.
 *
 * Responsabilidades:
 *  1. Almacenar la razón social extraída por IA de cada documento.
 *  2. Calcular reactivamente las alertas activas cada vez que cambia
 *     formData.razon_social o se sube/elimina un documento.
 *  3. Limpiar la extracción cuando el usuario elimina un documento.
 *
 * El bloqueo de navegación es responsabilidad de useFormulario (SRP).
 * Este hook solo decide SI hay inconsistencias — no cómo reaccionar a ellas.
 *
 * SRP : única responsabilidad — computar qué documentos tienen nombre distinto.
 * DRY : normalización centralizada aquí; espeja backend/services/alertas/normalizador_nombre.py.
 *
 * Nota de diseño: no existe "descartar alerta". El usuario debe corregir el
 * nombre en el formulario o reemplazar el archivo adjunto.
 */

import { useCallback, useState } from 'react';

// ── Configuración de documentos monitoreados (lenguaje ubícuo) ────────────────

const CONFIG_DOCUMENTOS = {
  certificado_existencia: {
    nombreLegible:    'Certificado de Existencia y Representación Legal',
    seccionReferencia: 'NOMBRE, IDENTIFICACIÓN Y DOMICILIO → Razón social',
  },
  rut: {
    nombreLegible:    'RUT (Registro Único Tributario)',
    seccionReferencia: 'IDENTIFICACIÓN → campo 35. Razón social',
  },
  estados_financieros: {
    nombreLegible:    'Estados Financieros',
    seccionReferencia: 'Encabezado del documento (razón social del emisor)',
  },
  referencias_bancarias: {
    nombreLegible:    'Referencias Bancarias',
    seccionReferencia: 'Nombre del titular de la cuenta',
  },
};

// ── Normalización (espejo de backend/services/alertas/normalizador_nombre.py) ─
// DRY dentro del frontend: una sola función de normalización usada en calcularAlertas.

const SIGLAS_SOCIETARIAS = [
  [/SOCIEDAD POR ACCIONES SIMPLIFICADA/g, 'SAS'],
  [/SOCIEDAD ANONIMA SIMPLIFICADA/g,      'SAS'],
  [/SOCIEDAD DE RESPONSABILIDAD LIMITADA/g, 'LTDA'],
  [/EMPRESA UNIPERSONAL/g,                'EU'],
  [/SOCIEDAD ANONIMA/g,                   'SA'],
  [/SOCIEDAD EN COMANDITA POR ACCIONES/g, 'SCA'],
  [/SOCIEDAD EN COMANDITA SIMPLE/g,       'SCS'],
  [/S\.A\.S\.?/g,  'SAS'],
  [/S\.A\.?/g,     'SA'],
  [/LTDA\.?/g,     'LTDA'],
  [/LIMITADA\.?/g, 'LTDA'],
  [/E\.U\.?/g,     'EU'],
  [/S\.R\.L\.?/g,  'SRL'],
  [/S\.C\.A\.?/g,  'SCA'],
  [/S\.C\.S\.?/g,  'SCS'],
  [/E\.S\.P\.?/g,  'ESP'],
  [/CÍA\.?/g,      'CIA'],
  [/CIA\.?/g,      'CIA'],
];

function normalizarRazonSocial(valor) {
  if (!valor) return '';
  let texto = valor.normalize('NFD').replace(/[\u0300-\u036f]/g, '');
  texto = texto.toUpperCase();
  for (const [patron, canonica] of SIGLAS_SOCIETARIAS) {
    texto = texto.replace(patron, canonica);
  }
  return texto.replace(/\./g, '').replace(/\s+/g, ' ').trim();
}

// ── Hook ─────────────────────────────────────────────────────────────────────

/**
 * @typedef {{
 *   tipoDoc:          string,
 *   nombreDocumento:  string,
 *   seccionReferencia: string,
 *   valorFormulario:  string,
 *   valorDocumento:   string,
 * }} AlertaInconsistencia
 */

export function useAlertasRazonSocial() {
  /** Razón social extraída por IA, indexada por tipo de documento. */
  const [razonSocialPorDocumento, setRazonSocialPorDocumento] = useState({});

  /**
   * Registra la razón social extraída tras cada carga de documento.
   * Llamar desde handleFileChange después de recibir razon_social_extraida.
   */
  const registrarExtraccion = useCallback((tipoDoc, razonSocialExtraida) => {
    if (!razonSocialExtraida) return;
    setRazonSocialPorDocumento(prev => ({ ...prev, [tipoDoc]: razonSocialExtraida }));
  }, []);

  /**
   * Calcula las alertas activas comparando cada extracción con la razón social
   * actual del formulario. Invocado en cada render desde useFormulario.
   *
   * @param {string | undefined} razonSocialFormulario
   * @returns {AlertaInconsistencia[]}
   */
  const calcularAlertas = useCallback(
    (razonSocialFormulario) => {
      if (!razonSocialFormulario) return [];

      const normForm = normalizarRazonSocial(razonSocialFormulario);

      return Object.entries(razonSocialPorDocumento)
        .map(([tipoDoc, razonSocialDoc]) => {
          const normDoc = normalizarRazonSocial(razonSocialDoc);
          if (!normDoc || normForm === normDoc) return null;

          const config = CONFIG_DOCUMENTOS[tipoDoc];
          return {
            tipoDoc,
            nombreDocumento:   config?.nombreLegible    ?? tipoDoc,
            seccionReferencia: config?.seccionReferencia ?? '',
            valorFormulario:   razonSocialFormulario,
            valorDocumento:    razonSocialDoc,
          };
        })
        .filter(Boolean);
    },
    [razonSocialPorDocumento],
  );

  /**
   * Elimina la extracción almacenada de un documento.
   * Llamar desde handleRemoveFile cuando el usuario borra un adjunto.
   */
  const limpiarExtraccion = useCallback((tipoDoc) => {
    setRazonSocialPorDocumento(prev => {
      const siguiente = { ...prev };
      delete siguiente[tipoDoc];
      return siguiente;
    });
  }, []);

  return { registrarExtraccion, calcularAlertas, limpiarExtraccion };
}
