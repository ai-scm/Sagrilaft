import { useState } from 'react';
import SelectorCamposCorreccion from './SelectorCamposCorreccion';

const LONGITUD_MINIMA_ESPECIFICACIONES = 20;
const LONGITUD_MAXIMA_ESPECIFICACIONES = 2000;

const s = {
  etiqueta: {
    display:    'block',
    fontSize:   '0.8rem',
    fontWeight: '700',
    color:      'var(--gray-700, #334155)',
    marginBottom: '6px',
    letterSpacing: '0.03em',
  },
  textarea: {
    width:        '100%',
    padding:      '10px 12px',
    borderWidth:  '1.5px',
    borderStyle:  'solid',
    borderColor:  'var(--gray-300, #cbd5e1)',
    borderRadius: 'var(--radius-sm, 6px)',
    fontSize:     '0.88rem',
    lineHeight:   1.6,
    color:        'var(--gray-900, #0f172a)',
    resize:       'vertical',
    fontFamily:   'inherit',
    boxSizing:    'border-box',
    outline:      'none',
    transition:   'border-color 0.15s',
  },
  textareaActivo: {
    borderColor: 'var(--primary-500, #3b82f6)',
  },
  contadorCaracteres: {
    display:        'flex',
    justifyContent: 'space-between',
    alignItems:     'center',
    marginTop:      '5px',
    fontSize:       '0.75rem',
    color:          'var(--gray-400, #94a3b8)',
  },
  avisoMinimo: {
    color: 'var(--orange-600, #ea580c)',
  },
  vistaPreviaContenedor: {
    marginTop:     '20px',
    marginBottom:  '4px',
  },
  vistaPreviaTitulo: {
    fontSize:    '0.75rem',
    fontWeight:  '700',
    color:       'var(--gray-500, #64748b)',
    textTransform: 'uppercase',
    letterSpacing: '0.06em',
    margin:      '0 0 8px',
  },
  vistaPrevia: {
    background:   '#fffbeb',
    border:       '1px solid #fde68a',
    borderRadius: 'var(--radius-sm, 6px)',
    padding:      '14px 16px',
  },
  vistaPreviaIntroduccion: {
    fontSize:   '0.83rem',
    color:      '#78350f',
    margin:     '0 0 10px',
    lineHeight: 1.5,
  },
  vistaPreviaEspecificaciones: {
    fontSize:    '0.83rem',
    color:       '#92400e',
    fontStyle:   'normal',
    whiteSpace:  'pre-wrap',
    wordBreak:   'break-word',
    margin:      0,
    padding:     '8px 10px',
    background:  '#fef3c7',
    borderRadius: '4px',
    minHeight:   '32px',
  },
};

export default function FormularioEspecificacionesCorreccion({
  especificaciones,
  setEspecificaciones,
  camposSeleccionados,
  setCamposSeleccionados,
  tipoPersona,
  deshabilitado,
  introduccionVistaPrevia = "Usted ha sido requerido para completar/modificar la siguiente información del formulario:",
}) {
  const [enfocado, setEnfocado] = useState(false);

  const longitudActual = especificaciones.trim().length;
  const especificacionesValidas = longitudActual >= LONGITUD_MINIMA_ESPECIFICACIONES;

  return (
    <>
      {/* Campo de especificaciones */}
      <label style={s.etiqueta} htmlFor="campo-especificaciones-correccion">
        Especificaciones de corrección
      </label>
      <textarea
        id="campo-especificaciones-correccion"
        style={{ ...s.textarea, ...(enfocado ? s.textareaActivo : {}) }}
        value={especificaciones}
        onChange={e => setEspecificaciones(e.target.value)}
        onFocus={() => setEnfocado(true)}
        onBlur={() => setEnfocado(false)}
        placeholder="Describa exactamente qué información debe corregirse o completarse en el formulario…"
        rows={6}
        maxLength={LONGITUD_MAXIMA_ESPECIFICACIONES}
        disabled={deshabilitado}
      />
      <div style={s.contadorCaracteres}>
        <span>{longitudActual} / {LONGITUD_MAXIMA_ESPECIFICACIONES}</span>
        {!especificacionesValidas && longitudActual > 0 && (
          <span style={s.avisoMinimo}>
            Mínimo {LONGITUD_MINIMA_ESPECIFICACIONES} caracteres
          </span>
        )}
      </div>

      {/* Selector de campos específicos */}
      <SelectorCamposCorreccion
        seleccionados={camposSeleccionados}
        onChange={setCamposSeleccionados}
        tipoPersona={tipoPersona}
      />

      {/* Vista previa del correo */}
      <div style={s.vistaPreviaContenedor}>
        <p style={s.vistaPreviaTitulo}>Vista previa del correo al destinatario</p>
        <div style={s.vistaPrevia}>
          <p style={s.vistaPreviaIntroduccion}>
            {introduccionVistaPrevia}
          </p>
          <p style={s.vistaPreviaEspecificaciones}>
            {especificaciones.trim() || (
              <span style={{ color: '#b45309', fontStyle: 'italic' }}>
                Las especificaciones aparecerán aquí…
              </span>
            )}
          </p>
        </div>
      </div>
    </>
  );
}
