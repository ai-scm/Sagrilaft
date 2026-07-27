import { useState } from 'react';
import ModalConfirmacion from '../../modals/ModalConfirmacion';
import ModalDevolucion from '../../modals/ModalDevolucion';
import ModalRechazo from '../../modals/ModalRechazo';
import { MODO_TRABAJO_ACTUALIZACION_REABIERTA } from '../../../config/constantes';
import { useFirmaExpediente } from '../../../hooks/useFirmaExpediente';
import BtnDescargaFirmado from './BtnDescargaFirmado';

const ESTADO_ENVIADO = 'enviado';
const ESTADO_EN_CORRECCION = 'en_correccion';
const ESTADO_VALIDADO = 'validado';
const ESTADO_PENDIENTE_FIRMA = 'pendiente_firma';
const ESTADO_FIRMADO = 'firmado';
const ESTADO_CERRADO = 'cerrado';

export default function BannerFirma({
  estado,
  modoTrabajo,
  formularioId,
  tipoPersona,
  documentoFirmadoDisponible,
  onFirmaEnviada,
}) {
  const firma = useFirmaExpediente({ formularioId, onActualizado: onFirmaEnviada });
  const [motivoReapertura, setMotivoReapertura] = useState('');
  const [mostrarModalDevolucion, setMostrarModalDevolucion] = useState(false);
  const [mostrarModalRechazo, setMostrarModalRechazo] = useState(false);
  const [mostrarModalAprobacion, setMostrarModalAprobacion] = useState(false);
  const [mostrarModalReabrirRevision, setMostrarModalReabrirRevision] = useState(false);
  const motivoReaperturaValido = motivoReapertura.trim().length >= 20;

  async function handleAprobar() {
    await firma.aprobar({ onAprobado: () => setMostrarModalAprobacion(false) });
  }

  async function handleDeshacerAprobacion() {
    if (!window.confirm('¿Está seguro de que desea deshacer la aprobación de este formulario?')) return;
    await firma.deshacerAprobacion();
  }

  async function handleDeshacerDevolucion() {
    if (!window.confirm('¿Está seguro de que desea deshacer la devolución de este formulario?')) return;
    await firma.deshacerDevolucion();
  }

  async function handleReabrirRevisionFirmado() {
    if (!motivoReaperturaValido) return;

    await firma.reabrirRevisionFirmado(motivoReapertura.trim(), {
      onReabierto: () => {
        setMostrarModalReabrirRevision(false);
        setMotivoReapertura('');
      },
    });
  }

  if (estado === ESTADO_ENVIADO) {
    const ocupado = firma.aprobando;
    return (
      <>
        <div className="banner-firma banner-firma-revisar">
          <div className="banner-firma-textos">
            <p className="banner-firma-titulo">{'Formulario recibido \u2014 pendiente de revisión'}</p>
            <p className="banner-firma-subtitulo">
              {firma.errorFirma || 'Revise los documentos adjuntos y apruebe, rechace o devuelva el formulario.'}
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
          ocupado={firma.aprobando}
        />
        <ModalDevolucion
          visible={mostrarModalDevolucion}
          formularioId={formularioId}
          tipoPersona={tipoPersona}
          onDevuelto={() => {
            setMostrarModalDevolucion(false);
            onFirmaEnviada();
          }}
          onCancelar={() => setMostrarModalDevolucion(false)}
        />
        <ModalRechazo
          visible={mostrarModalRechazo}
          formularioId={formularioId}
          onRechazado={() => {
            setMostrarModalRechazo(false);
            onFirmaEnviada();
          }}
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
          <p className="banner-firma-titulo">Formulario devuelto - en corrección</p>
          <p className="banner-firma-subtitulo">
            {firma.errorFirma || 'Se notificó al destinatario. El formulario estará disponible nuevamente cuando el remitente reenvíe la versión corregida.'}
          </p>
        </div>
        <div style={{ display: 'flex', gap: '8px', flexShrink: 0, flexWrap: 'wrap' }}>
          <button
            className="btn-outline"
            onClick={handleDeshacerDevolucion}
            disabled={firma.deshaciendoDevolucion}
            type="button"
          >
            {firma.deshaciendoDevolucion ? 'Deshaciendo\u2026' : 'Deshacer devolución'}
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
            {firma.errorFirma || 'El formulario fue validado. Envíelo a ZohoSign para que la contraparte firme.'}
          </p>
        </div>
        <div style={{ display: 'flex', gap: '8px', flexShrink: 0, flexWrap: 'wrap' }}>
          <button
            className="btn-outline"
            onClick={handleDeshacerAprobacion}
            disabled={firma.enviando || firma.deshaciendoAprobacion}
            type="button"
          >
            {firma.deshaciendoAprobacion ? 'Deshaciendo\u2026' : 'Deshacer aprobación'}
          </button>
          <button
            className="btn-firma btn-firma-color-validado"
            onClick={firma.enviarAFirma}
            disabled={firma.enviando || firma.deshaciendoAprobacion}
            type="button"
          >
            {firma.enviando ? 'Enviando\u2026' : 'Enviar a firma'}
          </button>
        </div>
      </div>
    );
  }

  if (estado === ESTADO_PENDIENTE_FIRMA) {
    const ocupado = firma.cancelando || firma.verificando;
    return (
      <div className="banner-firma banner-firma-pendiente">
        <div className="banner-firma-textos">
          <p className="banner-firma-titulo">Firma electrónica pendiente</p>
          <p className="banner-firma-subtitulo">
            {firma.errorFirma || 'Se envió la solicitud de firma a ZohoSign. Esperando que la contraparte firme.'}
          </p>
        </div>
        <div style={{ display: 'flex', gap: '8px', flexShrink: 0 }}>
          <button
            className="btn-firma btn-firma-color-pendiente"
            onClick={firma.verificarFirma}
            disabled={ocupado}
            type="button"
          >
            {firma.verificando ? 'Verificando\u2026' : 'Verificar estado'}
          </button>
          <button
            className="btn-firma btn-firma-color-pendiente"
            onClick={firma.cancelarFirma}
            disabled={ocupado}
            type="button"
          >
            {firma.cancelando ? 'Cancelando\u2026' : 'Cancelar'}
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
              {firma.errorFirma || 'La contraparte firmó el formulario y Certificado vía ZohoSign.'}
            </p>
          </div>
          <div style={{ display: 'flex', gap: '8px', flexShrink: 0, flexWrap: 'wrap' }}>
            <BtnDescargaFirmado formularioId={formularioId} />
            <button
              className="btn-firma btn-firma-color-reabrir"
              onClick={() => {
                firma.setErrorFirma(null);
                setMostrarModalReabrirRevision(true);
              }}
              disabled={firma.reabriendoRevision}
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
          ocupado={firma.reabriendoRevision}
          confirmarDeshabilitado={!motivoReaperturaValido}
        >
          <div>
            <p style={{ margin: '0 0 14px', color: '#475569', lineHeight: 1.5, fontSize: '0.9rem' }}>
              {'El documento firmado se conservará y el expediente volverá a \u201cFormulario recibido \u2014 pendiente de revisión\u201d.'}
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
              disabled={firma.reabriendoRevision}
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
