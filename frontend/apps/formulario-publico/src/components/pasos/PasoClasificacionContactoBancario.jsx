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
import ContactGroup from '../ContactGroup';
import { HR, SectionTitle, ESTILO_CELDA_ERROR, ESTILO_BTN_ELIMINAR, MensajeError } from '../TablaFormComponents';
import { onlyNumericKeyDown, onlyNumericPaste } from '../../utils/inputValidation';
import { SECTORES_EMPRESA } from '@shared/utils/constantes';
import { useCorreccion } from '../../context/CorreccionContext';


// ── Constantes de dominio ──────────────────────────────────────────────────────

const OPCIONES_SI_NO = [
  { value: 'true', label: 'Sí' },
  { value: 'false', label: 'No' },
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

// ── Primitivos de celda de tabla ──────────────────────────────────────────────

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

function CeldaSelect({ valor, opciones, err, onChange }) {
  return (
    <td>
      <select
        value={valor || ''}
        onChange={e => onChange(e.target.value)}
        style={err ? ESTILO_CELDA_ERROR : undefined}
      >
        <option value="">Seleccione...</option>
        {opciones.map(opt => <option key={opt.value} value={opt.value}>{opt.label}</option>)}
      </select>
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

// ── Sub-secciones (SRP por sección) ───────────────────────────────────────────

/**
 * Sección 8 — Clasificación de la empresa y régimen tributario.
 * Solo se renderiza para Persona Jurídica (condicional recibido por prop).
 */
function ClasificacionTributaria({ formData, onChange, onActividadChange, onOpenHelp, errors }) {
  const actividad = formData.actividad_clasificacion;
  const esOtraActividad = actividad === 'otra';
  const fieldProps = (name) => ({ name, value: formData[name], onChange, onOpenHelp, error: errors[name] });

  return (
    <>
      <SectionTitle>8. CLASIFICACIÓN DE LA EMPRESA Y RÉGIMEN TRIBUTARIO</SectionTitle>

      <div className="form-row">
        <FormField label="Actividad" type="select" required options={OPCIONES_ACTIVIDAD}
          {...fieldProps('actividad_clasificacion')} onChange={onActividadChange} />
        <FormField label="¿Cuál? Especifique" required disabled={!esOtraActividad}
          {...fieldProps('actividad_especifica')} />
        <FormField label="Sector" type="select" required options={SECTORES_EMPRESA}
          {...fieldProps('sector')} />
        <FormField label="Vigilado por la superintendencia de" required
          {...fieldProps('superintendencia')} />
      </div>

      <div className="form-row">
        <FormField label="Responsabilidades impuesto sobre la renta" type="select" required
          options={RESPONSABILIDADES_RENTA} {...fieldProps('responsabilidades_renta')} />
        <FormField label="Autorretenedor" type="select" required
          options={OPCIONES_SI_NO} {...fieldProps('autorretenedor')} />
        <FormField label="Responsabilidades en el impuesto sobre las ventas (IVA)" type="select" required
          options={RESPONSABILIDADES_IVA} {...fieldProps('responsabilidades_iva')} />
        <FormField label="Régimen IVA" type="select" required
          options={REGIMENES_IVA} {...fieldProps('regimen_iva')} />
        <FormField label="¿Es Gran Contribuyente?" type="select" required
          options={OPCIONES_SI_NO} {...fieldProps('gran_contribuyente')} />
      </div>

      <div className="form-row">
        <FormField label="Entidad sin Ánimo de Lucro" type="select" required
          options={OPCIONES_SI_NO} {...fieldProps('entidad_sin_animo_lucro')} />
        <FormField label="Retención de Industria y Comercio" type="select" required
          options={OPCIONES_SI_NO} {...fieldProps('retencion_ica')} />
        <FormField label="Impuesto de Industria y Comercio" type="select" required
          options={OPCIONES_SI_NO} {...fieldProps('impuesto_ica')} />
        <FormField label="Entidad Oficial" type="select" required
          options={OPCIONES_SI_NO} {...fieldProps('entidad_oficial')} />
        <FormField label="Exento de Retención en la Fuente" type="select" required
          options={OPCIONES_SI_NO} {...fieldProps('exento_retencion_fuente')} />
      </div>

      <HR />
    </>
  );
}

function ContactoAutorizado({ formData, onChange, onOpenHelp, errors }) {
  return (
    <>
      <SectionTitle>9. CONTACTO</SectionTitle>
      <ContactGroup
        titulo="Persona autorizada para recepción de órdenes de compra y de servicio"
        prefijo="contacto_ordenes"
        formData={formData} onChange={onChange} onOpenHelp={onOpenHelp} errors={errors}
      />
      <ContactGroup
        titulo="Persona autorizada para recepción de reportes de pago"
        prefijo="contacto_pagos"
        formData={formData} onChange={onChange} onOpenHelp={onOpenHelp} errors={errors}
        estiloTitulo={{ marginTop: '16px' }}
      />
      <HR />
    </>
  );
}

/**
 * Sección 10 — Información bancaria para pagos.
 * Tabla dinámica que reutiliza el mismo patrón de PasoContactosBancaria
 * (onXChange, onAddX, errFilasX) via TablaFormComponents.
 */
function InfoBancariaPagos({ infoBancariaPagos, onInfoBancariaPagosChange, onAddInfoBancariaPagos, onEliminarInfoBancariaPagos, errors }) {
  const errFilas = errors.info_bancaria_pagos_filas ?? [];
  const { camposPendientes } = useCorreccion();
  const marcada = camposPendientes.has('informacion_bancaria_pagos');

  return (
    <BloqueCorreccion marcado={marcada} titulo="10. INFORMACIÓN BANCARIA PARA PAGOS">
      <FilaError mensaje={errors.info_bancaria_pagos_tabla} />
      <div className="data-table-container">
        <table className="data-table">
          <thead>
            <tr>
              <th>Entidad Bancaria</th>
              <th>Ciudad / Oficina</th>
              <th>Tipo de Cuenta</th>
              <th>Número de Cuenta</th>
              {infoBancariaPagos.length > 1 && <th></th>}
            </tr>
          </thead>
          <tbody>
            {infoBancariaPagos.map((fila, idx) => {
              const err = errFilas[idx] ?? {};
              return (
                <tr key={idx}>
                  <CeldaTexto
                    valor={fila.entidad_bancaria} placeholder="Nombre de la entidad"
                    err={err.entidad_bancaria}
                    onChange={val => onInfoBancariaPagosChange(idx, 'entidad_bancaria', val)}
                  />
                  <CeldaTexto
                    valor={fila.ciudad_oficina} placeholder="Ciudad / Oficina"
                    err={err.ciudad_oficina}
                    onChange={val => onInfoBancariaPagosChange(idx, 'ciudad_oficina', val)}
                  />
                  <CeldaSelect
                    valor={fila.tipo_cuenta} opciones={TIPOS_CUENTA}
                    err={err.tipo_cuenta}
                    onChange={val => onInfoBancariaPagosChange(idx, 'tipo_cuenta', val)}
                  />
                  <CeldaTexto
                    valor={fila.numero_cuenta} placeholder="Número de cuenta"
                    err={err.numero_cuenta}
                    onChange={val => onInfoBancariaPagosChange(idx, 'numero_cuenta', val)}
                    inputMode="numeric"
                    onKeyDown={onlyNumericKeyDown} onPaste={onlyNumericPaste}
                  />
                  <CeldaEliminar
                    mostrar={infoBancariaPagos.length > 1}
                    onClick={() => onEliminarInfoBancariaPagos(idx)}
                    title="Eliminar cuenta"
                  />
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <button type="button" className="btn btn-sm btn-outline" onClick={onAddInfoBancariaPagos}>
        + Agregar cuenta
      </button>
    </BloqueCorreccion>
  );
}

// ── Componente orquestador del paso ───────────────────────────────────────────

export default function PasoClasificacionContactoBancario({
  formData, onChange, handleActividadChange, onOpenHelp, errors = {},
  infoBancariaPagos, onInfoBancariaPagosChange, onAddInfoBancariaPagos, onEliminarInfoBancariaPagos,
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
        onEliminarInfoBancariaPagos={onEliminarInfoBancariaPagos}
        errors={errors}
      />
    </div>
  );
}
