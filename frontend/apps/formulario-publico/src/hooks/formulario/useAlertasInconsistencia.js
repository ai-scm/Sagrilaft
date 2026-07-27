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
  DOCS_RAZON_SOCIAL,
  DOCS_NIT,
  DOCS_NOMBRE_REPRESENTANTE,
  DOCS_NUMERO_DOC_REPRESENTANTE,
  DOCS_DIRECCION,
} from '../../utils/calcularAlertasInconsistencia';

export function useAlertasInconsistencia(documentos, formData, alertasServidor = []) {
  // Restaurar datos extraídos desde las alertas del servidor si no están presentes en `documentos`.
  // Esto permite que el motor de alertas siga funcionando cuando se devuelve un formulario,
  // validando los valores extraídos antiguos contra los nuevos valores ingresados en el formulario.
  const documentosConAlertas = useMemo(() => {
    const docs = { ...documentos };
    alertasServidor.forEach(alerta => {
      // Intentar encontrar el tipo de documento por el nombre legible
      const tipoDocEntry = Object.entries({
        ...DOCS_RAZON_SOCIAL, ...DOCS_NIT, ...DOCS_NOMBRE_REPRESENTANTE, ...DOCS_NUMERO_DOC_REPRESENTANTE, ...DOCS_DIRECCION
      }).find(([, config]) => config.nombreLegible === alerta.nombre_documento);
      
      if (tipoDocEntry) {
        const [tipoDoc] = tipoDocEntry;
        if (docs[tipoDoc]) {
           docs[tipoDoc] = { ...docs[tipoDoc] }; // copy
           if (alerta.tipo_campo === 'razon_social' && docs[tipoDoc].razon_social_extraida == null) docs[tipoDoc].razon_social_extraida = alerta.valor_documento;
           if (alerta.tipo_campo === 'numero_identificacion' && docs[tipoDoc].nit_extraido == null) docs[tipoDoc].nit_extraido = alerta.valor_documento;
           if (alerta.tipo_campo === 'nombre_representante' && docs[tipoDoc].nombre_representante_extraido == null) docs[tipoDoc].nombre_representante_extraido = alerta.valor_documento;
           if (alerta.tipo_campo === 'numero_doc_representante' && docs[tipoDoc].numero_doc_representante_extraido == null) docs[tipoDoc].numero_doc_representante_extraido = alerta.valor_documento;
           if (alerta.tipo_campo === 'direccion' && docs[tipoDoc].direccion_extraida == null) docs[tipoDoc].direccion_extraida = alerta.valor_documento;
        }
      }
    });
    return docs;
  }, [documentos, alertasServidor]);

  const alertasRazonSocial = useMemo(
    () => calcularAlertasRazonSocial(documentosConAlertas, formData.razon_social),
    [documentosConAlertas, formData.razon_social],
  );

  const alertasNit = useMemo(
    () => calcularAlertasNit(documentosConAlertas, formData.numero_identificacion, formData.tipo_identificacion),
    [documentosConAlertas, formData.numero_identificacion, formData.tipo_identificacion],
  );

  const alertasNombreRepresentante = useMemo(
    () => calcularAlertasNombreRepresentante(documentosConAlertas, formData.nombre_representante),
    [documentosConAlertas, formData.nombre_representante],
  );

  const alertasNumeroDocRepresentante = useMemo(
    () => calcularAlertasNumeroDocRepresentante(documentosConAlertas, formData.numero_doc_representante),
    [documentosConAlertas, formData.numero_doc_representante],
  );

  const alertasDireccion = useMemo(
    () => calcularAlertasDireccion(documentosConAlertas, formData.direccion),
    [documentosConAlertas, formData.direccion],
  );

  const todasLasAlertasActivas = useMemo(
    () => [
      ...alertasRazonSocial,
      ...alertasNit,
      ...alertasNombreRepresentante,
      ...alertasNumeroDocRepresentante,
      ...alertasDireccion,
    ],
    [alertasRazonSocial, alertasNit, alertasNombreRepresentante, alertasNumeroDocRepresentante, alertasDireccion],
  );

  const hayAlertasActivas = useMemo(
    () => todasLasAlertasActivas.length > 0,
    [todasLasAlertasActivas],
  );

  return {
    alertasRazonSocial,
    alertasNit,
    alertasNombreRepresentante,
    alertasNumeroDocRepresentante,
    alertasDireccion,
    hayAlertasActivas,
    todasLasAlertasActivas,
  };
}
