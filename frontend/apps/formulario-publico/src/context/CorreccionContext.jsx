/**
 * CorreccionContext — estado de corrección pendiente disponible en todo el árbol
 * del formulario sin prop drilling a través de 8 componentes de paso.
 *
 * Responsabilidades:
 *   1. Distribuir el estado de corrección (qué campos están marcados).
 *   2. Calcular el avance global: cuántos campos siguen pendientes y si
 *      la corrección ya está completamente subsanada.
 *
 * DIP : FormField y los pasos dependen de esta abstracción, no de lógica concreta.
 * SRP : calcula Y distribuye el estado de corrección; no lo presenta.
 *
 * Uso:
 *   // Proveer (en FormularioSagrilaft):
 *   <CorreccionProvider
 *     estadoFormulario={...}
 *     camposACorregirRaw={...}
 *     valoresOriginales={formDataOriginal}
 *     formDataActual={formData}
 *     tablasActuales={{ juntaDirectiva, accionistas, ... }}
 *     tablasOriginales={tablasOriginales}
 *   >
 *     {children}
 *   </CorreccionProvider>
 *
 *   // Consumir (en FormField, BannerCorreccionPendiente, u otros):
 *   const { esCampoConCorreccion, todasCorreccionesCompletadas } = useCorreccion();
 */

import { createContext, useContext, useCallback } from 'react';
import { useCorreccionPendiente } from '../hooks/useCorreccionPendiente';
import { useEstadoCorreccionGlobal } from '../hooks/useEstadoCorreccionGlobal';

const CorreccionContext = createContext({
  activa:                         false,
  especificaciones:               '',
  camposIdentificados:            new Set(),
  camposCorregidos:               new Set(),
  camposPendientes:               new Set(),
  pasoInicialCorreccion:          null,
  todasCorreccionesCompletadas:   false,
  esCampoConCorreccion:           () => false,
  valorOriginalDeCampo:           () => undefined,
});

export function CorreccionProvider({
  estadoFormulario,
  camposACorregirRaw,
  valoresOriginales  = {},
  formDataActual     = {},
  tablasActuales     = null,
  tablasOriginales   = null,
  children,
}) {
  const correccionPendiente = useCorreccionPendiente(estadoFormulario, camposACorregirRaw);

  const { camposCorregidos, camposPendientes, todasCorreccionesCompletadas } =
    useEstadoCorreccionGlobal({
      camposIdentificados: correccionPendiente.camposIdentificados,
      formDataActual,
      formDataOriginal:    valoresOriginales,
      tablasActuales,
      tablasOriginales,
    });

  const valorOriginalDeCampo = useCallback(
    (nombre) => valoresOriginales[nombre],
    [valoresOriginales],
  );

  const contextoCorreccion = {
    ...correccionPendiente,
    camposCorregidos,
    camposPendientes,
    todasCorreccionesCompletadas,
    valorOriginalDeCampo,
  };

  return (
    <CorreccionContext.Provider value={contextoCorreccion}>
      {children}
    </CorreccionContext.Provider>
  );
}

export function useCorreccion() {
  return useContext(CorreccionContext);
}
