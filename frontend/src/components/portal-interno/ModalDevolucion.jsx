/**
 * ModalDevolucion — panel para devolver un formulario SAGRILAFT al remitente.
 *
 * El usuario del portal especifica qué debe corregirse o completarse y puede
 * seleccionar los campos específicos del formulario que requieren atención.
 * Al confirmar, el sistema cambia el estado a EN_CORRECCION y notifica
 * al destinatario registrado por correo electrónico.
 */

import { useState, useMemo } from 'react';
import { api } from '../../services/api';
import { CATALOGO_CORRECCIONES } from '../../data/catalogoCorrecciones';

const LONGITUD_MINIMA_ESPECIFICACIONES = 20;
const LONGITUD_MAXIMA_ESPECIFICACIONES = 2000;

// ── Sub-componente: selector de campos ────────────────────────────────────────

const sSelector = {
  contenedor: {
    marginTop: '20px',
  },
  etiqueta: {
    display:    'block',
    fontSize:   '0.8rem',
    fontWeight: '700',
    color:      'var(--gray-700, #334155)',
    marginBottom: '8px',
    letterSpacing: '0.03em',
  },
  descripcion: {
    fontSize:   '0.78rem',
    color:      'var(--gray-500, #64748b)',
    margin:     '0 0 12px',
    lineHeight: 1.4,
  },
  grupo: {
    marginBottom: '12px',
    border:       '1px solid var(--gray-200, #e2e8f0)',
    borderRadius: 'var(--radius-sm, 6px)',
    overflow:     'hidden',
  },
  grupoTitulo: {
    fontSize:     '0.75rem',
    fontWeight:   '700',
    color:        'var(--gray-600, #475569)',
    background:   'var(--gray-50, #f8fafc)',
    padding:      '7px 12px',
    margin:       0,
    borderBottom: '1px solid var(--gray-200, #e2e8f0)',
    textTransform: 'uppercase',
    letterSpacing: '0.05em',
  },
  grupoBoton: {
    display:       'flex',
    alignItems:    'center',
    justifyContent: 'space-between',
    width:         '100%',
    border:        'none',
    cursor:        'pointer',
    textAlign:     'left',
  },
  grupoMeta: {
    display:    'flex',
    alignItems: 'center',
    gap:        '6px',
    flexShrink: 0,
  },
  badgeSeleccionados: {
    display:       'inline-flex',
    alignItems:    'center',
    justifyContent: 'center',
    minWidth:      '18px',
    height:        '18px',
    padding:       '0 5px',
    borderRadius:  '9px',
    background:    '#ea580c',
    color:         '#fff',
    fontSize:      '0.7rem',
    fontWeight:    '700',
  },
  chevron: {
    display:    'inline-block',
    transition: 'transform 0.2s',
    fontSize:   '0.8rem',
    color:      'var(--gray-400, #94a3b8)',
  },
  chevronAbierto: {
    transform: 'rotate(90deg)',
  },
  camposLista: {
    display:             'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))',
    gap:                 '2px',
    padding:             '8px',
  },
  campoItem: {
    display:    'flex',
    alignItems: 'center',
    gap:        '6px',
    padding:    '5px 8px',
    borderRadius: '4px',
    cursor:     'pointer',
    userSelect: 'none',
    transition: 'background 0.1s',
  },
  campoItemSeleccionado: {
    background: '#fff7ed',
  },
  checkbox: {
    width:  '14px',
    height: '14px',
    accentColor: '#ea580c',
    cursor: 'pointer',
    flexShrink: 0,
  },
  campoLabel: {
    fontSize: '0.8rem',
    color:    'var(--gray-700, #334155)',
    cursor:   'pointer',
  },
  contadorSeleccionados: {
    fontSize:   '0.75rem',
    color:      '#ea580c',
    fontWeight: '600',
    marginTop:  '6px',
  },
};

function GrupoAcordeon({ grupo, seleccionados, onToggle }) {
  const tieneCamposSeleccionados = grupo.campos.some(campo => seleccionados.has(campo.id));
  const [abierto, setAbierto] = useState(tieneCamposSeleccionados);

  const cantidadSeleccionados = useMemo(
    () => grupo.campos.filter(campo => seleccionados.has(campo.id)).length,
    [grupo.campos, seleccionados],
  );

  return (
    <div style={sSelector.grupo}>
      <button
        type="button"
        style={{ ...sSelector.grupoTitulo, ...sSelector.grupoBoton }}
        onClick={() => setAbierto(v => !v)}
        aria-expanded={abierto}
      >
        <span>Paso {grupo.paso} — {grupo.etiqueta}</span>
        <span style={sSelector.grupoMeta}>
          {cantidadSeleccionados > 0 && (
            <span style={sSelector.badgeSeleccionados}>{cantidadSeleccionados}</span>
          )}
          <span style={{ ...sSelector.chevron, ...(abierto ? sSelector.chevronAbierto : {}) }}>▸</span>
        </span>
      </button>

      {abierto && (
        <div style={sSelector.camposLista}>
          {grupo.campos.map(campo => {
            const marcado = seleccionados.has(campo.id);
            return (
              <label
                key={campo.id}
                style={{ ...sSelector.campoItem, ...(marcado ? sSelector.campoItemSeleccionado : {}) }}
              >
                <input
                  type="checkbox"
                  style={sSelector.checkbox}
                  checked={marcado}
                  onChange={() => onToggle(campo.id)}
                />
                <span style={sSelector.campoLabel}>{campo.etiqueta}</span>
              </label>
            );
          })}
        </div>
      )}
    </div>
  );
}

function SelectorCamposCorreccion({ seleccionados, onChange }) {
  function toggleCampo(id) {
    const nuevaSeleccion = new Set(seleccionados);
    if (nuevaSeleccion.has(id)) {
      nuevaSeleccion.delete(id);
    } else {
      nuevaSeleccion.add(id);
    }
    onChange(nuevaSeleccion);
  }

  const sufijo = seleccionados.size !== 1 ? 's' : '';

  return (
    <div style={sSelector.contenedor}>
      <span style={sSelector.etiqueta}>Campos específicos que requieren corrección</span>
      <p style={sSelector.descripcion}>
        Opcional — selecciona los campos para que el destinatario los vea resaltados en el formulario.
      </p>

      {CATALOGO_CORRECCIONES.map(grupo => (
        <GrupoAcordeon
          key={grupo.paso}
          grupo={grupo}
          seleccionados={seleccionados}
          onToggle={toggleCampo}
        />
      ))}

      {seleccionados.size > 0 && (
        <p style={sSelector.contadorSeleccionados}>
          {seleccionados.size} campo{sufijo} seleccionado{sufijo}
        </p>
      )}
    </div>
  );
}

// ── Estilos ───────────────────────────────────────────────────────────────────

const s = {
  fondo: {
    position:        'fixed',
    inset:           0,
    background:      'rgba(15, 23, 42, 0.5)',
    display:         'flex',
    alignItems:      'center',
    justifyContent:  'center',
    zIndex:          200,
    padding:         '16px',
  },
  modal: {
    background:   '#fff',
    borderRadius: 'var(--radius-md, 10px)',
    boxShadow:    '0 20px 60px rgba(0,0,0,0.2)',
    width:        '100%',
    maxWidth:     '560px',
    maxHeight:    '90vh',
    overflowY:    'auto',
    display:      'flex',
    flexDirection: 'column',
  },
  encabezado: {
    padding:      '24px 24px 0',
  },
  titulo: {
    fontSize:   '1.15rem',
    fontWeight: '800',
    color:      'var(--gray-900, #0f172a)',
    margin:     '0 0 8px',
  },
  descripcion: {
    fontSize:    '0.85rem',
    color:       'var(--gray-500, #64748b)',
    margin:      '0 0 24px',
    lineHeight:  1.5,
  },
  cuerpo: {
    padding:    '0 24px',
    flex:       1,
  },
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
  bannerError: {
    marginTop:    '16px',
    padding:      '10px 14px',
    background:   '#fef2f2',
    border:       '1px solid #fca5a5',
    borderRadius: 'var(--radius-sm, 6px)',
    fontSize:     '0.85rem',
    color:        '#dc2626',
  },
  pie: {
    display:        'flex',
    justifyContent: 'flex-end',
    gap:            '10px',
    padding:        '20px 24px 24px',
    borderTop:      '1px solid var(--gray-100, #f1f5f9)',
    marginTop:      '20px',
  },
  btnCancelar: {
    padding:      '9px 20px',
    background:   '#fff',
    color:        'var(--gray-600, #475569)',
    border:       '1.5px solid var(--gray-300, #cbd5e1)',
    borderRadius: 'var(--radius-sm, 6px)',
    fontSize:     '0.88rem',
    fontWeight:   '600',
    cursor:       'pointer',
  },
  btnConfirmar: {
    padding:      '9px 20px',
    background:   '#c2410c',
    color:        '#fff',
    border:       'none',
    borderRadius: 'var(--radius-sm, 6px)',
    fontSize:     '0.88rem',
    fontWeight:   '700',
    cursor:       'pointer',
    transition:   'opacity 0.15s',
  },
  btnDeshabilitado: {
    opacity:  0.5,
    cursor:   'not-allowed',
  },
};

// ── Componente ────────────────────────────────────────────────────────────────

export default function ModalDevolucion({ visible, formularioId, onDevuelto, onCancelar }) {
  const [especificaciones, setEspecificaciones]     = useState('');
  const [camposSeleccionados, setCamposSeleccionados] = useState(new Set());
  const [enfocado, setEnfocado]                     = useState(false);
  const [enviando, setEnviando]                     = useState(false);
  const [error, setError]                           = useState(null);

  function resetearEstado() {
    setEspecificaciones('');
    setCamposSeleccionados(new Set());
    setError(null);
  }

  function limpiarYCerrar() {
    resetearEstado();
    onCancelar();
  }

  function validarEspecificaciones() {
    const longitudTexto = especificaciones.trim().length;
    if (longitudTexto < LONGITUD_MINIMA_ESPECIFICACIONES) {
      return `Mínimo ${LONGITUD_MINIMA_ESPECIFICACIONES} caracteres (actual: ${longitudTexto}).`;
    }
    return null;
  }

  async function handleConfirmar() {
    const errorValidacion = validarEspecificaciones();
    if (errorValidacion) {
      setError(errorValidacion);
      return;
    }

    setEnviando(true);
    setError(null);

    try {
      await api.devolverExpediente(formularioId, {
        especificaciones:    especificaciones.trim(),
        campos_identificados: [...camposSeleccionados],
      });
      resetearEstado();
      onDevuelto();
    } catch (errorDevolucion) {
      setError(errorDevolucion.message || 'Error al procesar la devolución. Intente nuevamente.');
    } finally {
      setEnviando(false);
    }
  }

  if (!visible) return null;

  const longitudActual   = especificaciones.trim().length;
  const especificacionesValidas = longitudActual >= LONGITUD_MINIMA_ESPECIFICACIONES;
  const textoBoton       = enviando ? 'Enviando devolución…' : 'Confirmar devolución';

  return (
    <div style={s.fondo} role="dialog" aria-modal="true" aria-labelledby="titulo-modal-devolucion">
      <div style={s.modal}>

        {/* Encabezado */}
        <div style={s.encabezado}>
          <h2 style={s.titulo} id="titulo-modal-devolucion">
            Devolver formulario para corrección
          </h2>
          <p style={s.descripcion}>
            El destinatario recibirá un correo con las especificaciones indicadas
            y podrá acceder al formulario para corregir o completar la información solicitada.
          </p>
        </div>

        {/* Cuerpo */}
        <div style={s.cuerpo}>

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
            disabled={enviando}
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
          />

          {/* Vista previa del correo */}
          <div style={s.vistaPreviaContenedor}>
            <p style={s.vistaPreviaTitulo}>Vista previa del correo al destinatario</p>
            <div style={s.vistaPrevia}>
              <p style={s.vistaPreviaIntroduccion}>
                Usted ha sido requerido para completar/modificar la siguiente información
                del formulario:
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

          {/* Banner de error */}
          {error && <div style={s.bannerError}>{error}</div>}

        </div>

        {/* Pie con acciones */}
        <div style={s.pie}>
          <button
            style={s.btnCancelar}
            onClick={limpiarYCerrar}
            disabled={enviando}
            type="button"
          >
            Cancelar
          </button>
          <button
            style={{
              ...s.btnConfirmar,
              ...(!especificacionesValidas || enviando ? s.btnDeshabilitado : {}),
            }}
            onClick={handleConfirmar}
            disabled={!especificacionesValidas || enviando}
            type="button"
          >
            {textoBoton}
          </button>
        </div>

      </div>
    </div>
  );
}
