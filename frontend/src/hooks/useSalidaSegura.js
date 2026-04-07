/**
 * Hook: useSalidaSegura
 *
 * Capa 2 de la estrategia híbrida: red de seguridad ante cierres abruptos.
 *
 * Suscribe eventos del ciclo de vida del documento para garantizar que el
 * borrador se persista en localStorage ANTES de que el usuario abandone
 * la página, independientemente de si el debounce alcanzó a dispararse.
 *
 * Eventos cubiertos:
 *  - beforeunload  → cierre de pestaña, recarga, navegación a otro sitio
 *  - visibilitychange (hidden) → cambio de pestaña, minimizar ventana,
 *                                bloqueo de pantalla en móvil
 *
 * Patrón useRef: los listeners se registran una sola vez (efecto sin deps),
 * mientras la ref garantiza que siempre lean el snapshot más reciente del
 * formulario sin necesidad de re-registrar los handlers.
 *
 * SRP: única responsabilidad = persistir localmente ante cualquier salida.
 */
import { useEffect, useRef } from 'react';
import { guardarBorradorEnStorage } from '../utils/borradorStorage';

/**
 * @param {object} snapshot - Estado actual del formulario.
 *   El hook mantiene una ref interna; no necesita ser estable entre renders.
 */
export function useSalidaSegura(snapshot) {
  const snapshotRef = useRef(snapshot);

  // Mantener la ref sincronizada en cada render sin re-ejecutar el efecto.
  // Este es el patrón estándar para "leer el valor más reciente desde un closure".
  snapshotRef.current = snapshot;

  useEffect(() => {
    const persistirAntesDeSalir = () => {
      const actual = snapshotRef.current;
      if (Object.keys(actual?.formData ?? {}).length > 0) {
        guardarBorradorEnStorage(actual);
      }
    };

    const alOcultarPagina = () => {
      if (document.visibilityState === 'hidden') {
        persistirAntesDeSalir();
      }
    };

    window.addEventListener('beforeunload', persistirAntesDeSalir);
    document.addEventListener('visibilitychange', alOcultarPagina);

    return () => {
      window.removeEventListener('beforeunload', persistirAntesDeSalir);
      document.removeEventListener('visibilitychange', alOcultarPagina);
    };
  }, []); // Registro único al montar; la ref mantiene el snapshot fresco
}
