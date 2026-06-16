import FormField from '../FormField';
import CurrencyInput from '../CurrencyInput';

const MONEDAS_DISPONIBLES = [
  { value: '', label: 'Seleccione una moneda...' },
  { value: 'COP', label: 'Pesos Colombianos (COP)' },
  { value: 'USD', label: 'Dólares Estadounidenses (USD)' },
  { value: 'EUR', label: 'Euros (EUR)' },
  { value: 'PEN', label: 'Soles Peruanos (PEN)' },
  { value: 'BRL', label: 'Reales Brasileños (BRL)' },
  { value: 'CLP', label: 'Peso Chileno (CLP)' },
  { value: 'ARS', label: 'Peso Argentino (ARS)' },
];

const SIMBOLOS_MONEDA = {
  'COP': '$',
  'USD': 'US$',
  'EUR': '€',
  'PEN': 'S/',
  'BRL': 'R$',
  'CLP': 'CL$',
  'ARS': 'AR$',
};

/**
 * Paso 5 — Información Financiera.
 * Los valores se contrastan con los estados financieros adjuntos.
 */
export default function PasoFinanciero({ formData, onChange, onOpenHelp, errors }) {
  const monedaActual = formData.moneda_declaracion || '';
  const simboloActual = SIMBOLOS_MONEDA[monedaActual] || '';

  return (
    <div className="form-card">
      <h2 className="section-title">Información Financiera</h2>
      <p className="section-subtitle">Datos financieros que serán contrastados con los estados financieros adjuntos</p>

      <div className="form-row">
        <FormField
          label="Moneda de Declaración" name="moneda_declaracion" type="select" required
          value={formData.moneda_declaracion || ''} onChange={onChange}
          onOpenHelp={onOpenHelp} error={errors.moneda_declaracion}
          options={MONEDAS_DISPONIBLES}
        />
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
        <CurrencyInput
          label="Ingresos Mensuales" name="ingresos_mensuales" required
          value={formData.ingresos_mensuales} onChange={onChange}
          onOpenHelp={onOpenHelp} error={errors.ingresos_mensuales} placeholder="0"
          symbol={simboloActual} currency={monedaActual}
        />
        <CurrencyInput
          label="Otros Ingresos" name="otros_ingresos"
          value={formData.otros_ingresos} onChange={onChange}
          onOpenHelp={onOpenHelp} placeholder="0"
          symbol={simboloActual} currency={monedaActual}
        />
        <CurrencyInput
          label="Egresos Mensuales" name="egresos_mensuales" required
          value={formData.egresos_mensuales} onChange={onChange}
          onOpenHelp={onOpenHelp} error={errors.egresos_mensuales} placeholder="0"
          symbol={simboloActual} currency={monedaActual}
        />
      </div>

      <div className="form-row">
        <CurrencyInput
          label="Total Activos" name="total_activos" required
          value={formData.total_activos} onChange={onChange}
          onOpenHelp={onOpenHelp} error={errors.total_activos} placeholder="0"
          symbol={simboloActual} currency={monedaActual}
        />
        <CurrencyInput
          label="Total Pasivos" name="total_pasivos" required
          value={formData.total_pasivos} onChange={onChange}
          onOpenHelp={onOpenHelp} error={errors.total_pasivos} placeholder="0"
          symbol={simboloActual} currency={monedaActual}
        />
        <CurrencyInput
          label="Patrimonio" name="patrimonio" required
          value={formData.patrimonio} onChange={onChange}
          onOpenHelp={onOpenHelp} error={errors.patrimonio} placeholder="0"
          symbol={simboloActual} currency={monedaActual}
        />
      </div>
    </div>
  );
}

