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

import { useState } from 'react';
import { api } from '../../services/api';
import { useExpedienteDetalle } from '../../hooks/useExpedienteDetalle';
import Spinner from '@shared/components/ui/Spinner';
import Alert from '@shared/components/ui/Alert';
import BadgeEstadoFormulario from '../badges/BadgeEstadoFormulario';
import ModalDevolucion from '../modals/ModalDevolucion';
import ModalRechazo from '../modals/ModalRechazo';
import HistorialVersionesFormulario from './HistorialVersionesFormulario';
import {
  ETIQUETA_TIPO_CONTRAPARTE,
  formatearFechaHora,
  formatearBytes,
  TIPO_DOCUMENTO_FORMULARIO_PDF,
  TIPO_DOCUMENTO_CERTIFICADO_SAGRILAFT,
} from '../../config/constantes';

const ESTADO_ENVIADO         = 'enviado';
const ESTADO_EN_CORRECCION   = 'en_correccion';
const ESTADO_VALIDADO        = 'validado';
const ESTADO_PENDIENTE_FIRMA = 'pendiente_firma';
const ESTADO_FIRMADO         = 'firmado';

const TIPOS_EXCLUIDOS_DE_ADJUNTOS = [TIPO_DOCUMENTO_FORMULARIO_PDF, TIPO_DOCUMENTO_CERTIFICADO_SAGRILAFT];

// ── Estilos ─────────────────────────────────────────────────────────────────

const s = {
  overlay: {
    position:   'fixed',
    inset:      0,
    background: 'var(--gray-50, #f8fafc)',
    overflowY:  'auto',
    zIndex:     100,
  },
  contenedor: {
    maxWidth: '800px',
    margin:   '0 auto',
    padding:  '32px 24px 64px',
  },
  // Encabezado
  encabezado: {
    marginBottom: '28px',
  },
  btnVolver: {
    display:      'inline-flex',
    alignItems:   'center',
    gap:          '6px',
    padding:      '6px 0',
    background:   'transparent',
    color:        'var(--primary-600, #2563eb)',
    border:       'none',
    fontSize:     '0.85rem',
    fontWeight:   '600',
    cursor:       'pointer',
    marginBottom: '16px',
  },
  tituloEncabezado: {
    display:    'flex',
    alignItems: 'flex-start',
    gap:        '12px',
    flexWrap:   'wrap',
  },
  razonSocial: {
    fontSize:   '1.5rem',
    fontWeight: '800',
    color:      'var(--gray-900, #0f172a)',
    margin:     '0 0 6px',
    lineHeight: 1.2,
  },
  metaEncabezado: {
    display:    'flex',
    gap:        '8px',
    flexWrap:   'wrap',
    alignItems: 'center',
  },
  chip: {
    fontSize:      '0.75rem',
    color:         'var(--gray-500, #64748b)',
    background:    'var(--gray-100, #f1f5f9)',
    border:        '1px solid var(--gray-200, #e2e8f0)',
    borderRadius:  '999px',
    padding:       '3px 10px',
    fontFamily:    'inherit',
    whiteSpace:    'nowrap',
  },
  chipCodigo: {
    fontSize:      '0.75rem',
    color:         'var(--gray-500, #64748b)',
    fontFamily:    'monospace',
    letterSpacing: '0.06em',
  },
  // Sección de documentos adjuntos
  seccion: {
    background:   '#fff',
    borderRadius: 'var(--radius-md, 8px)',
    border:       '1px solid var(--gray-200, #e2e8f0)',
    marginBottom: '16px',
    overflow:     'hidden',
  },
  seccionTitulo: {
    fontSize:      '0.8rem',
    fontWeight:    '700',
    color:         'var(--gray-500, #64748b)',
    textTransform: 'uppercase',
    letterSpacing: '0.06em',
    padding:       '12px 20px',
    background:    'var(--gray-50, #f8fafc)',
    borderBottom:  '1px solid var(--gray-100, #f1f5f9)',
    margin:        0,
  },
  // Banner PDF oficial
  bannerPdf: {
    display:       'flex',
    alignItems:    'center',
    justifyContent: 'space-between',
    gap:           '16px',
    background:    'linear-gradient(135deg, #1e3a5f 0%, #1d4ed8 100%)',
    borderRadius:  'var(--radius-md, 8px)',
    padding:       '20px 24px',
    marginBottom:  '20px',
    flexWrap:      'wrap',
  },
  bannerPdfTextos: {
    display:       'flex',
    flexDirection: 'column',
    gap:           '3px',
  },
  bannerPdfTitulo: {
    fontSize:   '0.92rem',
    fontWeight: '700',
    color:      '#fff',
    margin:     0,
  },
  bannerPdfSubtitulo: {
    fontSize: '0.78rem',
    color:    'rgba(255,255,255,0.7)',
    margin:   0,
  },
  btnDescargarPdf: {
    padding:        '9px 20px',
    background:     '#fff',
    color:          '#1d4ed8',
    border:         'none',
    borderRadius:   'var(--radius-sm, 6px)',
    fontSize:       '0.85rem',
    fontWeight:     '700',
    cursor:         'pointer',
    textDecoration: 'none',
    whiteSpace:     'nowrap',
    flexShrink:     0,
  },
  // Documentos
  listaDocumentos: {
    display:       'flex',
    flexDirection: 'column',
    gap:           '0',
  },
  filaDocumento: {
    display:        'flex',
    alignItems:     'center',
    justifyContent: 'space-between',
    padding:        '12px 20px',
    borderBottom:   '1px solid var(--gray-50, #f8fafc)',
    gap:            '12px',
  },
  infoDocumento: {
    display:       'flex',
    flexDirection: 'column',
    gap:           '2px',
    flex:          1,
    minWidth:      0,
  },
  nombreArchivo: {
    fontSize:     '0.88rem',
    fontWeight:   '500',
    color:        'var(--gray-800, #1e293b)',
    overflow:     'hidden',
    textOverflow: 'ellipsis',
    whiteSpace:   'nowrap',
  },
  tipoTamano: {
    fontSize: '0.75rem',
    color:    'var(--gray-400, #94a3b8)',
  },
  btnDescargar: {
    padding:      '5px 14px',
    background:   'var(--primary-50, #eff6ff)',
    color:        'var(--primary-700, #1d4ed8)',
    border:       '1px solid var(--primary-200, #bfdbfe)',
    borderRadius: 'var(--radius-sm, 6px)',
    fontSize:     '0.78rem',
    fontWeight:   '600',
    cursor:       'pointer',
    textDecoration: 'none',
    whiteSpace:   'nowrap',
    flexShrink:   0,
  },
  sinDocumentos: {
    padding:   '20px',
    textAlign: 'center',
    color:     'var(--gray-400, #94a3b8)',
    fontSize:  '0.85rem',
  },
  // Banner firma
  bannerFirma: {
    display:        'flex',
    alignItems:     'center',
    justifyContent: 'space-between',
    gap:            '16px',
    borderRadius:   'var(--radius-md, 8px)',
    padding:        '16px 20px',
    marginBottom:   '16px',
    flexWrap:       'wrap',
  },
  bannerFirmaValidado: {
    background: 'linear-gradient(135deg, #854d0e 0%, #ca8a04 100%)',
  },
  bannerFirmaPendiente: {
    background: 'linear-gradient(135deg, #78350f 0%, #d97706 100%)',
  },
  bannerFirmaFirmado: {
    background: 'linear-gradient(135deg, #4c1d95 0%, #7c3aed 100%)',
  },
  bannerFirmaTextos: {
    display:       'flex',
    flexDirection: 'column',
    gap:           '3px',
  },
  bannerFirmaTitulo: {
    fontSize:   '0.92rem',
    fontWeight: '700',
    color:      '#fff',
    margin:     0,
  },
  bannerFirmaSubtitulo: {
    fontSize: '0.78rem',
    color:    'rgba(255,255,255,0.75)',
    margin:   0,
  },
  btnFirma: {
    padding:        '9px 20px',
    background:     '#fff',
    border:         'none',
    borderRadius:   'var(--radius-sm, 6px)',
    fontSize:       '0.85rem',
    fontWeight:     '700',
    cursor:         'pointer',
    textDecoration: 'none',
    whiteSpace:     'nowrap',
    flexShrink:     0,
  },
  btnFirmaColor: { color: '#854d0e' },
  btnFirmaColorFirmado: { color: '#6d28d9' },
  btnFirmaDeshabilitado: {
    opacity: 0.6,
    cursor:  'not-allowed',
  },
};

// ── Sub-componentes ───────────────────────────────────────────────────────────

function BannerPdfFormulario({ documento, formularioId }) {
  const [descargando, setDescargando] = useState(false);
  const tamano = documento.tamano ? ` · ${formatearBytes(documento.tamano)}` : '';
  const fecha = documento.created_at ? formatearFechaHora(documento.created_at) : null;
  const fechaTexto = fecha ? ` · ${fecha}` : '';

  async function handleDescargar() {
    setDescargando(true);
    try {
      await api.descargarDocumento(formularioId, documento.id, documento.nombre_archivo);
    } finally {
      setDescargando(false);
    }
  }

  return (
    <div style={s.bannerPdf}>
      <div style={s.bannerPdfTextos}>
        <p style={s.bannerPdfTitulo}>Formulario SAGRILAFT — PDF oficial</p>
        <p style={s.bannerPdfSubtitulo}>
          {documento.nombre_archivo}{tamano}{fechaTexto}
        </p>
      </div>
      <button
        onClick={handleDescargar}
        disabled={descargando}
        style={{ ...s.btnDescargarPdf, opacity: descargando ? 0.6 : 1, cursor: descargando ? 'not-allowed' : 'pointer' }}
      >
        {descargando ? 'Descargando…' : 'Descargar PDF'}
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

  return (
    <div style={s.filaDocumento}>
      <div style={s.infoDocumento}>
        <span style={s.nombreArchivo} title={documento.nombre_archivo}>
          {documento.nombre_archivo}
        </span>
        <span style={s.tipoTamano}>
          {documento.tipo_documento}
          {documento.tamano ? ` · ${formatearBytes(documento.tamano)}` : ''}
        </span>
      </div>
      <button
        onClick={handleDescargar}
        disabled={descargando}
        style={{ ...s.btnDescargar, opacity: descargando ? 0.6 : 1, cursor: descargando ? 'not-allowed' : 'pointer' }}
      >
        {descargando ? 'Descargando…' : 'Descargar'}
      </button>
    </div>
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
      style={{ ...s.btnFirma, ...s.btnFirmaColorFirmado, opacity: descargando ? 0.6 : 1, cursor: descargando ? 'not-allowed' : 'pointer' }}
    >
      {descargando ? 'Descargando…' : 'Descargar firmado'}
    </button>
  );
}

function BannerFirma({ estado, formularioId, onFirmaEnviada }) {
  const [enviando, setEnviando]                         = useState(false); // enviar a ZohoSign (VALIDADO)
  const [aprobando, setAprobando]                       = useState(false); // aprobar expediente (ENVIADO)
  const [cancelando, setCancelando]                     = useState(false);
  const [verificando, setVerificando]                   = useState(false);
  const [errorFirma, setErrorFirma]                     = useState(null);
  const [mostrarModalDevolucion, setMostrarModalDevolucion] = useState(false);
  const [mostrarModalRechazo, setMostrarModalRechazo]   = useState(false);

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
      onFirmaEnviada();
    } catch (err) {
      setErrorFirma(err.message || 'Error al aprobar.');
    } finally {
      setAprobando(false);
    }
  }

  if (estado === ESTADO_ENVIADO) {
    const ocupado = aprobando;
    return (
      <>
        <div style={{ ...s.bannerFirma, background: 'linear-gradient(135deg, #1e3a5f 0%, #1d4ed8 100%)' }}>
          <div style={s.bannerFirmaTextos}>
            <p style={s.bannerFirmaTitulo}>Formulario recibido — pendiente de revisión</p>
            <p style={s.bannerFirmaSubtitulo}>
              {errorFirma || 'Revise los documentos adjuntos y apruebe, rechace o devuelva el formulario.'}
            </p>
          </div>
          <div style={{ display: 'flex', gap: '8px', flexShrink: 0, flexWrap: 'wrap' }}>
            <button
              style={{ ...s.btnFirma, color: '#1d4ed8', ...(ocupado ? s.btnFirmaDeshabilitado : {}) }}
              onClick={handleAprobar}
              disabled={ocupado}
              type="button"
            >
              {aprobando ? 'Aprobando…' : 'Aprobar'}
            </button>
            <button
              style={{ ...s.btnFirma, color: '#991b1b', opacity: 0.85, ...(ocupado ? s.btnFirmaDeshabilitado : {}) }}
              onClick={() => setMostrarModalRechazo(true)}
              disabled={ocupado}
              type="button"
            >
              Rechazar
            </button>
            <button
              style={{ ...s.btnFirma, color: '#c2410c', opacity: 0.9, ...(ocupado ? s.btnFirmaDeshabilitado : {}) }}
              onClick={() => setMostrarModalDevolucion(true)}
              disabled={ocupado}
              type="button"
            >
              Devolver
            </button>
          </div>
        </div>
        <ModalDevolucion
          visible={mostrarModalDevolucion}
          formularioId={formularioId}
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
    return (
      <div style={{ ...s.bannerFirma, background: 'linear-gradient(135deg, #7c2d12 0%, #c2410c 100%)' }}>
        <div style={s.bannerFirmaTextos}>
          <p style={s.bannerFirmaTitulo}>Formulario devuelto — en corrección</p>
          <p style={s.bannerFirmaSubtitulo}>
            Se notificó al destinatario. El formulario estará disponible nuevamente
            cuando el remitente reenvíe la versión corregida.
          </p>
        </div>
      </div>
    );
  }

  if (estado === ESTADO_VALIDADO) {
    return (
      <div style={{ ...s.bannerFirma, ...s.bannerFirmaValidado }}>
        <div style={s.bannerFirmaTextos}>
          <p style={s.bannerFirmaTitulo}>Formulario listo para firma electrónica</p>
          <p style={s.bannerFirmaSubtitulo}>
            {errorFirma || 'El formulario fue validado. Envíelo a ZohoSign para que la contraparte firme.'}
          </p>
        </div>
        <button
          style={{ ...s.btnFirma, ...s.btnFirmaColor, ...(enviando ? s.btnFirmaDeshabilitado : {}) }}
          onClick={handleEnviarAFirma}
          disabled={enviando}
          type="button"
        >
          {enviando ? 'Enviando…' : 'Enviar a firma'}
        </button>
      </div>
    );
  }

  if (estado === ESTADO_PENDIENTE_FIRMA) {
    const ocupado = cancelando || verificando;
    return (
      <div style={{ ...s.bannerFirma, ...s.bannerFirmaPendiente }}>
        <div style={s.bannerFirmaTextos}>
          <p style={s.bannerFirmaTitulo}>Firma electrónica pendiente</p>
          <p style={s.bannerFirmaSubtitulo}>
            {errorFirma || 'Se envió la solicitud de firma a ZohoSign. Esperando que la contraparte firme.'}
          </p>
        </div>
        <div style={{ display: 'flex', gap: '8px', flexShrink: 0 }}>
          <button
            style={{ ...s.btnFirma, color: '#78350f', ...(ocupado ? s.btnFirmaDeshabilitado : {}) }}
            onClick={handleVerificarFirma}
            disabled={ocupado}
            type="button"
          >
            {verificando ? 'Verificando…' : 'Verificar estado'}
          </button>
          <button
            style={{ ...s.btnFirma, color: '#78350f', opacity: 0.7, ...(ocupado ? s.btnFirmaDeshabilitado : {}) }}
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
      <div style={{ ...s.bannerFirma, ...s.bannerFirmaFirmado }}>
        <div style={s.bannerFirmaTextos}>
          <p style={s.bannerFirmaTitulo}>Documentos firmados electrónicamente</p>
          <p style={s.bannerFirmaSubtitulo}>La contraparte firmó el formulario y Certificado vía ZohoSign.</p>
        </div>
        <BtnDescargaFirmado formularioId={formularioId} />
      </div>
    );
  }

  return null;
}

// ── Componente principal ──────────────────────────────────────────────────────

export default function DetalleExpediente({ formularioId, razonSocial, onVolver }) {
  const { expediente, cargando, error, recargarExpediente } = useExpedienteDetalle(formularioId);

  const tipoLabel         = expediente ? (ETIQUETA_TIPO_CONTRAPARTE[expediente.tipo_contraparte] ?? expediente.tipo_contraparte) : '';
  const todosDocumentos   = expediente?.documentos ?? [];
  // Puede haber varias versiones del PDF; la activa es la de mayor version_numero.
  const pdfFormulario     = todosDocumentos
    .filter(d => d.tipo_documento === TIPO_DOCUMENTO_FORMULARIO_PDF)
    .sort((a, b) => b.version_numero - a.version_numero)[0] ?? null;
  const documentosAdjuntos = todosDocumentos.filter(d => !TIPOS_EXCLUIDOS_DE_ADJUNTOS.includes(d.tipo_documento));

  return (
    <div style={s.overlay}>
      <div style={s.contenedor}>
        {/* Botón volver */}
        <button style={s.btnVolver} onClick={onVolver} type="button">
          ← Volver a formularios
        </button>

        {cargando && <Spinner texto="Cargando expediente…" style={{ padding: '80px 0' }} />}
        {error    && <Alert mensaje={error} style={{ margin: '24px 0' }} />}

        {!cargando && expediente && (
          <>
            {/* Encabezado */}
            <div style={s.encabezado}>
              <h1 style={s.razonSocial}>{expediente.razon_social ?? razonSocial ?? '(Sin razón social)'}</h1>
              <div style={s.metaEncabezado}>
                <BadgeEstadoFormulario
                  estado={expediente.estado}
                  overrides={{ fontSize: '0.75rem', padding: '3px 12px' }}
                />
                {tipoLabel && <span style={s.chip}>{tipoLabel}</span>}
                <span style={s.chipCodigo}>{expediente.codigo_peticion}</span>
                {expediente.updated_at && (
                  <span style={s.chip}>Enviado {formatearFechaHora(expediente.updated_at)}</span>
                )}
              </div>
            </div>

            {/* PDF oficial del formulario — versión activa */}
            {pdfFormulario && (
              <BannerPdfFormulario documento={pdfFormulario} formularioId={formularioId} />
            )}

            {/* Historial de versiones — visible cuando hay más de una */}
            {todosDocumentos.length > 0 && (
              <HistorialVersionesFormulario
                documentos={todosDocumentos}
                formularioId={formularioId}
              />
            )}

            {/* Firma electrónica */}
            <BannerFirma
              estado={expediente.estado}
              formularioId={formularioId}
              onFirmaEnviada={recargarExpediente}
            />

            {/* Documentos adjuntos por el cliente/proveedor */}
            <div style={s.seccion}>
              <p style={s.seccionTitulo}>
                Documentos adjuntos ({documentosAdjuntos.length})
              </p>
              <div style={s.listaDocumentos}>
                {documentosAdjuntos.length === 0 ? (
                  <div style={s.sinDocumentos}>No hay documentos adjuntos en este formulario.</div>
                ) : (
                  documentosAdjuntos.map(doc => (
                    <FilaDocumento
                      key={doc.id}
                      documento={doc}
                      formularioId={formularioId}
                    />
                  ))
                )}
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
