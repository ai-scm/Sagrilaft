import Select from 'react-select';
import FormField from '../FormField';
import { buildSelectStyles } from '../../utils/selectStyles';
import { onlyNumericKeyDown, onlyNumericPaste } from '../../utils/inputValidation';
import { HR, SectionTitle, SubLabel, ESTILO_CELDA_ERROR, ESTILO_BTN_ELIMINAR, MensajeError, CeldaToggleProducto } from '../TablaFormComponents';
import { useCorreccion } from '../../context/CorreccionContext';

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

// ── Sub-componentes ───────────────────────────────────────────────────────────

function BloqueCorreccion({ marcado, titulo, children }) {
  return (
    <div className={marcado ? 'bloque-correccion-pendiente' : ''}>
      <SectionTitle>{titulo}</SectionTitle>
      {marcado && (
        <div className="correccion-aviso" style={{ marginBottom: '8px' }}>Esta sección requiere revisión</div>
      )}
      {children}
    </div>
  );
}

function FilaError({ mensaje }) {
  if (!mensaje) return null;
  return <div className="field-error" style={{ marginBottom: '8px' }}>{mensaje}</div>;
}

function CeldaTexto({ valor, placeholder, err, onChange, ...rest }) {
  return (
    <td>
      <input
        value={valor || ''} placeholder={placeholder}
        onChange={e => onChange(e.target.value)}
        style={err ? ESTILO_CELDA_ERROR : undefined}
        {...rest}
      />
      <MensajeError msg={err} />
    </td>
  );
}

function CeldaEliminar({ mostrar, onClick, title }) {
  if (!mostrar) return null;
  return (
    <td>
      <button type="button" onClick={onClick} style={ESTILO_BTN_ELIMINAR} title={title}>×</button>
    </td>
  );
}

const clsGrupo = (pendiente, completado) =>
  ['form-group', pendiente ? 'correccion-pendiente' : completado ? 'correccion-completada' : ''].filter(Boolean).join(' ');

// ── Componente ────────────────────────────────────────────────────────────────

/**
 * Paso 6 — Referencias Comerciales, Referencias Bancarias e Info Bancaria.
 */
export default function PasoContactosBancaria({
  formData, onChange, onOpenHelp, errors = {},
  onMonedaChange, onTiposChange,
  referenciasComerciales, onReferenciaChange, onAddReferencia, onEliminarReferencia,
  referenciasBancarias,   onReferenciaBancariaChange, onAddReferenciaBancaria, onEliminarReferenciaBancaria,
}) {
  const errFilasComerciales = errors.referencias_comerciales_filas ?? [];
  const errFilasBancarias   = errors.referencias_bancarias_filas   ?? [];
  const realizaMoneda      = formData.realiza_operaciones_moneda_extranjera === 'si';
  const tiposSeleccionados  = formData.tipos_transaccion ?? [];
  const muestraCuales      = tiposSeleccionados.includes('otras');

  const handleMonedaChange = (option) => onMonedaChange(option?.value ?? '');
  const handleTiposChange  = (opciones) => onTiposChange(opciones.map(o => o.value));

  const tiposValue  = TIPOS_TRANSACCION.filter(o => tiposSeleccionados.includes(o.value));
  const monedaValue = OPCIONES_MONEDA.find(o => o.value === formData.realiza_operaciones_moneda_extranjera) ?? null;

  const { esCampoConCorreccion, camposPendientes } = useCorreccion();
  const refComercMarcada = camposPendientes.has('referencias_comerciales');
  const refBancMarcada   = camposPendientes.has('referencias_bancarias');
  const monedaMarcada    = esCampoConCorreccion('realiza_operaciones_moneda_extranjera');
  const tiposTxMarcados  = esCampoConCorreccion('tipos_transaccion');

  const monedaPendiente  = monedaMarcada && !monedaValue;
  const monedaCompletada = monedaMarcada && !!monedaValue;
  const tiposPendiente   = tiposTxMarcados && tiposValue.length === 0;
  const tiposCompletado  = tiposTxMarcados && tiposValue.length > 0;

  return (
    <div className="form-card">
      <h2 className="section-title">REFERENCIAS COMERCIALES Y BANCARIAS</h2>
      <p className="section-subtitle">Datos de contacto y referencias comerciales y bancarias</p>

      {/* ── REFERENCIAS COMERCIALES ─────────────────────────────────────────── */}
      <BloqueCorreccion marcado={refComercMarcada} titulo="REFERENCIAS COMERCIALES">
      <FilaError mensaje={errors.referencias_comerciales_tabla} />
      <div className="data-table-container">
        <table className="data-table">
          <thead>
            <tr>
              <th>Nombre del establecimiento</th>
              <th>Persona a contactar</th>
              <th>Teléfono</th>
              <th>Ciudad</th>
              {referenciasComerciales.length > 1 && <th></th>}
            </tr>
          </thead>
          <tbody>
            {referenciasComerciales.map((ref, idx) => {
              const err = errFilasComerciales[idx] ?? {};
              return (
                <tr key={idx}>
                  <CeldaTexto
                    valor={ref.nombre_establecimiento} placeholder="Nombre del establecimiento"
                    err={err.nombre_establecimiento}
                    onChange={val => onReferenciaChange(idx, 'nombre_establecimiento', val)}
                  />
                  <CeldaTexto
                    valor={ref.persona_contacto} placeholder="Nombre completo"
                    err={err.persona_contacto}
                    onChange={val => onReferenciaChange(idx, 'persona_contacto', val)}
                  />
                  <CeldaTexto
                    valor={ref.telefono} placeholder="Teléfono"
                    err={err.telefono}
                    onChange={val => onReferenciaChange(idx, 'telefono', val)}
                    inputMode="numeric"
                    onKeyDown={onlyNumericKeyDown} onPaste={onlyNumericPaste}
                  />
                  <CeldaTexto
                    valor={ref.ciudad} placeholder="Ciudad"
                    err={err.ciudad}
                    onChange={val => onReferenciaChange(idx, 'ciudad', val)}
                  />
                  <CeldaEliminar
                    mostrar={referenciasComerciales.length > 1}
                    onClick={() => onEliminarReferencia(idx)}
                    title="Aqui puedes eliminar referencia comercial"
                  />
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <button type="button" className="btn btn-sm btn-outline" onClick={onAddReferencia} required>
        + Agregar referencia
      </button>
      </BloqueCorreccion>

      <HR />

      {/* ── REFERENCIAS BANCARIAS ───────────────────────────────────────────── */}
      <BloqueCorreccion marcado={refBancMarcada} titulo="REFERENCIAS BANCARIAS">
      <FilaError mensaje={errors.referencias_bancarias_tabla} />
      <div className="data-table-container">
        <table className="data-table">
          <thead>
            <tr>
              <th>Entidad</th>
              <th>Producto</th>
              {referenciasBancarias.length > 1 && <th></th>}
            </tr>
          </thead>
          <tbody>
            {referenciasBancarias.map((ref, idx) => {
              const err = errFilasBancarias[idx] ?? {};
              return (
                <tr key={idx}>
                  <CeldaTexto
                    valor={ref.entidad} placeholder="Nombre de la entidad"
                    err={err.entidad}
                    onChange={val => onReferenciaBancariaChange(idx, 'entidad', val)}
                  />
                  <CeldaToggleProducto
                    valor={ref.producto}
                    err={err.producto}
                    onChange={val => onReferenciaBancariaChange(idx, 'producto', val)}
                  />
                  <CeldaEliminar
                    mostrar={referenciasBancarias.length > 1}
                    onClick={() => onEliminarReferenciaBancaria(idx)}
                    title="Aqui puedes eliminar referencia bancaria"
                  />
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <button type="button" className="btn btn-sm btn-outline" onClick={onAddReferenciaBancaria}>
        + Agregar referencia bancaria
      </button>
      </BloqueCorreccion>

      {/* ── Operaciones en Moneda Extranjera ────────────────────────────────── */}
      <div style={{ marginTop: '20px' }}>
        <div
          className={clsGrupo(monedaPendiente, monedaCompletada)}
          style={{ maxWidth: '320px' }}
        >
          <label className="form-label">
            ¿Realiza Operaciones en Moneda Extranjera? <span style={{ color: 'var(--error, #e53e3e)' }}>*</span>
            {monedaPendiente  && <span className="correccion-mark"    title="Este campo requiere corrección" aria-label="Requiere corrección">✎</span>}
            {monedaCompletada && <span className="correccion-ok-mark" title="Corrección completada"          aria-label="Corregido">✓</span>}
          </label>
          <Select
            inputId="realiza_operaciones_moneda_extranjera"
            value={monedaValue}
            onChange={handleMonedaChange}
            options={OPCIONES_MONEDA}
            isClearable
            placeholder="Seleccione..."
            noOptionsMessage={() => 'Sin opciones'}
            styles={buildSelectStyles(!!errors.realiza_operaciones_moneda_extranjera, !!monedaValue, monedaPendiente)}
          />
          <MensajeError msg={errors.realiza_operaciones_moneda_extranjera} />
          {monedaPendiente  && !errors.realiza_operaciones_moneda_extranjera && <div className="correccion-aviso">Este campo requiere corrección</div>}
          {monedaCompletada && <div className="correccion-aviso correccion-aviso--ok">Corrección completada</div>}
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

            <div
              className={clsGrupo(tiposPendiente, tiposCompletado)}
              style={{ marginTop: '12px' }}
            >
              <SubLabel>
                Si su actividad implica transacciones en moneda extranjera, señale los tipos de transacción:
                {tiposPendiente  && <span className="correccion-mark"    title="Este campo requiere corrección" aria-label="Requiere corrección">✎</span>}
                {tiposCompletado && <span className="correccion-ok-mark" title="Corrección completada"          aria-label="Corregido">✓</span>}
              </SubLabel>
              <Select
                inputId="tipos_transaccion"
                isMulti
                value={tiposValue}
                onChange={handleTiposChange}
                options={TIPOS_TRANSACCION}
                placeholder="Seleccione uno o más tipos..."
                noOptionsMessage={() => 'Sin opciones'}
                styles={buildSelectStyles(false, tiposValue.length > 0, tiposPendiente)}
              />
              {tiposPendiente  && <div className="correccion-aviso">Este campo requiere corrección</div>}
              {tiposCompletado && <div className="correccion-aviso correccion-aviso--ok">Corrección completada</div>}
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
