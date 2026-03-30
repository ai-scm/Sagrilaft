/**
 * Motor de alertas de inconsistencia entre formulario y documentos adjuntos.
 *
 * Funciones puras — sin estado, sin efectos secundarios.
 * La fuente de verdad de las extracciones es el estado `documentos` de useFormulario,
 * que ya persiste en localStorage. Esto elimina el estado redundante que los hooks
 * anteriores mantenían por separado y que se perdía en cada recarga de página.
 *
 * DRY      : normalización delegada a utils/normalizadores.js.
 * SRP      : cada función decide SI hay inconsistencia para un campo; no cómo reaccionar.
 * Modular  : agregar un nuevo campo vigilado = agregar su configuración y función aquí.
 */

import {
  normalizarNombre,
  normalizarNit,
  normalizarNumeroDoc,
  normalizarDireccion,
} from './normalizadores';

// ── Configuración de campos vigilados por tipo de documento ───────────────────
// Lenguaje ubicuo: los nombres reflejan las secciones del documento físico.

const DOCS_RAZON_SOCIAL = {
  certificado_existencia: {
    nombreLegible:     'Certificado de Existencia y Representación Legal',
    seccionReferencia: 'NOMBRE, IDENTIFICACIÓN Y DOMICILIO → Razón social',
  },
  rut: {
    nombreLegible:     'RUT (Registro Único Tributario)',
    seccionReferencia: 'IDENTIFICACIÓN → campo 35. Razón social',
  },
  estados_financieros: {
    nombreLegible:     'Estados Financieros',
    seccionReferencia: 'Encabezado del documento (razón social del emisor)',
  },
  referencias_bancarias: {
    nombreLegible:     'Referencias Bancarias',
    seccionReferencia: 'Nombre del titular de la cuenta',
  },
};

const DOCS_NIT = {
  certificado_existencia: {
    nombreLegible:     'Certificado de Existencia y Representación Legal',
    seccionReferencia: 'NOMBRE, IDENTIFICACIÓN Y DOMICILIO → Nit',
  },
  rut: {
    nombreLegible:     'RUT (Registro Único Tributario)',
    seccionReferencia: 'IDENTIFICACIÓN → campo 5. Número de Identificación Tributaria (NIT)',
  },
  estados_financieros: {
    nombreLegible:     'Estados Financieros',
    seccionReferencia: 'Encabezado o membrete del documento (NIT del emisor)',
  },
  declaracion_renta: {
    nombreLegible:     'Declaración de Renta',
    seccionReferencia: 'IDENTIFICACIÓN → campo 5. Número de Identificación Tributaria (NIT)',
  },
  referencias_bancarias: {
    nombreLegible:     'Referencias Bancarias',
    seccionReferencia: 'NIT del titular de la cuenta (si aparece en el documento)',
  },
};

const DOCS_NOMBRE_REPRESENTANTE = {
  certificado_existencia: {
    nombreLegible:     'Certificado de Existencia y Representación Legal',
    seccionReferencia: 'REPRESENTANTES LEGALES → NOMBRE',
  },
  rut: {
    nombreLegible:     'RUT (Registro Único Tributario)',
    seccionReferencia: 'Representación → campos 106, 107, 104, 105 (Primer nombre, Otros nombres, Primer apellido, Segundo apellido)',
  },
  estados_financieros: {
    nombreLegible:     'Estados Financieros',
    seccionReferencia: 'Representante legal o firmante del documento',
  },
};

const DOCS_NUMERO_DOC_REPRESENTANTE = {
  cedula_representante: {
    nombreLegible:     'Cédula del Representante Legal',
    seccionReferencia: 'Número del documento de identidad del titular',
  },
  certificado_existencia: {
    nombreLegible:     'Certificado de Existencia y Representación Legal',
    seccionReferencia: 'NOMBRAMIENTOS → REPRESENTANTES LEGALES → IDENTIFICACIÓN',
  },
  rut: {
    nombreLegible:     'RUT (Registro Único Tributario)',
    seccionReferencia: 'Representación → 101. Número de identificación',
  },
  estados_financieros: {
    nombreLegible:     'Estados Financieros',
    seccionReferencia: 'Número de documento del representante legal o firmante del documento',
  },
};

const DOCS_DIRECCION = {
  certificado_existencia: {
    nombreLegible:     'Certificado de Existencia y Representación Legal',
    seccionReferencia: 'Dirección del domicilio principal',
  },
  rut: {
    nombreLegible:     'RUT (Registro Único Tributario)',
    seccionReferencia: 'Sección UBICACIÓN → campo 41. Dirección principal',
  },
};

// ── Motor de comparación ──────────────────────────────────────────────────────

/**
 * Itera sobre todos los documentos adjuntos y genera alertas para cada uno
 * cuyo valor extraído difiera del valor actual en el formulario.
 *
 * @param {Object}   documentos        — estado documentos de useFormulario (docRes por tipoDoc)
 * @param {string}   valorFormulario   — valor actual del campo en el formulario
 * @param {Function} extraerValorDoc   — extrae el campo relevante de cada docRes
 * @param {Function} normalizar        — función de normalización (de normalizadores.js)
 * @param {Object}   configPorTipoDoc  — nombre legible y sección de referencia por tipo de doc
 * @returns {Array<AlertaInconsistencia>}
 */
function detectarInconsistencias(documentos, valorFormulario, extraerValorDoc, normalizar, configPorTipoDoc) {
  if (!valorFormulario) return [];

  const normForm = normalizar(valorFormulario);
  if (!normForm) return [];

  return Object.entries(documentos)
    .map(([tipoDoc, docRes]) => {
      const valorExtraido = extraerValorDoc(docRes);
      if (!valorExtraido) return null;

      const normDoc = normalizar(valorExtraido);
      if (!normDoc || normForm === normDoc) return null;

      const config = configPorTipoDoc[tipoDoc];
      return {
        tipoDoc,
        nombreDocumento:   config?.nombreLegible    ?? tipoDoc,
        seccionReferencia: config?.seccionReferencia ?? '',
        valorFormulario,
        valorDocumento:    valorExtraido,
      };
    })
    .filter(Boolean);
}

// ── API pública ───────────────────────────────────────────────────────────────

/**
 * @typedef {{
 *   tipoDoc:           string,
 *   nombreDocumento:   string,
 *   seccionReferencia: string,
 *   valorFormulario:   string,
 *   valorDocumento:    string,
 * }} AlertaInconsistencia
 */

export const calcularAlertasRazonSocial = (documentos, razonSocial) =>
  detectarInconsistencias(
    documentos, razonSocial,
    docRes => docRes.razon_social_extraida,
    normalizarNombre,
    DOCS_RAZON_SOCIAL,
  );

export const calcularAlertasNit = (documentos, numeroIdentificacion, tipoIdentificacion) => {
  if ((tipoIdentificacion ?? '').toUpperCase() !== 'NIT') return [];
  return detectarInconsistencias(
    documentos, numeroIdentificacion,
    docRes => docRes.nit_extraido,
    normalizarNit,
    DOCS_NIT,
  );
};

export const calcularAlertasNombreRepresentante = (documentos, nombreRepresentante) =>
  detectarInconsistencias(
    documentos, nombreRepresentante,
    docRes => docRes.nombre_representante_extraido,
    normalizarNombre,
    DOCS_NOMBRE_REPRESENTANTE,
  );

export const calcularAlertasNumeroDocRepresentante = (documentos, numeroDocRepresentante) =>
  detectarInconsistencias(
    documentos, numeroDocRepresentante,
    docRes => docRes.numero_doc_representante_extraido,
    normalizarNumeroDoc,
    DOCS_NUMERO_DOC_REPRESENTANTE,
  );

export const calcularAlertasDireccion = (documentos, direccion) =>
  detectarInconsistencias(
    documentos, direccion,
    docRes => docRes.direccion_extraida,
    normalizarDireccion,
    DOCS_DIRECCION,
  );
