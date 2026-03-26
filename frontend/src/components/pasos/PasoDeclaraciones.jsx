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
          En cumplimiento de la Ley Estatutaria 1581 de 2012 de Protección de Datos (LEPD), del Decreto 1377 de 2013 y de las medidas de seguridad definidas en la política de tratamiento desarrollada por HIGHTECH SOFTWARE CONTABLE SAS l a las cuales
          puede tener acceso a través del correo electrónico: info@xxxxxl.com.co. Mediante el registro de sus datos personales en el presente formulario usted autoriza a HIGHTECH SOFTWARE CONTABLE SAS para la recolección, almacenamiento y uso de los
          mismos con la finalidad de llevar a cabo el procedimiento de conocimiento del cliente/proveedor de la empresa. Usted, como titular de sus datos personales puede ejercer sus derechos de acceso, corrección, supresión o revocación mediante un escrito
          dirigido a HIGHTECH SOFTWARE CONTABLE SAS, mediante correo electrónico a info@tXXXXXX indicando en el asunto el derecho que desea ejercitar
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
        <p>Manifiesto que todo lo aquí consignado es veraz. Así mismo, realizo la siguiente declaración de origen de fondos con el propósito de contribuir en la prevención y control del Lavado de Activos y Financiación del Terrorismo.</p>
        <ol>
          <li> Declaro que los recursos con los cuales esta sociedad fue constituida no provienen de ninguna actividad ilícita de las contempladas en el Código Penal Colombiano o en cualquier norma que lo modifique o adiciones</li>
          <li> No admitiré que terceros efectúen depósitos a mis cuentas con fondos de actividades ilícitas contempladas en el Código Penal Colombiano o en cualquier norma que lo modifique o adicione, ni efectuaré transacciones a tales actividades de o a favor de
              personas relacionadas con las mismas.</li>
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
