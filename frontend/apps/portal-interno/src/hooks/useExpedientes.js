import { useCallback, useEffect, useRef, useState } from 'react';
import { api } from '../services/api';

function useValorDebounce(valor, demoraMs) {
  const [valorDebounced, setValorDebounced] = useState(valor);

  useEffect(() => {
    const timeoutId = setTimeout(() => setValorDebounced(valor), demoraMs);
    return () => clearTimeout(timeoutId);
  }, [valor, demoraMs]);

  return valorDebounced;
}

/**
 * Hook de carga para expedientes del portal interno.
 *
 * Encapsula:
 * - debounce del término de búsqueda
 * - cancelación (AbortController) de solicitudes previas
 * - protección contra carreras (solo aplica el último resultado)
 */
export default function useExpedientes({
  filtroTipo,
  busqueda,
  demoraBusquedaMs = 450,
}) {
  const [expedientes, setExpedientes] = useState([]);
  const [expedientesParaConteos, setExpedientesParaConteos] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState(null);
  const [marcaRecarga, setMarcaRecarga] = useState(0);

  const busquedaDebounced = useValorDebounce(busqueda, demoraBusquedaMs);

  const idConsultaRef = useRef(0);
  const abortadoresRef = useRef({ lista: null, conteos: null });

  const recargar = useCallback(() => setMarcaRecarga(v => v + 1), []);

  useEffect(() => {
    const idConsulta = idConsultaRef.current + 1;
    idConsultaRef.current = idConsulta;

    setCargando(true);
    setError(null);

    const terminoBusqueda = busquedaDebounced.trim();
    const busquedaParam = terminoBusqueda ? terminoBusqueda : null;

    abortadoresRef.current.lista?.abort();
    abortadoresRef.current.conteos?.abort();

    const abortLista = new AbortController();
    abortadoresRef.current.lista = abortLista;

    const cargar = async () => {
      try {
        // Si no hay filtro por tipo, una sola llamada sirve tanto para lista como para conteos.
        if (!filtroTipo) {
          const datos = await api.listarExpedientes(null, busquedaParam, { signal: abortLista.signal });
          if (idConsulta !== idConsultaRef.current) return;
          setExpedientes(datos);
          setExpedientesParaConteos(datos);
          return;
        }

        const abortConteos = new AbortController();
        abortadoresRef.current.conteos = abortConteos;

        const [resultadoConteos, resultadoLista] = await Promise.allSettled([
          api.listarExpedientes(null, busquedaParam, { signal: abortConteos.signal }),
          api.listarExpedientes(filtroTipo, busquedaParam, { signal: abortLista.signal }),
        ]);

        if (resultadoConteos.status === 'fulfilled' && idConsulta === idConsultaRef.current) {
          setExpedientesParaConteos(resultadoConteos.value);
        }

        if (resultadoLista.status === 'fulfilled') {
          if (idConsulta !== idConsultaRef.current) return;
          setExpedientes(resultadoLista.value);
          return;
        }

        throw resultadoLista.reason;
      } catch (err) {
        if (err?.name === 'AbortError') return;
        if (idConsulta !== idConsultaRef.current) return;
        setError('No se pudieron cargar los formularios. Intente nuevamente.');
      } finally {
        if (idConsulta === idConsultaRef.current) {
          setCargando(false);
        }
      }
    };

    cargar();

    return () => {
      abortLista.abort();
    };
  }, [busquedaDebounced, filtroTipo, marcaRecarga]);

  return {
    expedientes,
    expedientesParaConteos,
    cargando,
    error,
    recargar,
    busquedaDebounced,
  };
}
