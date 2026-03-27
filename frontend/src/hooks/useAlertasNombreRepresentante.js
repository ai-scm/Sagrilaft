/**
 * Hook: useAlertasNombreRepresentante
 *
 * Gestiona el estado de inconsistencias de nombre del representante legal entre
 * el formulario y los documentos adjuntos.
 *
 * Responsabilidades:
 *  1. Almacenar el nombre del representante extraído por IA de cada documento.
 *  2. Calcular reactivamente las alertas activas cada vez que cambia
 *     formData.nombre_representante o se sube/elimina un documento.
 *  3. Limpiar la extracción cuando el usuario elimina un documento.
 *
 * El bloqueo de navegación es responsabilidad de useFormulario (SRP).
 * Este hook solo decide SI hay inconsistencias — no cómo reaccionar a ellas.
 *
 * SRP : única responsabilidad — computar qué documentos tienen nombre de
 *       representante distinto.
 * DRY : normalización centralizada aquí; reutiliza la misma lógica de
 *       useAlertasRazonSocial (mismas reglas de tolerancia: diacríticos,
 *       mayúsculas, espacios). Las sustituciones de siglas societarias no
 *       afectan a nombres de personas.
 *
 * Nota de diseño: no existe "descartar alerta". El usuario debe corregir el
 * campo en el formulario o reemplazar el archivo adjunto.
 */

import { useCallback, useState } from 'react';

// ── Configuración de documentos monitoreados ──────────────────────────────────

const CONFIG_DOCUMENTOS = {
  certificado_existencia: {
    nombreLegible:    'Certificado de Existencia y Representación Legal',
    seccionReferencia: 'REPRESENTANTES LEGALES → NOMBRE',
  },
  rut: {
    nombreLegible:    'RUT (Registro Único Tributario)',
    seccionReferencia: 'Representación → campos 106, 107, 104, 105 (Primer nombre, Otros nombres, Primer apellido, Segundo apellido)',
  },
  estados_financieros: {
    nombreLegible:    'Estados Financieros',
    seccionReferencia: 'Representante legal o firmante del documento',
  },
};

// ── Normalización (espejo de backend/services/alertas/normalizador_nombre.py) ─
// DRY: mismas reglas de tolerancia que useAlertasRazonSocial.
// Las siglas societarias no interfieren con nombres de personas.

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

function normalizarNombre(valor) {
  if (!valor) return '';
  let texto = valor.normalize('NFD').replace(/[\u0300-\u036f]/g, '');
  texto = texto.toUpperCase();
  for (const [patron, canonica] of SIGLAS_SOCIETARIAS) {
    texto = texto.replace(patron, canonica);
  }
  return texto.replace(/\./g, '').replace(/\s+/g, ' ').trim();
}

// ── Hook ──────────────────────────────────────────────────────────────────────

/**
 * @typedef {{
 *   tipoDoc:          string,
 *   nombreDocumento:  string,
 *   seccionReferencia: string,
 *   valorFormulario:  string,
 *   valorDocumento:   string,
 * }} AlertaInconsistenciaNombreRepresentante
 */

export function useAlertasNombreRepresentante() {
  /** Nombre del representante extraído por IA, indexado por tipo de documento. */
  const [nombrePorDocumento, setNombrePorDocumento] = useState({});

  /**
   * Registra el nombre del representante extraído tras cada carga de documento.
   * Llamar desde handleFileChange después de recibir nombre_representante_extraido.
   */
  const registrarExtraccionNombreRepresentante = useCallback((tipoDoc, nombreExtraido) => {
    if (!nombreExtraido) return;
    setNombrePorDocumento(prev => ({ ...prev, [tipoDoc]: nombreExtraido }));
  }, []);

  /**
   * Calcula las alertas activas comparando cada nombre extraído con el nombre
   * del representante actual del formulario. Invocado en cada render.
   *
   * @param {string | undefined} nombreRepresentanteFormulario
   * @returns {AlertaInconsistenciaNombreRepresentante[]}
   */
  const calcularAlertasNombreRepresentante = useCallback(
    (nombreRepresentanteFormulario) => {
      if (!nombreRepresentanteFormulario) return [];

      const normForm = normalizarNombre(nombreRepresentanteFormulario);
      if (!normForm) return [];

      return Object.entries(nombrePorDocumento)
        .map(([tipoDoc, nombreDoc]) => {
          const normDoc = normalizarNombre(nombreDoc);
          if (!normDoc || normForm === normDoc) return null;

          const config = CONFIG_DOCUMENTOS[tipoDoc];
          return {
            tipoDoc,
            nombreDocumento:   config?.nombreLegible    ?? tipoDoc,
            seccionReferencia: config?.seccionReferencia ?? '',
            valorFormulario:   nombreRepresentanteFormulario,
            valorDocumento:    nombreDoc,
          };
        })
        .filter(Boolean);
    },
    [nombrePorDocumento],
  );

  /**
   * Elimina el nombre almacenado de un documento.
   * Llamar desde handleRemoveFile cuando el usuario borra un adjunto.
   */
  const limpiarExtraccionNombreRepresentante = useCallback((tipoDoc) => {
    setNombrePorDocumento(prev => {
      const siguiente = { ...prev };
      delete siguiente[tipoDoc];
      return siguiente;
    });
  }, []);

  return {
    registrarExtraccionNombreRepresentante,
    calcularAlertasNombreRepresentante,
    limpiarExtraccionNombreRepresentante,
  };
}
