import { useState, useMemo } from 'react';
import { CATALOGO_CORRECCIONES } from '@shared/data/catalogoCorrecciones';

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

export default function SelectorCamposCorreccion({ seleccionados, onChange, tipoPersona }) {
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
  const gruposVisibles = useMemo(() => {
    const esPersonaJuridica = (tipoPersona || '').toLowerCase() === 'juridica';
    return esPersonaJuridica
      ? CATALOGO_CORRECCIONES
      : CATALOGO_CORRECCIONES.filter(grupo => grupo.paso !== 4);
  }, [tipoPersona]);

  return (
    <div style={sSelector.contenedor}>
      <span style={sSelector.etiqueta}>Campos específicos que requieren corrección o actualización</span>
      <p style={sSelector.descripcion}>
        Opcional — selecciona los campos para que el destinatario los vea resaltados en el formulario.
      </p>

      {gruposVisibles.map(grupo => (
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
