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
  'campos_a_corregir',
  'junta_directiva', 'accionistas', 'beneficiario_final',
  'referencias_comerciales', 'referencias_bancarias', 'informacion_bancaria_pagos',
  'clasificaciones', 'documentos', 'validaciones',
]);

const ERRORES_RECUPERACION = {
  CREDENCIALES_INVALIDAS: 'Código de petición o PIN incorrecto. Verifique los datos',
  FORMULARIO_YA_ENVIADO:  'Este formulario ya fue enviado y no puede recuperarse.',
  ACCESO_EXPIRADO:        'El acceso ha expirado. Solicite un nuevo enlace al área responsable.',
};

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
    step:                formulario.pagina_actual ?? 1,
    formularioId:        formulario.id,
    codigoPeticion:      formulario.codigo_peticion,
    estadoFormulario:    formulario.estado ?? null,
    camposACorregir:     formulario.campos_a_corregir ?? null,
    juntaDirectiva:      formulario.junta_directiva     ?? [],
    accionistas:         formulario.accionistas          ?? [],
    beneficiarios:       formulario.beneficiario_final   ?? [],
    referenciasComerciales:  formulario.referencias_comerciales    ?? [],
    referenciasBancarias:    formulario.referencias_bancarias       ?? [],
    infoBancariaPagos:       formulario.informacion_bancaria_pagos  ?? [],
    documentos:          _normalizarDocumentos(formulario.documentos),
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
  const _restaurarDesdeSnapshot = useCallback((snapshot_recuperar_sesion) => {
    setFormData(snapshot_recuperar_sesion.formData ?? {});
    setStep(snapshot_recuperar_sesion.step ?? 1);
    setFormularioId(snapshot_recuperar_sesion.formularioId ?? null);
    setCodigoPeticion(snapshot_recuperar_sesion.codigoPeticion ?? null);
    setEstadoFormulario(snapshot_recuperar_sesion.estadoFormulario ?? null);
    setCamposACorregir(snapshot_recuperar_sesion.camposACorregir ?? null);
    if (snapshot_recuperar_sesion.estadoFormulario === 'en_correccion') {
      setFormDataOriginal(snapshot_recuperar_sesion.formData ?? {});
      // Guarda snapshot de tablas para detectar modificaciones durante la corrección
      setTablasOriginales({
        juntaDirectiva:         snapshot_recuperar_sesion.juntaDirectiva          ?? [],
        accionistas:            snapshot_recuperar_sesion.accionistas              ?? [],
        beneficiarios:          snapshot_recuperar_sesion.beneficiarios            ?? [],
        referenciasComerciales: snapshot_recuperar_sesion.referenciasComerciales  ?? [],
        referenciasBancarias:   snapshot_recuperar_sesion.referenciasBancarias    ?? [],
        infoBancariaPagos:      snapshot_recuperar_sesion.infoBancariaPagos        ?? [],
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

  // Ref para que los effects de inicialización (dependencia []) siempre
  // tengan acceso a la versión más reciente de _restaurarDesdeSnapshot.
  const restaurarDesdeSnapshotRef = useRef(_restaurarDesdeSnapshot);
  useEffect(() => { restaurarDesdeSnapshotRef.current = _restaurarDesdeSnapshot; });

  // ── Resolución de token de diligenciamiento (enlace por correo) ───────────
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const token = params.get('token');
    if (!token) return;

    api.resolverTokenDiligenciamiento(token)
      .then(formulario => {
        credencialesRef.current = { token_diligenciamiento: token };
        window.history.replaceState({}, '', window.location.pathname);
        restaurarDesdeSnapshotRef.current(_adaptarRespuestaServidor(formulario));
      })
      .catch((errorToken) => {
        if (errorToken.code === 'ACCESO_EXPIRADO') {
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
    } catch (errorRecuperacion) {
      setError(ERRORES_RECUPERACION[errorRecuperacion.code] ?? 'Error al conectar con el servidor. Intente nuevamente.');
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
