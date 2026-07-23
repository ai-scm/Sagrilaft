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
import { useState, useRef } from 'react';
import { createPortal } from 'react-dom';
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

export const EditorVinculoPepFlotante = ({
  valor,
  alGuardar,
  textoAyuda = "Describa los vínculos...",
  disabled,
  errStyle
}) => {
  const [estaAbierto, setEstaAbierto] = useState(false);
  const [valorTemporal, setValorTemporal] = useState(valor);

  const abrirEditor = () => {
    if (disabled) return;
    setValorTemporal(valor);
    setEstaAbierto(true);
  };

  const cerrarYGuardar = () => {
    alGuardar(valorTemporal);
    setEstaAbierto(false);
  };

  return (
    <>
      <div 
        onClick={abrirEditor}
        style={{
          padding: '8px',
          cursor: disabled ? 'not-allowed' : 'pointer',
          whiteSpace: 'nowrap',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          minHeight: '36px',
          border: '1px solid #d1d5db',
          borderRadius: '4px',
          backgroundColor: disabled ? '#f3f4f6' : '#ffffff',
          boxSizing: 'border-box',
          ...errStyle
        }}
        title={disabled ? "" : "Haz clic para editar"}
      >
        {valor || (!disabled && <span style={{ color: '#9ca3af' }}>{textoAyuda}</span>)}
      </div>

      {estaAbierto && createPortal(
        <div 
          onClick={cerrarYGuardar}
          style={{
            position: 'fixed',
            top: 0, left: 0, right: 0, bottom: 0,
            zIndex: 99998,
            backgroundColor: 'rgba(0, 0, 0, 0.3)', // Un poco más oscuro para modo modal centrado
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            backdropFilter: 'blur(2px)' // Efecto opcional para enfocar el modal
          }}
        >
          <div 
            onClick={(e) => e.stopPropagation()}
            style={{
              width: '500px', // Un poco más ancho ya que está centrado
              maxWidth: '90vw',
              backgroundColor: '#fff',
              boxShadow: '0 10px 35px rgba(0,0,0,0.2)',
              borderRadius: '8px',
              padding: '20px',
              display: 'flex',
              flexDirection: 'column',
              gap: '12px',
              border: '1px solid #e5e7eb'
            }}
          >
            {/* Cabecera */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h4 style={{ margin: 0, fontSize: '16px', fontWeight: '600', color: '#111827' }}>
                Editar vínculos PEP
              </h4>
              <button 
                type="button"
                onClick={cerrarYGuardar}
                style={{
                  background: 'none', border: 'none', cursor: 'pointer',
                  fontSize: '20px', color: '#6b7280', padding: '0 4px',
                  lineHeight: '1'
                }}
              >
                ✕
              </button>
            </div>

            {/* Área de texto */}
            <textarea
              autoFocus
              value={valorTemporal}
              onChange={(e) => setValorTemporal(e.target.value)}
              placeholder={textoAyuda}
              rows={6}
              style={{
                width: '100%',
                resize: 'none',
                padding: '12px',
                border: '2px solid #2563eb', 
                borderRadius: '6px',
                outline: 'none',
                fontFamily: 'inherit',
                fontSize: '14px',
                boxSizing: 'border-box',
                color: '#374151'
              }}
            />

            {/* Pie de página: Contador y botón Listo */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: '12px', color: '#6b7280' }}>
                {valorTemporal.length} caracteres
              </span>
              <button 
                type="button"
                onClick={cerrarYGuardar}
                style={{
                  backgroundColor: '#2563eb', 
                  color: '#fff', 
                  border: 'none',
                  padding: '8px 24px', 
                  borderRadius: '6px', 
                  cursor: 'pointer',
                  fontWeight: '500',
                  fontSize: '14px'
                }}
              >
                Listo
              </button>
            </div>
          </div>
        </div>,
        document.body
      )}
    </>
  );
};

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
        <EditorVinculoPepFlotante 
          valor={item.vinculos_pep || ''}
          alGuardar={(val) => onChange('vinculos_pep', val)}
          disabled={item.es_pep === 'no'}
          errStyle={err.vinculos_pep ? ESTILO_CELDA_ERROR : undefined}
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
