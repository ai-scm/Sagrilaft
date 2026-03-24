import FormField from '../FormField';

const HR = () => (
  <hr style={{ border: 'none', borderTop: '1px solid var(--gray-200)', margin: '24px 0' }} />
);

/**
 * Paso 7 — Autorizaciones, Declaración de Origen de Fondos y Firma.
 */
export default function PasoDeclaraciones({ formData, onChange, onOpenHelp, errors }) {
  const toggleCheckbox = (name) =>
    onChange({ target: { name, type: 'checkbox', checked: !formData[name] } });

  return (
    <div className="form-card">
      <h2 className="section-title">✍️ Autorizaciones y Firma</h2>
      <p className="section-subtitle">Declaraciones legales y firma del formulario</p>

      {/* Autorización tratamiento de datos */}
      <div className="auth-box">
        <p>
          En cumplimiento de la Ley Estatutaria 1581 de 2012 de Protección de Datos (LEPD), mediante el
          registro de sus datos personales usted autoriza la recolección, almacenamiento y uso de los
          mismos para el procedimiento de conocimiento del cliente/proveedor de la empresa.
        </p>
      </div>
      <div className="checkbox-field" onClick={() => toggleCheckbox('autorizacion_datos')}>
        <input
          type="checkbox" name="autorizacion_datos"
          checked={formData.autorizacion_datos || false}
          onChange={onChange}
        />
        <span>
          Acepto la autorización de tratamiento de datos personales{' '}
          <strong style={{ color: 'var(--error)' }}>*</strong>
        </span>
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
        value={formData.origen_fondos} onChange={onChange}
        onOpenHelp={onOpenHelp} error={errors.origen_fondos}
        placeholder="Describa las actividades de las cuales provienen sus recursos"
      />
      <div className="checkbox-field" onClick={() => toggleCheckbox('declaracion_origen_fondos')}>
        <input
          type="checkbox" name="declaracion_origen_fondos"
          checked={formData.declaracion_origen_fondos || false}
          onChange={onChange}
        />
        <span>
          Acepto la declaración de origen de fondos{' '}
          <strong style={{ color: 'var(--error)' }}>*</strong>
        </span>
      </div>
      {errors.declaracion_origen_fondos && (
        <div className="field-error">{errors.declaracion_origen_fondos}</div>
      )}

      <HR />

      {/* Firma */}
      <h3 style={{ fontSize: '0.95rem', fontWeight: '600', color: 'var(--gray-800)', marginBottom: '12px' }}>
        Firma del Representante Legal
      </h3>
      <div className="form-row">
        <FormField
          label="Fecha" name="fecha_firma" type="date" required
          value={formData.fecha_firma} onChange={onChange}
          onOpenHelp={onOpenHelp} error={errors.fecha_firma}
        />
        <FormField
          label="Ciudad" name="ciudad_firma" required
          value={formData.ciudad_firma} onChange={onChange}
          onOpenHelp={onOpenHelp} error={errors.ciudad_firma}
        />
      </div>
      <div className="form-row single">
        <FormField
          label="Nombre del Representante Legal" name="nombre_firma" required
          value={formData.nombre_firma} onChange={onChange}
          onOpenHelp={onOpenHelp} error={errors.nombre_firma}
        />
      </div>
    </div>
  );
}
