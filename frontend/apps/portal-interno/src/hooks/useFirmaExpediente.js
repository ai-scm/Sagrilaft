import { useState } from 'react';
import { api } from '../services/api';

export function useFirmaExpediente({ formularioId, onActualizado }) {
  const [enviando, setEnviando] = useState(false);
  const [aprobando, setAprobando] = useState(false);
  const [cancelando, setCancelando] = useState(false);
  const [verificando, setVerificando] = useState(false);
  const [reabriendoRevision, setReabriendoRevision] = useState(false);
  const [errorFirma, setErrorFirma] = useState(null);
  const [deshaciendoAprobacion, setDeshaciendoAprobacion] = useState(false);
  const [deshaciendoDevolucion, setDeshaciendoDevolucion] = useState(false);

  async function ejecutarAccion(setOcupado, accion, mensajeError, despues = null) {
    setOcupado(true);
    setErrorFirma(null);
    try {
      await accion();
      if (despues) despues();
      onActualizado();
    } catch (err) {
      setErrorFirma(err.message || mensajeError);
    } finally {
      setOcupado(false);
    }
  }

  function enviarAFirma() {
    return ejecutarAccion(
      setEnviando,
      () => api.enviarAFirma(formularioId),
      'Error al enviar a firma. Intente nuevamente.',
    );
  }

  function cancelarFirma() {
    return ejecutarAccion(
      setCancelando,
      () => api.cancelarFirma(formularioId),
      'Error al cancelar la firma. Intente nuevamente.',
    );
  }

  function verificarFirma() {
    return ejecutarAccion(
      setVerificando,
      () => api.verificarFirma(formularioId),
      'Error al verificar el estado. Intente nuevamente.',
    );
  }

  function aprobar({ onAprobado } = {}) {
    return ejecutarAccion(
      setAprobando,
      () => api.aprobarExpediente(formularioId),
      'Error al aprobar.',
      onAprobado,
    );
  }

  function deshacerAprobacion() {
    return ejecutarAccion(
      setDeshaciendoAprobacion,
      () => api.deshacerAprobacionExpediente(formularioId),
      'Error al deshacer aprobación.',
    );
  }

  function deshacerDevolucion() {
    return ejecutarAccion(
      setDeshaciendoDevolucion,
      () => api.deshacerDevolucionExpediente(formularioId),
      'Error al deshacer devolución.',
    );
  }

  function reabrirRevisionFirmado(motivo, { onReabierto } = {}) {
    return ejecutarAccion(
      setReabriendoRevision,
      () => api.reabrirRevisionFirmado(formularioId, motivo),
      'Error al reabrir la revisión.',
      onReabierto,
    );
  }

  return {
    enviando,
    aprobando,
    cancelando,
    verificando,
    reabriendoRevision,
    errorFirma,
    setErrorFirma,
    deshaciendoAprobacion,
    deshaciendoDevolucion,
    enviarAFirma,
    cancelarFirma,
    verificarFirma,
    aprobar,
    deshacerAprobacion,
    deshacerDevolucion,
    reabrirRevisionFirmado,
  };
}
