/**
 * Hook: useTablasDinamicas
 *
 * Gestiona las filas de las tablas de Junta Directiva y Accionistas.
 * SRP: única responsabilidad = CRUD de filas en ambas tablas.
 * DRY: lógica de tabla genérica reutilizada para ambas entidades.
 */
import { useState, useCallback } from 'react';

const JUNTA_INICIAL = [
  { cargo: 'Presidente' },
  { cargo: 'Gerente General / Rep. Legal' },
];

/** Hook interno genérico para cualquier tabla de filas editables. */
function usarTabla(valorInicial) {
  const [filas, setFilas] = useState(valorInicial);

  const cambiarFila = useCallback((index, campo, valor) => {
    setFilas(prev => {
      const actualizado = [...prev];
      actualizado[index] = { ...actualizado[index], [campo]: valor };
      return actualizado;
    });
  }, []);

  const agregarFila = useCallback((filaInicial = {}) => {
    setFilas(prev => [...prev, filaInicial]);
  }, []);

  return { filas, setFilas, cambiarFila, agregarFila };
}

export function useTablasDinamicas() {
  const junta             = usarTabla(JUNTA_INICIAL);
  const accionistasTabla  = usarTabla([{}]);
  const beneficiariosTabla = usarTabla([{}]);

  return {
    // Junta Directiva
    juntaDirectiva:     junta.filas,
    setJuntaDirectiva:  junta.setFilas,
    handleJuntaChange:  junta.cambiarFila,
    addJuntaMember:     () => junta.agregarFila(),
    // Accionistas
    accionistas:            accionistasTabla.filas,
    setAccionistas:         accionistasTabla.setFilas,
    handleAccionistaChange: accionistasTabla.cambiarFila,
    addAccionista:          () => accionistasTabla.agregarFila({}),
    // Beneficiarios Finales
    beneficiarios:            beneficiariosTabla.filas,
    setBeneficiarios:         beneficiariosTabla.setFilas,
    handleBeneficiarioChange: beneficiariosTabla.cambiarFila,
    addBeneficiario:          () => beneficiariosTabla.agregarFila({}),
  };
}
