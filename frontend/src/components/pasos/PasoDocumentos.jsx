import FileUploadField from '../FileUploadField';
import { DOCUMENTOS_CONFIG } from '../../data/formularioConfig';

/**
 * Paso 1 — Documentos Adjuntos.
 * Renderiza los campos de carga según el tipo de persona.
 */
export default function PasoDocumentos({
  formData, documentos, onFileChange, onRemoveFile, onOpenHelp, uploadingDoc,
}) {
  return (
    <div className="form-card">
      <h2 className="section-title">📄 Documentos Adjuntos</h2>
      <p className="section-subtitle">
        Al adjuntar cada documento el sistema extrae y pre-llena los campos automáticamente.
      </p>

      <div className="info-box">
        <p>💡 Cada documento se analiza con IA en el momento de carga. Los campos del formulario se completan solos.</p>
      </div>

      {DOCUMENTOS_CONFIG
        .filter(d => !d.soloJuridica || formData.tipo_persona !== 'natural')
        .map(d => (
          <FileUploadField
            key={d.tipoDoc}
            label={d.label}
            tipoDoc={d.tipoDoc}
            documentos={documentos}
            onFileChange={onFileChange}
            onRemove={onRemoveFile}
            onOpenHelp={onOpenHelp}
            accepted={d.accepted}
            hint={d.hint}
            uploading={uploadingDoc[d.tipoDoc]}
          />
        ))
      }
    </div>
  );
}
