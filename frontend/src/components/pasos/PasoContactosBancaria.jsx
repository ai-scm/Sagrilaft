import FormField from '../FormField';
import ContactGroup from '../ContactGroup';

const TIPOS_CUENTA = [
  { value: 'ahorros',   label: 'Ahorros'   },
  { value: 'corriente', label: 'Corriente' },
];

const HR = () => (
  <hr style={{ border: 'none', borderTop: '1px solid var(--gray-200)', margin: '24px 0' }} />
);

/**
 * Paso 6 — Contactos y Datos Bancarios.
 */
export default function PasoContactosBancaria({ formData, onChange, onOpenHelp, errors }) {
  return (
    <div className="form-card">
      <h2 className="section-title">📋 Referencias, Contactos e Info Bancaria</h2>
      <p className="section-subtitle">Datos de contacto y referencias comerciales y bancarias</p>

      <ContactGroup
        titulo="Contacto para Órdenes de Compra"
        prefijo="contacto_ordenes"
        formData={formData} onChange={onChange}
        onOpenHelp={onOpenHelp} errors={errors}
        estiloTitulo={{ marginBottom: '12px' }}
      />
      <ContactGroup
        titulo="Contacto para Reportes de Pago"
        prefijo="contacto_pagos"
        formData={formData} onChange={onChange}
        onOpenHelp={onOpenHelp} errors={errors}
        estiloTitulo={{ margin: '20px 0 12px' }}
      />

      <HR />

      <h3 style={{ fontSize: '0.95rem', fontWeight: '600', color: 'var(--gray-800)', marginBottom: '12px' }}>
        🏦 Información Bancaria para Pagos
      </h3>
      <div className="form-row">
        <FormField
          label="Entidad Bancaria" name="entidad_bancaria" required
          value={formData.entidad_bancaria} onChange={onChange}
          onOpenHelp={onOpenHelp} error={errors.entidad_bancaria}
        />
        <FormField
          label="Ciudad / Oficina" name="ciudad_banco" required
          value={formData.ciudad_banco} onChange={onChange}
          onOpenHelp={onOpenHelp} error={errors.ciudad_banco}
        />
      </div>
      <div className="form-row">
        <FormField
          label="Tipo de Cuenta" name="tipo_cuenta" type="select" required
          value={formData.tipo_cuenta} onChange={onChange}
          onOpenHelp={onOpenHelp} error={errors.tipo_cuenta}
          options={TIPOS_CUENTA}
        />
        <FormField
          label="Número de Cuenta" name="numero_cuenta" required
          value={formData.numero_cuenta} onChange={onChange}
          onOpenHelp={onOpenHelp} error={errors.numero_cuenta}
        />
      </div>
    </div>
  );
}
