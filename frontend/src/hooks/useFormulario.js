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
import { useTablasDinamicas } from './useTablasDinamicas';
import { useFormPersistencia } from './useFormPersistencia';

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
  } = useTablasDinamicas();

  const _buildPayload = () => ({
    ...formData,
    pagina_actual: step,
    junta_directiva: juntaDirectiva,
    accionistas,
    beneficiarios,
    referencias_comerciales: referenciasComerciales,
    referencias_bancarias: referenciasBancarias,
  });

  const { lastSaved, limpiarBorrador, guardarBorradorLocal } = useFormPersistencia(
    { formData, step, formularioId, codigoPeticion, juntaDirectiva, accionistas, beneficiarios, referenciasComerciales, referenciasBancarias },
    { setFormData, setStep, setFormularioId, setCodigoPeticion, setJuntaDirectiva, setAccionistas, setBeneficiarios, setReferenciasComerciales, setReferenciasBancarias },
    _buildPayload,
  );

  // ── Handlers de formulario ───────────────────────────────────────────────

  const handleChange = useCallback((e) => {
    const { name, value, type, checked } = e.target;
    setFormData(prev => ({ ...prev, [name]: type === 'checkbox' ? checked : value }));
    limpiarError(name);
  }, [limpiarError]);

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

  // ── Navegación ───────────────────────────────────────────────────────────

  const handleNext = () => {
    const newErrors = validarPaso(step);
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
    if (!formData.autorizacion_datos) {
      allErrors.autorizacion_datos = 'Debe aceptar la autorización de tratamiento de datos';
    }
    if (!formData.declaracion_origen_fondos) {
      allErrors.declaracion_origen_fondos = 'Debe aceptar la declaración de origen de fondos';
    }
    aplicarErrores(allErrors);

    if (Object.keys(allErrors).length > 0) {
      const firstFailStep = [2, 3, 5, 6, 7].find(s =>
        (CAMPOS_REQUERIDOS[s] || []).some(f => allErrors[f]) ||
        (s === 7 && (allErrors.autorizacion_datos || allErrors.declaracion_origen_fondos))
      );
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
      alert('⚠️ Error al conectar con el servidor. Intente nuevamente.');
    }
    setSaving(false);
  };

  // ── Interfaz pública del hook ────────────────────────────────────────────

  return {
    step, formData, errors, helpField, setHelpField,
    codigoPeticion, documentos, saving, uploadingDoc,
    juntaDirectiva, accionistas, beneficiarios, submitted, lastSaved,
    referenciasComerciales, handleReferenciaChange, addReferencia,
    referenciasBancarias, handleReferenciaBancariaChange, addReferenciaBancaria,
    handleChange, handleFileChange, handleRemoveFile, handleSaveDraft,
    handleNext, handlePrev, handleStepClick, handleSubmit,
    handleJuntaChange, addJuntaMember, handleAccionistaChange, addAccionista,
    handleBeneficiarioChange, addBeneficiario,
  };
}
