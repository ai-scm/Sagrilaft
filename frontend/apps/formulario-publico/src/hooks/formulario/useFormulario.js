/**
 * Hook: useFormulario
 *
 * Orquestador principal del formulario SAGRILAFT.
 * Delega validación, persistencia y tablas a sub-hooks especializados.
 *
 * SRP: única responsabilidad = coordinar los sub-hooks y exponer la interfaz pública.
 * DIP: los pasos dependen de esta interfaz, no de implementaciones concretas.
 */
import { useState, useCallback, useMemo } from 'react';
import { api } from '../../services/api';
import {
  TOTAL_STEPS,
  CAMPOS_REQUERIDOS,
  CAMPOS_CLASIFICACION_TRIBUTARIA_EMPRESA,
  CAMPOS_PERSONA_NATURAL,
  calcularPasosVisibles,
} from '../../data/formularioConfig';
import { useFormValidacion } from './useFormValidacion';
import { useTablasDinamicas, JUNTA_INICIAL } from './useTablasDinamicas';
import { useFormPersistencia } from '../persistencia/useFormPersistencia';
import { useRecuperacionSesion } from '../persistencia/useRecuperacionSesion';
import { useAlertasInconsistencia } from './useAlertasInconsistencia';
import {
  validarTablasPaso4, CLAVES_ERROR_PASO4, purgarFilasVaciasPaso4,
  validarTablasPaso6, CLAVES_ERROR_PASO6, purgarFilasVaciasPaso6,
  validarTablasPaso7, CLAVES_ERROR_PASO7, purgarFilasVaciasPaso7,
} from '../../utils/validacionTablas';
import { sanitizarPayload } from '@shared/utils/normalizadores';
import { VALOR_ACTIVIDAD_OTRA } from '@shared/utils/constantes';
import { obtenerCamposDeDocumento } from '../../data/mapeoDocumentos';
import { calcularValorDv } from '../../utils/inputValidation';

const scrollTop = () => window.scrollTo({ top: 0, behavior: 'smooth' });

const CAMPOS_BOOLEANOS_SI_NO = new Set([
  'realiza_operaciones_moneda_extranjera',
  'autorretenedor',
  'gran_contribuyente',
  'entidad_sin_animo_lucro',
  'retencion_ica',
  'impuesto_ica',
  'entidad_oficial',
  'exento_retencion_fuente',
]);

/** Campos que dependen de la respuesta a 'realiza_operaciones_moneda_extranjera'. */
const CAMPOS_DEPENDIENTES_MONEDA_EXTRANJERA = [
  'paises_operaciones',
  'tipos_transaccion',
  'tipos_transaccion_otros',
];

/**
 * Retorna el nuevo estado del formulario tras cambiar la opción de moneda extranjera.
 * Si el nuevo valor es distinto de true, purga los campos dependientes para evitar
 * que datos residuales contaminen el envío o persistan en el borrador.
 */
function _actualizarMonedaConDependientes(estadoAnterior, nuevoValor) {
  const siguiente = { ...estadoAnterior, realiza_operaciones_moneda_extranjera: nuevoValor };
  if (nuevoValor !== true) {
    siguiente.paises_operaciones      = '';
    siguiente.tipos_transaccion       = [];
    siguiente.tipos_transaccion_otros = '';
  }
  return siguiente;
}

/**
 * Limpia los errores de validación de la pregunta principal y sus campos dependientes.
 * Se invoca siempre que el usuario modifica la selección de moneda extranjera.
 */
function _limpiarErroresDependientesMoneda(limpiarError) {
  limpiarError('realiza_operaciones_moneda_extranjera');
  CAMPOS_DEPENDIENTES_MONEDA_EXTRANJERA.forEach(limpiarError);
}

/**
 * Mapa declarativo: campo "tipo de documento" → campo "número" que lo acompaña.
 * Fuente única de verdad — agregar futuros pares aquí sin tocar handleChange.
 *
 *   Paso 2: tipo_identificacion     → numero_identificacion
 *   Paso 3: tipo_doc_representante  → numero_doc_representante
 */
const CAMPO_NUMERO_POR_TIPO_DOC = {
  tipo_identificacion:    'numero_identificacion',
  tipo_doc_representante: 'numero_doc_representante',
};

/**
 * Aplica el cambio de tipo-documento sobre el estado del formulario:
 *   1. Guarda el nuevo tipo.
 *   2. Limpia el campo número asociado para que el usuario reingrese el valor
 *      en el formato correcto del nuevo tipo.
 *
 * @param {Object} estadoAnterior - formData previo.
 * @param {string} campoTipo      - Nombre del campo selector (ej: 'tipo_identificacion').
 * @param {string} nuevoValor     - Valor seleccionado.
 * @param {string} campoNumero    - Nombre del campo número a limpiar.
 * @returns {Object} Nuevo estado parcial listo para fusionar.
 */
function _aplicarCambioDeTipoDoc(estadoAnterior, campoTipo, nuevoValor, campoNumero) {
  return {
    ...estadoAnterior,
    [campoTipo]:   nuevoValor,
    [campoNumero]: '',
  };
}

function _limpiarCampos(estado, campos) {
  const siguiente = { ...estado };
  for (const campo of campos) {
    siguiente[campo] = '';
  }
  return siguiente;
}

function _aplicarReglasTipoPersona(estadoAnterior, tipoPersona) {
  const siguiente = { ...estadoAnterior, tipo_persona: tipoPersona };
  if (tipoPersona === 'natural') {
    return _limpiarCampos(siguiente, CAMPOS_CLASIFICACION_TRIBUTARIA_EMPRESA);
  }
  if (tipoPersona === 'juridica') {
    return _limpiarCampos(siguiente, CAMPOS_PERSONA_NATURAL);
  }
  return siguiente;
}

function _purgarCamposNoAplicablesPorTipoPersona(datos) {
  if (datos.tipo_persona === 'natural') {
    return _limpiarCampos(datos, CAMPOS_CLASIFICACION_TRIBUTARIA_EMPRESA);
  }
  if (datos.tipo_persona === 'juridica') {
    return _limpiarCampos(datos, CAMPOS_PERSONA_NATURAL);
  }
  return datos;
}

function _limpiarErroresTipoPersona(limpiarError) {
  CAMPOS_CLASIFICACION_TRIBUTARIA_EMPRESA.forEach(limpiarError);
  CAMPOS_PERSONA_NATURAL.forEach(limpiarError);
  limpiarError('tipo_persona');
}

export function useFormulario() {
  const [step, setStep] = useState(1);
  const [formData, setFormData] = useState({});
  const [helpField, setHelpField] = useState(null);
  const [formularioId, setFormularioId] = useState(null);
  const [codigoPeticion, setCodigoPeticion] = useState(null);
  const [estadoFormulario, setEstadoFormulario] = useState(null);
  const [camposACorregir, setCamposACorregir] = useState(null);
  const [documentos, setDocumentos] = useState({});
  const [alertasServidor, setAlertasServidor] = useState([]);
  const [formDataOriginal, setFormDataOriginal] = useState(null);
  const [tablasOriginales, setTablasOriginales] = useState(null);
  const [saving, setSaving] = useState(false);
  const [uploadingDoc, setUploadingDoc] = useState({});
  const [eliminandoDoc, setEliminandoDoc] = useState({});
  const [estadoConfirmacion, setEstadoConfirmacion] = useState({ visible: false, tipoDoc: null });
  const [submitted, setSubmitted] = useState(false);

  const { errors, validarPaso, aplicarErrores, limpiarError } = useFormValidacion(formData);

  const {
    alertasRazonSocial,
    alertasNit,
    alertasNombreRepresentante,
    alertasNumeroDocRepresentante,
    alertasDireccion,
    hayAlertasActivas,
    todasLasAlertasActivas,
  } = useAlertasInconsistencia(documentos, formData, alertasServidor);

  const {
    juntaDirectiva, setJuntaDirectiva,
    handleJuntaChange, handleJuntaTipoIdChange, addJuntaMember, eliminarJuntaMember,
    accionistas, setAccionistas,
    handleAccionistaChange, handleAccionistaTipoIdChange, addAccionista, eliminarAccionista,
    beneficiarios, setBeneficiarios,
    handleBeneficiarioChange, handleBeneficiarioTipoIdChange, addBeneficiario, eliminarBeneficiario,
    referenciasComerciales, setReferenciasComerciales,
    handleReferenciaChange, addReferencia, eliminarReferencia,
    referenciasBancarias, setReferenciasBancarias,
    handleReferenciaBancariaChange, addReferenciaBancaria, eliminarReferenciaBancaria,
    infoBancariaPagos, setInfoBancariaPagos,
    handleInfoBancariaPagosChange, addInfoBancariaPagos, eliminarInfoBancariaPagos,
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
    const paso4 = esPersonaJuridica
      ? purgarFilasVaciasPaso4({ juntaDirectiva, accionistas, beneficiarios })
      : { juntaDirectiva: [], accionistas: [], beneficiarios: [] };
    const paso6 = purgarFilasVaciasPaso6({ referenciasComerciales, referenciasBancarias });
    const paso7 = purgarFilasVaciasPaso7({ infoBancariaPagos });
    const datosAplicables = _purgarCamposNoAplicablesPorTipoPersona(formData);
    return sanitizarPayload({
      ...datosAplicables,
      pagina_actual: step,
      junta_directiva:    paso4.juntaDirectiva,
      accionistas:        paso4.accionistas,
      beneficiario_final: paso4.beneficiarios,
      referencias_comerciales:    paso6.referenciasComerciales,
      referencias_bancarias:      paso6.referenciasBancarias,
      informacion_bancaria_pagos: paso7.infoBancariaPagos,
    });
  };

  // Setters agrupados: los consumen tanto useFormPersistencia como useRecuperacionSesion
  const _setters = {
    setFormData, setStep, setFormularioId, setCodigoPeticion,
    setEstadoFormulario, setCamposACorregir, setFormDataOriginal,
    setTablasOriginales,
    setJuntaDirectiva, setAccionistas, setBeneficiarios,
    setReferenciasComerciales, setReferenciasBancarias,
    setInfoBancariaPagos, setDocumentos, setAlertasServidor,
  };

  const { lastSaved, limpiarBorrador, guardarBorradorLocal } = useFormPersistencia(
    { formData, step, formularioId, codigoPeticion, submitted, saving, juntaDirectiva, accionistas, beneficiarios, referenciasComerciales, referenciasBancarias, infoBancariaPagos, documentos },
    _buildPayload,
  );

  const recuperacion = useRecuperacionSesion(_setters);

  // ── Handlers de formulario ───────────────────────────────────────────────

  const handleChange = useCallback((e) => {
    const { name, value, type, checked } = e.target;
    const nuevoValor = type === 'checkbox'
      ? checked
      : CAMPOS_BOOLEANOS_SI_NO.has(name)
        ? value === 'true'
        : value;
    const campoNumero = CAMPO_NUMERO_POR_TIPO_DOC[name];
    setFormData(prev => {
      // Si el campo modificado es un selector de tipo-documento, limpia
      // atómicamente su campo número asociado dentro del mismo setState.
      if (campoNumero) {
        const siguiente = _aplicarCambioDeTipoDoc(prev, name, nuevoValor, campoNumero);
        // Solo Paso 2 tiene DV; si no aplica, calcularValorDv queda fuera del bloque.
        if (name === 'tipo_identificacion') {
          siguiente.digito_verificacion = calcularValorDv(nuevoValor, prev.digito_verificacion);
        }
        return siguiente;
      }
      if (name === 'tipo_persona') {
        return _aplicarReglasTipoPersona(prev, nuevoValor);
      }
      return { ...prev, [name]: nuevoValor };
    });
    limpiarError(name);
    if (campoNumero) {
      limpiarError(campoNumero);
    }
    if (name === 'tipo_identificacion') {
      limpiarError('digito_verificacion');
    }

    if (name === 'tipo_persona') {
      _limpiarErroresTipoPersona(limpiarError);
      if (nuevoValor === 'natural') {
        setJuntaDirectiva(JUNTA_INICIAL);
        setAccionistas([{}]);
        setBeneficiarios([{}]);
        aplicarErrores(prev => {
          const sinTablasPaso4 = { ...prev };
          for (const clave of CLAVES_ERROR_PASO4) delete sinTablasPaso4[clave];
          return sinTablasPaso4;
        });
      }
    }
  }, [limpiarError, aplicarErrores, setJuntaDirectiva, setAccionistas, setBeneficiarios]);

  /**
   * Cambia '¿Realiza Operaciones en Moneda Extranjera?' y limpia atómicamente
   * todos los campos dependientes cuando la respuesta pasa a ser false o vacío.
   *
   * Centralizar aquí la lógica de cascada garantiza que el formulario nunca
   * persista datos de campos que el usuario ya no ve.
   */
  const handleMonedaExtranjeraChange = useCallback((nuevoValor) => {
    setFormData(prev => _actualizarMonedaConDependientes(prev, nuevoValor));
    _limpiarErroresDependientesMoneda(limpiarError);
  }, [limpiarError]);

  /**
   * Cambia la actividad principal y gestiona la dependencia con 'actividad_especifica'.
   * Si no es VALOR_ACTIVIDAD_OTRA, se fuerza el valor 'NA' para cumplir con la integridad del backend.
   */
  const handleActividadChange = useCallback((e) => {
    const { value } = e.target;
    setFormData(prev => {
      const siguiente = { ...prev, actividad_clasificacion: value };
      if (value === VALOR_ACTIVIDAD_OTRA) {
        siguiente.actividad_especifica = '';
      } else if (value !== '') {
        siguiente.actividad_especifica = 'NA';
      }
      return siguiente;
    });
    limpiarError('actividad_clasificacion');
    if (value !== VALOR_ACTIVIDAD_OTRA) {
      limpiarError('actividad_especifica');
    }
  }, [limpiarError]);

  /**
   * Cambia la moneda de declaración y gestiona la dependencia con 'moneda_declaracion_otra'.
   * Si no es 'OTRA', se fuerza el valor 'NA' para cumplir con la integridad del backend
   * (mismo patrón que handleActividadChange).
   */
  const handleMonedaDeclaracionChange = useCallback((e) => {
    const { value } = e.target;
    setFormData(prev => {
      const siguiente = { ...prev, moneda_declaracion: value };
      if (value === 'OTRA') {
        siguiente.moneda_declaracion_otra = '';
      } else if (value !== '') {
        siguiente.moneda_declaracion_otra = 'NA';
      }
      return siguiente;
    });
    limpiarError('moneda_declaracion');
    if (value !== 'OTRA') {
      limpiarError('moneda_declaracion_otra');
    }
  }, [limpiarError]);

  /**
   * Cambia los tipos de transacción seleccionados y limpia el campo '¿Cuáles?'
   * cuando 'Otras' deja de estar seleccionado.
   */
  const handleTiposTransaccionChange = useCallback((tiposSeleccionados) => {
    setFormData(prev => ({
      ...prev,
      tipos_transaccion: tiposSeleccionados,
      ...(!tiposSeleccionados.includes('otras') && { tipos_transaccion_otros: '' }),
    }));
    limpiarError('tipos_transaccion');
    if (!tiposSeleccionados.includes('otras')) {
      limpiarError('tipos_transaccion_otros');
    }
  }, [limpiarError]);

  const handleFileChange = useCallback(async (tipoDoc, file) => {
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
      if (!docRes.extraccion_exitosa) {
        alert(`El documento se subió correctamente, pero ocurrió un error al analizarlo con IA:\n${docRes.mensaje_extraccion || 'Timeout en el servidor'}\nPor favor, valide e ingrese la información manualmente.`);
      }
    } catch (err) {
      console.error(`Error subiendo ${tipoDoc}:`, err);
      alert('Error al subir el documento. Intente nuevamente.');
    } finally {
      setUploadingDoc(prev => ({ ...prev, [tipoDoc]: false }));
    }
  }, [formularioId]);

  const handleRemoveFile = useCallback((tipoDoc) => {
    setEstadoConfirmacion({ visible: true, tipoDoc });
  }, []);

  const cancelarEliminacion = useCallback(() => {
    setEstadoConfirmacion({ visible: false, tipoDoc: null });
  }, []);

  const _quitarDocumento = (tipo) =>
    setDocumentos(({ [tipo]: _, ...resto }) => resto);

  const confirmarEliminacion = useCallback(async () => {
    const { tipoDoc } = estadoConfirmacion;
    if (!tipoDoc) return;

    const docToDelete = documentos[tipoDoc];
    setEstadoConfirmacion({ visible: false, tipoDoc: null });

    if (!docToDelete) {
      _quitarDocumento(tipoDoc);
      return;
    }

    setEliminandoDoc(prev => ({ ...prev, [tipoDoc]: true }));
    try {
      if (formularioId && docToDelete.id) {
        await api.eliminarDocumento(formularioId, docToDelete.id);
      }

      const camposALimpiar = obtenerCamposDeDocumento(tipoDoc);
      if (camposALimpiar.length > 0) {
        setFormData(prev => {
          const next = { ...prev };
          camposALimpiar.forEach(key => {
            next[key] = "";
          });
          return next;
        });
      }

      _quitarDocumento(tipoDoc);
    } catch (err) {
      console.error(`Error eliminando ${tipoDoc}:`, err);
      alert('Error al intentar eliminar el documento. Intente nuevamente.');
    } finally {
      setEliminandoDoc(prev => ({ ...prev, [tipoDoc]: false }));
    }
  }, [estadoConfirmacion, documentos, formularioId]);

  /**
   * Upsert remoto: crea el formulario si aún no existe en el servidor,
   * o actualiza el existente. Devuelve el ID definitivo en ambos casos.
   * Punto único de verdad para el patrón "crear-o-actualizar" que comparten
   * handleSaveDraft y handleSubmit.
   */
  const _sincronizarConServidor = async () => {
    if (!formularioId) {
      const result = await api.crearFormulario(_buildPayload());
      setFormularioId(result.id);
      setCodigoPeticion(result.codigo_peticion);
      return result.id;
    }
    await api.actualizarFormulario(formularioId, _buildPayload());
    return formularioId;
  };

  const handleSaveDraft = async () => {
    setSaving(true);
    try {
      await _sincronizarConServidor();
      alert('✅ Borrador guardado exitosamente');
    } catch (err) {
      console.error('Error guardando borrador:', err);
      alert('⚠️ Borrador guardado localmente (el servidor no está disponible)');
      guardarBorradorLocal();
    } finally {
      setSaving(false);
    }
  };

  // ── Limpieza genérica de errores de tablas ──────────────────────────────────
  const limpiarClavesError = useCallback((claves) => {
    aplicarErrores(prev => {
      const limpio = { ...prev };
      for (const clave of claves) delete limpio[clave];
      return limpio;
    });
  }, [aplicarErrores]);

  /**
   * HOF: envuelve cualquier handler de tabla para que, tras ejecutarse,
   * limpie automáticamente las claves de error del paso correspondiente.
   * Reemplaza 15 useCallback idénticos en estructura: fn(...args) + limpiarClavesError(claves).
   */
  const conLimpieza = useCallback(
    (fn, claves) => (...args) => { fn(...args); limpiarClavesError(claves); },
    [limpiarClavesError],
  );

  // ── Handlers de tablas con limpieza de errores ──────────────────────────────
  const onJuntaChange              = useMemo(() => conLimpieza(handleJuntaChange,              CLAVES_ERROR_PASO4), [conLimpieza, handleJuntaChange]);
  const onJuntaTipoIdChange        = useMemo(() => conLimpieza(handleJuntaTipoIdChange,        CLAVES_ERROR_PASO4), [conLimpieza, handleJuntaTipoIdChange]);
  const onAccionistaChange         = useMemo(() => conLimpieza(handleAccionistaChange,         CLAVES_ERROR_PASO4), [conLimpieza, handleAccionistaChange]);
  const onAccionistaTipoIdChange   = useMemo(() => conLimpieza(handleAccionistaTipoIdChange,   CLAVES_ERROR_PASO4), [conLimpieza, handleAccionistaTipoIdChange]);
  const onBeneficiarioChange       = useMemo(() => conLimpieza(handleBeneficiarioChange,       CLAVES_ERROR_PASO4), [conLimpieza, handleBeneficiarioChange]);
  const onBeneficiarioTipoIdChange = useMemo(() => conLimpieza(handleBeneficiarioTipoIdChange, CLAVES_ERROR_PASO4), [conLimpieza, handleBeneficiarioTipoIdChange]);
  const onEliminarJuntaMember      = useMemo(() => conLimpieza(eliminarJuntaMember,            CLAVES_ERROR_PASO4), [conLimpieza, eliminarJuntaMember]);
  const onEliminarAccionista       = useMemo(() => conLimpieza(eliminarAccionista,             CLAVES_ERROR_PASO4), [conLimpieza, eliminarAccionista]);
  const onEliminarBeneficiario     = useMemo(() => conLimpieza(eliminarBeneficiario,           CLAVES_ERROR_PASO4), [conLimpieza, eliminarBeneficiario]);
  const onReferenciaChange         = useMemo(() => conLimpieza(handleReferenciaChange,         CLAVES_ERROR_PASO6), [conLimpieza, handleReferenciaChange]);
  const onReferenciaBancariaChange = useMemo(() => conLimpieza(handleReferenciaBancariaChange, CLAVES_ERROR_PASO6), [conLimpieza, handleReferenciaBancariaChange]);
  const onEliminarReferencia       = useMemo(() => conLimpieza(eliminarReferencia,             CLAVES_ERROR_PASO6), [conLimpieza, eliminarReferencia]);
  const onEliminarReferenciaBancaria = useMemo(() => conLimpieza(eliminarReferenciaBancaria,   CLAVES_ERROR_PASO6), [conLimpieza, eliminarReferenciaBancaria]);
  const onInfoBancariaPagosChange  = useMemo(() => conLimpieza(handleInfoBancariaPagosChange,  CLAVES_ERROR_PASO7), [conLimpieza, handleInfoBancariaPagosChange]);
  const onEliminarInfoBancariaPagos = useMemo(() => conLimpieza(eliminarInfoBancariaPagos,     CLAVES_ERROR_PASO7), [conLimpieza, eliminarInfoBancariaPagos]);

  // ── Navegación ───────────────────────────────────────────────────────────

  const handleNext = () => {
    const newErrors = validarPaso(step);

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
      if (step === 4) {
        const purged = purgarFilasVaciasPaso4({ juntaDirectiva, accionistas, beneficiarios });
        setJuntaDirectiva(purged.juntaDirectiva);
        setAccionistas(purged.accionistas);
        setBeneficiarios(purged.beneficiarios);
      }
      else if (step === 6) {
        const purged = purgarFilasVaciasPaso6({ referenciasComerciales, referenciasBancarias });
        setReferenciasComerciales(purged.referenciasComerciales);
        setReferenciasBancarias(purged.referenciasBancarias);
      }
      else if (step === 7) {
        const purged = purgarFilasVaciasPaso7({ infoBancariaPagos });
        setInfoBancariaPagos(purged.infoBancariaPagos);
      }
      const visibles = calcularPasosVisibles(formData);
      const siguientePaso = visibles.find(p => p > step) ?? step;
      setStep(siguientePaso);
      scrollTop();
    }
  };

  const handlePrev = () => {
    const visibles = calcularPasosVisibles(formData);
    const anteriorPaso = [...visibles].reverse().find(p => p < step) ?? step;
    setStep(anteriorPaso);
    scrollTop();
  };

  const handleStepClick = useCallback((stepNum) => {
    const visibles = calcularPasosVisibles(formData);
    if (stepNum < step && visibles.includes(stepNum)) {
      setStep(stepNum);
      scrollTop();
    }
  }, [formData, step]);

  // Navegación incondicional usada exclusivamente por el flujo de corrección.
  // No aplica la restricción de "solo hacia atrás" de handleStepClick porque
  // la contraparte debe poder saltar directamente al paso con campos marcados
  // independientemente de dónde guardó el formulario por última vez.
  const irAPasoCorreccion = useCallback((stepNum) => {
    setStep(stepNum);
    scrollTop();
  }, []);

  // ── Helpers de envío final ──────────────────────────────────────────────────

  /**
   * Recolecta todos los errores de validación para el envío final.
   * Función pura: solo consulta estado, sin efectos secundarios.
   */
  const _recopilarErroresEnvio = () => {
    const errores = {};
    for (let s = 2; s <= TOTAL_STEPS; s++) {
      Object.assign(errores, validarPaso(s));
    }
    Object.assign(errores, validarTablasPaso4({
      juntaDirectiva, accionistas, beneficiarios,
      tipoPersona: formData.tipo_persona,
    }));
    Object.assign(errores, validarTablasPaso6({ referenciasComerciales, referenciasBancarias }));
    Object.assign(errores, validarTablasPaso7({ infoBancariaPagos }));
    if (!formData.autorizacion_datos) {
      errores.autorizacion_datos = 'Debe aceptar la autorización de tratamiento de datos';
    }
    if (!formData.declaracion_origen_fondos) {
      errores.declaracion_origen_fondos = 'Debe aceptar la declaración de origen de fondos';
    }
    return errores;
  };

  /**
   * Navega al primer paso que contiene errores tras un intento de envío fallido.
   * Centralizar aquí la búsqueda evita que handleSubmit conozca la estructura
   * interna de qué claves corresponden a cada paso.
   */
  const _navegarAlPrimerPasoConError = (errores) => {
    const tieneErroresPaso4 = CLAVES_ERROR_PASO4.some(k => errores[k]);
    const tieneErroresPaso6 = CLAVES_ERROR_PASO6.some(k => errores[k]);
    const tieneErroresPaso7 = CLAVES_ERROR_PASO7.some(k => errores[k]);
    const primerPaso = [2, 3, 4, 5, 6, 7, 8].find(s => {
      if (s === 4) return tieneErroresPaso4;
      if (s === 6) return tieneErroresPaso6 || (CAMPOS_REQUERIDOS[6] || []).some(f => errores[f]);
      if (s === 7) return tieneErroresPaso7;
      return (CAMPOS_REQUERIDOS[s] || []).some(f => errores[f]) ||
        (s === 8 && (errores.autorizacion_datos || errores.declaracion_origen_fondos));
    });
    if (primerPaso) {
      setStep(primerPaso);
      scrollTop();
    }
  };

  const handleSubmit = async () => {
    const errores = _recopilarErroresEnvio();
    aplicarErrores(errores);

    if (Object.keys(errores).length > 0) {
      _navegarAlPrimerPasoConError(errores);
      return;
    }

    setSaving(true);
    try {
      const credenciales = recuperacion.credencialesRef?.current ?? null;
      const id = await _sincronizarConServidor();
      await api.enviarFormulario(id, credenciales, todasLasAlertasActivas);
      limpiarBorrador();
      setSubmitted(true);
    } catch (err) {
      console.error('Error enviando formulario:', err);
      if (err.status === 401) {
        // Credenciales ausentes o incorrectas: re-abrir modal con código pre-llenado.
        recuperacion.abrirConError('Su sesión ha expirado. Ingrese su PIN para continuar.');
      } else if (err.status === 410) {
        // El AccesoManual venció: el usuario debe solicitar un nuevo enlace al área interna.
        alert('⚠️ El acceso ha expirado. Solicite un nuevo enlace al área responsable.');
      } else {
        // err.message contiene los mensajes del backend cuando valido === false
        // (ver api.js:enviarFormulario). Solo usar el texto genérico para
        // errores reales de red donde no hay mensaje estructurado.
        const mensaje = err?.message && err.message !== 'Failed to fetch'
          ? `⚠️ El formulario no pudo enviarse:\n\n${err.message}`
          : '⚠️ Error al conectar con el servidor. Intente nuevamente.';
        alert(mensaje);
      }
    }
    setSaving(false);
  };

  // ── Interfaz pública del hook ────────────────────────────────────────────

  return {
    step, formData, errors, helpField, setHelpField,
    pasosVisibles: calcularPasosVisibles(formData),
    recuperacion,
    codigoPeticion, estadoFormulario, camposACorregir, formDataOriginal, tablasOriginales, documentos, saving, uploadingDoc, eliminandoDoc,
    estadoConfirmacion, confirmarEliminacion, cancelarEliminacion,
    juntaDirectiva, accionistas, beneficiarios, submitted, lastSaved,
    referenciasComerciales, handleReferenciaChange: onReferenciaChange, addReferencia, eliminarReferencia: onEliminarReferencia,
    referenciasBancarias, handleReferenciaBancariaChange: onReferenciaBancariaChange, addReferenciaBancaria, eliminarReferenciaBancaria: onEliminarReferenciaBancaria,
    infoBancariaPagos, handleInfoBancariaPagosChange: onInfoBancariaPagosChange, addInfoBancariaPagos, eliminarInfoBancariaPagos: onEliminarInfoBancariaPagos,
    handleChange, handleMonedaExtranjeraChange, handleActividadChange, handleTiposTransaccionChange,
    handleMonedaDeclaracionChange,
    handleFileChange, handleRemoveFile, handleSaveDraft,
    handleNext, handlePrev, handleStepClick, irAPasoCorreccion, handleSubmit,
    handleJuntaChange: onJuntaChange, handleJuntaTipoIdChange: onJuntaTipoIdChange, addJuntaMember, eliminarJuntaMember: onEliminarJuntaMember,
    handleAccionistaChange: onAccionistaChange, handleAccionistaTipoIdChange: onAccionistaTipoIdChange, addAccionista, eliminarAccionista: onEliminarAccionista,
    handleBeneficiarioChange: onBeneficiarioChange, handleBeneficiarioTipoIdChange: onBeneficiarioTipoIdChange, addBeneficiario, eliminarBeneficiario: onEliminarBeneficiario,
    alertasRazonSocial,
    alertasNit,
    alertasNombreRepresentante,
    alertasNumeroDocRepresentante,
    alertasDireccion,
    hayAlertasActivas,
    todasLasAlertasActivas,
  };
}
