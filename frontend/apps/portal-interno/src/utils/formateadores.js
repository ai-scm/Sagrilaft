/**
 * Mapeo de identificadores técnicos de documentos a nombres amigables para la UI.
 * Centralizado aquí para mantener la consistencia en todas las vistas del portal.
 */
export const NOMBRES_DOCUMENTOS = {
  // Documentos de la Contraparte
  'cedula_representante': 'Documento de Identidad del Representante Legal',
  'certificado_existencia': 'Certificado de Existencia y Representación Legal',
  'estados_financieros': 'Estados Financieros',
  'declaracion_renta': 'Declaración de Renta',
  'rut': 'RUT (Registro Único Tributario)',
  'referencias_bancarias': 'Certificaciones Bancarias',
  
  // Documentos Oficiales y del Sistema
  'FORMULARIO_PDF': 'Formulario SAGRILAFT (Oficial)',
  'CERTIFICADO_SAGRILAFT': 'Certificado de Firma Electrónica',
  'REPORTE_FINAL': 'Informe Final de Evaluación'
};

/**
 * Traduce el tipo de documento técnico a su etiqueta amigable.
 * Si no encuentra mapeo, devuelve el valor original.
 * 
 * @param {string} tipoTecnico - Identificador de base de datos (ej: 'cedula_representante')
 * @returns {string} - Nombre para la UI
 */
export const formatTipoDocumento = (tipoTecnico) => {
  return NOMBRES_DOCUMENTOS[tipoTecnico] || tipoTecnico;
};

/**
 * Mapeo de Clasificación de Actividad.
 */
export const NOMBRES_CLASIFICACION_ACTIVIDAD = {
  'C': 'Comercializador (C)',
  'D': 'Distribuidor autorizado (D)',
  'R': 'Representante (R)',
  'F': 'Fabricante (F)',
  'I': 'Importador (I)'
};

/**
 * Traduce el valor interno de clasificación de actividad a su etiqueta.
 */
export const formatClasificacionActividad = (valor) => {
  return NOMBRES_CLASIFICACION_ACTIVIDAD[valor] || valor;
};
