/**
 * Paso 7 — Clasificación Tributaria, Contactos e Información Bancaria para Pagos.
 *
 * Sección 8: CLASIFICACIÓN DE LA EMPRESA Y RÉGIMEN TRIBUTARIO (solo persona jurídica)
 * Sección 9: CONTACTO
 * Sección 10: INFORMACIÓN BANCARIA PARA PAGOS
 *
 * SRP : solo renderiza los campos de las secciones 8, 9 y 10.
 * DIP : depende de interfaces (props + TablaFormComponents), no de implementaciones concretas.
 * ISP : cada sección recibe solo los props que necesita.
 * DRY : reutiliza FormField, HR, SectionTitle, MensajeError y ESTILO_CELDA_ERROR de módulos compartidos.
 */
import FormField from '../FormField';
import { HR, SectionTitle, ESTILO_CELDA_ERROR, MensajeError } from '../TablaFormComponents';
import { onlyNumericKeyDown, onlyNumericPaste } from '../../utils/inputValidation';

// ── Constantes de dominio ──────────────────────────────────────────────────────

const OPCIONES_SI_NO = [
  { value: 'si', label: 'Sí' },
  { value: 'no', label: 'No' },
];

/**
 * Sector económico de la empresa.
 * Fuente única de verdad — espeja los valores validados en el backend (validar_sector).
 */
const SECTORES_EMPRESA = [
  { value: 'Público',  label: 'Público'  },
  { value: 'Privado', label: 'Privado' },
  { value: 'Mixto',   label: 'Mixto'   },
];

/**
 * Responsabilidades impuesto sobre la renta de la empresa.
 * Fuente única de verdad — espeja los valores validados en el backend (validar_responsabilidades_renta).
 */
const RESPONSABILIDADES_RENTA = [
  { value: 'Declarante', label: 'Declarante' },
  { value: 'No declarante', label: 'No declarante' },
  { value: 'Declarante Regimen Especial', label: 'Declarante Regimen Especial' },
];

/**
 * Responsabilidades en IVA.
 */
const RESPONSABILIDADES_IVA = [
  { value: 'Responsable', label: 'Responsable' },
  { value: 'No responsable', label: 'No responsable' },
];

/**
 * Regímenes de IVA.
 */
const REGIMENES_IVA = [
  { value: 'Régimen común', label: 'Régimen común' },
  { value: 'Régimen simplificado', label: 'Régimen simplificado' },
  { value: 'Ningún régimen', label: 'Ningún régimen' },
];

/**
 * Actividad principal de la empresa.
 * Mapeado con el Enum ActividadClasificacion del backend.
 */
const OPCIONES_ACTIVIDAD = [
  { value: 'industrial',         label: 'Industrial'         },
  { value: 'comercial',          label: 'Comercial'          },
  { value: 'financiera',         label: 'Financiera'         },
  { value: 'economia_solidaria', label: 'Economía solidaria' },
  { value: 'otra',               label: 'Otra'               },
];

const TIPOS_CUENTA = [
  { value: 'ahorro',    label: 'Cuenta de Ahorro'   },
  { value: 'corriente', label: 'Cuenta Corriente'    },
  { value: 'fiducia',   label: 'Fiducia'             },
];

// ── Sub-secciones (SRP por sección) ───────────────────────────────────────────

/**
 * Sección 8 — Clasificación de la empresa y régimen tributario.
 * Solo se renderiza para Persona Jurídica (condicional recibido por prop).
 */
function ClasificacionTributaria({ formData, onChange, onActividadChange, onOpenHelp, errors }) {
  const actividad = formData.actividad_clasificacion;
  const esOtraActividad = actividad === 'otra';

  return (
    <>
      <SectionTitle>8. CLASIFICACIÓN DE LA EMPRESA Y RÉGIMEN TRIBUTARIO</SectionTitle>
      
      <div className="form-row">
        <FormField
          label="Actividad" name="actividad_clasificacion" type="select" required
          value={actividad} onChange={onActividadChange} onOpenHelp={onOpenHelp}
          options={OPCIONES_ACTIVIDAD} error={errors.actividad_clasificacion}
        />
        <FormField
          label="¿Cuál? Especifique" name="actividad_especifica" required
          value={formData.actividad_especifica} onChange={onChange} onOpenHelp={onOpenHelp}
          error={errors.actividad_especifica}
          disabled={!esOtraActividad}
        />
        <FormField
          label="Sector" name="sector" type="select" required
          value={formData.sector} onChange={onChange} onOpenHelp={onOpenHelp}
          options={SECTORES_EMPRESA} error={errors.sector}
        />
        <FormField
          label="Vigilado por la superintendencia de" name="superintendencia" required
          value={formData.superintendencia} onChange={onChange} onOpenHelp={onOpenHelp}
          error={errors.superintendencia}
        />
      </div>

      <div className="form-row">
        <FormField
          label="Responsabilidades impuesto sobre la renta" name="responsabilidades_renta" type="select" required
          value={formData.responsabilidades_renta} onChange={onChange} onOpenHelp={onOpenHelp}
          options={RESPONSABILIDADES_RENTA} error={errors.responsabilidades_renta}
        />
        <FormField
          label="Autorretenedor" name="autorretenedor" type="select" required
          value={formData.autorretenedor} onChange={onChange} onOpenHelp={onOpenHelp}
          options={OPCIONES_SI_NO} error={errors.autorretenedor}
        />
        <FormField
          label="Responsabilidades en el impuesto sobre las ventas (IVA)" name="responsabilidades_iva" type="select" required
          value={formData.responsabilidades_iva} onChange={onChange} onOpenHelp={onOpenHelp}
          options={RESPONSABILIDADES_IVA} error={errors.responsabilidades_iva}
        />
        <FormField
          label="Régimen IVA" name="regimen_iva" type="select" required
          value={formData.regimen_iva} onChange={onChange} onOpenHelp={onOpenHelp}
          options={REGIMENES_IVA} error={errors.regimen_iva}
        />
        <FormField
          label="¿Es Gran Contribuyente?" name="gran_contribuyente" type="select" required
          value={formData.gran_contribuyente} onChange={onChange} onOpenHelp={onOpenHelp}
          options={OPCIONES_SI_NO} error={errors.gran_contribuyente}
        />
      </div>

      <div className="form-row">
        <FormField
          label="Entidad sin Ánimo de Lucro" name="entidad_sin_animo_lucro" type="select" required
          value={formData.entidad_sin_animo_lucro} onChange={onChange} onOpenHelp={onOpenHelp}
          options={OPCIONES_SI_NO} error={errors.entidad_sin_animo_lucro}
        />
        <FormField
          label="Retención de Industria y Comercio" name="retencion_ica" type="select" required
          value={formData.retencion_ica} onChange={onChange} onOpenHelp={onOpenHelp}
          options={OPCIONES_SI_NO} error={errors.retencion_ica}
        />
        <FormField
          label="Impuesto de Industria y Comercio" name="impuesto_ica" type="select" required
          value={formData.impuesto_ica} onChange={onChange} onOpenHelp={onOpenHelp}
          options={OPCIONES_SI_NO} error={errors.impuesto_ica}
        />
        <FormField
          label="Entidad Oficial" name="entidad_oficial" type="select" required
          value={formData.entidad_oficial} onChange={onChange} onOpenHelp={onOpenHelp}
          options={OPCIONES_SI_NO} error={errors.entidad_oficial}
        />
        <FormField
          label="Exento de Retención en la Fuente" name="exento_retencion_fuente" type="select" required
          value={formData.exento_retencion_fuente} onChange={onChange} onOpenHelp={onOpenHelp}
          options={OPCIONES_SI_NO} error={errors.exento_retencion_fuente}
        />
      </div>

      <HR />
    </>
  );
}

/**
 * Sección 9 — Personas de contacto autorizadas.
 * Reutiliza FormField con los mismos patrones de los otros pasos.
 */
function ContactoAutorizado({ formData, onChange, onOpenHelp, errors }) {
  return (
    <>
      <SectionTitle>9. CONTACTO</SectionTitle>

      <p style={{ fontWeight: '600', fontSize: '0.875rem', marginBottom: '8px' }}>
        Persona autorizada para recepción de órdenes de compra y de servicio
      </p>
      <div className="form-row">
        <FormField
          label="Nombre" name="contacto_ordenes_nombre" required
          value={formData.contacto_ordenes_nombre} onChange={onChange} onOpenHelp={onOpenHelp}
          error={errors.contacto_ordenes_nombre}
        />
        <FormField
          label="Cargo" name="contacto_ordenes_cargo" required
          value={formData.contacto_ordenes_cargo} onChange={onChange} onOpenHelp={onOpenHelp}
          error={errors.contacto_ordenes_cargo}
        />
        <FormField
          label="Teléfono y Extensión" name="contacto_ordenes_telefono" required
          value={formData.contacto_ordenes_telefono} onChange={onChange} onOpenHelp={onOpenHelp}
          error={errors.contacto_ordenes_telefono}
        />
        <FormField
          label="Correo Electrónico" name="contacto_ordenes_correo" required
          value={formData.contacto_ordenes_correo} onChange={onChange} onOpenHelp={onOpenHelp}
          error={errors.contacto_ordenes_correo}
        />
      </div>

      <p style={{ fontWeight: '600', fontSize: '0.875rem', marginBottom: '8px', marginTop: '16px' }}>
        Persona autorizada para recepción de reportes de pago
      </p>
      <div className="form-row">
        <FormField
          label="Nombre" name="contacto_pagos_nombre" required
          value={formData.contacto_pagos_nombre} onChange={onChange} onOpenHelp={onOpenHelp}
          error={errors.contacto_pagos_nombre}
        />
        <FormField
          label="Cargo" name="contacto_pagos_cargo" required
          value={formData.contacto_pagos_cargo} onChange={onChange} onOpenHelp={onOpenHelp}
          error={errors.contacto_pagos_cargo}
        />
        <FormField
          label="Teléfono y Extensión" name="contacto_pagos_telefono" required
          value={formData.contacto_pagos_telefono} onChange={onChange} onOpenHelp={onOpenHelp}
          error={errors.contacto_pagos_telefono}
        />
        <FormField
          label="Correo Electrónico" name="contacto_pagos_correo" required
          value={formData.contacto_pagos_correo} onChange={onChange} onOpenHelp={onOpenHelp}
          error={errors.contacto_pagos_correo}
        />
      </div>

      <HR />
    </>
  );
}

/**
 * Sección 10 — Información bancaria para pagos.
 * Tabla dinámica que reutiliza el mismo patrón de PasoContactosBancaria
 * (onXChange, onAddX, errFilasX) via TablaFormComponents.
 */
function InfoBancariaPagos({ infoBancariaPagos, onInfoBancariaPagosChange, onAddInfoBancariaPagos, errors }) {
  const errFilas = errors.info_bancaria_pagos_filas ?? [];

  return (
    <>
      <SectionTitle>10. INFORMACIÓN BANCARIA PARA PAGOS</SectionTitle>
      {errors.info_bancaria_pagos_tabla && (
        <div className="field-error" style={{ marginBottom: '8px' }}>
          {errors.info_bancaria_pagos_tabla}
        </div>
      )}
      <div className="data-table-container">
        <table className="data-table">
          <thead>
            <tr>
              <th>Entidad Bancaria</th>
              <th>Ciudad / Oficina</th>
              <th>Tipo de Cuenta</th>
              <th>Número de Cuenta</th>
            </tr>
          </thead>
          <tbody>
            {infoBancariaPagos.map((fila, idx) => {
              const err = errFilas[idx] ?? {};
              return (
                <tr key={idx}>
                  <td>
                    <input
                      value={fila.entidad_bancaria || ''}
                      placeholder="Nombre de la entidad"
                      onChange={(e) => onInfoBancariaPagosChange(idx, 'entidad_bancaria', e.target.value)}
                      style={err.entidad_bancaria ? ESTILO_CELDA_ERROR : undefined}
                    />
                    <MensajeError msg={err.entidad_bancaria} />
                  </td>
                  <td>
                    <input
                      value={fila.ciudad_oficina || ''}
                      placeholder="Ciudad / Oficina"
                      onChange={(e) => onInfoBancariaPagosChange(idx, 'ciudad_oficina', e.target.value)}
                      style={err.ciudad_oficina ? ESTILO_CELDA_ERROR : undefined}
                    />
                    <MensajeError msg={err.ciudad_oficina} />
                  </td>
                  <td>
                    <select
                      value={fila.tipo_cuenta || ''}
                      onChange={(e) => onInfoBancariaPagosChange(idx, 'tipo_cuenta', e.target.value)}
                      style={err.tipo_cuenta ? ESTILO_CELDA_ERROR : undefined}
                    >
                      <option value="">Seleccione...</option>
                      {TIPOS_CUENTA.map(opt => (
                        <option key={opt.value} value={opt.value}>{opt.label}</option>
                      ))}
                    </select>
                    <MensajeError msg={err.tipo_cuenta} />
                  </td>
                  <td>
                    <input
                      value={fila.numero_cuenta || ''}
                      placeholder="Número de cuenta"
                      inputMode="numeric"
                      onKeyDown={onlyNumericKeyDown}
                      onPaste={onlyNumericPaste}
                      onChange={(e) => onInfoBancariaPagosChange(idx, 'numero_cuenta', e.target.value)}
                      style={err.numero_cuenta ? ESTILO_CELDA_ERROR : undefined}
                    />
                    <MensajeError msg={err.numero_cuenta} />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <button type="button" className="btn btn-sm btn-outline" onClick={onAddInfoBancariaPagos}>
        + Agregar cuenta
      </button>
    </>
  );
}

// ── Componente orquestador del paso ───────────────────────────────────────────

export default function PasoClasificacionContactoBancario({
  formData, onChange, handleActividadChange, onOpenHelp, errors = {},
  infoBancariaPagos, onInfoBancariaPagosChange, onAddInfoBancariaPagos,
}) {
  const esJuridica = formData.tipo_persona === 'juridica';

  return (
    <div className="form-card">
      <h2 className="section-title">CLASIFICACIÓN, CONTACTOS E INFORMACIÓN BANCARIA</h2>
      <p className="section-subtitle">Datos tributarios, personas de contacto y cuentas para pagos</p>

      {esJuridica && (
        <ClasificacionTributaria
          formData={formData}
          onChange={onChange}
          onActividadChange={handleActividadChange}
          onOpenHelp={onOpenHelp}
          errors={errors}
        />
      )}

      <ContactoAutorizado
        formData={formData}
        onChange={onChange}
        onOpenHelp={onOpenHelp}
        errors={errors}
      />

      <InfoBancariaPagos
        infoBancariaPagos={infoBancariaPagos}
        onInfoBancariaPagosChange={onInfoBancariaPagosChange}
        onAddInfoBancariaPagos={onAddInfoBancariaPagos}
        errors={errors}
      />
    </div>
  );
}
