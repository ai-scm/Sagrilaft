import ModalCargaManual from '../../modals/ModalCargaManual';
import ModalCargaReporteFinal from '../../modals/ModalCargaReporteFinal';
import ModalReaperturaActualizacion from '../../modals/ModalReaperturaActualizacion';
import ModalSagrilaft from './ModalSagrilaft';

export default function ExpedienteModals({
  formularioId,
  expediente,
  mostrarModalCargaManual,
  mostrarModalReporteFinal,
  mostrarModalReapertura,
  mostrarModalSagrilaft,
  verificandoSagrilaft,
  errorSagrilaft,
  onCargaManualCargada,
  onReporteFinalCargado,
  onReabierto,
  onVerificarSagrilaft,
  onCerrarCargaManual,
  onCerrarReporteFinal,
  onCerrarReapertura,
  onCerrarSagrilaft,
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
      <ModalSagrilaft
        visible={mostrarModalSagrilaft}
        ocupado={verificandoSagrilaft}
        expediente={expediente}
        error={errorSagrilaft}
        onConfirmar={onVerificarSagrilaft}
        onCancelar={onCerrarSagrilaft}
      />
    </>
  );
}
