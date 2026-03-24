import { useState, useCallback, useEffect } from 'react';
import HelpPanel, { HelpIcon } from './HelpPanel';
import ProgressBar from './ProgressBar';
import { api } from '../services/api';
import helpTexts from '../data/helpTexts';

const TOTAL_STEPS = 7;

/**
 * Campo de formulario con tooltip de ayuda integrado.
 */
function FormField({
  label, name, type = 'text', required = false,
  value, onChange, onOpenHelp, placeholder,
  error, options, children,
  className = '', ...rest
}) {
  const helpKey = name;
  const hasHelp = !!helpTexts[helpKey];
  const placeholderText = placeholder || (helpTexts[helpKey]?.ejemplo ? `Ej: ${helpTexts[helpKey].ejemplo}` : '');

  const fieldClasses = [
    type === 'textarea' ? 'form-textarea' : (type === 'select' ? 'form-select' : 'form-input'),
    error ? 'error' : '',
    value && !error ? 'valid' : '',
  ].filter(Boolean).join(' ');

  return (
    <div className={`form-group ${className}`}>
      <label className="form-label">
        {label}
        {required && <span className="required-mark">*</span>}
        {hasHelp && <HelpIcon fieldKey={helpKey} onOpenHelp={onOpenHelp} />}
      </label>

      {type === 'select' ? (
        <select
          name={name}
          className={fieldClasses}
          value={value || ''}
          onChange={onChange}
          {...rest}
        >
          <option value="">Seleccione...</option>
          {options?.map(opt => (
            <option key={opt.value} value={opt.value}>{opt.label}</option>
          ))}
        </select>
      ) : type === 'textarea' ? (
        <textarea
          name={name}
          className={fieldClasses}
          value={value || ''}
          onChange={onChange}
          placeholder={placeholderText}
          rows={3}
          {...rest}
        />
      ) : (
        <input
          type={type}
          name={name}
          className={fieldClasses}
          value={value || ''}
          onChange={onChange}
          placeholder={placeholderText}
          {...rest}
        />
      )}

      {error && <div className="field-error">{error}</div>}
      {children}
    </div>
  );
}

/**
 * Componente principal: Formulario SAGRILAFT multipágina.
 */
export default function FormularioSagrilaft() {
  const [step, setStep] = useState(1);
  const [formData, setFormData] = useState({});
  const [errors, setErrors] = useState({});
  const [helpField, setHelpField] = useState(null);
  const [formularioId, setFormularioId] = useState(null);
  const [codigoPeticion, setCodigoPeticion] = useState(null);
  const [documentos, setDocumentos] = useState({});
  const [saving, setSaving] = useState(false);
  const [uploadingDoc, setUploadingDoc] = useState({});
  const [juntaDirectiva, setJuntaDirectiva] = useState([{ cargo: 'Presidente' }, { cargo: 'Gerente General / Rep. Legal' }]);
  const [accionistas, setAccionistas] = useState([{}]);
  const [submitted, setSubmitted] = useState(false);
  const [lastSaved, setLastSaved] = useState(null);

  // ── Restaurar borrador al cargar ──────────────────────────────
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
        setJuntaDirectiva(draft.juntaDirectiva || [{ cargo: 'Presidente' }, { cargo: 'Gerente General / Rep. Legal' }]);
        setAccionistas(draft.accionistas || [{}]);
      }
    } catch (_) {}
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── Autosave cada 30 segundos ─────────────────────────────────
  useEffect(() => {
    if (Object.keys(formData).length === 0) return;
    const interval = setInterval(async () => {
      const snapshot = {
        formData, step, formularioId, codigoPeticion, juntaDirectiva, accionistas,
        savedAt: new Date().toISOString(),
      };
      localStorage.setItem('sagrilaft_autosave', JSON.stringify(snapshot));
      if (formularioId) {
        try {
          await api.actualizarFormulario(formularioId, {
            ...formData,
            pagina_actual: step,
            junta_directiva: juntaDirectiva,
            accionistas,
          });
        } catch (_) {}
      }
      setLastSaved(new Date());
    }, 30000);
    return () => clearInterval(interval);
  }, [formData, step, formularioId, codigoPeticion, juntaDirectiva, accionistas]);

  const handleChange = useCallback((e) => {
    const { name, value, type, checked } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value
    }));
    // Clear error on change
    if (errors[name]) {
      setErrors(prev => ({ ...prev, [name]: null }));
    }
  }, [errors]);

  /**
   * Upload inmediato al seleccionar archivo.
   * Crea el formulario en backend si aún no existe, sube el archivo
   * y aplica los campos_sugeridos devueltos por Bedrock — una sola
   * invocación por documento, sin batch.
   */
  const handleFileChange = async (tipoDoc, file) => {
    if (!file) return;

    setUploadingDoc(prev => ({ ...prev, [tipoDoc]: true }));
    try {
      // Asegurar que el formulario exista en el servidor
      let currentId = formularioId;
      let currentCodigo = codigoPeticion;
      if (!currentId) {
        const result = await api.crearFormulario({ pagina_actual: 1 });
        currentId = result.id;
        currentCodigo = result.codigo_peticion;
        setFormularioId(currentId);
        setCodigoPeticion(currentCodigo);
      }

      // Subir archivo — backend extrae con Bedrock solo este tipo_documento
      const docRes = await api.subirDocumento(currentId, tipoDoc, file);

      // Guardar referencia del documento (objeto servidor, no File)
      setDocumentos(prev => ({ ...prev, [tipoDoc]: docRes }));

      // Aplicar campos sugeridos extraídos por IA inmediatamente
      if (docRes.campos_sugeridos && Object.keys(docRes.campos_sugeridos).length > 0) {
        setFormData(prev => ({ ...prev, ...docRes.campos_sugeridos }));
      }
    } catch (err) {
      console.error(`Error subiendo ${tipoDoc}:`, err);
      alert(`Error al subir el documento. Intente nuevamente.`);
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
        const result = await api.crearFormulario({
          ...formData,
          pagina_actual: step,
          junta_directiva: juntaDirectiva,
          accionistas,
        });
        setFormularioId(result.id);
        setCodigoPeticion(result.codigo_peticion);
      } else {
        await api.actualizarFormulario(formularioId, {
          ...formData,
          pagina_actual: step,
          junta_directiva: juntaDirectiva,
          accionistas,
        });
      }
      alert('✅ Borrador guardado exitosamente');
    } catch (err) {
      console.error('Error guardando borrador:', err);
      alert('⚠️ Borrador guardado localmente (el servidor no está disponible)');
      localStorage.setItem('sagrilaft_autosave', JSON.stringify({
        formData, step, formularioId, codigoPeticion, juntaDirectiva, accionistas,
        savedAt: new Date().toISOString(),
      }));
    } finally {
      setSaving(false);
    }
  };


  const validateStep = (stepNum) => {
    const newErrors = {};
    const required = getRequiredFields(stepNum);

    for (const field of required) {
      const value = formData[field];
      if (!value || (typeof value === 'string' && !value.trim())) {
        const help = helpTexts[field];
        newErrors[field] = `${help?.titulo || field} es obligatorio`;
      }
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const getRequiredFields = (stepNum) => {
    switch (stepNum) {
      case 1: return [];
      case 2: return ['tipo_contraparte', 'tipo_persona', 'tipo_solicitud', 'razon_social', 'tipo_identificacion', 'numero_identificacion', 'direccion', 'departamento', 'ciudad', 'telefono', 'correo'];
      case 3: return ['nombre_representante', 'tipo_doc_representante', 'numero_doc_representante', 'fecha_expedicion', 'ciudad_expedicion', 'nacionalidad', 'fecha_nacimiento', 'ciudad_nacimiento', 'profesion', 'correo_representante', 'telefono_representante', 'direccion_funciones', 'ciudad_funciones'];
      case 4: return [];
      case 5: return ['actividad_economica', 'codigo_ciiu', 'ingresos_mensuales', 'egresos_mensuales', 'total_activos', 'total_pasivos', 'patrimonio'];
      case 6: return ['contacto_ordenes_nombre', 'contacto_ordenes_cargo', 'contacto_ordenes_telefono', 'contacto_ordenes_correo', 'contacto_pagos_nombre', 'contacto_pagos_cargo', 'contacto_pagos_telefono', 'contacto_pagos_correo', 'entidad_bancaria', 'ciudad_banco', 'tipo_cuenta', 'numero_cuenta'];
      case 7: return ['origen_fondos', 'nombre_firma', 'fecha_firma', 'ciudad_firma'];
      default: return [];
    }
  };

  // Valida TODOS los pasos antes del envío final.
  // Retorna true si todo está completo; si no, marca errores y navega al primer paso con falla.
  const validateAllSteps = () => {
    const allErrors = {};

    for (let s = 2; s <= TOTAL_STEPS; s++) {
      for (const field of getRequiredFields(s)) {
        const value = formData[field];
        if (value === undefined || value === null || (typeof value === 'string' && !value.trim())) {
          const help = helpTexts[field];
          allErrors[field] = `${help?.titulo || field} es obligatorio`;
        }
      }
    }

    if (!formData.autorizacion_datos) {
      allErrors.autorizacion_datos = 'Debe aceptar la autorización de tratamiento de datos';
    }
    if (!formData.declaracion_origen_fondos) {
      allErrors.declaracion_origen_fondos = 'Debe aceptar la declaración de origen de fondos';
    }

    setErrors(allErrors);

    if (Object.keys(allErrors).length > 0) {
      // Navegar al primer paso que tenga errores
      const stepOrder = [2, 3, 5, 6, 7];
      const firstFailStep = stepOrder.find(s =>
        getRequiredFields(s).some(f => allErrors[f]) ||
        (s === 7 && (allErrors.autorizacion_datos || allErrors.declaracion_origen_fondos))
      );
      if (firstFailStep) {
        setStep(firstFailStep);
        window.scrollTo({ top: 0, behavior: 'smooth' });
      }
      return false;
    }
    return true;
  };

  const handleNext = () => {
    if (validateStep(step)) {
      setStep(prev => Math.min(prev + 1, TOTAL_STEPS));
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }
  };

  const handlePrev = () => {
    setStep(prev => Math.max(prev - 1, 1));
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const handleStepClick = (stepNum) => {
    // Allow navigating to previous steps freely
    if (stepNum < step) {
      setStep(stepNum);
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }
  };

  const handleSubmit = async () => {
    // Validación completa de todos los pasos antes de radicar
    if (!validateAllSteps()) return;

    setSaving(true);
    try {
      // Los documentos ya están subidos (event-driven en handleFileChange).
      // Solo guardamos los datos del formulario y llamamos enviar.
      if (!formularioId) {
        const result = await api.crearFormulario({
          ...formData,
          pagina_actual: step,
          junta_directiva: juntaDirectiva,
          accionistas,
        });
        setFormularioId(result.id);
        setCodigoPeticion(result.codigo_peticion);
        await api.enviarFormulario(result.id);
      } else {
        await api.actualizarFormulario(formularioId, {
          ...formData,
          pagina_actual: step,
          junta_directiva: juntaDirectiva,
          accionistas,
        });
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

  // Junta Directiva table handlers
  const handleJuntaChange = (index, field, value) => {
    setJuntaDirectiva(prev => {
      const updated = [...prev];
      updated[index] = { ...updated[index], [field]: value };
      return updated;
    });
  };

  const addJuntaMember = () => {
    setJuntaDirectiva(prev => [...prev, {}]);
  };

  // Accionistas table handlers
  const handleAccionistaChange = (index, field, value) => {
    setAccionistas(prev => {
      const updated = [...prev];
      updated[index] = { ...updated[index], [field]: value };
      return updated;
    });
  };

  const addAccionista = () => {
    setAccionistas(prev => [...prev, {}]);
  };

  // ============ RENDER ============

  if (submitted) {
    return (
      <div className="app-container">
        <header className="app-header">
          <h1>FORMULARIO DE VINCULACIÓN DE CONTRAPARTE</h1>
          <p className="subtitle">SAGRILAFT - Sistema de Autocontrol de Riesgo de LA/FT</p>
          {codigoPeticion && (
            <div className="codigo-peticion">Código: {codigoPeticion}</div>
          )}
        </header>
        <main className="main-content">
          <div className="form-card" style={{ textAlign: 'center', padding: '60px 40px' }}>
            <div style={{ fontSize: '3rem', marginBottom: '16px' }}>✅</div>
            <h2 style={{ color: 'var(--gray-900)', marginBottom: '12px' }}>¡Formulario Enviado!</h2>
            <p style={{ color: 'var(--gray-500)', fontSize: '0.95rem', maxWidth: '500px', margin: '0 auto' }}>
              Su formulario ha sido recibido exitosamente. Se realizarán las validaciones correspondientes
              y será notificado del resultado.
            </p>
            {codigoPeticion && (
              <div style={{
                marginTop: '24px',
                padding: '16px 24px',
                background: 'var(--primary-50)',
                borderRadius: 'var(--radius-md)',
                display: 'inline-block'
              }}>
                <span style={{ fontSize: '0.82rem', color: 'var(--gray-500)' }}>Código de seguimiento</span>
                <div style={{ fontSize: '1.3rem', fontWeight: '700', color: 'var(--primary-700)', marginTop: '4px' }}>
                  {codigoPeticion}
                </div>
              </div>
            )}
          </div>
        </main>
      </div>
    );
  }

  return (
    <div className="app-container">
      <header className="app-header">
        <h1>FORMULARIO DE VINCULACIÓN O ACTUALIZACIÓN DE CONTRAPARTE</h1>
        <p className="subtitle">SAGRILAFT - Sistema de Autocontrol de Riesgo de LA/FT</p>
        {codigoPeticion && (
          <div className="codigo-peticion">Código: {codigoPeticion}</div>
        )}
      </header>

      <main className="main-content">
        <ProgressBar
          currentStep={step}
          totalSteps={TOTAL_STEPS}
          onStepClick={handleStepClick}
        />

        {/* === STEP 1: DOCUMENTOS === */}
        {step === 1 && (
          <div className="form-card">
            <h2 className="section-title">📄 Documentos Adjuntos</h2>
            <p className="section-subtitle">
              Al adjuntar cada documento el sistema extrae y pre-llena los campos automáticamente.
            </p>

            <div className="info-box">
              <p>💡 Cada documento se analiza con IA en el momento de carga. Los campos del formulario se completan solos.</p>
            </div>

            {formData.tipo_persona !== 'natural' && (
              <>
                <FileUploadField
                  label="Cédula del Representante Legal"
                  tipoDoc="cedula_representante"
                  documentos={documentos}
                  onFileChange={handleFileChange}
                  onRemove={handleRemoveFile}
                  onOpenHelp={setHelpField}
                  accepted=".pdf,.jpg,.jpeg,.png"
                  uploading={uploadingDoc['cedula_representante']}
                />
                <FileUploadField
                  label="Certificado de Existencia y Representación Legal"
                  tipoDoc="certificado_existencia"
                  documentos={documentos}
                  onFileChange={handleFileChange}
                  onRemove={handleRemoveFile}
                  onOpenHelp={setHelpField}
                  accepted=".pdf"
                  hint="No mayor a 30 días"
                  uploading={uploadingDoc['certificado_existencia']}
                />
                <FileUploadField
                  label="Estados Financieros"
                  tipoDoc="estados_financieros"
                  documentos={documentos}
                  onFileChange={handleFileChange}
                  onRemove={handleRemoveFile}
                  onOpenHelp={setHelpField}
                  accepted=".pdf"
                  uploading={uploadingDoc['estados_financieros']}
                />
                <FileUploadField
                  label="Declaración de Renta"
                  tipoDoc="declaracion_renta"
                  documentos={documentos}
                  onFileChange={handleFileChange}
                  onRemove={handleRemoveFile}
                  onOpenHelp={setHelpField}
                  accepted=".pdf"
                />
              </>
            )}

            <FileUploadField
              label="RUT (Registro Único Tributario)"
              tipoDoc="rut"
              documentos={documentos}
              onFileChange={handleFileChange}
              onRemove={handleRemoveFile}
              onOpenHelp={setHelpField}
              accepted=".pdf"
              hint="Debe ser del año en curso"
              uploading={uploadingDoc['rut']}
            />

            <FileUploadField
              label="Referencias Bancarias"
              tipoDoc="referencias_bancarias"
              documentos={documentos}
              onFileChange={handleFileChange}
              onRemove={handleRemoveFile}
              onOpenHelp={setHelpField}
              accepted=".pdf"
              uploading={uploadingDoc['referencias_bancarias']}
            />
          </div>
        )}

        {/* === STEP 2: CLASIFICACIÓN + INFO BÁSICA === */}
        {step === 2 && (
          <div className="form-card">
            <h2 className="section-title">🏢 Clasificación e Información Básica</h2>
            <p className="section-subtitle">Datos generales de la empresa o persona natural</p>

            <div className="form-row">
              <FormField
                label="Tipo de Contraparte" name="tipo_contraparte" type="select" required
                value={formData.tipo_contraparte} onChange={handleChange}
                onOpenHelp={setHelpField} error={errors.tipo_contraparte}
                options={[
                  { value: 'proveedor', label: 'Proveedor' },
                  { value: 'cliente', label: 'Cliente' },
                ]}
              />
              <FormField
                label="Tipo de Persona" name="tipo_persona" type="select" required
                value={formData.tipo_persona} onChange={handleChange}
                onOpenHelp={setHelpField} error={errors.tipo_persona}
                options={[
                  { value: 'juridica', label: 'Persona Jurídica' },
                  { value: 'natural', label: 'Persona Natural' },
                ]}
              />
              <FormField
                label="Tipo de Solicitud" name="tipo_solicitud" type="select" required
                value={formData.tipo_solicitud} onChange={handleChange}
                onOpenHelp={setHelpField} error={errors.tipo_solicitud}
                options={[
                  { value: 'vinculacion', label: 'Vinculación' },
                  { value: 'actualizacion', label: 'Actualización' },
                ]}
              />
            </div>

            <hr style={{ border: 'none', borderTop: '1px solid var(--gray-200)', margin: '24px 0' }} />

            <div className="form-row single">
              <FormField
                label="Nombre o Razón Social" name="razon_social" required
                value={formData.razon_social} onChange={handleChange}
                onOpenHelp={setHelpField} error={errors.razon_social}
              />
            </div>

            <div className="form-row">
              <FormField
                label="Tipo de Identificación" name="tipo_identificacion" type="select" required
                value={formData.tipo_identificacion} onChange={handleChange}
                onOpenHelp={setHelpField} error={errors.tipo_identificacion}
                options={[
                  { value: 'NIT', label: 'NIT' },
                  { value: 'CC', label: 'Cédula de Ciudadanía' },
                  { value: 'CE', label: 'Cédula de Extranjería' },
                  { value: 'PAS', label: 'Pasaporte' },
                ]}
              />
              <FormField
                label="Número de Identificación" name="numero_identificacion" required
                value={formData.numero_identificacion} onChange={handleChange}
                onOpenHelp={setHelpField} error={errors.numero_identificacion}
              />
            </div>

            <div className="form-row single">
              <FormField
                label="Dirección" name="direccion" required
                value={formData.direccion} onChange={handleChange}
                onOpenHelp={setHelpField} error={errors.direccion}
              />
            </div>

            <div className="form-row">
              <FormField
                label="País" name="pais"
                value={formData.pais || 'Colombia'} onChange={handleChange}
                onOpenHelp={setHelpField}
              />
              <FormField
                label="Departamento" name="departamento" required
                value={formData.departamento} onChange={handleChange}
                onOpenHelp={setHelpField} error={errors.departamento}
              />
              <FormField
                label="Ciudad" name="ciudad" required
                value={formData.ciudad} onChange={handleChange}
                onOpenHelp={setHelpField} error={errors.ciudad}
              />
            </div>

            <div className="form-row">
              <FormField
                label="Teléfono" name="telefono" type="tel" required
                value={formData.telefono} onChange={handleChange}
                onOpenHelp={setHelpField} error={errors.telefono}
              />
              <FormField
                label="Fax" name="fax" type="tel"
                value={formData.fax} onChange={handleChange}
                onOpenHelp={setHelpField}
              />
              <FormField
                label="Correo Electrónico" name="correo" type="email" required
                value={formData.correo} onChange={handleChange}
                onOpenHelp={setHelpField} error={errors.correo}
              />
            </div>

            <div className="form-row">
              <FormField
                label="Código Actividad ICA" name="codigo_ica"
                value={formData.codigo_ica} onChange={handleChange}
                onOpenHelp={setHelpField}
              />
              <FormField
                label="Página Web" name="pagina_web" type="url"
                value={formData.pagina_web} onChange={handleChange}
                onOpenHelp={setHelpField}
              />
            </div>
          </div>
        )}

        {/* === STEP 3: REPRESENTANTE LEGAL === */}
        {step === 3 && (
          <div className="form-card">
            <h2 className="section-title">👤 Representante Legal</h2>
            <p className="section-subtitle">
              {formData.tipo_persona === 'natural'
                ? 'Información de la persona natural'
                : 'Datos del representante legal de la empresa'}
            </p>

            <div className="form-row single">
              <FormField
                label="Nombres y Apellidos" name="nombre_representante" required
                value={formData.nombre_representante} onChange={handleChange}
                onOpenHelp={setHelpField} error={errors.nombre_representante}
              />
            </div>

            <div className="form-row">
              <FormField
                label="Tipo de Documento" name="tipo_doc_representante" type="select" required
                value={formData.tipo_doc_representante} onChange={handleChange}
                onOpenHelp={setHelpField} error={errors.tipo_doc_representante}
                options={[
                  { value: 'CC', label: 'Cédula de Ciudadanía' },
                  { value: 'CE', label: 'Cédula de Extranjería' },
                  { value: 'PAS', label: 'Pasaporte' },
                ]}
              />
              <FormField
                label="No. de Identificación" name="numero_doc_representante" required
                value={formData.numero_doc_representante} onChange={handleChange}
                onOpenHelp={setHelpField} error={errors.numero_doc_representante}
              />
            </div>

            <div className="form-row">
              <FormField
                label="Fecha de Expedición" name="fecha_expedicion" type="date" required
                value={formData.fecha_expedicion} onChange={handleChange}
                onOpenHelp={setHelpField} error={errors.fecha_expedicion}
              />
              <FormField
                label="Ciudad de Expedición" name="ciudad_expedicion" required
                value={formData.ciudad_expedicion} onChange={handleChange}
                onOpenHelp={setHelpField} error={errors.ciudad_expedicion}
              />
            </div>

            <div className="form-row">
              <FormField
                label="Nacionalidad" name="nacionalidad" required
                value={formData.nacionalidad} onChange={handleChange}
                onOpenHelp={setHelpField} error={errors.nacionalidad}
              />
              <FormField
                label="Fecha de Nacimiento" name="fecha_nacimiento" type="text" required
                placeholder="Ej: 15-AGO-1990"
                value={formData.fecha_nacimiento} onChange={handleChange}
                onOpenHelp={setHelpField} error={errors.fecha_nacimiento}
              />
              <FormField
                label="Ciudad de Nacimiento" name="ciudad_nacimiento" required
                value={formData.ciudad_nacimiento} onChange={handleChange}
                onOpenHelp={setHelpField} error={errors.ciudad_nacimiento}
              />
            </div>

            <div className="form-row">
              <FormField
                label="Profesión" name="profesion" required
                value={formData.profesion} onChange={handleChange}
                onOpenHelp={setHelpField} error={errors.profesion}
              />
              <FormField
                label="Correo Electrónico" name="correo_representante" type="email" required
                value={formData.correo_representante} onChange={handleChange}
                onOpenHelp={setHelpField} error={errors.correo_representante}
              />
              <FormField
                label="Teléfono" name="telefono_representante" type="tel" required
                value={formData.telefono_representante} onChange={handleChange}
                onOpenHelp={setHelpField} error={errors.telefono_representante}
              />
            </div>

            <div className="form-row">
              <FormField
                label="Dirección donde ejerce funciones" name="direccion_funciones" required
                value={formData.direccion_funciones} onChange={handleChange}
                onOpenHelp={setHelpField} error={errors.direccion_funciones}
              />
              <FormField
                label="Ciudad" name="ciudad_funciones" required
                value={formData.ciudad_funciones} onChange={handleChange}
                onOpenHelp={setHelpField} error={errors.ciudad_funciones}
              />
            </div>

            {formData.tipo_persona === 'natural' && (
              <div className="form-row">
                <FormField
                  label="Dirección de Residencia" name="direccion_residencia"
                  value={formData.direccion_residencia} onChange={handleChange}
                  onOpenHelp={setHelpField}
                />
                <FormField
                  label="Ciudad de Residencia" name="ciudad_residencia"
                  value={formData.ciudad_residencia} onChange={handleChange}
                  onOpenHelp={setHelpField}
                />
              </div>
            )}
          </div>
        )}

        {/* === STEP 4: JUNTA DIRECTIVA + ACCIONISTAS === */}
        {step === 4 && formData.tipo_persona !== 'natural' && (
          <div className="form-card">
            <h2 className="section-title">🏛️ Junta Directiva y Composición Accionaria</h2>
            <p className="section-subtitle">Información de directivos, representantes y accionistas</p>

            <div className="info-box">
              <p>📌 PEP: Persona Expuesta Políticamente — persona que maneja recursos públicos, tiene poder público o reconocimiento público.</p>
            </div>

            <h3 style={{ fontSize: '1rem', fontWeight: '600', color: 'var(--gray-800)', marginBottom: '12px' }}>
              Junta Directiva y Representantes
            </h3>

            <div className="data-table-container">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Cargo</th>
                    <th>Nombre</th>
                    <th>Tipo ID</th>
                    <th>Número ID</th>
                    <th>¿PEP?</th>
                    <th>Vínculos PEP</th>
                  </tr>
                </thead>
                <tbody>
                  {juntaDirectiva.map((miembro, idx) => (
                    <tr key={idx}>
                      <td>
                        <input
                          value={miembro.cargo || ''}
                          onChange={(e) => handleJuntaChange(idx, 'cargo', e.target.value)}
                          placeholder="Cargo"
                        />
                      </td>
                      <td>
                        <input
                          value={miembro.nombre || ''}
                          onChange={(e) => handleJuntaChange(idx, 'nombre', e.target.value)}
                          placeholder="Nombre completo"
                        />
                      </td>
                      <td>
                        <select
                          value={miembro.tipo_id || ''}
                          onChange={(e) => handleJuntaChange(idx, 'tipo_id', e.target.value)}
                        >
                          <option value="">-</option>
                          <option value="CC">CC</option>
                          <option value="CE">CE</option>
                          <option value="PAS">PAS</option>
                        </select>
                      </td>
                      <td>
                        <input
                          value={miembro.numero_id || ''}
                          onChange={(e) => handleJuntaChange(idx, 'numero_id', e.target.value)}
                          placeholder="Número"
                        />
                      </td>
                      <td>
                        <select
                          value={miembro.es_pep || ''}
                          onChange={(e) => handleJuntaChange(idx, 'es_pep', e.target.value)}
                        >
                          <option value="">-</option>
                          <option value="si">Sí</option>
                          <option value="no">No</option>
                        </select>
                      </td>
                      <td>
                        <input
                          value={miembro.vinculos_pep || ''}
                          onChange={(e) => handleJuntaChange(idx, 'vinculos_pep', e.target.value)}
                          placeholder="Detalle"
                        />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <button type="button" className="btn btn-sm btn-outline" onClick={addJuntaMember}>
              + Agregar miembro
            </button>

            <hr style={{ border: 'none', borderTop: '1px solid var(--gray-200)', margin: '28px 0' }} />

            <h3 style={{ fontSize: '1rem', fontWeight: '600', color: 'var(--gray-800)', marginBottom: '12px' }}>
              Composición Accionaria
            </h3>

            <div className="info-box">
              <p>📌 Registre accionistas o asociados con más del 5% del capital social.</p>
            </div>

            <div className="data-table-container">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Nombre / Razón Social</th>
                    <th>% Participación</th>
                    <th>Tipo ID</th>
                    <th>Número ID</th>
                    <th>¿PEP?</th>
                    <th>Vínculos PEP</th>
                  </tr>
                </thead>
                <tbody>
                  {accionistas.map((acc, idx) => (
                    <tr key={idx}>
                      <td>
                        <input
                          value={acc.nombre || ''}
                          onChange={(e) => handleAccionistaChange(idx, 'nombre', e.target.value)}
                          placeholder="Nombre"
                        />
                      </td>
                      <td>
                        <input
                          type="number" step="0.01" min="0" max="100"
                          value={acc.porcentaje || ''}
                          onChange={(e) => handleAccionistaChange(idx, 'porcentaje', e.target.value)}
                          placeholder="%"
                        />
                      </td>
                      <td>
                        <select
                          value={acc.tipo_id || ''}
                          onChange={(e) => handleAccionistaChange(idx, 'tipo_id', e.target.value)}
                        >
                          <option value="">-</option>
                          <option value="CC">CC</option>
                          <option value="NIT">NIT</option>
                          <option value="CE">CE</option>
                          <option value="PAS">PAS</option>
                        </select>
                      </td>
                      <td>
                        <input
                          value={acc.numero_id || ''}
                          onChange={(e) => handleAccionistaChange(idx, 'numero_id', e.target.value)}
                          placeholder="Número"
                        />
                      </td>
                      <td>
                        <select
                          value={acc.es_pep || ''}
                          onChange={(e) => handleAccionistaChange(idx, 'es_pep', e.target.value)}
                        >
                          <option value="">-</option>
                          <option value="si">Sí</option>
                          <option value="no">No</option>
                        </select>
                      </td>
                      <td>
                        <input
                          value={acc.vinculos_pep || ''}
                          onChange={(e) => handleAccionistaChange(idx, 'vinculos_pep', e.target.value)}
                          placeholder="Detalle"
                        />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <button type="button" className="btn btn-sm btn-outline" onClick={addAccionista}>
              + Agregar accionista
            </button>

            <div style={{ marginTop: '24px' }}>
              <FormField
                label="Beneficiario Final" name="beneficiario_final" type="textarea"
                value={formData.beneficiario_final} onChange={handleChange}
                onOpenHelp={setHelpField}
                placeholder="Persona natural que ejerce control efectivo sobre socios jurídicos o titular del 25%+ del capital"
              />
            </div>
          </div>
        )}

        {/* Step 4 for Persona Natural - skip to step 5 visually */}
        {step === 4 && formData.tipo_persona === 'natural' && (
          <div className="form-card" style={{ textAlign: 'center', padding: '40px' }}>
            <p style={{ color: 'var(--gray-500)' }}>
              Esta sección aplica solo para Persona Jurídica. Haga clic en "Siguiente" para continuar.
            </p>
          </div>
        )}

        {/* === STEP 5: INFORMACIÓN FINANCIERA === */}
        {step === 5 && (
          <div className="form-card">
            <h2 className="section-title">💰 Información Financiera</h2>
            <p className="section-subtitle">Datos financieros que serán contrastados con los estados financieros adjuntos</p>

            <div className="form-row">
              <FormField
                label="Actividad Económica Principal" name="actividad_economica" required
                value={formData.actividad_economica} onChange={handleChange}
                onOpenHelp={setHelpField} error={errors.actividad_economica}
              />
              <FormField
                label="Código CIIU" name="codigo_ciiu" required
                value={formData.codigo_ciiu} onChange={handleChange}
                onOpenHelp={setHelpField} error={errors.codigo_ciiu}
              />
            </div>

            <div className="form-row">
              <FormField
                label="Ingresos Mensuales (COP)" name="ingresos_mensuales" type="number" required
                value={formData.ingresos_mensuales} onChange={handleChange}
                onOpenHelp={setHelpField} error={errors.ingresos_mensuales}
                placeholder="0"
              />
              <FormField
                label="Otros Ingresos (COP)" name="otros_ingresos" type="number"
                value={formData.otros_ingresos} onChange={handleChange}
                onOpenHelp={setHelpField}
                placeholder="0"
              />
              <FormField
                label="Egresos Mensuales (COP)" name="egresos_mensuales" type="number" required
                value={formData.egresos_mensuales} onChange={handleChange}
                onOpenHelp={setHelpField} error={errors.egresos_mensuales}
                placeholder="0"
              />
            </div>

            <div className="form-row">
              <FormField
                label="Total Activos (COP)" name="total_activos" type="number" required
                value={formData.total_activos} onChange={handleChange}
                onOpenHelp={setHelpField} error={errors.total_activos}
                placeholder="0"
              />
              <FormField
                label="Total Pasivos (COP)" name="total_pasivos" type="number" required
                value={formData.total_pasivos} onChange={handleChange}
                onOpenHelp={setHelpField} error={errors.total_pasivos}
                placeholder="0"
              />
              <FormField
                label="Patrimonio (COP)" name="patrimonio" type="number" required
                value={formData.patrimonio} onChange={handleChange}
                onOpenHelp={setHelpField} error={errors.patrimonio}
                placeholder="0"
              />
            </div>

            <hr style={{ border: 'none', borderTop: '1px solid var(--gray-200)', margin: '24px 0' }} />

            <div className="form-row">
              <FormField
                label="¿Operaciones en Moneda Extranjera?" name="operaciones_moneda_extranjera" type="select"
                value={formData.operaciones_moneda_extranjera} onChange={handleChange}
                onOpenHelp={setHelpField}
                options={[
                  { value: 'si', label: 'Sí' },
                  { value: 'no', label: 'No' },
                ]}
              />
              {formData.operaciones_moneda_extranjera === 'si' && (
                <FormField
                  label="Países" name="paises_operaciones"
                  value={formData.paises_operaciones} onChange={handleChange}
                  onOpenHelp={setHelpField}
                  placeholder="Países donde realiza operaciones"
                />
              )}
            </div>
          </div>
        )}

        {/* === STEP 6: REFERENCIAS + CONTACTOS + BANCARIA === */}
        {step === 6 && (
          <div className="form-card">
            <h2 className="section-title">📋 Referencias, Contactos e Info Bancaria</h2>
            <p className="section-subtitle">Datos de contacto y referencias comerciales y bancarias</p>

            {/* Contacto Órdenes */}
            <h3 style={{ fontSize: '0.95rem', fontWeight: '600', color: 'var(--gray-800)', marginBottom: '12px' }}>
              Contacto para Órdenes de Compra
            </h3>
            <div className="form-row">
              <FormField
                label="Nombre" name="contacto_ordenes_nombre" required
                value={formData.contacto_ordenes_nombre} onChange={handleChange}
                onOpenHelp={setHelpField} error={errors.contacto_ordenes_nombre}
              />
              <FormField
                label="Cargo" name="contacto_ordenes_cargo" required
                value={formData.contacto_ordenes_cargo} onChange={handleChange}
                onOpenHelp={setHelpField} error={errors.contacto_ordenes_cargo}
              />
              <FormField
                label="Teléfono" name="contacto_ordenes_telefono" type="tel" required
                value={formData.contacto_ordenes_telefono} onChange={handleChange}
                onOpenHelp={setHelpField} error={errors.contacto_ordenes_telefono}
              />
              <FormField
                label="Correo" name="contacto_ordenes_correo" type="email" required
                value={formData.contacto_ordenes_correo} onChange={handleChange}
                onOpenHelp={setHelpField} error={errors.contacto_ordenes_correo}
              />
            </div>

            {/* Contacto Pagos */}
            <h3 style={{ fontSize: '0.95rem', fontWeight: '600', color: 'var(--gray-800)', margin: '20px 0 12px' }}>
              Contacto para Reportes de Pago
            </h3>
            <div className="form-row">
              <FormField
                label="Nombre" name="contacto_pagos_nombre" required
                value={formData.contacto_pagos_nombre} onChange={handleChange}
                onOpenHelp={setHelpField} error={errors.contacto_pagos_nombre}
              />
              <FormField
                label="Cargo" name="contacto_pagos_cargo" required
                value={formData.contacto_pagos_cargo} onChange={handleChange}
                onOpenHelp={setHelpField} error={errors.contacto_pagos_cargo}
              />
              <FormField
                label="Teléfono" name="contacto_pagos_telefono" type="tel" required
                value={formData.contacto_pagos_telefono} onChange={handleChange}
                onOpenHelp={setHelpField} error={errors.contacto_pagos_telefono}
              />
              <FormField
                label="Correo" name="contacto_pagos_correo" type="email" required
                value={formData.contacto_pagos_correo} onChange={handleChange}
                onOpenHelp={setHelpField} error={errors.contacto_pagos_correo}
              />
            </div>

            <hr style={{ border: 'none', borderTop: '1px solid var(--gray-200)', margin: '24px 0' }} />

            {/* Info Bancaria */}
            <h3 style={{ fontSize: '0.95rem', fontWeight: '600', color: 'var(--gray-800)', marginBottom: '12px' }}>
              🏦 Información Bancaria para Pagos
            </h3>
            <div className="form-row">
              <FormField
                label="Entidad Bancaria" name="entidad_bancaria" required
                value={formData.entidad_bancaria} onChange={handleChange}
                onOpenHelp={setHelpField} error={errors.entidad_bancaria}
              />
              <FormField
                label="Ciudad / Oficina" name="ciudad_banco" required
                value={formData.ciudad_banco} onChange={handleChange}
                onOpenHelp={setHelpField} error={errors.ciudad_banco}
              />
            </div>
            <div className="form-row">
              <FormField
                label="Tipo de Cuenta" name="tipo_cuenta" type="select" required
                value={formData.tipo_cuenta} onChange={handleChange}
                onOpenHelp={setHelpField} error={errors.tipo_cuenta}
                options={[
                  { value: 'ahorros', label: 'Ahorros' },
                  { value: 'corriente', label: 'Corriente' },
                ]}
              />
              <FormField
                label="Número de Cuenta" name="numero_cuenta" required
                value={formData.numero_cuenta} onChange={handleChange}
                onOpenHelp={setHelpField} error={errors.numero_cuenta}
              />
            </div>
          </div>
        )}

        {/* === STEP 7: DECLARACIONES + FIRMA === */}
        {step === 7 && (
          <div className="form-card">
            <h2 className="section-title">✍️ Autorizaciones y Firma</h2>
            <p className="section-subtitle">Declaraciones legales y firma del formulario</p>

            {/* Autorización datos */}
            <div className="auth-box">
              <p>
                En cumplimiento de la Ley Estatutaria 1581 de 2012 de Protección de Datos (LEPD), mediante el
                registro de sus datos personales usted autoriza la recolección, almacenamiento y uso de los
                mismos para el procedimiento de conocimiento del cliente/proveedor de la empresa.
              </p>
            </div>
            <div className="checkbox-field" onClick={() => handleChange({ target: { name: 'autorizacion_datos', type: 'checkbox', checked: !formData.autorizacion_datos } })}>
              <input
                type="checkbox"
                name="autorizacion_datos"
                checked={formData.autorizacion_datos || false}
                onChange={handleChange}
              />
              <span>Acepto la autorización de tratamiento de datos personales <strong style={{ color: 'var(--error)' }}>*</strong></span>
            </div>
            {errors.autorizacion_datos && <div className="field-error">{errors.autorizacion_datos}</div>}

            <div style={{ height: '24px' }} />

            {/* Declaración origen de fondos */}
            <div className="auth-box">
              <p>Realizo la siguiente declaración de origen de fondos para contribuir en la prevención del LA/FT:</p>
              <ol>
                <li>Los recursos con los cuales esta sociedad fue constituida no provienen de actividades ilícitas.</li>
                <li>No admitiré depósitos con fondos de actividades ilícitas.</li>
              </ol>
            </div>

            <FormField
              label="Mis recursos provienen de las siguientes actividades" name="origen_fondos" type="textarea" required
              value={formData.origen_fondos} onChange={handleChange}
              onOpenHelp={setHelpField} error={errors.origen_fondos}
              placeholder="Describa las actividades de las cuales provienen sus recursos"
            />

            <div className="checkbox-field" onClick={() => handleChange({ target: { name: 'declaracion_origen_fondos', type: 'checkbox', checked: !formData.declaracion_origen_fondos } })}>
              <input
                type="checkbox"
                name="declaracion_origen_fondos"
                checked={formData.declaracion_origen_fondos || false}
                onChange={handleChange}
              />
              <span>Acepto la declaración de origen de fondos <strong style={{ color: 'var(--error)' }}>*</strong></span>
            </div>
            {errors.declaracion_origen_fondos && <div className="field-error">{errors.declaracion_origen_fondos}</div>}

            <hr style={{ border: 'none', borderTop: '1px solid var(--gray-200)', margin: '24px 0' }} />

            <h3 style={{ fontSize: '0.95rem', fontWeight: '600', color: 'var(--gray-800)', marginBottom: '12px' }}>
              Firma del Representante Legal
            </h3>

            <div className="form-row">
              <FormField
                label="Fecha" name="fecha_firma" type="date" required
                value={formData.fecha_firma} onChange={handleChange}
                onOpenHelp={setHelpField} error={errors.fecha_firma}
              />
              <FormField
                label="Ciudad" name="ciudad_firma" required
                value={formData.ciudad_firma} onChange={handleChange}
                onOpenHelp={setHelpField} error={errors.ciudad_firma}
              />
            </div>

            <div className="form-row single">
              <FormField
                label="Nombre del Representante Legal" name="nombre_firma" required
                value={formData.nombre_firma} onChange={handleChange}
                onOpenHelp={setHelpField} error={errors.nombre_firma}
              />
            </div>
          </div>
        )}

        {/* === NAVIGATION BUTTONS === */}
        <div className="form-card">
          {lastSaved && (
            <div style={{ fontSize: '0.78rem', color: 'var(--gray-400)', textAlign: 'right', marginBottom: '8px' }}>
              Guardado automáticamente: {lastSaved.toLocaleTimeString('es-CO')}
            </div>
          )}
          <div className="form-actions">
            <div>
              {step > 1 && (
                <button type="button" className="btn btn-outline" onClick={handlePrev}>
                  ← Anterior
                </button>
              )}
            </div>
            <div className="form-actions-right">
              <button
                type="button"
                className="btn btn-secondary"
                onClick={handleSaveDraft}
                disabled={saving}
              >
                {saving ? '⏳ Guardando...' : '💾 Guardar Borrador'}
              </button>

              {step < TOTAL_STEPS ? (
                <button type="button" className="btn btn-primary" onClick={handleNext}>
                  Siguiente →
                </button>
              ) : (
                <button
                  type="button"
                  className="btn btn-success"
                  onClick={handleSubmit}
                  disabled={saving}
                >
                  {saving ? '⏳ Enviando...' : '✅ Radicar Formulario'}
                </button>
              )}
            </div>
          </div>
        </div>
      </main>

      {/* Help Panel */}
      {helpField && (
        <HelpPanel fieldKey={helpField} onClose={() => setHelpField(null)} />
      )}
    </div>
  );
}


/**
 * Componente de upload de archivo individual.
 */
function FileUploadField({ label, tipoDoc, documentos, onFileChange, onRemove, onOpenHelp, accepted, hint, uploading }) {
  const doc = documentos[tipoDoc]; // puede ser un objeto servidor o null
  const helpKey = `doc_${tipoDoc}`;
  const hasHelp = !!helpTexts[helpKey];

  // Nombre y tamaño toleran tanto File como objeto servidor
  const fileName = doc?.nombre_archivo ?? doc?.name ?? null;
  const fileSize = doc?.tamano ?? doc?.size ?? null;

  const handleDragOver = (e) => {
    e.preventDefault();
    e.currentTarget.classList.add('dragover');
  };

  const handleDragLeave = (e) => {
    e.currentTarget.classList.remove('dragover');
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.currentTarget.classList.remove('dragover');
    const droppedFile = e.dataTransfer.files[0];
    if (droppedFile) onFileChange(tipoDoc, droppedFile);
  };

  return (
    <div style={{ marginBottom: '16px' }}>
      <label className="form-label">
        {label}
        {hasHelp && <HelpIcon fieldKey={helpKey} onOpenHelp={onOpenHelp} />}
        {hint && <span style={{ fontWeight: '400', color: 'var(--warning)', fontSize: '0.75rem', marginLeft: '8px' }}>({hint})</span>}
      </label>

      {uploading ? (
        <div className="file-upload-zone" style={{ cursor: 'default', opacity: 0.7 }}>
          <div className="upload-icon">⏳</div>
          <div className="upload-text">Analizando con IA...</div>
        </div>
      ) : !fileName ? (
        <div
          className="file-upload-zone"
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onClick={() => {
            const input = document.createElement('input');
            input.type = 'file';
            input.accept = accepted || '*';
            input.onchange = (e) => {
              if (e.target.files[0]) onFileChange(tipoDoc, e.target.files[0]);
            };
            input.click();
          }}
        >
          <div className="upload-icon">📁</div>
          <div className="upload-text">
            Arrastre un archivo aquí o <strong>haga clic para seleccionar</strong>
          </div>
        </div>
      ) : (
        <div className="file-upload-list">
          <div className="file-upload-item">
            <span className="file-icon">✅</span>
            <div className="file-info">
              <div className="file-name">{fileName}</div>
              {fileSize && <div className="file-size">{(fileSize / 1024).toFixed(1)} KB</div>}
            </div>
            <button
              type="button"
              className="file-remove"
              onClick={() => onRemove(tipoDoc)}
              title="Eliminar"
            >
              ✕
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
