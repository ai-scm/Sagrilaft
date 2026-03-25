import Select from 'react-select';
import FormField from '../FormField';
import { buildSelectStyles } from '../../utils/selectStyles';

// ── Constantes ────────────────────────────────────────────────────────────────

const OPCIONES_MONEDA = [
  { value: 'si', label: 'Sí' },
  { value: 'no', label: 'No' },
];

const TIPOS_TRANSACCION = [
  { value: 'importacion',    label: 'Importación'       },
  { value: 'exportacion',    label: 'Exportación'       },
  { value: 'inversiones',    label: 'Inversiones'       },
  { value: 'pago_servicios', label: 'Pago de servicios' },
  { value: 'otras',          label: 'Otras'             },
];

// ── Helpers de presentación ────────────────────────────────────────────────────

const HR = () => (
  <hr style={{ border: 'none', borderTop: '1px solid var(--gray-200)', margin: '24px 0' }} />
);

const SectionTitle = ({ children }) => (
  <h3 style={{ fontSize: '1rem', fontWeight: '600', color: 'var(--gray-800)', marginBottom: '12px' }}>
    {children}
  </h3>
);

const SubLabel = ({ children }) => (
  <p style={{ fontSize: '0.875rem', color: 'var(--gray-600)', marginBottom: '8px' }}>
    {children}
  </p>
);

// ── Componente ────────────────────────────────────────────────────────────────

/**
 * Paso 6 — Referencias Comerciales, Referencias Bancarias e Info Bancaria.
 */
export default function PasoContactosBancaria({
  formData, onChange, onOpenHelp,
  referenciasComerciales, onReferenciaChange, onAddReferencia,
  referenciasBancarias,   onReferenciaBancariaChange, onAddReferenciaBancaria,
}) {
  const realizaMoneda     = formData.realiza_operaciones_moneda_extranjera === 'si';
  const tiposSeleccionados = formData.tipos_transaccion ?? [];
  const muestraCuales     = tiposSeleccionados.includes('otras');

  const handleMonedaChange = (option) =>
    onChange({ target: { name: 'realiza_operaciones_moneda_extranjera', value: option?.value ?? '', type: 'text' } });

  const handleTiposChange = (opciones) =>
    onChange({ target: { name: 'tipos_transaccion', value: opciones.map(o => o.value), type: 'text' } });

  const tiposValue = TIPOS_TRANSACCION.filter(o => tiposSeleccionados.includes(o.value));
  const monedaValue = OPCIONES_MONEDA.find(o => o.value === formData.realiza_operaciones_moneda_extranjera) ?? null;

  return (
    <div className="form-card">
      <h2 className="section-title">REFERENCIAS COMERCIALES Y BANCARIAS</h2>
      <p className="section-subtitle">Datos de contacto y referencias comerciales y bancarias</p>

      {/* ── REFERENCIAS COMERCIALES ─────────────────────────────────────────── */}
      <SectionTitle>REFERENCIAS COMERCIALES</SectionTitle>
      <div className="data-table-container">
        <table className="data-table">
          <thead>
            <tr>
              <th>Nombre del establecimiento</th>
              <th>Persona a contactar</th>
              <th>Teléfono</th>
              <th>Ciudad</th>
            </tr>
          </thead>
          <tbody>
            {referenciasComerciales.map((ref, idx) => (
              <tr key={idx}>
                <td>
                  <input
                    value={ref.nombre_establecimiento || ''}
                    placeholder="Nombre del establecimiento"
                    onChange={(e) => onReferenciaChange(idx, 'nombre_establecimiento', e.target.value)}
                  />
                </td>
                <td>
                  <input
                    value={ref.persona_contacto || ''}
                    placeholder="Nombre completo"
                    onChange={(e) => onReferenciaChange(idx, 'persona_contacto', e.target.value)}
                  />
                </td>
                <td>
                  <input
                    value={ref.telefono || ''}
                    placeholder="Teléfono"
                    inputMode="numeric"
                    onChange={(e) => onReferenciaChange(idx, 'telefono', e.target.value)}
                  />
                </td>
                <td>
                  <input
                    value={ref.ciudad || ''}
                    placeholder="Ciudad"
                    onChange={(e) => onReferenciaChange(idx, 'ciudad', e.target.value)}
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <button type="button" className="btn btn-sm btn-outline" onClick={onAddReferencia}>
        + Agregar referencia
      </button>

      <HR />

      {/* ── REFERENCIAS BANCARIAS ───────────────────────────────────────────── */}
      <SectionTitle>REFERENCIAS BANCARIAS</SectionTitle>
      <div className="data-table-container">
        <table className="data-table">
          <thead>
            <tr>
              <th>Entidad</th>
              <th>Producto</th>
            </tr>
          </thead>
          <tbody>
            {referenciasBancarias.map((ref, idx) => (
              <tr key={idx}>
                <td>
                  <input
                    value={ref.entidad || ''}
                    placeholder="Nombre de la entidad"
                    onChange={(e) => onReferenciaBancariaChange(idx, 'entidad', e.target.value)}
                  />
                </td>
                <td>
                  <input
                    value={ref.producto || ''}
                    placeholder="Ej: Cuenta corriente, CDT"
                    onChange={(e) => onReferenciaBancariaChange(idx, 'producto', e.target.value)}
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <button type="button" className="btn btn-sm btn-outline" onClick={onAddReferenciaBancaria}>
        + Agregar referencia bancaria
      </button>

      {/* ── Operaciones en Moneda Extranjera ────────────────────────────────── */}
      <div style={{ marginTop: '20px' }}>
        <div className="form-group" style={{ maxWidth: '320px' }}>
          <label className="form-label">¿Realiza Operaciones en Moneda Extranjera?</label>
          <Select
            inputId="realiza_operaciones_moneda_extranjera"
            value={monedaValue}
            onChange={handleMonedaChange}
            options={OPCIONES_MONEDA}
            isClearable
            placeholder="Seleccione..."
            noOptionsMessage={() => 'Sin opciones'}
            styles={buildSelectStyles(false, !!monedaValue)}
          />
        </div>

        {realizaMoneda && (
          <div style={{ marginTop: '16px' }}>
            <div className="form-row single">
              <FormField
                label="Países en los que realiza operaciones"
                name="paises_operaciones"
                value={formData.paises_operaciones} onChange={onChange}
                onOpenHelp={onOpenHelp}
                placeholder="Ej: Estados Unidos, Alemania, China"
              />
            </div>

            <div className="form-group" style={{ marginTop: '12px' }}>
              <SubLabel>
                Si su actividad implica transacciones en moneda extranjera, señale los tipos de transacción:
              </SubLabel>
              <Select
                inputId="tipos_transaccion"
                isMulti
                value={tiposValue}
                onChange={handleTiposChange}
                options={TIPOS_TRANSACCION}
                placeholder="Seleccione uno o más tipos..."
                noOptionsMessage={() => 'Sin opciones'}
                styles={buildSelectStyles(false, tiposValue.length > 0)}
              />
            </div>

            {muestraCuales && (
              <div className="form-row single" style={{ marginTop: '12px' }}>
                <FormField
                  label="¿Cuáles?"
                  name="tipos_transaccion_otros"
                  value={formData.tipos_transaccion_otros} onChange={onChange}
                  onOpenHelp={onOpenHelp}
                  placeholder="Describa las otras transacciones"
                />
              </div>
            )}
          </div>
        )}
      </div>

    </div>
  );
}
