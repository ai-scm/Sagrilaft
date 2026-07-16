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
} from '@shared/utils/normalizadores';

// ── Configuración de campos vigilados por tipo de documento ───────────────────
// Lenguaje ubicuo: los nombres reflejan las secciones del documento físico.

export const DOCS_RAZON_SOCIAL = {
  certificado_existencia: {
    nombreLegible:     'Certificado de Existencia y Representación Legal',
    seccionReferencia: 'Puede aparecer en la sección de “Nombre, identificación y domicilio” o en la sección de identificación del documento, donde aparece la razón social.',
  },
  rut: {
    nombreLegible:     'RUT (Registro Único Tributario)',
    seccionReferencia: 'En la sección de identificación del contribuyente, donde aparece la razón social',
  },
  estados_financieros: {
    nombreLegible:     'Estados Financieros',
    seccionReferencia: 'En la parte superior del documento, donde aparece la razón social del emisor',
  },
  referencias_bancarias: {
    nombreLegible:     'Referencias Bancarias',
    seccionReferencia: 'Sección de datos de la cuenta, donde se identifica/informa el titular',
  },
};

export const DOCS_NIT = {
  certificado_existencia: {
    nombreLegible:     'Certificado de Existencia y Representación Legal',
    seccionReferencia: 'puede aparecer en la sección “Nombre, identificación y domicilio” o en la sección de identificación (NIT)',
  },
  rut: {
    nombreLegible:     'RUT (Registro Único Tributario)',
    seccionReferencia: 'Parte superior o sección de identificación del documento (NIT)',
  },
  estados_financieros: {
    nombreLegible:     'Estados Financieros',
    seccionReferencia: 'Encabezado o membrete del documento (NIT del emisor)',
  },
  declaracion_renta: {
    nombreLegible:     'Declaración de Renta',
    seccionReferencia: 'En la sección de identificación del contribuyente (NIT)',
  },
  referencias_bancarias: {
    nombreLegible:     'Referencias Bancarias',
    seccionReferencia: 'NIT del titular de la cuenta (si aparece en el documento)',
  },
};

export const DOCS_NOMBRE_REPRESENTANTE = {
  certificado_existencia: {
    nombreLegible:     'Certificado de Existencia y Representación Legal',
    seccionReferencia: 'Sección de representantes legales (nombres y apellidos del representante)',
  },
  rut: {
    nombreLegible:     'RUT (Registro Único Tributario)',
    seccionReferencia: 'En la sección de identificación/representación del contribuyente (nombres y apellidos)',
  },
  estados_financieros: {
    nombreLegible:     'Estados Financieros',
    seccionReferencia: 'Parte superior o inferior, seccion de representante legal',
  },
};

export const DOCS_NUMERO_DOC_REPRESENTANTE = {
  cedula_representante: {
    nombreLegible:     'Cédula del Representante Legal',
    seccionReferencia: 'Número del documento de identidad del titular',
  },
  certificado_existencia: {
    nombreLegible:     'Certificado de Existencia y Representación Legal',
    seccionReferencia: 'Seccion de representantes legales (número de documento del representante)',
  },
  rut: {
    nombreLegible:     'RUT (Registro Único Tributario)',
    seccionReferencia: 'En la sección de representacion del contribuyente, donde se encuentra el número de identificación (NIT)',
  },
  estados_financieros: {
    nombreLegible:     'Estados Financieros',
    seccionReferencia: 'Parte superior o inferior, seccion de representante legal',
  },
};

export const DOCS_DIRECCION = {
  certificado_existencia: {
    nombreLegible:     'Certificado de Existencia y Representación Legal',
    seccionReferencia: 'Dirección del domicilio principal',
  },
  rut: {
    nombreLegible:     'RUT (Registro Único Tributario)',
    seccionReferencia: 'En la sección de ubicación o datos del contribuyente, donde aparece la dirección principal',
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
function detectarInconsistencias(documentos, valorFormulario, extraerValorDoc, normalizar, configPorTipoDoc, tipoCampo) {
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
        tipo_campo:        tipoCampo,
        nombre_documento:   config?.nombreLegible    ?? tipoDoc,
        seccion_referencia: config?.seccionReferencia ?? '',
        valor_formulario:   valorFormulario,
        valor_documento:    valorExtraido,
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
    'razon_social'
  );

export const calcularAlertasNit = (documentos, numeroIdentificacion, tipoIdentificacion) => {
  if ((tipoIdentificacion ?? '').toUpperCase() !== 'NIT') return [];
  return detectarInconsistencias(
    documentos, numeroIdentificacion,
    docRes => docRes.nit_extraido,
    normalizarNit,
    DOCS_NIT,
    'numero_identificacion'
  );
};

export const calcularAlertasNombreRepresentante = (documentos, nombreRepresentante) =>
  detectarInconsistencias(
    documentos, nombreRepresentante,
    docRes => docRes.nombre_representante_extraido,
    normalizarNombre,
    DOCS_NOMBRE_REPRESENTANTE,
    'nombre_representante'
  );

export const calcularAlertasNumeroDocRepresentante = (documentos, numeroDocRepresentante) =>
  detectarInconsistencias(
    documentos, numeroDocRepresentante,
    docRes => docRes.numero_doc_representante_extraido,
    normalizarNumeroDoc,
    DOCS_NUMERO_DOC_REPRESENTANTE,
    'numero_doc_representante'
  );

export const calcularAlertasDireccion = (documentos, direccion) =>
  detectarInconsistencias(
    documentos, direccion,
    docRes => docRes.direccion_extraida,
    normalizarDireccion,
    DOCS_DIRECCION,
    'direccion'
  );
