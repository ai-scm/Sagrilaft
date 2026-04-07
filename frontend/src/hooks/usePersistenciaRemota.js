/**
 * Hook: usePersistenciaRemota
 *
 * Capa 3 de la estrategia híbrida: sincronización con el servidor.
 *
 * Persiste el formulario en la API con un debounce más largo que la capa
 * local, reduciendo la carga sobre el backend. Solo actúa cuando ya existe
 * un formularioId (el borrador fue creado previamente en la base de datos).
 *
 * Los fallos son silenciosos por diseño: la capa local actúa como respaldo
 * ante errores de red o indisponibilidad temporal del servidor.
 *
 * Por qué debounce y no intervalo fijo:
 *  - Intervalo: guarda aunque el usuario lleve 28s sin tocar el formulario.
 *  - Debounce:  guarda 10s después del último cambio real → cero llamadas
 *               innecesarias cuando el usuario está inactivo.
 *
 * SRP: única responsabilidad = persistencia remota con debounce.
 */
import { useEffect } from 'react';
import { api } from '../services/api';

const DEMORA_GUARDADO_REMOTO_MS = 10_000;

/**
 * @param {object} snapshot              - Estado completo del formulario
 * @param {() => object} construirPayload - Función que arma el payload para la API.
 *   Se invoca dentro del timeout, capturando el estado del último render que
 *   disparó el efecto — comportamiento correcto con debounce.
 * @param {(fecha: Date) => void} alGuardar - Callback tras guardado remoto exitoso
 */
export function usePersistenciaRemota(snapshot, construirPayload, alGuardar) {
  const {
    formData, step, formularioId, codigoPeticion,
    juntaDirectiva, accionistas, beneficiarios,
    referenciasComerciales, referenciasBancarias,
    infoBancariaPagos, documentos,
  } = snapshot;

  useEffect(() => {
    // Sin datos o sin ID de formulario: no hay nada que sincronizar remotamente.
    if (Object.keys(formData).length === 0 || !formularioId) return;

    let cancelado = false;

    const timer = setTimeout(async () => {
      try {
        await api.actualizarFormulario(formularioId, construirPayload());
        if (!cancelado) alGuardar(new Date());
      } catch {
        // Fallo silencioso: localStorage ya tiene el snapshot reciente.
        // El usuario no pierde datos; el servidor se sincronizará en el
        // próximo guardado manual o en el guardado ante salida (Capa 2).
      }
    }, DEMORA_GUARDADO_REMOTO_MS);

    return () => {
      clearTimeout(timer);
      cancelado = true;
    };
    // `construirPayload` se omite: es la función _buildPayload de useFormulario,
    // recreada en cada render pero capturada correctamente por el closure del
    // render que disparó el efecto — semántica correcta con debounce.
    // `alGuardar` se omite: es setLastSaved, referencia estable por React.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [formData, step, formularioId, codigoPeticion, juntaDirectiva, accionistas, beneficiarios, referenciasComerciales, referenciasBancarias, infoBancariaPagos, documentos]);
}
