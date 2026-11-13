import ModalCargaManual from '../../modals/ModalCargaManual';
import ModalCargaReporteFinal from '../../modals/ModalCargaReporteFinal';
import ModalReaperturaActualizacion from '../../modals/ModalReaperturaActualizacion';

export default function ExpedienteModals({
  formularioId,
  expediente,
  mostrarModalCargaManual,
  mostrarModalReporteFinal,
  mostrarModalReapertura,
  onCargaManualCargada,
  onReporteFinalCargado,
  onReabierto,
  onCerrarCargaManual,
  onCerrarReporteFinal,
  onCerrarReapertura,
}) {
  return (
    <>
      <ModalCargaManual
        visible={mostrarModalCargaManual}
        formularioId={formularioId}
        onCargado={onCargaManualCargada}
        onCancelar={onCerrarCargaManual}
      />
      <ModalCargaReporteFinal
        visible={mostrarModalReporteFinal}
        formularioId={formularioId}
        onCargado={onReporteFinalCargado}
        onCancelar={onCerrarReporteFinal}
      />
      <ModalReaperturaActualizacion
        visible={mostrarModalReapertura}
        formularioId={formularioId}
        tipoPersona={expediente?.tipo_persona}
        onReabierto={onReabierto}
        onCancelar={onCerrarReapertura}
      />

    </>
  );
}
