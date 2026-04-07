/**
 * Hook: useFormPersistencia
 *
 * Orquestador de la estrategia híbrida de autoguardado.
 * Combina tres capas complementarias con responsabilidades distintas:
 *
 *   Capa 1 — usePersistenciaLocal   (debounce 3s  → localStorage)
 *     Guarda tras cada pausa natural del usuario. Rápido, offline-first.
 *
 *   Capa 2 — useSalidaSegura        (beforeunload + visibilitychange)
 *     Red de seguridad: garantiza un guardado local ante cualquier cierre
 *     abrupto, independientemente del estado del debounce.
 *
 *   Capa 3 — usePersistenciaRemota  (debounce 10s → API)
 *     Sincroniza con el servidor a menor frecuencia. Fallo silencioso;
 *     la Capa 1 actúa como respaldo si el servidor no está disponible.
 *
 * Al montar, detecta borradores previos en localStorage y ofrece
 * recuperación al usuario mediante un diálogo de confirmación.
 *
 * Interfaz pública idéntica a la versión anterior — sin cambios en consumidores.
 *
 * SRP: única responsabilidad = orquestar las capas y gestionar el ciclo
 *      de vida del borrador (detectar / restaurar / limpiar).
 */
import { useState, useEffect } from 'react';
import { usePersistenciaLocal } from './usePersistenciaLocal';
import { usePersistenciaRemota } from './usePersistenciaRemota';
import { useSalidaSegura } from './useSalidaSegura';
import {
  leerBorradorDeStorage,
  eliminarBorradorDeStorage,
  construirMensajeRecuperacion,
} from '../utils/borradorStorage';

export function useFormPersistencia(snapshot, setters, construirPayload) {
  const {
    setFormData, setStep, setFormularioId, setCodigoPeticion,
    setJuntaDirectiva, setAccionistas, setBeneficiarios,
    setReferenciasComerciales, setReferenciasBancarias,
    setInfoBancariaPagos, setDocumentos,
  } = setters;

  const [lastSaved, setLastSaved] = useState(null);

  // ── Capa 2: red de seguridad ante cierres abruptos ────────────────────────
  // Se registra primero para que los listeners estén activos lo antes posible.
  useSalidaSegura(snapshot);

  // ── Capa 1: guardado local con debounce (3s) ──────────────────────────────
  const { guardarAhora: guardarBorradorLocal } = usePersistenciaLocal(snapshot, setLastSaved);

  // ── Capa 3: guardado remoto con debounce (10s) ────────────────────────────
  usePersistenciaRemota(snapshot, construirPayload, setLastSaved);

  // ── Restauración de borrador al montar ────────────────────────────────────
  useEffect(() => {
    const borrador = leerBorradorDeStorage();
    if (!borrador) return;
    if (!borrador.formularioId && !borrador.codigoPeticion) return;

    if (window.confirm(construirMensajeRecuperacion(borrador))) {
      setFormData(borrador.formData ?? {});
      setStep(borrador.step ?? 1);
      setFormularioId(borrador.formularioId ?? null);
      setCodigoPeticion(borrador.codigoPeticion ?? null);
      setJuntaDirectiva(
        borrador.juntaDirectiva ?? [{ cargo: 'Presidente' }, { cargo: 'Gerente General / Rep. Legal' }],
      );
      setAccionistas(borrador.accionistas ?? [{}]);
      setBeneficiarios(borrador.beneficiarios ?? [{}]);
      setReferenciasComerciales(borrador.referenciasComerciales ?? [{}, {}]);
      setReferenciasBancarias(borrador.referenciasBancarias ?? [{}, {}]);
      setInfoBancariaPagos(borrador.infoBancariaPagos ?? [{}, {}]);
      setDocumentos(borrador.documentos ?? {});
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── Interfaz pública ──────────────────────────────────────────────────────
  return {
    lastSaved,
    limpiarBorrador: eliminarBorradorDeStorage,
    guardarBorradorLocal,
  };
}
