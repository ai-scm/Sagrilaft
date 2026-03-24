/**
 * Hook: useFormulario
 *
 * Centraliza TODO el estado y la lógica del formulario SAGRILAFT.
 * Los componentes de paso solo reciben datos y callbacks — no saben
 * nada de cómo se persiste ni valida el formulario.
 *
 * SRP: lógica de negocio separada del renderizado.
 * DIP: los pasos dependen de esta interfaz, no de implementaciones concretas.
 */

import { useState, useCallback, useEffect } from 'react';
import { api } from '../services/api';
import helpTexts from '../data/helpTexts';
import { TOTAL_STEPS, CAMPOS_REQUERIDOS } from '../data/formularioConfig';

const JUNTA_INICIAL = [
  { cargo: 'Presidente' },
  { cargo: 'Gerente General / Rep. Legal' },
];

export function useFormulario() {
  const [step, setStep] = useState(1);
  const [formData, setFormData] = useState({});
  const [errors, setErrors] = useState({});
  const [helpField, setHelpField] = useState(null);
  const [formularioId, setFormularioId] = useState(null);
  const [codigoPeticion, setCodigoPeticion] = useState(null);
  const [documentos, setDocumentos] = useState({});
  const [saving, setSaving] = useState(false);
  const [uploadingDoc, setUploadingDoc] = useState({});
  const [juntaDirectiva, setJuntaDirectiva] = useState(JUNTA_INICIAL);
  const [accionistas, setAccionistas] = useState([{}]);
  const [submitted, setSubmitted] = useState(false);
  const [lastSaved, setLastSaved] = useState(null);

  // ── Restaurar borrador al montar ─────────────────────────────────────────
  useEffect(() => {
    const raw = localStorage.getItem('sagrilaft_autosave');
    if (!raw) return;
    try {
      const draft = JSON.parse(raw);
      if (!draft.formularioId && !draft.codigoPeticion) return;
      const label = draft.codigoPeticion ? `Código: ${draft.codigoPeticion}` : 'un borrador sin código';
      const fecha = draft.savedAt ? ` (guardado: ${new Date(draft.savedAt).toLocaleString('es-CO')})` : '';
      if (window.confirm(`Se encontró ${label}${fecha}.\n¿Desea retomar donde lo dejó?`)) {
        setFormData(draft.formData || {});
        setStep(draft.step || 1);
        setFormularioId(draft.formularioId || null);
        setCodigoPeticion(draft.codigoPeticion || null);
        setJuntaDirectiva(draft.juntaDirectiva || JUNTA_INICIAL);
        setAccionistas(draft.accionistas || [{}]);
      }
    } catch (_) {}
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── Autosave cada 30 segundos ────────────────────────────────────────────
  useEffect(() => {
    if (Object.keys(formData).length === 0) return;
    const interval = setInterval(async () => {
      const snapshot = {
        formData, step, formularioId, codigoPeticion,
        juntaDirectiva, accionistas,
        savedAt: new Date().toISOString(),
      };
      localStorage.setItem('sagrilaft_autosave', JSON.stringify(snapshot));
      if (formularioId) {
        try {
          await api.actualizarFormulario(formularioId, _buildPayload());
        } catch (_) {}
      }
      setLastSaved(new Date());
    }, 30000);
    return () => clearInterval(interval);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [formData, step, formularioId, codigoPeticion, juntaDirectiva, accionistas]);

  // ── Helpers internos ─────────────────────────────────────────────────────

  const _buildPayload = () => ({
    ...formData,
    pagina_actual: step,
    junta_directiva: juntaDirectiva,
    accionistas,
  });

  const _validarCamposPaso = (stepNum) => {
    const camposErr = {};
    for (const field of (CAMPOS_REQUERIDOS[stepNum] || [])) {
      const value = formData[field];
      if (!value || (typeof value === 'string' && !value.trim())) {
        camposErr[field] = `${helpTexts[field]?.titulo || field} es obligatorio`;
      }
    }
    return camposErr;
  };

  // ── Handlers de formulario ───────────────────────────────────────────────

  const handleChange = useCallback((e) => {
    const { name, value, type, checked } = e.target;
    setFormData(prev => ({ ...prev, [name]: type === 'checkbox' ? checked : value }));
    if (errors[name]) setErrors(prev => ({ ...prev, [name]: null }));
  }, [errors]);

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
      localStorage.setItem('sagrilaft_autosave', JSON.stringify({
        formData, step, formularioId, codigoPeticion,
        juntaDirectiva, accionistas,
        savedAt: new Date().toISOString(),
      }));
    } finally {
      setSaving(false);
    }
  };

  // ── Navegación y validación ──────────────────────────────────────────────

  const handleNext = () => {
    const newErrors = _validarCamposPaso(step);
    setErrors(newErrors);
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
    // Valida todos los pasos antes de radicar
    const allErrors = {};
    for (let s = 2; s <= TOTAL_STEPS; s++) {
      Object.assign(allErrors, _validarCamposPaso(s));
    }
    if (!formData.autorizacion_datos) {
      allErrors.autorizacion_datos = 'Debe aceptar la autorización de tratamiento de datos';
    }
    if (!formData.declaracion_origen_fondos) {
      allErrors.declaracion_origen_fondos = 'Debe aceptar la declaración de origen de fondos';
    }
    setErrors(allErrors);

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
      localStorage.removeItem('sagrilaft_autosave');
      setSubmitted(true);
    } catch (err) {
      console.error('Error enviando formulario:', err);
      alert('⚠️ Error al conectar con el servidor. Intente nuevamente.');
    }
    setSaving(false);
  };

  // ── Handlers de tablas ───────────────────────────────────────────────────

  const handleJuntaChange = (index, field, value) => {
    setJuntaDirectiva(prev => {
      const updated = [...prev];
      updated[index] = { ...updated[index], [field]: value };
      return updated;
    });
  };

  const addJuntaMember = () => setJuntaDirectiva(prev => [...prev, {}]);

  const handleAccionistaChange = (index, field, value) => {
    setAccionistas(prev => {
      const updated = [...prev];
      updated[index] = { ...updated[index], [field]: value };
      return updated;
    });
  };

  const addAccionista = () => setAccionistas(prev => [...prev, {}]);

  // ── Interfaz pública del hook ────────────────────────────────────────────

  return {
    // Estado
    step, formData, errors, helpField, setHelpField,
    codigoPeticion, documentos, saving, uploadingDoc,
    juntaDirectiva, accionistas, submitted, lastSaved,
    // Handlers
    handleChange, handleFileChange, handleRemoveFile, handleSaveDraft,
    handleNext, handlePrev, handleStepClick, handleSubmit,
    handleJuntaChange, addJuntaMember, handleAccionistaChange, addAccionista,
  };
}
