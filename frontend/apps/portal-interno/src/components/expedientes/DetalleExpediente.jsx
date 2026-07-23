/**
 * DetalleExpediente — Vista completa de un formulario enviado.
 *
 * Se superpone a la lista como overlay de pantalla completa. Muestra:
 *   1. Banner de descarga del PDF oficial (FORMULARIO_PDF generado al enviar).
 *   2. Documentos adjuntos por el cliente/proveedor con descarga directa.
 *
 * Los datos del formulario NO se muestran en pantalla — toda la información
 * sensible está contenida exclusivamente en el PDF oficial descargable.
 */

import { useState, useEffect } from 'react';
import { Download, Upload, ShieldCheck, FileText, FileBarChart } from 'lucide-react';
import './DetalleExpediente.css';
import '../modals/Modals.css';
import { api } from '../../services/api';
import { useExpedienteDetalle } from '../../hooks/useExpedienteDetalle';
import Spinner from '@shared/components/ui/Spinner';
import Alert from '@shared/components/ui/Alert';
import BadgeEstadoFormulario from '../badges/BadgeEstadoFormulario';
import ModalDevolucion from '../modals/ModalDevolucion';
import ModalRechazo from '../modals/ModalRechazo';
import ModalCargaManual from '../modals/ModalCargaManual';
import ModalConfirmacion from '../modals/ModalConfirmacion';
import ModalCargaReporteFinal from '../modals/ModalCargaReporteFinal';
import ModalReaperturaActualizacion from '../modals/ModalReaperturaActualizacion';
import HistorialVersionesFormulario from './HistorialVersionesFormulario';
import HistorialExpediente from './HistorialExpediente';
import PanelAlertasAuditoria from './PanelAlertasAuditoria';
import {
  ETIQUETA_TIPO_CONTRAPARTE,
  ETIQUETA_CAUSAL_CIERRE,
  formatearFechaHora,
  formatearBytes,
  TIPO_DOCUMENTO_FORMULARIO_PDF,
  TIPO_DOCUMENTO_CERTIFICADO_SAGRILAFT,
  TIPO_DOCUMENTO_REPORTE_FINAL,
  TIPO_SOLICITUD_ACTUALIZACION,
  ETIQUETA_TIPO_SOLICITUD,
  MODO_TRABAJO_ACTUALIZACION_REABIERTA,
} from '../../config/constantes';
import { ESTADO_FORM_CERRADO } from '@shared/utils/constantes';
import { formatTipoDocumento } from '../../utils/formateadores';

const ESTADO_ENVIADO = 'enviado';
const ESTADO_EN_CORRECCION = 'en_correccion';
const ESTADO_VALIDADO = 'validado';
const ESTADO_PENDIENTE_FIRMA = 'pendiente_firma';
const ESTADO_FIRMADO = 'firmado';
const ESTADO_CERRADO = 'cerrado';

const TIPOS_EXCLUIDOS_DE_ADJUNTOS = [TIPO_DOCUMENTO_FORMULARIO_PDF, TIPO_DOCUMENTO_CERTIFICADO_SAGRILAFT, TIPO_DOCUMENTO_REPORTE_FINAL];

// ── Estilos ─────────────────────────────────────────────────────────────────

// ── Sub-componentes ───────────────────────────────────────────────────────────

function BannerPdfFormulario({ documento, formularioId }) {
  const [descargando, setDescargando] = useState(false);
  const tamano = documento.tamano ? formatearBytes(documento.tamano) : '';
  const fecha = documento.created_at ? formatearFechaHora(documento.created_at) : null;

  async function handleDescargar() {
    setDescargando(true);
    try {
      await api.descargarDocumento(formularioId, documento.id, documento.nombre_archivo);
    } finally {
      setDescargando(false);
    }
  }

  return (
    <div className="card summary-card">
      <div className="card-icon">
        <FileText className="text-blue-500" size={24} />
      </div>
      <div className="card-content">
        <h3 className="doc-title">Formulario Oficial SAGRILAFT</h3>
        <div className="doc-meta">
          <span>{documento.nombre_archivo}</span>
          {fecha && <><span className="separator">•</span><span>{fecha}</span></>}
          {tamano && <><span className="separator">•</span><span>{tamano}</span></>}
        </div>
      </div>
      <button
        className="btn-icon"
        onClick={handleDescargar}
        disabled={descargando}
        title="Descargar"
        style={{ opacity: descargando ? 0.5 : 1 }}
      >
        <Download size={18} />
      </button>
    </div>
  );
}

function FilaDocumento({ documento, formularioId }) {
  const [descargando, setDescargando] = useState(false);

  async function handleDescargar() {
    setDescargando(true);
    try {
      await api.descargarDocumento(formularioId, documento.id, documento.nombre_archivo);
    } finally {
      setDescargando(false);
    }
  }

  const tamano = documento.tamano ? formatearBytes(documento.tamano) : '—';
  const fecha = documento.created_at ? formatearFechaHora(documento.created_at) : '—';

  return (
    <tr>
      <td>
        <div className="cell-doc-name">
          <FileText size={16} className="text-gray-400" />
          <span title={documento.nombre_archivo}>{documento.nombre_archivo}</span>
        </div>
      </td>
      <td>{formatTipoDocumento(documento.tipo_documento)}</td>
      <td>{tamano}</td>
      <td>{documento.subido_por || '—'}</td>
      <td>{fecha}</td>
      <td className="text-right">
        <button
          className="btn-icon-small"
          onClick={handleDescargar}
          disabled={descargando}
          title="Descargar"
          style={{ opacity: descargando ? 0.5 : 1 }}
        >
          <Download size={16} />
        </button>
      </td>
    </tr>
  );
}

function BtnDescargaFirmado({ formularioId }) {
  const [descargando, setDescargando] = useState(false);
  async function handleDescargar() {
    setDescargando(true);
    try { await api.descargarDocumentoFirmado(formularioId); }
    finally { setDescargando(false); }
  }
  return (
    <button
      onClick={handleDescargar}
      disabled={descargando}
      className="btn-firma btn-firma-color-firmado"
    >
      {descargando ? 'Descargando…' : 'Descargar firmado'}
    </button>
  );
}

function BannerFirma({ estado, modoTrabajo, formularioId, tipoPersona, documentoFirmadoDisponible, onFirmaEnviada }) {
  const [enviando, setEnviando] = useState(false); // enviar a ZohoSign (VALIDADO)
  const [aprobando, setAprobando] = useState(false); // aprobar expediente (ENVIADO)
  const [cancelando, setCancelando] = useState(false);
  const [verificando, setVerificando] = useState(false);
  const [reabriendoRevision, setReabriendoRevision] = useState(false);
  const [motivoReapertura, setMotivoReapertura] = useState('');
  const [errorFirma, setErrorFirma] = useState(null);
  const [deshaciendoAprobacion, setDeshaciendoAprobacion] = useState(false);
  const [deshaciendoDevolucion, setDeshaciendoDevolucion] = useState(false);
  const [mostrarModalDevolucion, setMostrarModalDevolucion] = useState(false);
  const [mostrarModalRechazo, setMostrarModalRechazo] = useState(false);
  const [mostrarModalAprobacion, setMostrarModalAprobacion] = useState(false);
  const [mostrarModalReabrirRevision, setMostrarModalReabrirRevision] = useState(false);
  const motivoReaperturaValido = motivoReapertura.trim().length >= 20;

  async function handleEnviarAFirma() {
    setEnviando(true);
    setErrorFirma(null);
    try {
      await api.enviarAFirma(formularioId);
      onFirmaEnviada();
    } catch (err) {
      setErrorFirma(err.message || 'Error al enviar a firma. Intente nuevamente.');
    } finally {
      setEnviando(false);
    }
  }

  async function handleCancelarFirma() {
    setCancelando(true);
    setErrorFirma(null);
    try {
      await api.cancelarFirma(formularioId);
      onFirmaEnviada();
    } catch (err) {
      setErrorFirma(err.message || 'Error al cancelar la firma. Intente nuevamente.');
    } finally {
      setCancelando(false);
    }
  }

  async function handleVerificarFirma() {
    setVerificando(true);
    setErrorFirma(null);
    try {
      await api.verificarFirma(formularioId);
      onFirmaEnviada();
    } catch (err) {
      setErrorFirma(err.message || 'Error al verificar el estado. Intente nuevamente.');
    } finally {
      setVerificando(false);
    }
  }

  async function handleAprobar() {
    setAprobando(true);
    setErrorFirma(null);
    try {
      await api.aprobarExpediente(formularioId);
      setMostrarModalAprobacion(false);
      onFirmaEnviada();
    } catch (err) {
      setErrorFirma(err.message || 'Error al aprobar.');
    } finally {
      setAprobando(false);
    }
  }

  async function handleDeshacerAprobacion() {
    if (!window.confirm('¿Está seguro de que desea deshacer la aprobación de este formulario?')) {
      return;
    }
    setDeshaciendoAprobacion(true);
    setErrorFirma(null);
    try {
      await api.deshacerAprobacionExpediente(formularioId);
      onFirmaEnviada();
    } catch (err) {
      setErrorFirma(err.message || 'Error al deshacer aprobación.');
    } finally {
      setDeshaciendoAprobacion(false);
    }
  }

  async function handleDeshacerDevolucion() {
    if (!window.confirm('¿Está seguro de que desea deshacer la devolución de este formulario?')) {
      return;
    }
    setDeshaciendoDevolucion(true);
    setErrorFirma(null);
    try {
      await api.deshacerDevolucionExpediente(formularioId);
      onFirmaEnviada();
    } catch (err) {
      setErrorFirma(err.message || 'Error al deshacer devolución.');
    } finally {
      setDeshaciendoDevolucion(false);
    }
  }

  async function handleReabrirRevisionFirmado() {
    if (!motivoReaperturaValido) return;
    setReabriendoRevision(true);
    setErrorFirma(null);
    try {
      await api.reabrirRevisionFirmado(formularioId, motivoReapertura.trim());
      setMostrarModalReabrirRevision(false);
      setMotivoReapertura('');
      onFirmaEnviada();
    } catch (err) {
      setErrorFirma(err.message || 'Error al reabrir la revisión.');
    } finally {
      setReabriendoRevision(false);
    }
  }

  if (estado === ESTADO_ENVIADO) {
    const ocupado = aprobando;
    return (
      <>
        <div className="banner-firma banner-firma-revisar">
          <div className="banner-firma-textos">
            <p className="banner-firma-titulo">Formulario recibido — pendiente de revisión</p>
            <p className="banner-firma-subtitulo">
              {errorFirma || 'Revise los documentos adjuntos y apruebe, rechace o devuelva el formulario.'}
            </p>
          </div>
          <div style={{ display: 'flex', gap: '8px', flexShrink: 0, flexWrap: 'wrap' }}>
            <button
              className="btn-firma btn-firma-color-revisar"
              onClick={() => setMostrarModalAprobacion(true)}
              disabled={ocupado}
              type="button"
            >
              Aprobar
            </button>
            <button
              className="btn-firma btn-firma-color-correccion"
              onClick={() => setMostrarModalRechazo(true)}
              disabled={ocupado}
              type="button"
            >
              Rechazar
            </button>
            <button
              className="btn-firma btn-firma-color-correccion"
              onClick={() => setMostrarModalDevolucion(true)}
              disabled={ocupado}
              type="button"
            >
              Devolver
            </button>
            {documentoFirmadoDisponible && <BtnDescargaFirmado formularioId={formularioId} />}
          </div>
        </div>
        <ModalConfirmacion
          visible={mostrarModalAprobacion}
          titulo="¿Aprobar formulario?"
          mensaje="El expediente pasará a estado Validado y quedará listo para enviarse a firma electrónica. ¿Desea continuar?"
          textoConfirmar="Sí, aprobar"
          onConfirmar={handleAprobar}
          onCancelar={() => setMostrarModalAprobacion(false)}
          ocupado={aprobando}
        />
        <ModalDevolucion
          visible={mostrarModalDevolucion}
          formularioId={formularioId}
          tipoPersona={tipoPersona}
          onDevuelto={() => { setMostrarModalDevolucion(false); onFirmaEnviada(); }}
          onCancelar={() => setMostrarModalDevolucion(false)}
        />
        <ModalRechazo
          visible={mostrarModalRechazo}
          formularioId={formularioId}
          onRechazado={() => { setMostrarModalRechazo(false); onFirmaEnviada(); }}
          onCancelar={() => setMostrarModalRechazo(false)}
        />
      </>
    );
  }

  if (estado === ESTADO_EN_CORRECCION) {
    if (modoTrabajo === MODO_TRABAJO_ACTUALIZACION_REABIERTA) {
      return (
        <div className="banner-firma banner-firma-revisar">
          <div className="banner-firma-textos">
            <p className="banner-firma-titulo">Actualización reabierta - en trabajo</p>
            <p className="banner-firma-subtitulo">
              El expediente quedó habilitado para actualizar información, cargar documentos y completar nuevos cuestionarios.
            </p>
          </div>
        </div>
      );
    }

    return (
      <div className="banner-firma banner-firma-correccion">
        <div className="banner-firma-textos">
          <p className="banner-firma-titulo">Formulario devuelto — en corrección</p>
          <p className="banner-firma-subtitulo">
            {errorFirma || 'Se notificó al destinatario. El formulario estará disponible nuevamente cuando el remitente reenvíe la versión corregida.'}
          </p>
        </div>
        <div style={{ display: 'flex', gap: '8px', flexShrink: 0, flexWrap: 'wrap' }}>
          <button
            className="btn-outline"
            onClick={handleDeshacerDevolucion}
            disabled={deshaciendoDevolucion}
            type="button"
          >
            {deshaciendoDevolucion ? 'Deshaciendo…' : 'Deshacer devolución'}
          </button>
        </div>
      </div>
    );
  }

  if (estado === ESTADO_VALIDADO) {
    return (
      <div className="banner-firma banner-firma-validado">
        <div className="banner-firma-textos">
          <p className="banner-firma-titulo">Formulario listo para firma electrónica</p>
          <p className="banner-firma-subtitulo">
            {errorFirma || 'El formulario fue validado. Envíelo a ZohoSign para que la contraparte firme.'}
          </p>
        </div>
        <div style={{ display: 'flex', gap: '8px', flexShrink: 0, flexWrap: 'wrap' }}>
          <button
            className="btn-outline"
            onClick={handleDeshacerAprobacion}
            disabled={enviando || deshaciendoAprobacion}
            type="button"
          >
            {deshaciendoAprobacion ? 'Deshaciendo…' : 'Deshacer aprobación'}
          </button>
          <button
            className="btn-firma btn-firma-color-validado"
            onClick={handleEnviarAFirma}
            disabled={enviando || deshaciendoAprobacion}
            type="button"
          >
            {enviando ? 'Enviando…' : 'Enviar a firma'}
          </button>
        </div>
      </div>
    );
  }

  if (estado === ESTADO_PENDIENTE_FIRMA) {
    const ocupado = cancelando || verificando;
    return (
      <div className="banner-firma banner-firma-pendiente">
        <div className="banner-firma-textos">
          <p className="banner-firma-titulo">Firma electrónica pendiente</p>
          <p className="banner-firma-subtitulo">
            {errorFirma || 'Se envió la solicitud de firma a ZohoSign. Esperando que la contraparte firme.'}
          </p>
        </div>
        <div style={{ display: 'flex', gap: '8px', flexShrink: 0 }}>
          <button
            className="btn-firma btn-firma-color-pendiente"
            onClick={handleVerificarFirma}
            disabled={ocupado}
            type="button"
          >
            {verificando ? 'Verificando…' : 'Verificar estado'}
          </button>
          <button
            className="btn-firma btn-firma-color-pendiente"
            onClick={handleCancelarFirma}
            disabled={ocupado}
            type="button"
          >
            {cancelando ? 'Cancelando…' : 'Cancelar'}
          </button>
        </div>
      </div>
    );
  }

  if (estado === ESTADO_FIRMADO) {
    return (
      <>
        <div className="banner-firma banner-firma-firmado">
          <div className="banner-firma-textos">
            <p className="banner-firma-titulo">Documentos firmados electrónicamente</p>
            <p className="banner-firma-subtitulo">
              {errorFirma || 'La contraparte firmó el formulario y Certificado vía ZohoSign.'}
            </p>
          </div>
          <div style={{ display: 'flex', gap: '8px', flexShrink: 0, flexWrap: 'wrap' }}>
            <BtnDescargaFirmado formularioId={formularioId} />
            <button
              className="btn-firma btn-firma-color-reabrir"
              onClick={() => {
                setErrorFirma(null);
                setMostrarModalReabrirRevision(true);
              }}
              disabled={reabriendoRevision}
              type="button"
            >
              Reabrir revisión
            </button>
          </div>
        </div>
        <ModalConfirmacion
          visible={mostrarModalReabrirRevision}
          titulo="Reabrir revisión"
          textoConfirmar="Reabrir revisión"
          colorConfirmar="#c2410c"
          onConfirmar={handleReabrirRevisionFirmado}
          onCancelar={() => setMostrarModalReabrirRevision(false)}
          ocupado={reabriendoRevision}
          confirmarDeshabilitado={!motivoReaperturaValido}
        >
          <div>
            <p style={{ margin: '0 0 14px', color: '#475569', lineHeight: 1.5, fontSize: '0.9rem' }}>
              El documento firmado se conservará y el expediente volverá a “Formulario recibido — pendiente de revisión”.
            </p>
            <label htmlFor="motivo-reapertura-firma" className="form-label">
              Motivo de reapertura
            </label>
            <textarea
              id="motivo-reapertura-firma"
              className="form-input form-textarea"
              value={motivoReapertura}
              onChange={e => setMotivoReapertura(e.target.value)}
              rows={4}
              maxLength={1000}
              disabled={reabriendoRevision}
              placeholder="Ej. Se detectaron inconsistencias en los datos firmados..."
            />
            <div className="char-counter">
              <span>{motivoReapertura.trim().length} / 1000</span>
              <span style={{ color: motivoReaperturaValido ? '#166534' : '#DC2626' }}>
                {motivoReaperturaValido ? 'Mínimo cumplido' : `Mínimo 20 caracteres (${motivoReapertura.trim().length}/20)`}
              </span>
            </div>
          </div>
        </ModalConfirmacion>
      </>
    );
  }

  if (estado === ESTADO_CERRADO && documentoFirmadoDisponible) {
    return (
      <div className="banner-firma banner-firma-cerrado">
        <div className="banner-firma-textos">
          <p className="banner-firma-titulo">Expediente cerrado</p>
          <p className="banner-firma-subtitulo">
            El expediente está cerrado. El documento firmado se conserva como evidencia.
          </p>
        </div>
        <BtnDescargaFirmado formularioId={formularioId} />
      </div>
    );
  }

  return null;
}

function ModalSagrilaft({ visible, onConfirmar, onCancelar, ocupado, error, expediente }) {
  const [datos, setDatos] = useState({
    tipo_identificacion: expediente?.tipo_identificacion || '',
    numero_identificacion: expediente?.numero_identificacion || '',
    nombre_completo: expediente?.razon_social || '',
    fecha_expedicion: '' // Siempre arranca vacío para que lo digiten
  });

  // Solo si cambia el expediente actualizamos los valores iniciales.
  useEffect(() => {
    if (visible && expediente) {
      setDatos({
        tipo_identificacion: expediente.tipo_identificacion || '',
        numero_identificacion: expediente.numero_identificacion || '',
        nombre_completo: expediente.razon_social || '',
        fecha_expedicion: '' 
      });
    }
  }, [visible, expediente]);

  if (!visible) return null;

  return (
    <div className="modal-overlay" role="dialog" aria-modal="true">
      <div className="modal-container" style={{ maxWidth: '460px' }}>
        <div className="modal-header">
          <h3 className="modal-title">Consultar SAGRILAFT</h3>
          <p className="modal-desc">
            Confirma o edita los datos que se enviarán a la central de riesgo.
          </p>
        </div>
        
        <div className="modal-body">
          {error && <Alert mensaje={error} style={{ marginBottom: '16px' }} />}
          
          <div className="form-group" style={{ marginBottom: '12px' }}>
            <label className="field-label" style={{ display: 'block', marginBottom: '4px' }}>Tipo de Identificación</label>
            <input 
              className="input-base" 
              type="text"
              value={datos.tipo_identificacion} 
              onChange={e => setDatos({...datos, tipo_identificacion: e.target.value})}
              disabled={ocupado}
              style={{ width: '100%', padding: '8px', border: '1px solid #d1d5db', borderRadius: '4px' }}
            />
          </div>

          <div className="form-group" style={{ marginBottom: '12px' }}>
            <label className="field-label" style={{ display: 'block', marginBottom: '4px' }}>Número de Identificación</label>
            <input 
              className="input-base" 
              type="text"
              value={datos.numero_identificacion} 
              onChange={e => setDatos({...datos, numero_identificacion: e.target.value})}
              disabled={ocupado}
              style={{ width: '100%', padding: '8px', border: '1px solid #d1d5db', borderRadius: '4px' }}
            />
          </div>

          <div className="form-group" style={{ marginBottom: '12px' }}>
            <label className="field-label" style={{ display: 'block', marginBottom: '4px' }}>Nombre / Razón Social</label>
            <input 
              className="input-base" 
              type="text"
              value={datos.nombre_completo} 
              onChange={e => setDatos({...datos, nombre_completo: e.target.value})}
              disabled={ocupado}
              style={{ width: '100%', padding: '8px', border: '1px solid #d1d5db', borderRadius: '4px' }}
            />
          </div>

          <div className="form-group" style={{ marginBottom: '16px' }}>
            <label className="field-label" style={{ display: 'block', marginBottom: '4px' }}>
              Fecha de Expedición <span style={{ color: '#6b7280', fontSize: '0.85em', fontWeight: 'normal' }}>(dd/mm/yyyy - Obligatorio para CE y PPT)</span>
            </label>
            <input 
              className="input-base" 
              type="text"
              placeholder="Ej: 01/12/2017"
              value={datos.fecha_expedicion} 
              onChange={e => setDatos({...datos, fecha_expedicion: e.target.value})}
              disabled={ocupado}
              style={{ width: '100%', padding: '8px', border: '1px solid #d1d5db', borderRadius: '4px' }}
            />
          </div>
        </div>

        <div className="modal-footer" style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', padding: '16px', borderTop: '1px solid #f3f4f6' }}>
          <button className="btn btn-secondary" onClick={onCancelar} disabled={ocupado} type="button">
            Cancelar
          </button>
          <button 
            className="btn btn-primary" 
            onClick={() => onConfirmar(datos)} 
            disabled={ocupado || !datos.tipo_identificacion || !datos.numero_identificacion || !datos.nombre_completo}
            type="button"
          >
            {ocupado ? 'Consultando...' : 'Verificar en Tusdatos'}
          </button>
        </div>
      </div>
    </div>
  );
}


// ── Componente principal ──────────────────────────────────────────────────────

export default function DetalleExpediente({ formularioId, razonSocial, onVolver }) {
  const { expediente, cargando, error, recargarExpediente } = useExpedienteDetalle(formularioId);
  const [mostrarModalCargaManual, setMostrarModalCargaManual] = useState(false);
  const [mostrarModalReapertura, setMostrarModalReapertura] = useState(false);
  const [avisoReapertura, setAvisoReapertura] = useState(null);

  const tipoLabel = expediente ? (ETIQUETA_TIPO_CONTRAPARTE[expediente.tipo_contraparte] ?? expediente.tipo_contraparte) : '';
  const tipoSolicitudLabel = expediente ? (ETIQUETA_TIPO_SOLICITUD[expediente.tipo_solicitud] ?? expediente.tipo_solicitud) : '';
  const todosDocumentos = expediente?.documentos ?? [];
  // Puede haber varias versiones del PDF; la activa es la de mayor version_numero.
  const pdfFormulario = [...todosDocumentos]
    .filter(d => d.tipo_documento === TIPO_DOCUMENTO_FORMULARIO_PDF)
    .sort((a, b) => b.version_numero - a.version_numero)[0] ?? null;
  const reporteFinal = [...todosDocumentos]
    .filter(d => d.tipo_documento === TIPO_DOCUMENTO_REPORTE_FINAL)
    .sort((a, b) => b.version_numero - a.version_numero)[0] ?? null;
  const documentosAdjuntos = todosDocumentos.filter(d => !TIPOS_EXCLUIDOS_DE_ADJUNTOS.includes(d.tipo_documento));

  const estaCerrado = expediente?.estado === ESTADO_FORM_CERRADO;
  // Permitir reapertura para iniciar un proceso de actualización desde cualquier expediente cerrado (ej. Vinculación)
  const permiteReaperturaActualizacion = estaCerrado;
  const [mostrarModalReporteFinal, setMostrarModalReporteFinal] = useState(false);
  const [descargandoTodos, setDescargandoTodos] = useState(false);

  const [verificandoSagrilaft, setVerificandoSagrilaft] = useState(false);
  const [resultadoSagrilaft, setResultadoSagrilaft] = useState(null);
  const [mostrarModalSagrilaft, setMostrarModalSagrilaft] = useState(false);
  
  const [descargandoCertificado, setDescargandoCertificado] = useState(false);
  const [errorCertificado, setErrorCertificado] = useState(null);

  async function handleVerificarSagrilaft(datosManuales) {
    setVerificandoSagrilaft(true);
    setResultadoSagrilaft(null);
    try {
      const res = await api.verificarSagrilaft(formularioId, datosManuales);
      setResultadoSagrilaft(res);
      setMostrarModalSagrilaft(false);
      // Recargar para obtener el reporte_id recién guardado
      recargarExpediente();
    } catch (err) {
      setResultadoSagrilaft({ error: err.message || 'Error de conexión' });
    } finally {
      setVerificandoSagrilaft(false);
    }
  }

  async function handleDescargarCertificado() {
    setDescargandoCertificado(true);
    setErrorCertificado(null);
    try {
      const blob = await api.descargarCertificadoSagrilaft(formularioId);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `sagrilaft_${expediente.codigo_peticion || formularioId}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      setErrorCertificado(err.message || 'Error al descargar el certificado');
    } finally {
      setDescargandoCertificado(false);
    }
  }

  async function handleDescargarTodos() {
    if (documentosAdjuntos.length === 0 || descargandoTodos) return;
    setDescargandoTodos(true);
    try {
      for (const doc of documentosAdjuntos) {
        await api.descargarDocumento(formularioId, doc.id, doc.nombre_archivo);
        await new Promise(resolve => setTimeout(resolve, 300)); // Prevenir bloqueo del navegador
      }
    } catch (err) {
      console.error('Error al descargar todos:', err);
    } finally {
      setDescargandoTodos(false);
    }
  }

  function handleReabierto(resultado) {
    setMostrarModalReapertura(false);
    if (resultado && !resultado.correo_enviado) {
      setAvisoReapertura(
        resultado.correo_notificado
          ? `La actualización fue reabierta, pero no se pudo enviar el correo a ${resultado.correo_notificado}.`
          : 'La actualización fue reabierta, pero no hay correo de destinatario registrado para notificar.',
      );
    }
    recargarExpediente();
  }

  return (
    <div className="expediente-overlay">
      <div className="expediente-container">
        {/* Botón volver */}
        <button className="btn-volver" onClick={onVolver} type="button">
          ← Volver a formularios
        </button>

        {cargando && <Spinner texto="Cargando expediente…" style={{ padding: '80px 0' }} />}
        {error && <Alert mensaje={error} style={{ margin: '24px 0' }} />}

        {!cargando && expediente && (
          <>
            {/* Header Section */}
            <header className="expediente-header">
              <div className="header-left">
                <div className="title-group">
                  <h1 className="company-name">{expediente.razon_social ?? razonSocial ?? '(Sin razón social)'}</h1>
                  <span className="case-code">{expediente.codigo_peticion}</span>
                </div>
                <div className="badge-group">
                  {tipoLabel && <span className="badge badge-neutral">{tipoLabel}</span>}
                  {tipoSolicitudLabel && <span className="badge badge-neutral">{tipoSolicitudLabel}</span>}
                  <BadgeEstadoFormulario estado={expediente.estado} />
                  {expediente.causal_cierre && (
                    <span className="badge badge-neutral">Causal: {ETIQUETA_CAUSAL_CIERRE[expediente.causal_cierre] || expediente.causal_cierre}</span>
                  )}
                  {expediente.updated_at && (
                    <span className="badge badge-neutral">{estaCerrado ? 'Cerrado' : 'Enviado'} {formatearFechaHora(expediente.updated_at)}</span>
                  )}
                </div>
              </div>
              <div className="header-actions">
                {permiteReaperturaActualizacion && (
                  <button
                    className="btn btn-outline-green"
                    onClick={() => { setAvisoReapertura(null); setMostrarModalReapertura(true); }}
                    type="button"
                  >
                    Reabrir Actualización
                  </button>
                )}
                <button
                  className="btn btn-secondary"
                  onClick={() => setMostrarModalSagrilaft(true)}
                  disabled={verificandoSagrilaft}
                  type="button"
                >
                  <ShieldCheck size={16} />
                  Verificar SAGRILAFT
                </button>
                {expediente.sagrilaft_reporte_id && (
                  <button
                    className="btn btn-outline"
                    onClick={handleDescargarCertificado}
                    disabled={descargandoCertificado}
                    type="button"
                    title="Descargar Certificado SAGRILAFT"
                  >
                    📄 {descargandoCertificado ? 'Descargando...' : 'Descargar Certificado'}
                  </button>
                )}
                <button
                  className="btn btn-secondary"
                  onClick={() => { if (!estaCerrado) setMostrarModalCargaManual(true); }}
                  disabled={estaCerrado}
                  type="button"
                  title={estaCerrado ? "No se puede modificar un expediente cerrado" : ""}
                >
                  <Upload size={16} />
                  Cargar Formulario Manual
                </button>
                <button
                  className="btn btn-primary"
                  onClick={() => setMostrarModalReporteFinal(true)}
                  type="button"
                >
                  <ShieldCheck size={16} />
                  Cerrar Expediente
                </button>
              </div>
            </header>

            {avisoReapertura && (
              <Alert
                mensaje={avisoReapertura}
                style={{ marginBottom: '16px', background: '#fffbeb', borderColor: '#fbbf24', color: '#92400e' }}
              />
            )}
            
            {errorCertificado && (
              <Alert
                mensaje={errorCertificado}
                style={{ marginBottom: '16px', background: '#fef2f2', borderColor: '#f87171', color: '#b91c1c' }}
              />
            )}

            {resultadoSagrilaft && (
              <Alert
                mensaje={`SAGRILAFT: ${resultadoSagrilaft.estado || resultadoSagrilaft.error}. ${resultadoSagrilaft.riesgo ? `Riesgo: ${resultadoSagrilaft.riesgo}.` : ''} ${resultadoSagrilaft.detalles || ''}`}
                style={{ 
                  marginBottom: '16px', 
                  background: resultadoSagrilaft.estado === 'APROBADO_SAGRILAFT' ? '#ecfdf5' : '#fef2f2', 
                  borderColor: resultadoSagrilaft.estado === 'APROBADO_SAGRILAFT' ? '#10b981' : '#ef4444', 
                  color: resultadoSagrilaft.estado === 'APROBADO_SAGRILAFT' ? '#065f46' : '#991b1b' 
                }}
              />
            )}

            {/* Modales */}
            <ModalCargaManual
              visible={mostrarModalCargaManual}
              formularioId={formularioId}
              onCargado={() => { setMostrarModalCargaManual(false); recargarExpediente(); }}
              onCancelar={() => setMostrarModalCargaManual(false)}
            />
            <ModalCargaReporteFinal
              visible={mostrarModalReporteFinal}
              formularioId={formularioId}
              onCargado={() => { setMostrarModalReporteFinal(false); recargarExpediente(); }}
              onCancelar={() => setMostrarModalReporteFinal(false)}
            />
            <ModalReaperturaActualizacion
              visible={mostrarModalReapertura}
              formularioId={formularioId}
              tipoPersona={expediente?.tipo_persona}
              onReabierto={handleReabierto}
              onCancelar={() => setMostrarModalReapertura(false)}
            />

            <div className="expediente-grid">
              {/* Main Content Column */}
              <div className="main-column">

                {/* Banner de Firma */}
                <BannerFirma
                  estado={expediente.estado}
                  modoTrabajo={expediente.modo_trabajo}
                  formularioId={formularioId}
                  tipoPersona={expediente.tipo_persona}
                  documentoFirmadoDisponible={expediente.documento_firmado_disponible}
                  onFirmaEnviada={recargarExpediente}
                />



                {/* Summary Cards */}
                {(pdfFormulario || reporteFinal) && (
                  <section className="section-block">
                    <div className="section-header">
                      <h2 className="section-title">Resumen del Expediente</h2>
                    </div>
                    <div className="summary-cards">
                      {pdfFormulario && <BannerPdfFormulario documento={pdfFormulario} formularioId={formularioId} />}
                      {reporteFinal && (
                        <div className="card summary-card">
                          <div className="card-icon green">
                            <FileBarChart className="text-green-500" size={24} />
                          </div>
                          <div className="card-content">
                            <h3 className="doc-title">Reporte Final de Cierre</h3>
                            <div className="doc-meta">
                              <span>{reporteFinal.nombre_archivo}</span>
                              {reporteFinal.created_at && <><span className="separator">•</span><span>{formatearFechaHora(reporteFinal.created_at)}</span></>}
                              {reporteFinal.tamano && <><span className="separator">•</span><span>{formatearBytes(reporteFinal.tamano)}</span></>}
                            </div>
                          </div>
                          <button
                            className="btn-outline"
                            onClick={() => api.descargarDocumento(formularioId, reporteFinal.id, reporteFinal.nombre_archivo)}
                            title="Descargar Reporte"
                          >
                            <Download size={16} />
                          </button>
                        </div>
                      )}
                    </div>
                  </section>
                )}

                <section className="section-block">
                  {todosDocumentos.length > 0 ? (
                    <HistorialVersionesFormulario documentos={todosDocumentos} formularioId={formularioId} />
                  ) : (
                    <>
                      <div className="section-header">
                        <h2 className="section-title">Historial de Versiones del Formulario</h2>
                      </div>
                      <div className="card timeline-card" style={{ padding: '24px', color: '#9CA3AF', fontSize: '13px' }}>
                        Sin versiones disponibles.
                      </div>
                    </>
                  )}
                </section>

                {/* Attached Documents Table */}
                <section className="section-block">
                  <div className="section-header">
                    <h2 className="section-title">Documentos Adjuntos ({documentosAdjuntos.length})</h2>
                    {documentosAdjuntos.length > 0 && (
                      <button 
                        className="btn-outline btn-outline-gray"
                        onClick={handleDescargarTodos}
                        disabled={descargandoTodos}
                        type="button"
                      >
                        <Download size={14} /> {descargandoTodos ? 'Descargando...' : 'Descargar todos'}
                      </button>
                    )}
                  </div>
                  <div className="card table-card">
                    {documentosAdjuntos.length === 0 ? (
                      <div style={{ padding: '24px', textAlign: 'center', color: '#9CA3AF' }}>
                        No hay documentos adjuntos en este formulario.
                      </div>
                    ) : (
                      <table className="data-table">
                        <thead>
                          <tr>
                            <th>Documento</th>
                            <th>Tipo</th>
                            <th>Tamaño</th>
                            <th>Cargado por</th>
                            <th>Fecha de carga</th>
                            <th className="text-right">Acciones</th>
                          </tr>
                        </thead>
                        <tbody>
                          {documentosAdjuntos.map(doc => (
                            <FilaDocumento key={doc.id} documento={doc} formularioId={formularioId} />
                          ))}
                        </tbody>
                      </table>
                    )}
                  </div>
                </section>

                <section className="section-block">
                  <HistorialExpediente formularioId={formularioId} />
                </section>

                {/* Alertas de Inconsistencia Documental */}
                <PanelAlertasAuditoria
                  alertas={expediente.alertas_inconsistencia}
                  formularioId={formularioId}
                  onAlertaActualizada={recargarExpediente}
                />
              </div>
            </div>
          </>
        )}
      </div>

      <ModalSagrilaft 
        visible={mostrarModalSagrilaft}
        ocupado={verificandoSagrilaft}
        expediente={expediente}
        error={resultadoSagrilaft?.error}
        onConfirmar={handleVerificarSagrilaft}
        onCancelar={() => {
          setMostrarModalSagrilaft(false);
          setResultadoSagrilaft(null);
        }}
      />
    </div>
  );
}
