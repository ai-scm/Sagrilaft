/**
 * Mapa centralizado de qué campos del formulario rellena cada tipo de documento.
 * Sirve como única de fuente de verdad en el frontend para saber qué limpiar.
 */
export const MAPEO_DOCUMENTOS = {
  rut: [
    "razon_social",
    "numero_identificacion",
    "digito_verificacion",
    "tipo_persona",
    "direccion",
    "correo",
    "telefono",
    "codigo_ica",
  ],
  certificado_existencia: [
    "razon_social",
    "tipo_persona",
    "tipo_identificacion",
    "numero_identificacion",
    "nombre_representante",
    "numero_doc_representante",
    "termino_duracion",
    "direccion",
    "ciudad",
    "correo",
    "telefono",
  ],
  cedula_representante: [
    "nombre_representante",
    "numero_doc_representante",
    "tipo_doc_representante",
    "fecha_nacimiento",
    "ciudad_nacimiento",
    "fecha_expedicion",
    "ciudad_expedicion",
  ],
  estados_financieros: [
    "total_activos",
    "total_pasivos",
    "patrimonio",
    "ingresos_mensuales",
    "egresos_mensuales",
  ]
};

export const obtenerCamposDeDocumento = (tipoDocumento) => {
  return MAPEO_DOCUMENTOS[tipoDocumento] || [];
};
