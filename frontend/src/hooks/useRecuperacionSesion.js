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

function _normalizarDocumentos(documentosArray) {
  if (!Array.isArray(documentosArray)) return {};
  return documentosArray.reduce((acc, doc) => {
    acc[doc.tipo_documento] = doc;
    return acc;
  }, {});
}

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

  // Credenciales en memoria para autorizar el envío del formulario.
  // Nunca se persisten en localStorage. Se populan tras token resolution o PIN recovery.
  const credencialesRef = useRef(null);

  // ── Restauración de estado ─────────────────────────────────────────────────
  // Declarado antes de los effects para que las closures capturen la referencia
  // estable via ref y siempre usen la versión más reciente del callback.
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

  // Ref para que los effects de inicialización (dependencia []) siempre
  // tengan acceso a la versión más reciente de _restaurarDesdeSnapshot.
  const restaurarRef = useRef(_restaurarDesdeSnapshot);
  useEffect(() => { restaurarRef.current = _restaurarDesdeSnapshot; });

  // ── Resolución de token de diligenciamiento (enlace por correo) ───────────
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const token = params.get('token');
    if (!token) return;

    api.resolverTokenDiligenciamiento(token)
      .then(formulario => {
        credencialesRef.current = { token_diligenciamiento: token };
        window.history.replaceState({}, '', window.location.pathname);
        restaurarRef.current(_adaptarRespuestaServidor(formulario));
      })
      .catch((err) => {
        if (err.code === 'ACCESO_EXPIRADO') {
          setError('El enlace de acceso ha expirado. Ingrese su código de petición y PIN, o solicite un nuevo enlace.');
          setVisible(true);
        }
        // TOKEN_INVALIDO y otros errores: el formulario se muestra vacío sin modal.
      });
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Detección de borrador al montar ────────────────────────────────────────
  useEffect(() => {
    // Si llegamos via token, no hay borrador local relevante que restaurar.
    const params = new URLSearchParams(window.location.search);
    if (params.get('token')) return;

    const borrador = leerBorradorDeStorage();
    if (!borrador) return;

    if (borradorEsFormularioEnviado(borrador)) {
      eliminarBorradorDeStorage();
      return;
    }

    if (!borrador.formularioId && !borrador.codigoPeticion) return;

    setBorradorLocal(borrador);
    setVisible(true);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Recuperar sesión (código de petición + PIN) ────────────────────────────
  const recuperarSesion = useCallback(async (codigoPeticion, pin) => {
    setCargando(true);
    setError(null);

    try {
      const formulario = await api.recuperarSesionPorAcceso(codigoPeticion, pin);
      if (formulario) {
        credencialesRef.current = { codigo_peticion: codigoPeticion, pin };
        const snap = _adaptarRespuestaServidor(formulario);
        _restaurarDesdeSnapshot(snap);
        eliminarBorradorDeStorage();
        setVisible(false);
      }
    } catch (err) {
      if (err.code === 'CREDENCIALES_INVALIDAS') {
        setError('Código de petición o PIN incorrecto. Verifique los datos');
      } else if (err.code === 'FORMULARIO_YA_ENVIADO') {
        setError('Este formulario ya fue enviado y no puede recuperarse.');
      } else if (err.code === 'ACCESO_EXPIRADO') {
        setError('El acceso ha expirado. Solicite un nuevo enlace al área responsable.');
      } else {
        setError('Error al conectar con el servidor. Intente nuevamente.');
      }
    } finally {
      setCargando(false);
    }
  }, [_restaurarDesdeSnapshot]);

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

  // ── Apertura programática con mensaje de error (ej: 401 en submit) ─────────
  const abrirConError = useCallback((mensaje) => {
    setError(mensaje);
    setVisible(true);
  }, []);

  // ── Interfaz pública ───────────────────────────────────────────────────────
  return {
    visible,
    error,
    cargando,
    fechaBorrador:          borradorLocal?.guardadoEn ?? null,
    codigoPeticionBorrador: borradorLocal?.codigoPeticion ?? null,
    abrirModal,
    abrirConError,
    recuperarSesion,
    descartar,
    credencialesRef,
  };
}
