import { useState } from 'react';
import Spinner from '@shared/components/ui/Spinner';
import Alert from '@shared/components/ui/Alert';
import './DetalleExpediente.css';
import '../../modals/Modals.css';
import { useExpedienteDetalle } from '../../../hooks/useExpedienteDetalle';
import { useDocumentosExpediente } from '../../../hooks/useDocumentosExpediente';
import { useSagrilaftExpediente } from '../../../hooks/useSagrilaftExpediente';
import {
  ETIQUETA_TIPO_CONTRAPARTE,
  ETIQUETA_TIPO_SOLICITUD,
} from '../../../config/constantes';
import { ESTADO_FORM_CERRADO } from '@shared/utils/constantes';
import HistorialVersionesFormulario from '../HistorialVersionesFormulario';
import HistorialExpediente from '../HistorialExpediente';
import PanelAlertasAuditoria from '../PanelAlertasAuditoria';
import BannerFirma from './BannerFirma';
import DetalleExpedienteAlerts from './DetalleExpedienteAlerts';
import DetalleExpedienteHeader from './DetalleExpedienteHeader';
import DocumentosAdjuntosSection from './DocumentosAdjuntosSection';
import ExpedienteModals from './ExpedienteModals';
import ResumenExpediente from './ResumenExpediente';

export default function DetalleExpediente({ formularioId, razonSocial, onVolver }) {
  const { expediente, cargando, error, recargarExpediente } = useExpedienteDetalle(formularioId);
  const [mostrarModalCargaManual, setMostrarModalCargaManual] = useState(false);
  const [mostrarModalReapertura, setMostrarModalReapertura] = useState(false);
  const [mostrarModalReporteFinal, setMostrarModalReporteFinal] = useState(false);
  const [mostrarModalSagrilaft, setMostrarModalSagrilaft] = useState(false);
  const [avisoReapertura, setAvisoReapertura] = useState(null);

  const todosDocumentos = expediente?.documentos ?? [];
  const { pdfFormulario, reporteFinal, documentosAdjuntos } = useDocumentosExpediente(todosDocumentos);
  const estaCerrado = expediente?.estado === ESTADO_FORM_CERRADO;
  const permiteReaperturaActualizacion = estaCerrado;
  const tipoLabel = expediente
    ? (ETIQUETA_TIPO_CONTRAPARTE[expediente.tipo_contraparte] ?? expediente.tipo_contraparte)
    : '';
  const tipoSolicitudLabel = expediente
    ? (ETIQUETA_TIPO_SOLICITUD[expediente.tipo_solicitud] ?? expediente.tipo_solicitud)
    : '';

  const sagrilaft = useSagrilaftExpediente({
    formularioId,
    expediente: expediente ?? {},
    onActualizado: recargarExpediente,
  });

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

  async function handleVerificarSagrilaft(datosManuales) {
    const resultado = await sagrilaft.verificarSagrilaft(datosManuales);
    if (!resultado?.error) {
      setMostrarModalSagrilaft(false);
    }
  }

  return (
    <div className="expediente-overlay">
      <div className="expediente-container">
        <button className="btn-volver" onClick={onVolver} type="button">
          ← Volver a formularios
        </button>

        {cargando && <Spinner texto={'Cargando expediente\u2026'} style={{ padding: '80px 0' }} />}
        {error && <Alert mensaje={error} style={{ margin: '24px 0' }} />}

        {!cargando && expediente && (
          <>
            <DetalleExpedienteHeader
              expediente={expediente}
              razonSocial={razonSocial}
              tipoLabel={tipoLabel}
              tipoSolicitudLabel={tipoSolicitudLabel}
              estaCerrado={estaCerrado}
              permiteReaperturaActualizacion={permiteReaperturaActualizacion}
              verificandoSagrilaft={sagrilaft.verificandoSagrilaft}
              descargandoCertificado={sagrilaft.descargandoCertificado}
              onReabrirActualizacion={() => {
                setAvisoReapertura(null);
                setMostrarModalReapertura(true);
              }}
              onVerificarSagrilaft={() => setMostrarModalSagrilaft(true)}
              onDescargarCertificado={sagrilaft.descargarCertificado}
              onCargarManual={() => {
                if (!estaCerrado) setMostrarModalCargaManual(true);
              }}
              onCerrarExpediente={() => setMostrarModalReporteFinal(true)}
            />

            <DetalleExpedienteAlerts
              avisoReapertura={avisoReapertura}
              errorCertificado={sagrilaft.errorCertificado}
              resultadoSagrilaft={sagrilaft.resultadoSagrilaft}
            />

            <ExpedienteModals
              formularioId={formularioId}
              expediente={expediente}
              mostrarModalCargaManual={mostrarModalCargaManual}
              mostrarModalReporteFinal={mostrarModalReporteFinal}
              mostrarModalReapertura={mostrarModalReapertura}
              mostrarModalSagrilaft={mostrarModalSagrilaft}
              verificandoSagrilaft={sagrilaft.verificandoSagrilaft}
              errorSagrilaft={sagrilaft.resultadoSagrilaft?.error}
              onCargaManualCargada={() => {
                setMostrarModalCargaManual(false);
                recargarExpediente();
              }}
              onReporteFinalCargado={() => {
                setMostrarModalReporteFinal(false);
                recargarExpediente();
              }}
              onReabierto={handleReabierto}
              onVerificarSagrilaft={handleVerificarSagrilaft}
              onCerrarCargaManual={() => setMostrarModalCargaManual(false)}
              onCerrarReporteFinal={() => setMostrarModalReporteFinal(false)}
              onCerrarReapertura={() => setMostrarModalReapertura(false)}
              onCerrarSagrilaft={() => {
                setMostrarModalSagrilaft(false);
                sagrilaft.setResultadoSagrilaft(null);
              }}
            />

            <div className="expediente-grid">
              <div className="main-column">
                <BannerFirma
                  estado={expediente.estado}
                  modoTrabajo={expediente.modo_trabajo}
                  formularioId={formularioId}
                  tipoPersona={expediente.tipo_persona}
                  documentoFirmadoDisponible={expediente.documento_firmado_disponible}
                  onFirmaEnviada={recargarExpediente}
                />

                <ResumenExpediente
                  formularioId={formularioId}
                  pdfFormulario={pdfFormulario}
                  reporteFinal={reporteFinal}
                />

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

                <DocumentosAdjuntosSection documentos={documentosAdjuntos} formularioId={formularioId} />

                <section className="section-block">
                  <HistorialExpediente formularioId={formularioId} />
                </section>

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
    </div>
  );
}
