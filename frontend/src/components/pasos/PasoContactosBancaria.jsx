import Select from 'react-select';
import FormField from '../FormField';
import { buildSelectStyles } from '../../utils/selectStyles';
import { onlyNumericKeyDown, onlyNumericPaste } from '../../utils/inputValidation';
import { HR, SectionTitle, SubLabel, ESTILO_CELDA_ERROR, MensajeError } from '../TablaFormComponents';

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

// ── Componente ────────────────────────────────────────────────────────────────

/**
 * Paso 6 — Referencias Comerciales, Referencias Bancarias e Info Bancaria.
 */
export default function PasoContactosBancaria({
  formData, onChange, onOpenHelp, errors = {},
  referenciasComerciales, onReferenciaChange, onAddReferencia,
  referenciasBancarias,   onReferenciaBancariaChange, onAddReferenciaBancaria,
}) {
  const errFilasComerciales = errors.referencias_comerciales_filas ?? [];
  const errFilasBancarias   = errors.referencias_bancarias_filas   ?? [];
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
      {errors.referencias_comerciales_tabla && (
        <div className="field-error" style={{ marginBottom: '8px' }}>{errors.referencias_comerciales_tabla}</div>
      )}
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
            {referenciasComerciales.map((ref, idx) => {
              const err = errFilasComerciales[idx] ?? {};
              return (
                <tr key={idx}>
                  <td>
                    <input
                      value={ref.nombre_establecimiento || ''}
                      placeholder="Nombre del establecimiento"
                      onChange={(e) => onReferenciaChange(idx, 'nombre_establecimiento', e.target.value)}
                      style={err.nombre_establecimiento ? ESTILO_CELDA_ERROR : undefined}
                    />
                    <MensajeError msg={err.nombre_establecimiento} />
                  </td>
                  <td>
                    <input
                      value={ref.persona_contacto || ''}
                      placeholder="Nombre completo"
                      onChange={(e) => onReferenciaChange(idx, 'persona_contacto', e.target.value)}
                      style={err.persona_contacto ? ESTILO_CELDA_ERROR : undefined}
                    />
                    <MensajeError msg={err.persona_contacto} />
                  </td>
                  <td>
                    <input
                      value={ref.telefono || ''}
                      placeholder="Teléfono"
                      inputMode="numeric"
                      maxLength={10}
                      onKeyDown={onlyNumericKeyDown}
                      onPaste={onlyNumericPaste}
                      onChange={(e) => onReferenciaChange(idx, 'telefono', e.target.value)}
                      style={err.telefono ? ESTILO_CELDA_ERROR : undefined}
                    />
                    <MensajeError msg={err.telefono} />
                  </td>
                  <td>
                    <input
                      value={ref.ciudad || ''}
                      placeholder="Ciudad"
                      onChange={(e) => onReferenciaChange(idx, 'ciudad', e.target.value)}
                      style={err.ciudad ? ESTILO_CELDA_ERROR : undefined}
                    />
                    <MensajeError msg={err.ciudad} />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <button type="button" className="btn btn-sm btn-outline" onClick={onAddReferencia}>
        + Agregar referencia
      </button>

      <HR />

      {/* ── REFERENCIAS BANCARIAS ───────────────────────────────────────────── */}
      <SectionTitle>REFERENCIAS BANCARIAS</SectionTitle>
      {errors.referencias_bancarias_tabla && (
        <div className="field-error" style={{ marginBottom: '8px' }}>{errors.referencias_bancarias_tabla}</div>
      )}
      <div className="data-table-container">
        <table className="data-table">
          <thead>
            <tr>
              <th>Entidad</th>
              <th>Producto</th>
            </tr>
          </thead>
          <tbody>
            {referenciasBancarias.map((ref, idx) => {
              const err = errFilasBancarias[idx] ?? {};
              return (
                <tr key={idx}>
                  <td>
                    <input
                      value={ref.entidad || ''}
                      placeholder="Nombre de la entidad"
                      onChange={(e) => onReferenciaBancariaChange(idx, 'entidad', e.target.value)}
                      style={err.entidad ? ESTILO_CELDA_ERROR : undefined}
                    />
                    <MensajeError msg={err.entidad} />
                  </td>
                  <td>
                    <input
                      value={ref.producto || ''}
                      placeholder="Ej: Cuenta corriente, CDT"
                      onChange={(e) => onReferenciaBancariaChange(idx, 'producto', e.target.value)}
                      style={err.producto ? ESTILO_CELDA_ERROR : undefined}
                    />
                    <MensajeError msg={err.producto} />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <button type="button" className="btn btn-sm btn-outline" onClick={onAddReferenciaBancaria}>
        + Agregar referencia bancaria
      </button>

      {/* ── Operaciones en Moneda Extranjera ────────────────────────────────── */}
      <div style={{ marginTop: '20px' }}>
        <div className="form-group" style={{ maxWidth: '320px' }}>
          <label className="form-label">
            ¿Realiza Operaciones en Moneda Extranjera? <span style={{ color: 'var(--error, #e53e3e)' }}>*</span>
          </label>
          <Select
            inputId="realiza_operaciones_moneda_extranjera"
            value={monedaValue}
            onChange={handleMonedaChange}
            options={OPCIONES_MONEDA}
            isClearable
            placeholder="Seleccione..."
            noOptionsMessage={() => 'Sin opciones'}
            styles={buildSelectStyles(!!errors.realiza_operaciones_moneda_extranjera, !!monedaValue)}
          />
          <MensajeError msg={errors.realiza_operaciones_moneda_extranjera} />
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
