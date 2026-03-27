import FileUploadField from '../FileUploadField';
import AlertasRazonSocial from '../AlertasRazonSocial';
import AlertasNit from '../AlertasNit';
import AlertasNombreRepresentante from '../AlertasNombreRepresentante';
import AlertasNumeroDocRepresentante from '../AlertasNumeroDocRepresentante';
import AlertasDireccion from '../AlertasDireccion';
import { DOCUMENTOS_CONFIG } from '../../data/formularioConfig';

/**
 * Paso 1 — Documentos Adjuntos.
 *
 * Renderiza los campos de carga según el tipo de persona y muestra alertas
 * de inconsistencia cuando la razón social extraída de un documento no coincide
 * con la ingresada en el formulario.
 */
export default function PasoDocumentos({
  formData, documentos, onFileChange, onRemoveFile, onOpenHelp, uploadingDoc,
  alertasRazonSocial, alertasNit, alertasNombreRepresentante, alertasNumeroDocRepresentante, alertasDireccion,
}) {
  return (
    <div className="form-card">
      <h2 className="section-title">📄 Documentos Adjuntos</h2>
      <p className="section-subtitle">
        Al adjuntar cada documento el sistema extrae y pre-llena los campos automáticamente.
      </p>

      <div className="info-box">
        <p>💡 Cada documento se analiza con IA en el momento de carga. Los campos del formulario se completan solos. (Recuerda validar que todo esté correcto).</p>
      </div>

      <AlertasRazonSocial alertas={alertasRazonSocial} />
      <AlertasNit alertas={alertasNit} />
      <AlertasNombreRepresentante alertas={alertasNombreRepresentante} />
      <AlertasNumeroDocRepresentante alertas={alertasNumeroDocRepresentante} />
      <AlertasDireccion alertas={alertasDireccion} />

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
