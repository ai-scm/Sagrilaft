/**
 * Hook: useAlertasInconsistencia
 *
 * Calcula reactivamente todas las alertas de inconsistencia entre los campos
 * del formulario y los valores extraídos de los documentos adjuntos.
 *
 * Fuente de verdad única: el estado `documentos` de useFormulario, que persiste
 * en localStorage y se restaura íntegro en cada recarga de página. Esto elimina
 * el estado de extracción redundante que los hooks anteriores mantenían en memoria
 * y que se perdía al recargar.
 *
 * SRP     : única responsabilidad — exponer las alertas activas por campo.
 * DRY     : lógica de comparación delegada a utils/calcularAlertasInconsistencia.js.
 * Modular : agregar un nuevo campo vigilado = agregar su cálculo aquí + su config en utils.
 *
 * @param {Object} documentos — mapa tipoDoc → docRes (incluye valores extraídos por IA)
 * @param {Object} formData   — estado actual del formulario
 */

import { useMemo } from 'react';
import {
  calcularAlertasRazonSocial,
  calcularAlertasNit,
  calcularAlertasNombreRepresentante,
  calcularAlertasNumeroDocRepresentante,
  calcularAlertasDireccion,
} from '../utils/calcularAlertasInconsistencia';

export function useAlertasInconsistencia(documentos, formData) {
  const alertasRazonSocial = useMemo(
    () => calcularAlertasRazonSocial(documentos, formData.razon_social),
    [documentos, formData.razon_social],
  );

  const alertasNit = useMemo(
    () => calcularAlertasNit(documentos, formData.numero_identificacion, formData.tipo_identificacion),
    [documentos, formData.numero_identificacion, formData.tipo_identificacion],
  );

  const alertasNombreRepresentante = useMemo(
    () => calcularAlertasNombreRepresentante(documentos, formData.nombre_representante),
    [documentos, formData.nombre_representante],
  );

  const alertasNumeroDocRepresentante = useMemo(
    () => calcularAlertasNumeroDocRepresentante(documentos, formData.numero_doc_representante),
    [documentos, formData.numero_doc_representante],
  );

  const alertasDireccion = useMemo(
    () => calcularAlertasDireccion(documentos, formData.direccion),
    [documentos, formData.direccion],
  );

  const hayAlertasActivas = useMemo(
    () => [
      alertasRazonSocial,
      alertasNit,
      alertasNombreRepresentante,
      alertasNumeroDocRepresentante,
      alertasDireccion,
    ].some(alertas => alertas.length > 0),
    [alertasRazonSocial, alertasNit, alertasNombreRepresentante, alertasNumeroDocRepresentante, alertasDireccion],
  );

  return {
    alertasRazonSocial,
    alertasNit,
    alertasNombreRepresentante,
    alertasNumeroDocRepresentante,
    alertasDireccion,
    hayAlertasActivas,
  };
}
