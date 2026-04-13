/**
 * Hook: useRecuperacionSesion
 *
 * Gestiona el flujo de recuperación de sesión identificado por correo + NIT.
 *
 * Estrategia de recuperación por prioridad:
 *   1. Rápida (local)  — verifica las credenciales contra el borrador en
 *                        localStorage. Sin llamada de red, respuesta inmediata.
 *   2. Remota (API)    — cuando no hay borrador local o las credenciales no
 *                        coinciden, consulta el backend para encontrar un
 *                        borrador activo con esas credenciales.
 *
 * Flujos de apertura del modal:
 *   - Automático: al montar detecta un borrador local con sesión previa.
 *   - Manual:     el usuario pulsa "Recuperar sesión" desde el encabezado.
 *
 * SRP: única responsabilidad = detectar, identificar y restaurar sesiones previas.
 * DIP: depende de borradorStorage y api, no de implementaciones de persistencia.
 */

import { useState, useEffect, useCallback } from 'react';
import { api } from '../services/api';
import {
  leerBorradorDeStorage,
  eliminarBorradorDeStorage,
  borradorEsFormularioEnviado,
} from '../utils/borradorStorage';

// Campos del servidor que NO deben copiarse en formData del cliente.
// Son metadatos del formulario o tablas gestionadas como estado separado.
const _CAMPOS_EXCLUIR_DE_FORMDATA = new Set([
  'id', 'codigo_peticion', 'estado', 'pagina_actual', 'created_at', 'updated_at',
  'junta_directiva', 'accionistas', 'beneficiario_final',
  'referencias_comerciales', 'referencias_bancarias', 'informacion_bancaria_pagos',
  'clasificaciones', 'documentos', 'validaciones',
]);

/**
 * Convierte el array de documentos del servidor al mapa por tipo_documento
 * que maneja el estado del cliente.
 */
function _normalizarDocumentos(documentosArray) {
  if (!Array.isArray(documentosArray)) return {};
  return documentosArray.reduce((acc, doc) => {
    acc[doc.tipo_documento] = doc;
    return acc;
  }, {});
}

/**
 * Adapta la respuesta plana del servidor (FormularioConDetalles) al formato
 * de snapshot que esperan los setters del cliente.
 */
function _adaptarRespuestaServidor(formulario) {
  const formData = Object.fromEntries(
    Object.entries(formulario).filter(([k]) => !_CAMPOS_EXCLUIR_DE_FORMDATA.has(k)),
  );

  return {
    formData,
    step:               formulario.pagina_actual ?? 1,
    formularioId:       formulario.id,
    codigoPeticion:     formulario.codigo_peticion,
    juntaDirectiva:     formulario.junta_directiva     ?? [],
    accionistas:        formulario.accionistas          ?? [],
    beneficiarios:      formulario.beneficiario_final   ?? [],
    referenciasComerciales:  formulario.referencias_comerciales    ?? [],
    referenciasBancarias:    formulario.referencias_bancarias       ?? [],
    infoBancariaPagos:       formulario.informacion_bancaria_pagos  ?? [],
    documentos:         _normalizarDocumentos(formulario.documentos),
  };
}

export function useRecuperacionSesion(setters) {
  const {
    setFormData, setStep, setFormularioId, setCodigoPeticion,
    setJuntaDirectiva, setAccionistas, setBeneficiarios,
    setReferenciasComerciales, setReferenciasBancarias,
    setInfoBancariaPagos, setDocumentos,
  } = setters;

  const [visible, setVisible]           = useState(false);
  const [borradorLocal, setBorradorLocal] = useState(null);
  const [error, setError]               = useState(null);
  const [cargando, setCargando]         = useState(false);

  // ── Detección de borrador al montar ────────────────────────────────────────
  useEffect(() => {
    const borrador = leerBorradorDeStorage();
    if (!borrador) return;

    // Un formulario ya enviado no es recuperable; limpiar residuos del storage.
    if (borradorEsFormularioEnviado(borrador)) {
      eliminarBorradorDeStorage();
      return;
    }

    // Solo vale la pena mostrar el modal si existe una sesión en el servidor
    // (hay formularioId). Sin él, no hay nada que recuperar de forma cruzada.
    if (!borrador.formularioId && !borrador.codigoPeticion) return;

    setBorradorLocal(borrador);
    setVisible(true);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Restauración de estado ─────────────────────────────────────────────────
  const _restaurarDesdeSnapshot = useCallback((snap) => {
    setFormData(snap.formData ?? {});
    setStep(snap.step ?? 1);
    setFormularioId(snap.formularioId ?? null);
    setCodigoPeticion(snap.codigoPeticion ?? null);
    setJuntaDirectiva(
      snap.juntaDirectiva?.length > 0
        ? snap.juntaDirectiva
        : [{ cargo: 'Presidente' }, { cargo: 'Gerente General / Rep. Legal' }],
    );
    setAccionistas(snap.accionistas?.length > 0 ? snap.accionistas : [{}]);
    setBeneficiarios(snap.beneficiarios?.length > 0 ? snap.beneficiarios : [{}]);
    setReferenciasComerciales(snap.referenciasComerciales?.length > 0 ? snap.referenciasComerciales : [{}, {}]);
    setReferenciasBancarias(snap.referenciasBancarias?.length > 0 ? snap.referenciasBancarias : [{}, {}]);
    setInfoBancariaPagos(snap.infoBancariaPagos?.length > 0 ? snap.infoBancariaPagos : [{}, {}]);
    setDocumentos(snap.documentos ?? {});
  }, [
    setFormData, setStep, setFormularioId, setCodigoPeticion,
    setJuntaDirectiva, setAccionistas, setBeneficiarios,
    setReferenciasComerciales, setReferenciasBancarias,
    setInfoBancariaPagos, setDocumentos,
  ]);

  // ── Recuperar sesión (correo + NIT) ────────────────────────────────────────
  /**
   * Intenta recuperar la sesión con las credenciales provistas.
   *
   * Prioridad 1: coincidencia con el borrador local (sin llamada de red).
   * Prioridad 2: búsqueda en el servidor si no hay coincidencia local.
   */
  const recuperarSesion = useCallback(async (correo, nit) => {
    setCargando(true);
    setError(null);

    // Estrategia rápida: verificar contra borrador local
    if (borradorLocal) {
      const correoLocal  = (borradorLocal.formData?.correo ?? '').trim().toLowerCase();
      const nitLocal     = (borradorLocal.formData?.numero_identificacion ?? '').trim();
      const dvLocal      = (borradorLocal.formData?.digito_verificacion   ?? '').trim();
      const nitConDvLocal = nitLocal + dvLocal;
      const nitIngresado  = nit.trim();

      // Acepta el NIT con o sin dígito de verificación (campo separado en el formulario)
      if (correo.trim().toLowerCase() === correoLocal &&
          (nitIngresado === nitLocal || nitIngresado === nitConDvLocal)) {
        _restaurarDesdeSnapshot(borradorLocal);
        setVisible(false);
        setCargando(false);
        return;
      }
    }

    // Estrategia remota: consultar el servidor
    // api.recuperarSesion devuelve:
    //   FormularioConDetalles (objeto) → borrador encontrado  [HTTP 200]
    //   null                           → sin borrador activo  [HTTP 404]
    //   lanza excepción                → error de servidor    [HTTP 4xx/5xx o red]
    try {
      const formulario = await api.recuperarSesion(correo.trim(), nit.trim());
      if (formulario) {
        const snap = _adaptarRespuestaServidor(formulario);
        _restaurarDesdeSnapshot(snap);
        eliminarBorradorDeStorage(); // descartar borrador local obsoleto si existía
        setVisible(false);
      } else {
        // 404: credenciales correctas pero sin borrador activo
        setError('No se encontró un formulario activo con esas credenciales.');
      }
    } catch (err) {
      if (err.code === 'FORMULARIO_YA_ENVIADO') {
        setError('Este formulario ya fue enviado y no puede recuperarse.');
      } else {
        // Error real de servidor o de red (500, timeout, etc.)
        setError('Error al conectar con el servidor. Intente nuevamente.');
      }
    } finally {
      setCargando(false);
    }
  }, [borradorLocal, _restaurarDesdeSnapshot]);

  // ── Descartar recuperación (comenzar desde cero) ───────────────────────────
  const descartar = useCallback(() => {
    if (borradorLocal) eliminarBorradorDeStorage();
    setBorradorLocal(null);
    setVisible(false);
    setError(null);
  }, [borradorLocal]);

  // ── Apertura manual del modal (botón en encabezado) ────────────────────────
  const abrirModal = useCallback(() => {
    setError(null);
    setVisible(true);
  }, []);

  // ── Interfaz pública ───────────────────────────────────────────────────────
  return {
    visible,
    error,
    cargando,
    /** Fecha del último guardado del borrador local (para mostrar en el modal). */
    fechaBorrador: borradorLocal?.guardadoEn ?? null,
    abrirModal,
    recuperarSesion,
    descartar,
  };
}
