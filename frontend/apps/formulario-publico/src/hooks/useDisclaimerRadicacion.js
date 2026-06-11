import { useCallback, useState } from 'react';

export const DISCLAIMER_RADICACION = {
  badge: 'ATENCIÓN',
  titulo: 'Confirmación obligatoria antes de radicar',
  resumen: 'Antes de continuar, ten en cuenta lo siguiente:',
  puntos: [
    'ATENCIÓN: Al correo electrónico del representante legal que usted le indico al area responsable se enviará automáticamente el formulario diligenciado junto con el Certificado SAGRILAFT para su firma electrónica. ',
    'Al presionar " ✅ Radicar Formulario " los documentos se remitirán automáticamente para firma del representante legal indicado.',
  ],
  confirmacion:
    'He leído y entiendo este aviso, y confirmo que deseo continuar con la radicación del formulario.',
};

/**
 * Controla la confirmación obligatoria previa a la radicación del formulario.
 *
 * Mantiene aisladas tres responsabilidades:
 * - estado del checkbox
 * - validación obligatoria
 * - limpieza del estado cuando se requiera reiniciar la confirmación
 */
export function useDisclaimerRadicacion() {
  const [aceptado, setAceptado] = useState(false);
  const [mensajeError, setMensajeError] = useState('');

  const actualizarAceptacion = useCallback((nuevoValor) => {
    setAceptado(Boolean(nuevoValor));
    if (nuevoValor) {
      setMensajeError('');
    }
  }, []);

  const validarDisclaimer = useCallback(() => {
    if (!aceptado) {
      setMensajeError('Debe confirmar que leyó el aviso antes de radicar el formulario.');
      return false;
    }

    setMensajeError('');
    return true;
  }, [aceptado]);

  const limpiarDisclaimer = useCallback(() => {
    setAceptado(false);
    setMensajeError('');
  }, []);

  return {
    aceptado,
    mensajeError,
    setAceptado: actualizarAceptacion,
    validarDisclaimer,
    limpiarDisclaimer,
  };
}
