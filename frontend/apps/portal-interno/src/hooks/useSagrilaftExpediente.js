import { useEffect, useState } from 'react';
import { api } from '../services/api';

export function useSagrilaftExpediente({ formularioId, expediente, onActualizado }) {
  const [verificandoSagrilaft, setVerificandoSagrilaft] = useState(false);
  const [resultadoSagrilaft, setResultadoSagrilaft] = useState(null);
  const [descargandoCertificado, setDescargandoCertificado] = useState(false);
  const [errorCertificado, setErrorCertificado] = useState(null);
  // null mientras se consulta el feature flag: evita parpadeo del botón.
  const [sagrilaftHabilitado, setSagrilaftHabilitado] = useState(null);

  useEffect(() => {
    let vigente = true;
    api.obtenerDisponibilidadSagrilaft()
      .then(({ habilitado }) => {
        if (vigente) setSagrilaftHabilitado(habilitado);
      })
      .catch(() => {
        // Ante un error de red asumimos deshabilitado: es más seguro ocultar
        // la acción que ofrecer una verificación que podría fallar.
        if (vigente) setSagrilaftHabilitado(false);
      });
    return () => {
      vigente = false;
    };
  }, []);

  async function verificarSagrilaft(datosManuales) {
    setVerificandoSagrilaft(true);
    setResultadoSagrilaft(null);
    try {
      const resultado = await api.verificarSagrilaft(formularioId, datosManuales);
      setResultadoSagrilaft(resultado);
      onActualizado();
      return resultado;
    } catch (err) {
      const error = { error: err.message || 'Error de conexión' };
      setResultadoSagrilaft(error);
      return error;
    } finally {
      setVerificandoSagrilaft(false);
    }
  }

  async function descargarCertificado() {
    setDescargandoCertificado(true);
    setErrorCertificado(null);
    try {
      const blob = await api.descargarCertificadoSagrilaft(formularioId);
      const url = window.URL.createObjectURL(blob);
      const enlace = document.createElement('a');
      enlace.href = url;
      enlace.download = `sagrilaft_${expediente.codigo_peticion || formularioId}.pdf`;
      document.body.appendChild(enlace);
      enlace.click();
      enlace.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      setErrorCertificado(err.message || 'Error al descargar el certificado');
    } finally {
      setDescargandoCertificado(false);
    }
  }

  return {
    sagrilaftHabilitado,
    verificandoSagrilaft,
    resultadoSagrilaft,
    setResultadoSagrilaft,
    descargandoCertificado,
    errorCertificado,
    verificarSagrilaft,
    descargarCertificado,
  };
}
