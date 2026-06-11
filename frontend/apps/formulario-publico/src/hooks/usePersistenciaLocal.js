/**
 * Hook: usePersistenciaLocal
 *
 * Capa 1 de la estrategia híbrida de autoguardado.
 *
 * Persiste el formulario en localStorage con debounce: espera DEMORA_MS
 * tras el último cambio detectado antes de escribir. Esto evita guardar
 * en mitad de una edición activa y reduce escrituras innecesarias.
 *
 * Ventajas de esta capa:
 *  - Respuesta rápida (3s de pausa natural del usuario)
 *  - Síncrono con localStorage → no falla por red
 *  - Funciona sin formularioId (borrador aún no creado en servidor)
 *
 * SRP: única responsabilidad = persistencia local con debounce.
 */
import { useEffect, useCallback } from 'react';
import { guardarBorradorEnStorage } from '../utils/borradorStorage';

const DEMORA_GUARDADO_LOCAL_MS = 3_000;

/**
 * @param {object} snapshot        - Estado completo del formulario a persistir
 * @param {(fecha: Date) => void} alGuardar - Callback invocado tras cada guardado exitoso
 * @returns {{ guardarAhora: () => void }} Función para guardado inmediato (sin debounce)
 */
export function usePersistenciaLocal(snapshot, alGuardar) {
  const {
    formData, step, formularioId, codigoPeticion,
    submitted,
    juntaDirectiva, accionistas, beneficiarios,
    referenciasComerciales, referenciasBancarias,
    infoBancariaPagos, documentos,
  } = snapshot;

  // Debounce: cada cambio reinicia el timer. El guardado ocurre solo
  // después de DEMORA_MS sin actividad — en la pausa natural del usuario.
  //
  // `submitted` está en las dependencias: cuando el formulario se envía
  // React ejecuta el cleanup (clearTimeout) antes de re-ejecutar el efecto,
  // cancelando cualquier timer pendiente. El nuevo efecto aborta de inmediato
  // gracias al guard, por lo que nunca reescribe el borrador ya limpiado.
  useEffect(() => {
    if (Object.keys(formData).length === 0) return;
    // Formulario enviado: no persistir. El storage ya fue limpiado por
    // handleSubmit → limpiarBorrador(). Este guard es la segunda línea de
    // defensa ante el timer de debounce que quedó pendiente del último cambio.
    if (submitted) return;

    const timer = setTimeout(() => {
      guardarBorradorEnStorage(snapshot);
      alGuardar(new Date());
    }, DEMORA_GUARDADO_LOCAL_MS);

    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [formData, step, formularioId, codigoPeticion, submitted, juntaDirectiva, accionistas, beneficiarios, referenciasComerciales, referenciasBancarias, infoBancariaPagos, documentos]);

  // Guardado inmediato para uso programático (ej: fallback en error de red)
  const guardarAhora = useCallback(() => {
    guardarBorradorEnStorage(snapshot);
    alGuardar(new Date());
  }, [snapshot, alGuardar]);

  return { guardarAhora };
}
