/**
 * ControlsPaginacion — Componente UI para controles de navegación de paginación
 *
 * Renderiza:
 * - Información: página actual / total de páginas y rango de elementos mostrados
 * - Botones: anterior, siguiente
 * - Campo de entrada: saltar a página específica
 *
 * Uso:
 *   const paginacion = usePaginacion(elementos, 5);
 *   <ControlsPaginacion {...paginacion} />
 */

const s = {
  contenedor: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: '16px',
    padding: '12px 0',
    flexWrap: 'wrap',
    fontSize: '0.85rem',
    color: 'var(--gray-600, #475569)',
  },

  info: {
    display: 'flex',
    gap: '16px',
    alignItems: 'center',
    flexWrap: 'wrap',
  },

  textoInfo: {
    margin: 0,
    fontSize: '0.85rem',
    fontWeight: '500',
  },

  controles: {
    display: 'flex',
    gap: '8px',
    alignItems: 'center',
  },

  boton: {
    padding: '6px 12px',
    border: '1.5px solid var(--gray-200, #e2e8f0)',
    background: '#fff',
    borderRadius: 'var(--radius-sm, 6px)',
    cursor: 'pointer',
    fontSize: '0.8rem',
    fontWeight: '600',
    color: 'var(--gray-700, #334155)',
    transition: 'all 0.15s',
  },

  botonDeshabilitado: {
    opacity: '0.5',
    cursor: 'not-allowed',
  },

  botonHover: {
    background: 'var(--gray-50, #f8fafc)',
    borderColor: 'var(--gray-300, #cbd5e1)',
  },

  inputSaltar: {
    width: '45px',
    padding: '6px 8px',
    border: '1.5px solid var(--gray-200, #e2e8f0)',
    borderRadius: 'var(--radius-sm, 6px)',
    fontSize: '0.8rem',
    textAlign: 'center',
    fontWeight: '600',
  },
};

export default function ControlsPaginacion({
  paginaActual,
  totalPaginas,
  totalElementos,
  indiceInicio,
  indiceFin,
  esPromeraraPage,
  esUltimaPagina,
  hayMultiplesPaginas,
  irAPaginaAnterior,
  irAPaginaSiguiente,
  irAPagina,
}) {
  // Si no hay múltiples páginas, no muestra controles
  if (!hayMultiplesPaginas) {
    return null;
  }

  const handleSaltar = (e) => {
    const valor = parseInt(e.target.value, 10);
    if (!isNaN(valor)) {
      irAPagina(valor);
    }
  };

  return (
    <div style={s.contenedor}>
      {/* Información de la página actual */}
      <div style={s.info}>
        <p style={s.textoInfo}>
          Mostrando {indiceInicio + 1}–{Math.min(indiceFin, totalElementos)} de {totalElementos}
        </p>
        <span style={{ color: 'var(--gray-400, #94a3b8)' }}>•</span>
        <p style={s.textoInfo}>
          Página {paginaActual} de {totalPaginas}
        </p>
      </div>

      {/* Controles de navegación */}
      <div style={s.controles}>
        {/* Botón anterior */}
        <button
          style={{
            ...s.boton,
            ...(esPromeraraPage ? s.botonDeshabilitado : {}),
          }}
          onClick={irAPaginaAnterior}
          disabled={esPromeraraPage}
          type="button"
          title="Ir a página anterior"
        >
          ← Anterior
        </button>

        {/* Campo para saltar a página */}
        <input
          style={s.inputSaltar}
          type="number"
          min="1"
          max={totalPaginas}
          value={paginaActual}
          onChange={handleSaltar}
          title="Saltar a página"
          aria-label="Ir a página"
        />

        {/* Botón siguiente */}
        <button
          style={{
            ...s.boton,
            ...(esUltimaPagina ? s.botonDeshabilitado : {}),
          }}
          onClick={irAPaginaSiguiente}
          disabled={esUltimaPagina}
          type="button"
          title="Ir a página siguiente"
        >
          Siguiente →
        </button>
      </div>
    </div>
  );
}
