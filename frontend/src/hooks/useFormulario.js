/**
 * Hook: useFormulario
 *
 * Orquestador principal del formulario SAGRILAFT.
 * Delega validación, persistencia y tablas a sub-hooks especializados.
 *
 * SRP: única responsabilidad = coordinar los sub-hooks y exponer la interfaz pública.
 * DIP: los pasos dependen de esta interfaz, no de implementaciones concretas.
 */
import { useState, useCallback } from 'react';
import { api } from '../services/api';
import { TOTAL_STEPS, CAMPOS_REQUERIDOS } from '../data/formularioConfig';
import { useFormValidacion } from './useFormValidacion';
import { useTablasDinamicas, JUNTA_INICIAL } from './useTablasDinamicas';
import { useFormPersistencia } from './useFormPersistencia';
import { useAlertasInconsistencia } from './useAlertasInconsistencia';
import {
  validarTablasPaso4, CLAVES_ERROR_PASO4,
  validarTablasPaso6, CLAVES_ERROR_PASO6,
  validarTablasPaso7, CLAVES_ERROR_PASO7,
} from '../utils/validacionTablas';
import { sanitizarPayload } from '../utils/normalizadores';

export function useFormulario() {
  const [step, setStep] = useState(1);
  const [formData, setFormData] = useState({});
  const [helpField, setHelpField] = useState(null);
  const [formularioId, setFormularioId] = useState(null);
  const [codigoPeticion, setCodigoPeticion] = useState(null);
  const [documentos, setDocumentos] = useState({});
  const [saving, setSaving] = useState(false);
  const [uploadingDoc, setUploadingDoc] = useState({});
  const [submitted, setSubmitted] = useState(false);

  const { errors, validarPaso, aplicarErrores, limpiarError } = useFormValidacion(formData);

  const {
    alertasRazonSocial,
    alertasNit,
    alertasNombreRepresentante,
    alertasNumeroDocRepresentante,
    alertasDireccion,
    hayAlertasActivas,
  } = useAlertasInconsistencia(documentos, formData);

  const {
    juntaDirectiva, setJuntaDirectiva,
    handleJuntaChange, addJuntaMember,
    accionistas, setAccionistas,
    handleAccionistaChange, addAccionista,
    beneficiarios, setBeneficiarios,
    handleBeneficiarioChange, addBeneficiario,
    referenciasComerciales, setReferenciasComerciales,
    handleReferenciaChange, addReferencia,
    referenciasBancarias, setReferenciasBancarias,
    handleReferenciaBancariaChange, addReferenciaBancaria,
    infoBancariaPagos, setInfoBancariaPagos,
    handleInfoBancariaPagosChange, addInfoBancariaPagos,
  } = useTablasDinamicas();

  /**
   * Construye el payload que se envía a la API.
   *
   * Las tablas del Paso 4 (Junta, Accionistas, Beneficiarios) son exclusivas
   * de Persona Jurídica. Para Persona Natural se envían arrays vacíos para
   * evitar que datos residuales contaminen la DB y generen errores de
   * validación en el backend cuando el tipo cambia entre sesiones.
   */
  const _buildPayload = () => {
    const esPersonaJuridica = formData.tipo_persona === 'juridica';
    return sanitizarPayload({
      ...formData,
      pagina_actual: step,
      junta_directiva:    esPersonaJuridica ? juntaDirectiva : [],
      accionistas:        esPersonaJuridica ? accionistas    : [],
      beneficiario_final: esPersonaJuridica ? beneficiarios  : [],
      referencias_comerciales:    referenciasComerciales,
      referencias_bancarias:      referenciasBancarias,
      informacion_bancaria_pagos: infoBancariaPagos,
    });
  };

  const { lastSaved, limpiarBorrador, guardarBorradorLocal } = useFormPersistencia(
    { formData, step, formularioId, codigoPeticion, submitted, juntaDirectiva, accionistas, beneficiarios, referenciasComerciales, referenciasBancarias, infoBancariaPagos, documentos },
    { setFormData, setStep, setFormularioId, setCodigoPeticion, setJuntaDirectiva, setAccionistas, setBeneficiarios, setReferenciasComerciales, setReferenciasBancarias, setInfoBancariaPagos, setDocumentos },
    _buildPayload,
  );

  // ── Handlers de formulario ───────────────────────────────────────────────

  const handleChange = useCallback((e) => {
    const { name, value, type, checked } = e.target;
    const nuevoValor = type === 'checkbox' ? checked : value;
    setFormData(prev => ({ ...prev, [name]: nuevoValor }));
    limpiarError(name);

    // Al cambiar a Persona Natural, reiniciar las tablas del Paso 4 a su
    // estado vacío/inicial y limpiar sus errores. Evita que datos de una
    // sesión previa como Jurídica queden activos y disparen validaciones.
    if (name === 'tipo_persona' && nuevoValor === 'natural') {
      setJuntaDirectiva(JUNTA_INICIAL);
      setAccionistas([{}]);
      setBeneficiarios([{}]);
      aplicarErrores(prev => {
        const sinTablasPaso4 = { ...prev };
        for (const clave of CLAVES_ERROR_PASO4) delete sinTablasPaso4[clave];
        return sinTablasPaso4;
      });
    }
  }, [limpiarError, aplicarErrores, setJuntaDirectiva, setAccionistas, setBeneficiarios]);

  const handleFileChange = async (tipoDoc, file) => {
    if (!file) return;
    setUploadingDoc(prev => ({ ...prev, [tipoDoc]: true }));
    try {
      let currentId = formularioId;
      if (!currentId) {
        const result = await api.crearFormulario({ pagina_actual: 1 });
        currentId = result.id;
        setFormularioId(currentId);
        setCodigoPeticion(result.codigo_peticion);
      }
      const docRes = await api.subirDocumento(currentId, tipoDoc, file);
      setDocumentos(prev => ({ ...prev, [tipoDoc]: docRes }));
      if (docRes.campos_sugeridos && Object.keys(docRes.campos_sugeridos).length > 0) {
        setFormData(prev => ({ ...prev, ...docRes.campos_sugeridos }));
      }
    } catch (err) {
      console.error(`Error subiendo ${tipoDoc}:`, err);
      alert('Error al subir el documento. Intente nuevamente.');
    } finally {
      setUploadingDoc(prev => ({ ...prev, [tipoDoc]: false }));
    }
  };

  const handleRemoveFile = useCallback((tipoDoc) => {
    setDocumentos(prev => {
      const updated = { ...prev };
      delete updated[tipoDoc];
      return updated;
    });
  }, []);

  const handleSaveDraft = async () => {
    setSaving(true);
    try {
      if (!formularioId) {
        const result = await api.crearFormulario(_buildPayload());
        setFormularioId(result.id);
        setCodigoPeticion(result.codigo_peticion);
      } else {
        await api.actualizarFormulario(formularioId, _buildPayload());
      }
      alert('✅ Borrador guardado exitosamente');
    } catch (err) {
      console.error('Error guardando borrador:', err);
      alert('⚠️ Borrador guardado localmente (el servidor no está disponible)');
      guardarBorradorLocal();
    } finally {
      setSaving(false);
    }
  };

  // ── Handlers de tablas (limpian errores del paso 4 al editar) ────────────

  const _limpiarErroresPaso4 = useCallback(() => {
    aplicarErrores(prev => {
      const sinTablas = { ...prev };
      for (const clave of CLAVES_ERROR_PASO4) delete sinTablas[clave];
      return sinTablas;
    });
  }, [aplicarErrores]);

  const onJuntaChange = useCallback((...args) => {
    handleJuntaChange(...args);
    _limpiarErroresPaso4();
  }, [handleJuntaChange, _limpiarErroresPaso4]);

  const onAccionistaChange = useCallback((...args) => {
    handleAccionistaChange(...args);
    _limpiarErroresPaso4();
  }, [handleAccionistaChange, _limpiarErroresPaso4]);

  const onBeneficiarioChange = useCallback((...args) => {
    handleBeneficiarioChange(...args);
    _limpiarErroresPaso4();
  }, [handleBeneficiarioChange, _limpiarErroresPaso4]);

  // ── Handlers de tablas (limpian errores del paso 6 al editar) ────────────

  const _limpiarErroresPaso6 = useCallback(() => {
    aplicarErrores(prev => {
      const sinTablas = { ...prev };
      for (const clave of CLAVES_ERROR_PASO6) delete sinTablas[clave];
      return sinTablas;
    });
  }, [aplicarErrores]);

  const onReferenciaChange = useCallback((...args) => {
    handleReferenciaChange(...args);
    _limpiarErroresPaso6();
  }, [handleReferenciaChange, _limpiarErroresPaso6]);

  const onReferenciaBancariaChange = useCallback((...args) => {
    handleReferenciaBancariaChange(...args);
    _limpiarErroresPaso6();
  }, [handleReferenciaBancariaChange, _limpiarErroresPaso6]);

  // ── Handlers de tablas (limpian errores del paso 7 al editar) ────────────

  const _limpiarErroresPaso7 = useCallback(() => {
    aplicarErrores(prev => {
      const sinTablas = { ...prev };
      for (const clave of CLAVES_ERROR_PASO7) delete sinTablas[clave];
      return sinTablas;
    });
  }, [aplicarErrores]);

  const onInfoBancariaPagosChange = useCallback((...args) => {
    handleInfoBancariaPagosChange(...args);
    _limpiarErroresPaso7();
  }, [handleInfoBancariaPagosChange, _limpiarErroresPaso7]);

  // ── Navegación ───────────────────────────────────────────────────────────

  const handleNext = () => {
    const newErrors = validarPaso(step);
    if (step === 1 && alertasRazonSocial.length > 0) {
      newErrors._inconsistencias_nombre =
        'Corrige la razón social en el formulario o reemplaza el archivo adjunto para que los nombres coincidan.';
    }
    if (step === 1 && alertasNit.length > 0) {
      newErrors._inconsistencias_nit =
        'Corrige el NIT en el formulario o reemplaza el archivo adjunto para que los NITs coincidan.';
    }
    if (step === 1 && alertasNombreRepresentante.length > 0) {
      newErrors._inconsistencias_nombre_representante =
        'Corrige el nombre del representante en el formulario o reemplaza el archivo adjunto para que los nombres coincidan.';
    }
    if (step === 1 && alertasNumeroDocRepresentante.length > 0) {
      newErrors._inconsistencias_numero_doc_representante =
        'Corrige el No. de Identificación del representante en el formulario o reemplaza el archivo adjunto para que los números coincidan.';
    }
    if (step === 1 && alertasDireccion.length > 0) {
      newErrors._inconsistencias_direccion =
        'Corrige la dirección en el formulario o reemplaza el archivo adjunto para que las direcciones coincidan.';
    }
    if (step === 4) {
      Object.assign(newErrors, validarTablasPaso4({
        juntaDirectiva, accionistas, beneficiarios,
        tipoPersona: formData.tipo_persona,
      }));
    }
    if (step === 6) {
      Object.assign(newErrors, validarTablasPaso6({ referenciasComerciales, referenciasBancarias }));
    }
    if (step === 7) {
      Object.assign(newErrors, validarTablasPaso7({ infoBancariaPagos }));
    }
    aplicarErrores(newErrors);
    if (Object.keys(newErrors).length === 0) {
      setStep(prev => Math.min(prev + 1, TOTAL_STEPS));
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }
  };

  const handlePrev = () => {
    setStep(prev => Math.max(prev - 1, 1));
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const handleStepClick = (stepNum) => {
    if (stepNum < step) {
      setStep(stepNum);
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }
  };

  const handleSubmit = async () => {
    const allErrors = {};
    for (let s = 2; s <= TOTAL_STEPS; s++) {
      Object.assign(allErrors, validarPaso(s));
    }
    Object.assign(allErrors, validarTablasPaso4({
      juntaDirectiva, accionistas, beneficiarios,
      tipoPersona: formData.tipo_persona,
    }));
    Object.assign(allErrors, validarTablasPaso6({ referenciasComerciales, referenciasBancarias }));
    Object.assign(allErrors, validarTablasPaso7({ infoBancariaPagos }));
    if (!formData.autorizacion_datos) {
      allErrors.autorizacion_datos = 'Debe aceptar la autorización de tratamiento de datos';
    }
    if (!formData.declaracion_origen_fondos) {
      allErrors.declaracion_origen_fondos = 'Debe aceptar la declaración de origen de fondos';
    }
    aplicarErrores(allErrors);

    if (Object.keys(allErrors).length > 0) {
      const tieneErroresPaso4 = CLAVES_ERROR_PASO4.some(k => allErrors[k]);
      const tieneErroresPaso7 = CLAVES_ERROR_PASO7.some(k => allErrors[k]);
      const firstFailStep = [2, 3, 4, 5, 6, 7, 8].find(s => {
        if (s === 4) return tieneErroresPaso4;
        if (s === 7) return tieneErroresPaso7;
        return (CAMPOS_REQUERIDOS[s] || []).some(f => allErrors[f]) ||
          (s === 8 && (allErrors.autorizacion_datos || allErrors.declaracion_origen_fondos));
      });
      if (firstFailStep) {
        setStep(firstFailStep);
        window.scrollTo({ top: 0, behavior: 'smooth' });
      }
      return;
    }

    setSaving(true);
    try {
      if (!formularioId) {
        const result = await api.crearFormulario(_buildPayload());
        setFormularioId(result.id);
        setCodigoPeticion(result.codigo_peticion);
        await api.enviarFormulario(result.id);
      } else {
        await api.actualizarFormulario(formularioId, _buildPayload());
        await api.enviarFormulario(formularioId);
      }
      limpiarBorrador();
      setSubmitted(true);
    } catch (err) {
      console.error('Error enviando formulario:', err);
      // err.message contiene los mensajes del backend cuando valido === false
      // (ver api.js:enviarFormulario). Solo usar el texto genérico para
      // errores reales de red donde no hay mensaje estructurado.
      const mensaje = err?.message && err.message !== 'Failed to fetch'
        ? `⚠️ El formulario no pudo enviarse:\n\n${err.message}`
        : '⚠️ Error al conectar con el servidor. Intente nuevamente.';
      alert(mensaje);
    }
    setSaving(false);
  };

  // ── Interfaz pública del hook ────────────────────────────────────────────

  return {
    step, formData, errors, helpField, setHelpField,
    codigoPeticion, documentos, saving, uploadingDoc,
    juntaDirectiva, accionistas, beneficiarios, submitted, lastSaved,
    referenciasComerciales, handleReferenciaChange: onReferenciaChange, addReferencia,
    referenciasBancarias, handleReferenciaBancariaChange: onReferenciaBancariaChange, addReferenciaBancaria,
    infoBancariaPagos, handleInfoBancariaPagosChange: onInfoBancariaPagosChange, addInfoBancariaPagos,
    handleChange, handleFileChange, handleRemoveFile, handleSaveDraft,
    handleNext, handlePrev, handleStepClick, handleSubmit,
    handleJuntaChange: onJuntaChange, addJuntaMember,
    handleAccionistaChange: onAccionistaChange, addAccionista,
    handleBeneficiarioChange: onBeneficiarioChange, addBeneficiario,
    alertasRazonSocial,
    alertasNit,
    alertasNombreRepresentante,
    alertasNumeroDocRepresentante,
    alertasDireccion,
    hayAlertasActivas,
  };
}
