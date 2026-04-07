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
    submitted,
    juntaDirectiva, accionistas, beneficiarios,
    referenciasComerciales, referenciasBancarias,
    infoBancariaPagos, documentos,
  } = snapshot;

  useEffect(() => {
    // Sin datos, sin ID o ya enviado: no sincronizar.
    // El guard de `submitted` cancela el timer de 10s que pudo haber quedado
    // pendiente desde la última edición. Sin él, el timer dispararía un PUT
    // sobre un formulario en estado ENVIADO, recibiendo un 400 del backend.
    if (Object.keys(formData).length === 0 || !formularioId || submitted) return;

    let cancelado = false;

    const timer = setTimeout(async () => {
      try {
        await api.actualizarFormulario(formularioId, construirPayload());
        if (!cancelado) alGuardar(new Date());
      } catch {
        // Fallo silencioso: localStorage ya tiene el snapshot reciente.
      }
    }, DEMORA_GUARDADO_REMOTO_MS);

    return () => {
      clearTimeout(timer);
      cancelado = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [formData, step, formularioId, codigoPeticion, submitted, juntaDirectiva, accionistas, beneficiarios, referenciasComerciales, referenciasBancarias, infoBancariaPagos, documentos]);
}
