import FormField from '../FormField';

const OPCIONES_MONEDA_EXTRANJERA = [
  { value: 'si', label: 'Sí' },
  { value: 'no', label: 'No' },
];

const HR = () => (
  <hr style={{ border: 'none', borderTop: '1px solid var(--gray-200)', margin: '24px 0' }} />
);

/**
 * Paso 5 — Información Financiera.
 * Los valores se contrastan con los estados financieros adjuntos.
 */
export default function PasoFinanciero({ formData, onChange, onOpenHelp, errors }) {
  return (
    <div className="form-card">
      <h2 className="section-title">💰 Información Financiera</h2>
      <p className="section-subtitle">Datos financieros que serán contrastados con los estados financieros adjuntos</p>

      <div className="form-row">
        <FormField
          label="Actividad Económica Principal" name="actividad_economica" required
          value={formData.actividad_economica} onChange={onChange}
          onOpenHelp={onOpenHelp} error={errors.actividad_economica}
        />
        <FormField
          label="Código CIIU" name="codigo_ciiu" required
          value={formData.codigo_ciiu} onChange={onChange}
          onOpenHelp={onOpenHelp} error={errors.codigo_ciiu}
        />
      </div>

      <div className="form-row">
        <FormField
          label="Ingresos Mensuales (COP)" name="ingresos_mensuales" type="number" required
          value={formData.ingresos_mensuales} onChange={onChange}
          onOpenHelp={onOpenHelp} error={errors.ingresos_mensuales} placeholder="0"
        />
        <FormField
          label="Otros Ingresos (COP)" name="otros_ingresos" type="number"
          value={formData.otros_ingresos} onChange={onChange}
          onOpenHelp={onOpenHelp} placeholder="0"
        />
        <FormField
          label="Egresos Mensuales (COP)" name="egresos_mensuales" type="number" required
          value={formData.egresos_mensuales} onChange={onChange}
          onOpenHelp={onOpenHelp} error={errors.egresos_mensuales} placeholder="0"
        />
      </div>

      <div className="form-row">
        <FormField
          label="Total Activos (COP)" name="total_activos" type="number" required
          value={formData.total_activos} onChange={onChange}
          onOpenHelp={onOpenHelp} error={errors.total_activos} placeholder="0"
        />
        <FormField
          label="Total Pasivos (COP)" name="total_pasivos" type="number" required
          value={formData.total_pasivos} onChange={onChange}
          onOpenHelp={onOpenHelp} error={errors.total_pasivos} placeholder="0"
        />
        <FormField
          label="Patrimonio (COP)" name="patrimonio" type="number" required
          value={formData.patrimonio} onChange={onChange}
          onOpenHelp={onOpenHelp} error={errors.patrimonio} placeholder="0"
        />
      </div>

      <HR />

      <div className="form-row">
        <FormField
          label="¿Operaciones en Moneda Extranjera?" name="operaciones_moneda_extranjera" type="select"
          value={formData.operaciones_moneda_extranjera} onChange={onChange}
          onOpenHelp={onOpenHelp} options={OPCIONES_MONEDA_EXTRANJERA}
        />
        {formData.operaciones_moneda_extranjera === 'si' && (
          <FormField
            label="Países" name="paises_operaciones"
            value={formData.paises_operaciones} onChange={onChange}
            onOpenHelp={onOpenHelp} placeholder="Países donde realiza operaciones"
          />
        )}
      </div>
    </div>
  );
}
