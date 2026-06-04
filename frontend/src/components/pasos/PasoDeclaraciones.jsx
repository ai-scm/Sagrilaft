import FormField from '../FormField';
import { HR } from '../TablaFormComponents';
import FirmaRepresentanteLegal from '../FirmaRepresentanteLegal';
import { RAZON_SOCIAL_EMPRESA, CORREO_DATOS_PERSONALES } from '../../config/textos-legales';

/**
 * Paso 8 — Autorizaciones, Declaración de Origen de Fondos y Firma.
 */
export default function PasoDeclaraciones({
  formData,
  onChange,
  onOpenHelp,
  errors,
}) {
  const toggleCheckbox = (name) =>
    onChange({ target: { name, type: 'checkbox', checked: !formData[name] } });

  return (
    <div className="form-card">
      <h2 className="section-title">AUTORIZACION - DECLARACION DE FONDOS Y FIRMA REPRESENTANTE LEGAL</h2>
      <p className="section-subtitle">Declaraciones legales y firma del formulario</p>

      {/* Autorización tratamiento de datos */}
      <div className="auth-box">
        <p>
          En cumplimiento de la Ley Estatutaria 1581 de 2012 de Protección de Datos (LEPD), del Decreto 1377 de 2013 y de las medidas de seguridad definidas en la política de tratamiento desarrollada
          por {RAZON_SOCIAL_EMPRESA}, a las cuales puede tener acceso a través del correo
          electrónico: {CORREO_DATOS_PERSONALES}. Mediante el registro de sus datos personales en el presente formulario usted
          autoriza a {RAZON_SOCIAL_EMPRESA} para la recolección, almacenamiento y uso de los mismos con la finalidad de llevar
          a cabo el procedimiento de conocimiento del cliente/proveedor de la empresa. Usted, como titular de sus datos
          personales puede ejercer sus derechos de acceso, corrección, supresión o revocación mediante un escrito dirigido
          a {RAZON_SOCIAL_EMPRESA}, mediante correo electrónico a {CORREO_DATOS_PERSONALES} indicando en el asunto el derecho
          que desea ejercitar.
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

      <FirmaRepresentanteLegal
        formData={formData}
        onChange={onChange}
        onOpenHelp={onOpenHelp}
        errors={errors}
      />
    </div>
  );
}
