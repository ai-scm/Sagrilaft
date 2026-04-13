import { HelpIcon } from './HelpPanel';
import helpTexts from '../data/helpTexts';

/**
 * Campo de carga de archivo con drag-and-drop y estado de uploading.
 * Muestra el archivo cargado o la zona de drop según el estado.
 */
export default function FileUploadField({
  label, tipoDoc, documentos, onFileChange, onRemove,
  onOpenHelp, accepted, hint, uploading, eliminando,
}) {
  const doc = documentos[tipoDoc];
  const helpKey = `doc_${tipoDoc}`;
  const hasHelp = !!helpTexts[helpKey];

  const fileName = doc?.nombre_archivo ?? doc?.name ?? null;
  const fileSize = doc?.tamano ?? doc?.size ?? null;

  const handleDragOver = (e) => {
    e.preventDefault();
    e.currentTarget.classList.add('dragover');
  };

  const handleDragLeave = (e) => {
    e.currentTarget.classList.remove('dragover');
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.currentTarget.classList.remove('dragover');
    const droppedFile = e.dataTransfer.files[0];
    if (droppedFile) onFileChange(tipoDoc, droppedFile);
  };

  const handleClick = () => {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = accepted || '*';
    input.onchange = (e) => {
      if (e.target.files[0]) onFileChange(tipoDoc, e.target.files[0]);
    };
    input.click();
  };

  return (
    <div style={{ marginBottom: '16px' }}>
      <label className="form-label">
        {label}
        {hasHelp && <HelpIcon fieldKey={helpKey} onOpenHelp={onOpenHelp} />}
        {hint && (
          <span style={{ fontWeight: '400', color: 'var(--warning)', fontSize: '0.75rem', marginLeft: '8px' }}>
            ({hint})
          </span>
        )}
      </label>

      {uploading ? (
        <div className="file-upload-zone" style={{ cursor: 'default', opacity: 0.7 }}>
          <div className="upload-icon">⏳</div>
          <div className="upload-text">Analizando con IA...</div>
        </div>
      ) : !fileName ? (
        <div
          className="file-upload-zone"
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onClick={handleClick}
        >
          <div className="upload-icon">📁</div>
          <div className="upload-text">
            Arrastre un archivo aquí o <strong>haga clic para seleccionar</strong>
          </div>
        </div>
      ) : (
        <div className="file-upload-list">
          <div className="file-upload-item">
            <span className="file-icon">✅</span>
            <div className="file-info">
              <div className="file-name">{fileName}</div>
              {fileSize && <div className="file-size">{(fileSize / 1024).toFixed(1)} KB</div>}
            </div>
            <button 
              type="button" 
              className="file-remove" 
              onClick={() => onRemove(tipoDoc)} 
              title="Eliminar"
              disabled={eliminando}
              style={{ opacity: eliminando ? 0.3 : 1, cursor: eliminando ? 'not-allowed' : 'pointer' }}
            >
              {eliminando ? '⏳' : '✕'}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
