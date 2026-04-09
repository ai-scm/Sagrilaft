/**
 * Hook: useTablasDinamicas
 *
 * Gestiona las filas de las tablas de Junta Directiva y Accionistas.
 * SRP: única responsabilidad = CRUD de filas en ambas tablas.
 * DRY: lógica de tabla genérica reutilizada para ambas entidades.
 */
import { useState, useCallback } from 'react';

/**
 * Fila pre-cargada para Junta Directiva: un único miembro obligatorio.
 * Los miembros adicionales son opcionales y se agregan con "+ Agregar miembro".
 * Se exporta para poder reinicializar el estado desde useFormulario cuando
 * el tipo de persona cambia.
 */
export const JUNTA_INICIAL = [
  { cargo: 'Seleccione...' },
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

  /**
   * Cambia el tipo de identificación de una fila y limpia el número
   * de identificación asociado en una única actualización de estado.
   *
   * La dependencia tipo_id → numero_id vive aquí y no en el componente:
   * cualquier tabla que gestione identificaciones puede reutilizar este
   * comportamiento sin repetir la regla en la capa de presentación.
   */
  const cambiarTipoIdentificacion = useCallback((index, nuevoTipo) => {
    setFilas(prev => {
      const actualizado = [...prev];
      actualizado[index] = { ...actualizado[index], tipo_id: nuevoTipo, numero_id: '' };
      return actualizado;
    });
  }, []);

  const agregarFila = useCallback((filaInicial = {}) => {
    setFilas(prev => [...prev, filaInicial]);
  }, []);

  return { filas, setFilas, cambiarFila, cambiarTipoIdentificacion, agregarFila };
}

export function useTablasDinamicas() {
  const junta              = usarTabla(JUNTA_INICIAL);
  const accionistasTabla   = usarTabla([{}]);
  const beneficiariosTabla = usarTabla([{}]);
  const referenciasTabla          = usarTabla([{}, {}]);
  const referenciasBancariasTabla = usarTabla([{}, {}]);
  const infoBancariaPagosTabla    = usarTabla([{}, {}]);

  return {
    // Junta Directiva
    juntaDirectiva:              junta.filas,
    setJuntaDirectiva:           junta.setFilas,
    handleJuntaChange:           junta.cambiarFila,
    handleJuntaTipoIdChange:     junta.cambiarTipoIdentificacion,
    addJuntaMember:              () => junta.agregarFila(),
    // Accionistas
    accionistas:                     accionistasTabla.filas,
    setAccionistas:                  accionistasTabla.setFilas,
    handleAccionistaChange:          accionistasTabla.cambiarFila,
    handleAccionistaTipoIdChange:    accionistasTabla.cambiarTipoIdentificacion,
    addAccionista:                   () => accionistasTabla.agregarFila({}),
    // Beneficiarios Finales
    beneficiarios:                    beneficiariosTabla.filas,
    setBeneficiarios:                 beneficiariosTabla.setFilas,
    handleBeneficiarioChange:         beneficiariosTabla.cambiarFila,
    handleBeneficiarioTipoIdChange:   beneficiariosTabla.cambiarTipoIdentificacion,
    addBeneficiario:                  () => beneficiariosTabla.agregarFila({}),
    // Referencias Comerciales
    referenciasComerciales:        referenciasTabla.filas,
    setReferenciasComerciales:     referenciasTabla.setFilas,
    handleReferenciaChange:        referenciasTabla.cambiarFila,
    addReferencia:                 () => referenciasTabla.agregarFila({}),
    // Referencias Bancarias
    referenciasBancarias:          referenciasBancariasTabla.filas,
    setReferenciasBancarias:       referenciasBancariasTabla.setFilas,
    handleReferenciaBancariaChange: referenciasBancariasTabla.cambiarFila,
    addReferenciaBancaria:         () => referenciasBancariasTabla.agregarFila({}),
    // Información Bancaria para Pagos (paso 7)
    infoBancariaPagos:            infoBancariaPagosTabla.filas,
    setInfoBancariaPagos:         infoBancariaPagosTabla.setFilas,
    handleInfoBancariaPagosChange: infoBancariaPagosTabla.cambiarFila,
    addInfoBancariaPagos:         () => infoBancariaPagosTabla.agregarFila({}),
  };
}
