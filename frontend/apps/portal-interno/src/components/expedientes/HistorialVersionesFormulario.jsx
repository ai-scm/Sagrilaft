import { useState } from 'react';
import { Download, GitCompare } from 'lucide-react';
import { api } from '../../services/api';
import ModalComparacionVersiones from './ModalComparacionVersiones';
import {
  TIPO_DOCUMENTO_FORMULARIO_PDF,
  formatearFechaHora,
  formatearBytes,
} from '../../config/constantes';

// ── Sub-componente ────────────────────────────────────────────────────────────
function FilaVersion({ documento, esVersionActiva, formularioId }) {
  const [descargando, setDescargando] = useState(false);

  async function handleDescargar() {
    setDescargando(true);
    try {
      await api.descargarDocumento(formularioId, documento.id, documento.nombre_archivo);
    } finally {
      setDescargando(false);
    }
  }

  const tamano = documento.tamano ? formatearBytes(documento.tamano) : null;
  const fecha = documento.created_at ? formatearFechaHora(documento.created_at) : null;

  return (
    <div className={`timeline-row ${esVersionActiva ? 'active-row' : ''}`}>
      <div className="timeline-marker">
        <div className={`marker-dot ${esVersionActiva ? 'active' : ''}`}></div>
      </div>
      <div className="timeline-content">
        <div className="timeline-info">
          <span className="version-name">v{documento.version_numero}</span>
          <div className="doc-tags">
            {esVersionActiva && <span className="badge-version-active">Versión activa</span>}
            {documento.subido_por && documento.subido_por !== 'SISTEMA' && (
              <span className="badge-version-manual" title={`Subido por: ${documento.subido_por}`}>Carga manual</span>
            )}
          </div>
          <div className="version-meta">
            {fecha && <span>{fecha}</span>}
            {tamano && <><span className="separator">•</span><span>{tamano}</span></>}
            <><span className="separator">•</span><span>{documento.nombre_archivo}</span></>
          </div>
        </div>
        <div className="timeline-actions">
          <button 
            className="btn-outline btn-outline-gray" 
            onClick={handleDescargar}
            disabled={descargando}
          >
            <Download size={14} /> Descargar
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Componente principal ──────────────────────────────────────────────────────
export default function HistorialVersionesFormulario({ documentos, formularioId }) {
  const [comparacion, setComparacion] = useState(null);
  const [cargandoComparacion, setCargandoComparacion] = useState(false);
  const [errorComparacion, setErrorComparacion] = useState(null);
  const [errorDescarga, setErrorDescarga] = useState(null);
  const [mostrarComparacion, setMostrarComparacion] = useState(false);
  const [descargandoReporte, setDescargandoReporte] = useState(false);

  const versionesDelFormulario = [...documentos]
    .filter(doc => doc.tipo_documento === TIPO_DOCUMENTO_FORMULARIO_PDF)
    .sort((a, b) => b.version_numero - a.version_numero);

  if (versionesDelFormulario.length === 0) return null;

  const numeroVersionMaxima = versionesDelFormulario[0].version_numero;

  async function handleVerCambios() {
    setMostrarComparacion(true);
    setCargandoComparacion(true);
    setErrorComparacion(null);
    setErrorDescarga(null);
    try {
      setComparacion(await api.compararVersionesFormulario(formularioId));
    } catch (err) {
      setErrorComparacion(err.message || 'No se pudo comparar las versiones.');
    } finally {
      setCargandoComparacion(false);
    }
  }

  async function handleDescargarEvidencia() {
    setDescargandoReporte(true);
    setErrorDescarga(null);
    try {
      await api.descargarReporteComparacion(formularioId);
    } catch (err) {
      setErrorDescarga(err.message || 'No se pudo descargar la evidencia.');
    } finally {
      setDescargandoReporte(false);
    }
  }

  function handleCerrarComparacion() {
    setMostrarComparacion(false);
    setErrorDescarga(null);
  }

  return (
    <>
      <div className="section-header">
        <h2 className="section-title">Historial de versiones del formulario</h2>
        {versionesDelFormulario.length > 1 && (
          <button type="button" className="btn-outline" onClick={handleVerCambios}>
            <GitCompare size={14} /> Ver todos los cambios
          </button>
        )}
      </div>

      <div className="card timeline-card">
        <div className="timeline-list">
          {versionesDelFormulario.map(doc => (
            <FilaVersion
              key={doc.id}
              documento={doc}
              esVersionActiva={doc.version_numero === numeroVersionMaxima}
              formularioId={formularioId}
            />
          ))}
        </div>
      </div>

      <ModalComparacionVersiones
        visible={mostrarComparacion}
        comparacion={comparacion}
        cargando={cargandoComparacion}
        error={errorComparacion}
        errorDescarga={errorDescarga}
        descargandoReporte={descargandoReporte}
        onDescargarReporte={handleDescargarEvidencia}
        onCerrar={handleCerrarComparacion}
      />
    </>
  );
}
