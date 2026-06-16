/**
 * TablaFormComponents — Primitivos de UI compartidos por tablas editables.
 *
 * DRY : fuente única de verdad para estilos y mensajes de error de tabla.
 * ISP : cada tabla importa solo los primitivos que necesita.
 * OCP : nuevos primitivos se agregan aquí sin tocar los consumidores existentes.
 *
 * NOTA: Las constantes de estilo (ESTILO_CELDA_ERROR, ESTILO_BTN_ELIMINAR) se
 * mantienen en tablaFormStyles.js (archivo .js sin JSX) y se re-exportan aquí.
 * Esto es necesario para que Vite Fast Refresh funcione correctamente: un módulo
 * .jsx solo puede exportar componentes React; mezclar valores planos con
 * componentes produce la advertencia «export is incompatible with Fast Refresh».
 */
import { getIdPropsByTipoDocumento, sanitizeIdValue } from '../utils/inputValidation';
import { LONGITUD_MAXIMA_ID } from '@shared/utils/constantes';
import { ESTILO_CELDA_ERROR, ESTILO_BTN_ELIMINAR } from './tablaFormStyles';

// Re-exportadas desde tablaFormStyles.js para que todos los importadores
// existentes sigan funcionando sin cambios.
export { ESTILO_CELDA_ERROR, ESTILO_BTN_ELIMINAR } from './tablaFormStyles';

export const HR = () => (
  <hr style={{ border: 'none', borderTop: '1px solid var(--gray-200)', margin: '24px 0' }} />
);

export const SectionTitle = ({ children, bold = false }) => (
  <h3 style={{ fontSize: '1rem', fontWeight: bold ? '800' : '600', color: 'var(--gray-800)', marginBottom: '12px' }}>
    {children}
  </h3>
);

export const SubLabel = ({ children }) => (
  <p style={{ fontSize: '0.875rem', color: 'var(--gray-600)', marginBottom: '8px' }}>
    {children}
  </p>
);

export const MensajeError = ({ msg }) =>
  msg ? (
    <span style={{ color: 'var(--error, #e53e3e)', fontSize: '0.75rem', display: 'block' }}>
      {msg}
    </span>
  ) : null;

const OPCIONES_PEP = [
  { value: 'si', label: 'Sí' },
  { value: 'no', label: 'No' },
];

export function CeldaPEP({ item, err, onChange }) {
  return (
    <>
      <td>
        <select
          value={item.es_pep || ''}
          onChange={(e) => onChange('es_pep', e.target.value)}
          style={err.es_pep ? ESTILO_CELDA_ERROR : undefined}
        >
          <option value="">-</option>
          {OPCIONES_PEP.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
      </td>
      <td>
        <input
          value={item.vinculos_pep || ''} placeholder="Describa:"
          onChange={(e) => onChange('vinculos_pep', e.target.value)}
          disabled={item.es_pep === 'no'}
          style={err.vinculos_pep ? ESTILO_CELDA_ERROR : undefined}
        />
      </td>
    </>
  );
}

const TIPOS_PRODUCTO_BANCARIO = [
  { value: 'cuenta_corriente', label: 'Cuenta corriente' },
  { value: 'cuenta_ahorros',   label: 'Cuenta ahorros'   },
];

export function CeldaToggleProducto({ valor, err, onChange }) {
  const clsWrap = ['toggle-cuenta', err ? 'toggle-cuenta--error' : ''].filter(Boolean).join(' ');
  return (
    <td>
      <div className={clsWrap}>
        {TIPOS_PRODUCTO_BANCARIO.map(({ value, label }) => {
          const activo = valor === value;
          return (
            <button
              key={value}
              type="button"
              className={['toggle-cuenta__btn', activo ? 'toggle-cuenta__btn--activo' : ''].filter(Boolean).join(' ')}
              onClick={() => onChange(activo ? '' : value)}
              aria-pressed={activo}
            >
              {label}
            </button>
          );
        })}
      </div>
      <MensajeError msg={err} />
    </td>
  );
}

export function CeldaIdentificacion({ item, err, tiposId, onTipoChange, onNumeroChange }) {
  return (
    <>
      <td>
        <select
          value={item.tipo_id || ''}
          onChange={(e) => onTipoChange(e.target.value)}
          style={err.tipo_id ? ESTILO_CELDA_ERROR : undefined}
        >
          <option value="">-</option>
          {tiposId.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
      </td>
      <td>
        <input
          value={item.numero_id || ''} placeholder="Número"
          onChange={(e) => onNumeroChange(sanitizeIdValue(e.target.value, item.tipo_id))}
          {...getIdPropsByTipoDocumento(item.tipo_id)}
          maxLength={LONGITUD_MAXIMA_ID}
          disabled={!item.tipo_id}
          style={err.numero_id ? ESTILO_CELDA_ERROR : undefined}
        />
      </td>
    </>
  );
}
