import { useState, useCallback } from 'react';

/**
 * Persiste un valor en sessionStorage: sobrevive la navegación entre pasos
 * pero se reinicia al abrir una nueva sesión del navegador.
 */
export function usePersistenciaAviso(clave, valorInicial) {
  const [valor, setValorInterno] = useState(() => {
    try {
      const guardado = sessionStorage.getItem(clave);
      return guardado !== null ? JSON.parse(guardado) : valorInicial;
    } catch {
      return valorInicial;
    }
  });

  const setValor = useCallback((actualizador) => {
    setValorInterno(prev => {
      const siguiente = typeof actualizador === 'function' ? actualizador(prev) : actualizador;
      try {
        sessionStorage.setItem(clave, JSON.stringify(siguiente));
      } catch { /* sessionStorage no disponible — degradación silenciosa */ }
      return siguiente;
    });
  }, [clave]);

  return [valor, setValor];
}
