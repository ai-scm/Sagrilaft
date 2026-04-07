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
    juntaDirectiva, accionistas, beneficiarios,
    referenciasComerciales, referenciasBancarias,
    infoBancariaPagos, documentos,
  } = snapshot;

  // Debounce: cada cambio reinicia el timer. El guardado ocurre solo
  // después de DEMORA_MS sin actividad — en la pausa natural del usuario.
  useEffect(() => {
    if (Object.keys(formData).length === 0) return;

    const timer = setTimeout(() => {
      guardarBorradorEnStorage(snapshot);
      alGuardar(new Date());
    }, DEMORA_GUARDADO_LOCAL_MS);

    return () => clearTimeout(timer);
    // `snapshot` se omite: sus campos individuales ya están en el array y
    // el objeto se recrea en cada render. `alGuardar` se omite porque es
    // setLastSaved (setter de useState) — referencia estable garantizada por React.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [formData, step, formularioId, codigoPeticion, juntaDirectiva, accionistas, beneficiarios, referenciasComerciales, referenciasBancarias, infoBancariaPagos, documentos]);

  // Guardado inmediato para uso programático (ej: fallback en error de red)
  const guardarAhora = useCallback(() => {
    guardarBorradorEnStorage(snapshot);
    alGuardar(new Date());
  }, [snapshot, alGuardar]);

  return { guardarAhora };
}
