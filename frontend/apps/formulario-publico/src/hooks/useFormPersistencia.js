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
 * La detección y restauración del borrador al montar fue extraída a
 * useRecuperacionSesion, que gestiona el flujo de recuperación por acceso manual
 * (código de petición + PIN) y la resolución por token (?token=...).
 *
 * SRP: única responsabilidad = orquestar las tres capas de escritura y
 *      exponer la limpieza del borrador tras un envío exitoso.
 */
import { useState } from 'react';
import { usePersistenciaLocal } from './usePersistenciaLocal';
import { usePersistenciaRemota } from './usePersistenciaRemota';
import { useSalidaSegura } from './useSalidaSegura';
import { eliminarBorradorDeStorage } from '../utils/borradorStorage';

export function useFormPersistencia(snapshot, construirPayload) {
  const [lastSaved, setLastSaved] = useState(null);

  // ── Capa 2: red de seguridad ante cierres abruptos ────────────────────────
  // Se registra primero para que los listeners estén activos lo antes posible.
  useSalidaSegura(snapshot);

  // ── Capa 1: guardado local con debounce (3s) ──────────────────────────────
  const { guardarAhora: guardarBorradorLocal } = usePersistenciaLocal(snapshot, setLastSaved);

  // ── Capa 3: guardado remoto con debounce (10s) ────────────────────────────
  usePersistenciaRemota(snapshot, construirPayload, setLastSaved);

  // ── Interfaz pública ──────────────────────────────────────────────────────
  return {
    lastSaved,
    limpiarBorrador: eliminarBorradorDeStorage,
    guardarBorradorLocal,
  };
}
