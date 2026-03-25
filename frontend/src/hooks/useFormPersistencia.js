/**
 * Hook: useFormPersistencia
 *
 * Gestiona persistencia del formulario: autosave periódico en localStorage
 * y restauración de borrador al montar.
 *
 * SRP: única responsabilidad = leer/escribir el estado en localStorage y API.
 */
import { useState, useEffect } from 'react';
import { api } from '../services/api';

const STORAGE_KEY = 'sagrilaft_autosave';
const INTERVALO_AUTOSAVE_MS = 30_000;

export function useFormPersistencia(
  /** Datos actuales del formulario para persistir */
  snapshot,
  /** Setters para restaurar el borrador al montar */
  setters,
  /** Función que construye el payload para la API */
  construirPayload,
) {
  const {
    formData, step, formularioId, codigoPeticion,
    juntaDirectiva, accionistas, beneficiarios,
  } = snapshot;

  const {
    setFormData, setStep, setFormularioId, setCodigoPeticion,
    setJuntaDirectiva, setAccionistas, setBeneficiarios,
  } = setters;

  const [lastSaved, setLastSaved] = useState(null);

  // Restaurar borrador al montar
  useEffect(() => {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return;
    try {
      const borrador = JSON.parse(raw);
      if (!borrador.formularioId && !borrador.codigoPeticion) return;
      const label = borrador.codigoPeticion
        ? `Código: ${borrador.codigoPeticion}`
        : 'un borrador sin código';
      const fecha = borrador.savedAt
        ? ` (guardado: ${new Date(borrador.savedAt).toLocaleString('es-CO')})`
        : '';
      if (window.confirm(`Se encontró ${label}${fecha}.\n¿Desea retomar donde lo dejó?`)) {
        setFormData(borrador.formData || {});
        setStep(borrador.step || 1);
        setFormularioId(borrador.formularioId || null);
        setCodigoPeticion(borrador.codigoPeticion || null);
        setJuntaDirectiva(borrador.juntaDirectiva || [{ cargo: 'Presidente' }, { cargo: 'Gerente General / Rep. Legal' }]);
        setAccionistas(borrador.accionistas || [{}]);
        setBeneficiarios(borrador.beneficiarios || [{}]);
      }
    } catch (_) {}
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Autosave cada 30 segundos
  useEffect(() => {
    if (Object.keys(formData).length === 0) return;
    const interval = setInterval(async () => {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({
        formData, step, formularioId, codigoPeticion,
        juntaDirectiva, accionistas, beneficiarios,
        savedAt: new Date().toISOString(),
      }));
      if (formularioId) {
        try {
          await api.actualizarFormulario(formularioId, construirPayload());
        } catch (_) {}
      }
      setLastSaved(new Date());
    }, INTERVALO_AUTOSAVE_MS);
    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [formData, step, formularioId, codigoPeticion, juntaDirectiva, accionistas, beneficiarios]);

  const limpiarBorrador = () => localStorage.removeItem(STORAGE_KEY);

  const guardarBorradorLocal = () => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({
      formData, step, formularioId, codigoPeticion,
      juntaDirectiva, accionistas, beneficiarios,
      savedAt: new Date().toISOString(),
    }));
  };

  return { lastSaved, limpiarBorrador, guardarBorradorLocal };
}
