/**
 * Hook: useRecuperacionSesion
 *
 * Gestiona el flujo de recuperación de sesión identificado por código de petición + PIN.
 *
 * La verificación del PIN requiere siempre una llamada de red al backend (el hash
 * Argon2 nunca se almacena en localStorage por razones de seguridad). El borrador
 * local se usa para detectar la existencia de una sesión previa y mostrar el modal,
 * pero las credenciales siempre se validan contra el servidor.
 *
 * Flujos de inicialización:
 *   - Token URL (?token=...): resuelve el enlace de diligenciamiento y carga el formulario.
 *   - Borrador local: detecta sesión previa y muestra el modal de recuperación.
 *   - Manual: el usuario pulsa "Recuperar sesión" desde el encabezado.
 *
 * SRP: única responsabilidad = detectar, identificar y restaurar sesiones previas.
 * DIP: depende de borradorStorage y api, no de implementaciones de persistencia.
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { useDiligenciamiento } from '../context/DiligenciamientoContext';

// Campos del servidor que NO deben copiarse en formData del cliente.
// Son metadatos del formulario o tablas gestionadas como estado separado.
const _CAMPOS_EXCLUIR_DE_FORMDATA = new Set([
  'id', 'codigo_peticion', 'estado', 'pagina_actual', 'created_at', 'updated_at',
  'campos_a_corregir',
  'junta_directiva', 'accionistas', 'beneficiario_final',
  'referencias_comerciales', 'referencias_bancarias', 'informacion_bancaria_pagos',
  'documentos', 'validaciones',
]);

const _CAMPOS_BOOLEANOS_SI_NO = [
  'realiza_operaciones_moneda_extranjera',
  'autorretenedor',
  'gran_contribuyente',
  'entidad_sin_animo_lucro',
  'retencion_ica',
  'impuesto_ica',
  'entidad_oficial',
  'exento_retencion_fuente',
];

const ERRORES_RECUPERACION = {
  CREDENCIALES_INVALIDAS: 'Código de petición o PIN incorrecto. Verifique los datos',
  FORMULARIO_YA_ENVIADO: 'Este formulario ya fue enviado y no puede recuperarse.',
  ACCESO_EXPIRADO: 'El acceso ha expirado. Solicite un nuevo enlace al área responsable.',
};

function _normalizarBooleanoSiNo(valor) {
  if (valor === true || valor === false || valor === null || valor === undefined) return valor;
  if (typeof valor !== 'string') return valor;
  const normalizado = valor.trim().toLowerCase();
  if (normalizado === 'si' || normalizado === 'sí' || normalizado === 'true') return true;
  if (normalizado === 'no' || normalizado === 'false') return false;
  return valor;
}

function _normalizarBooleanosFormulario(formData) {
  const normalizado = { ...(formData ?? {}) };
  _CAMPOS_BOOLEANOS_SI_NO.forEach(campo => {
    if (campo in normalizado) normalizado[campo] = _normalizarBooleanoSiNo(normalizado[campo]);
  });
  return normalizado;
}

function _normalizarDocumentos(documentosArray) {
  if (!Array.isArray(documentosArray)) return {};
  return documentosArray.reduce((acc, doc) => {
    acc[doc.tipo_documento] = doc;
    return acc;
  }, {});
}

function _adaptarRespuestaServidor(formulario, borradorLocal = null) {
  const formData = _normalizarBooleanosFormulario(Object.fromEntries(
    Object.entries(formulario).filter(([k]) => !_CAMPOS_EXCLUIR_DE_FORMDATA.has(k)),
  ));

  const documentos = _normalizarDocumentos(formulario.documentos);

  // Preservar datos extraídos por IA (que el backend no persiste en la BD)
  // cruzando el ID del documento para asegurar que es el mismo archivo.
  if (borradorLocal && borradorLocal.documentos) {
    Object.keys(documentos).forEach(tipo => {
      const docLocal = borradorLocal.documentos[tipo];
      const docServer = documentos[tipo];
      if (docLocal && docLocal.id === docServer.id) {
        if (docServer.razon_social_extraida == null && docLocal.razon_social_extraida != null) {
          docServer.razon_social_extraida = docLocal.razon_social_extraida;
        }
        if (docServer.nit_extraido == null && docLocal.nit_extraido != null) {
          docServer.nit_extraido = docLocal.nit_extraido;
        }
        if (docServer.nombre_representante_extraido == null && docLocal.nombre_representante_extraido != null) {
          docServer.nombre_representante_extraido = docLocal.nombre_representante_extraido;
        }
        if (docServer.numero_doc_representante_extraido == null && docLocal.numero_doc_representante_extraido != null) {
          docServer.numero_doc_representante_extraido = docLocal.numero_doc_representante_extraido;
        }
        if (docServer.direccion_extraida == null && docLocal.direccion_extraida != null) {
          docServer.direccion_extraida = docLocal.direccion_extraida;
        }
      }
    });
  }

  return {
    formData,
    step: formulario.pagina_actual ?? 1,
    formularioId: formulario.id,
    codigoPeticion: formulario.codigo_peticion,
    estadoFormulario: formulario.estado ?? null,
    camposACorregir: formulario.campos_a_corregir ?? null,
    juntaDirectiva: formulario.junta_directiva ?? [],
    accionistas: formulario.accionistas ?? [],
    beneficiarios: formulario.beneficiario_final ?? [],
    referenciasComerciales: formulario.referencias_comerciales ?? [],
    referenciasBancarias: formulario.referencias_bancarias ?? [],
    infoBancariaPagos: formulario.informacion_bancaria_pagos ?? [],
    documentos,
  };
}

export function useRecuperacionSesion(setters) {
  const {
    setFormData, setStep, setFormularioId, setCodigoPeticion,
    setEstadoFormulario, setCamposACorregir, setFormDataOriginal,
    setTablasOriginales,
    setJuntaDirectiva, setAccionistas, setBeneficiarios,
    setReferenciasComerciales, setReferenciasBancarias,
    setInfoBancariaPagos, setDocumentos,
  } = setters;

  const { snapshotInicial, credencialesRef, cerrarSesion } = useDiligenciamiento();

  const _restaurarDesdeSnapshot = useCallback((snapshot_recuperar_sesion) => {
    setFormData(_normalizarBooleanosFormulario(snapshot_recuperar_sesion.formData ?? {}));
    setStep(snapshot_recuperar_sesion.step ?? 1);
    setFormularioId(snapshot_recuperar_sesion.formularioId ?? null);
    setCodigoPeticion(snapshot_recuperar_sesion.codigoPeticion ?? null);
    setEstadoFormulario(snapshot_recuperar_sesion.estadoFormulario ?? null);
    setCamposACorregir(snapshot_recuperar_sesion.camposACorregir ?? null);
    if (snapshot_recuperar_sesion.estadoFormulario === 'en_correccion') {
      setFormDataOriginal(_normalizarBooleanosFormulario(snapshot_recuperar_sesion.formData ?? {}));
      setTablasOriginales({
        juntaDirectiva: snapshot_recuperar_sesion.juntaDirectiva ?? [],
        accionistas: snapshot_recuperar_sesion.accionistas ?? [],
        beneficiarios: snapshot_recuperar_sesion.beneficiarios ?? [],
        referenciasComerciales: snapshot_recuperar_sesion.referenciasComerciales ?? [],
        referenciasBancarias: snapshot_recuperar_sesion.referenciasBancarias ?? [],
        infoBancariaPagos: snapshot_recuperar_sesion.infoBancariaPagos ?? [],
      });
    }
    setJuntaDirectiva(
      snapshot_recuperar_sesion.juntaDirectiva?.length > 0
        ? snapshot_recuperar_sesion.juntaDirectiva
        : [{ cargo: 'Presidente' }, { cargo: 'Gerente General / Rep. Legal' }],
    );
    setAccionistas(snapshot_recuperar_sesion.accionistas?.length > 0 ? snapshot_recuperar_sesion.accionistas : [{}]);
    setBeneficiarios(snapshot_recuperar_sesion.beneficiarios?.length > 0 ? snapshot_recuperar_sesion.beneficiarios : [{}]);
    setReferenciasComerciales(snapshot_recuperar_sesion.referenciasComerciales?.length > 0 ? snapshot_recuperar_sesion.referenciasComerciales : [{}, {}]);
    setReferenciasBancarias(snapshot_recuperar_sesion.referenciasBancarias?.length > 0 ? snapshot_recuperar_sesion.referenciasBancarias : [{}, {}]);
    setInfoBancariaPagos(snapshot_recuperar_sesion.infoBancariaPagos?.length > 0 ? snapshot_recuperar_sesion.infoBancariaPagos : [{}, {}]);
    setDocumentos(snapshot_recuperar_sesion.documentos ?? {});
  }, [
    setFormData, setStep, setFormularioId, setCodigoPeticion,
    setEstadoFormulario, setCamposACorregir, setFormDataOriginal,
    setTablasOriginales,
    setJuntaDirectiva, setAccionistas, setBeneficiarios,
    setReferenciasComerciales, setReferenciasBancarias,
    setInfoBancariaPagos, setDocumentos,
  ]);

  const restaurarDesdeSnapshotRef = useRef(_restaurarDesdeSnapshot);
  useEffect(() => { restaurarDesdeSnapshotRef.current = _restaurarDesdeSnapshot; });

  useEffect(() => {
    if (snapshotInicial) {
      if (snapshotInicial.formularioId !== undefined) {
        // Es un borrador local directamente (formato cliente)
        restaurarDesdeSnapshotRef.current(snapshotInicial);
      } else {
        // Es respuesta del servidor (formato API)
        restaurarDesdeSnapshotRef.current(_adaptarRespuestaServidor(
          snapshotInicial, 
          snapshotInicial._borradorLocalPrecedente
        ));
      }
    }
  }, [snapshotInicial]);

  // Apertura programática con mensaje de error (ej: 401 en submit)
  const abrirConError = useCallback((mensaje) => {
    cerrarSesion(mensaje);
  }, [cerrarSesion]);

  return {
    abrirConError,
    credencialesRef,
  };
}
