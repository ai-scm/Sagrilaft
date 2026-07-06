/**
 * Hook usePaginacion — Lógica reutilizable para gestionar paginación
 *
 * Encapsula toda la lógica de estado y cálculos de paginación:
 * - Mantiene la página actual
 * - Calcula el total de páginas basado en la cantidad de elementos
 * - Extrae los elementos de la página actual
 * - Proporciona funciones para navegar (anterior, siguiente, saltar a página)
 *
 * @param {Array} elementos - Lista completa de elementos a paginar
 * @param {number} elementosPorPagina - Máximo de elementos por página (default: 5)
 * @returns {Object} Estado y funciones para gestionar paginación
 */

import { useState, useMemo } from 'react';

export function usePaginacion(elementos = [], elementosPorPagina = 5) {
  // Estado: página actual (inicia en 1, no en 0)
  const [paginaActual, setPaginaActual] = useState(1);

  // Calcula el total de páginas y elementos de la página actual
  const paginacion = useMemo(() => {
    const totalElementos = elementos.length;
    const totalPaginas = Math.ceil(totalElementos / elementosPorPagina);

    // Validar que la página actual no sea mayor al total de páginas
    if (paginaActual > totalPaginas && totalPaginas > 0) {
      setPaginaActual(totalPaginas);
    }

    // Calcular índices de inicio y fin para extraer elementos
    const indiceInicio = (paginaActual - 1) * elementosPorPagina;
    const indiceFin = indiceInicio + elementosPorPagina;
    const elementosPagina = elementos.slice(indiceInicio, indiceFin);

    return {
      paginaActual,
      totalPaginas: Math.max(1, totalPaginas), // Mínimo 1 página
      totalElementos,
      elementosPagina,
      indiceInicio,
      indiceFin,
      esPromeraraPage: paginaActual === 1,
      esUltimaPagina: paginaActual === totalPaginas,
    };
  }, [elementos, elementosPorPagina, paginaActual]);

  // Navega a la página anterior
  function irAPaginaAnterior() {
    setPaginaActual(prev => Math.max(1, prev - 1));
  }

  // Navega a la página siguiente
  function irAPaginaSiguiente() {
    setPaginaActual(prev => Math.min(paginacion.totalPaginas, prev + 1));
  }

  // Salta a una página específica
  function irAPagina(numeroPagina) {
    const paginaValida = Math.max(1, Math.min(numeroPagina, paginacion.totalPaginas));
    setPaginaActual(paginaValida);
  }

  // Reinicia la paginación a la primera página
  function reiniciarPaginacion() {
    setPaginaActual(1);
  }

  return {
    // Estado
    paginaActual: paginacion.paginaActual,
    totalPaginas: paginacion.totalPaginas,
    totalElementos: paginacion.totalElementos,
    elementosPagina: paginacion.elementosPagina,

    // Indicadores booleanos
    esPromeraraPage: paginacion.esPromeraraPage,
    esUltimaPagina: paginacion.esUltimaPagina,
    hayMultiplesPaginas: paginacion.totalPaginas > 1,

    // Funciones de navegación
    irAPaginaAnterior,
    irAPaginaSiguiente,
    irAPagina,
    reiniciarPaginacion,

    // Información útil
    indiceInicio: paginacion.indiceInicio,
    indiceFin: paginacion.indiceFin,
  };
}
