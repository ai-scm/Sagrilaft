import {
  TIPO_DOCUMENTO_CERTIFICADO_SAGRILAFT,
  TIPO_DOCUMENTO_FORMULARIO_PDF,
  TIPO_DOCUMENTO_REPORTE_FINAL,
} from '../config/constantes';

const TIPOS_EXCLUIDOS_DE_ADJUNTOS = [
  TIPO_DOCUMENTO_FORMULARIO_PDF,
  TIPO_DOCUMENTO_CERTIFICADO_SAGRILAFT,
  TIPO_DOCUMENTO_REPORTE_FINAL,
];

function obtenerUltimaVersion(documentos, tipoDocumento) {
  return [...documentos]
    .filter(documento => documento.tipo_documento === tipoDocumento)
    .sort((a, b) => b.version_numero - a.version_numero)[0] ?? null;
}

export function useDocumentosExpediente(documentos = []) {
  return {
    pdfFormulario: obtenerUltimaVersion(documentos, TIPO_DOCUMENTO_FORMULARIO_PDF),
    reporteFinal: obtenerUltimaVersion(documentos, TIPO_DOCUMENTO_REPORTE_FINAL),
    documentosAdjuntos: documentos.filter(
      documento => !TIPOS_EXCLUIDOS_DE_ADJUNTOS.includes(documento.tipo_documento),
    ),
  };
}
