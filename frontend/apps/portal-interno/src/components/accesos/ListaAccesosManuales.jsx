import { useState, useEffect, useCallback } from 'react';
import { api } from '../../services/api';
import BadgeEstadoAcceso from '../badges/BadgeEstadoAcceso';
import { estilosBandeja } from '../ui/listaStyles';
import Spinner from '@shared/components/ui/Spinner';
import Alert from '@shared/components/ui/Alert';
import {
  ESTADOS_ACCESO,
  TIPOS_CONTRAPARTE,
  AREAS_RESPONSABLES,
  ETIQUETA_TIPO_CONTRAPARTE,
  ETIQUETA_AREA_RESPONSABLE,
  formatearFechaCorta,
  generarTextoConteo,
} from '../../config/constantes';

// ── Constantes de filtrado ────────────────────────────────────────────────────

const FILTRO_TODOS = '';

const FILTROS_VACIOS = { estado: FILTRO_TODOS, area: FILTRO_TODOS, tipo: FILTRO_TODOS };

// ── Lógica de filtrado ────────────────────────────────────────────────────────

function aplicarFiltros(accesos, { estado, area, tipo }) {
  return accesos
    .filter(a => !estado || a.estado_acceso    === estado)
    .filter(a => !area   || a.area_responsable === area)
    .filter(a => !tipo   || a.tipo_contraparte === tipo);
}

function hayFiltrosActivos(filtros) {
  return Object.values(filtros).some(v => v !== FILTRO_TODOS);
}

// ── Utilidades de presentación ────────────────────────────────────────────────

function obtenerEtiqueta(mapaEtiquetas, valor) {
  return mapaEtiquetas[valor] ?? valor;
}

function formatearEtiquetaFechaLimite(acceso) {
  switch (acceso.estado_acceso) {
    case 'consumido':
      return acceso.consumed_at
        ? `Enviado el ${formatearFechaCorta(acceso.consumed_at)}`
        : 'Enviado';
    case 'expirado':
      return `Venció el ${formatearFechaCorta(acceso.expires_at)}`;
    default:
      return `Vence el ${formatearFechaCorta(acceso.expires_at)}`;
  }
}

// ── Estilos ───────────────────────────────────────────────────────────────────

const s = {
  ...estilosBandeja,
  titulo: {
    fontSize:   '0.9rem',
    fontWeight: '600',
    color:      'var(--gray-700, #334155)',
    margin:     0,
  },
  barraFiltros: {
    ...estilosBandeja.barraFiltros,
    paddingBottom: '4px',
  },
  selectFiltro: estilosBandeja.selectFiltro,
  btnLimpiarFiltros: {
    padding:      '6px 12px',
    background:   'transparent',
    color:        'var(--gray-500, #64748b)',
    border:       '1.5px solid var(--gray-200, #e2e8f0)',
    borderRadius: 'var(--radius-sm, 6px)',
    fontSize:     '0.8rem',
    cursor:       'pointer',
  },
  tarjeta: {
    background:    '#fff',
    borderRadius:  'var(--radius-md, 8px)',
    border:        '1px solid var(--gray-200, #e2e8f0)',
    padding:       '16px 20px',
    display:       'flex',
    flexDirection: 'column',
    gap:           '6px',
  },
  tarjetaExpirada: {
    borderColor: '#fca5a5',
    background:  '#fff9f9',
  },
  filaSuperior: {
    display:        'flex',
    alignItems:     'center',
    justifyContent: 'space-between',
    gap:            '12px',
    flexWrap:       'wrap',
  },
  filaCodigo: {
    display:    'flex',
    alignItems: 'center',
    gap:        '10px',
    flexWrap:   'wrap',
  },
  codigo: {
    fontSize:      '0.9rem',
    fontWeight:    '700',
    color:         'var(--gray-900, #0f172a)',
    fontFamily:    'monospace',
    letterSpacing: '0.06em',
  },
  razonSocial: {
    fontSize:   '0.88rem',
    fontWeight: '600',
    color:      'var(--gray-800, #1e293b)',
  },
  metadatos: {
    display:    'flex',
    gap:        '16px',
    flexWrap:   'wrap',
    alignItems: 'center',
  },
  chip: {
    fontSize:     '0.75rem',
    color:        'var(--gray-500, #64748b)',
    background:   'var(--gray-50, #f8fafc)',
    border:       '1px solid var(--gray-200, #e2e8f0)',
    borderRadius: '999px',
    padding:      '2px 10px',
    whiteSpace:   'nowrap',
  },
  chipPendiente: {
    fontSize:     '0.75rem',
    color:        '#1e40af',
    background:   '#eff6ff',
    border:       '1px solid #bfdbfe',
    borderRadius: '999px',
    padding:      '2px 10px',
    whiteSpace:   'nowrap',
    fontStyle:    'italic',
  },
  fechaLimite: (estado) => ({
    fontSize:   '0.75rem',
    fontWeight: '500',
    color:      estado === 'expirado' ? '#dc2626' : 'var(--gray-500, #64748b)',
    whiteSpace: 'nowrap',
  }),
  estadoVacio: estilosBandeja.estadoVacio,
};

// ── Sub-componente: barra de filtros ──────────────────────────────────────────

function BarraFiltros({ filtros, onCambiar, onLimpiar }) {
  return (
    <div style={s.barraFiltros}>
      <select
        style={s.selectFiltro}
        value={filtros.estado}
        onChange={e => onCambiar('estado', e.target.value)}
      >
        <option value={FILTRO_TODOS}>Todos los estados</option>
        {ESTADOS_ACCESO.map(({ valor, etiqueta }) => (
          <option key={valor} value={valor}>{etiqueta}</option>
        ))}
      </select>

      <select
        style={s.selectFiltro}
        value={filtros.area}
        onChange={e => onCambiar('area', e.target.value)}
      >
        <option value={FILTRO_TODOS}>Todas las áreas</option>
        {AREAS_RESPONSABLES.map(({ valor, etiqueta }) => (
          <option key={valor} value={valor}>{etiqueta}</option>
        ))}
      </select>

      <select
        style={s.selectFiltro}
        value={filtros.tipo}
        onChange={e => onCambiar('tipo', e.target.value)}
      >
        <option value={FILTRO_TODOS}>Todos los tipos</option>
        {TIPOS_CONTRAPARTE.map(({ valor, etiqueta }) => (
          <option key={valor} value={valor}>{etiqueta}</option>
        ))}
      </select>

      {hayFiltrosActivos(filtros) && (
        <button style={s.btnLimpiarFiltros} type="button" onClick={onLimpiar}>
          Limpiar filtros
        </button>
      )}
    </div>
  );
}

// ── Sub-componente: tarjeta individual ───────────────────────────────────────

function TarjetaAccesoManual({ acceso }) {
  const tipoLabel      = obtenerEtiqueta(ETIQUETA_TIPO_CONTRAPARTE, acceso.tipo_contraparte);
  const areaLabel      = obtenerEtiqueta(ETIQUETA_AREA_RESPONSABLE, acceso.area_responsable);
  const accesoExpirado = acceso.estado_acceso === 'expirado';
  const estiloTarjeta  = accesoExpirado ? { ...s.tarjeta, ...s.tarjetaExpirada } : s.tarjeta;

  return (
    <div style={estiloTarjeta}>
      <div style={s.filaSuperior}>
        <div style={s.filaCodigo}>
          <span style={s.codigo}>{acceso.codigo_peticion}</span>
          <span style={s.razonSocial}>{acceso.razon_social}</span>
        </div>
        <BadgeEstadoAcceso estado={acceso.estado_acceso} />
      </div>

      <div style={s.metadatos}>
        <span style={s.chip}>{tipoLabel}</span>
        <span style={s.chip}>{areaLabel}</span>
        {acceso.correo_destinatario
          ? <span style={s.chip}>{acceso.correo_destinatario}</span>
          : <span style={s.chipPendiente}>⏳ Pendiente de correo</span>
        }
        <span style={s.fechaLimite(acceso.estado_acceso)}>
          {formatearEtiquetaFechaLimite(acceso)}
        </span>
      </div>
    </div>
  );
}

// ── Componente principal ──────────────────────────────────────────────────────

const MENSAJE_VACIO_DEFAULT  = 'No hay accesos creados aún.';
const MENSAJE_SIN_RESULTADOS = 'Ningún acceso coincide con los filtros seleccionados.';

export default function ListaAccesosManuales({ mensajeVacio = MENSAJE_VACIO_DEFAULT }) {
  const [accesosManuales, setAccesosManuales] = useState([]);
  const [cargando, setCargando]               = useState(true);
  const [error, setError]                     = useState(null);
  const [filtros, setFiltros]                 = useState(FILTROS_VACIOS);

  const cargarAccesos = useCallback(async () => {
    setCargando(true);
    setError(null);
    try {
      const datos = await api.listarAccesosManuales();
      setAccesosManuales(datos);
    } catch {
      setError('No se pudieron cargar los accesos. Intente nuevamente.');
    } finally {
      setCargando(false);
    }
  }, []);

  useEffect(() => { cargarAccesos(); }, [cargarAccesos]);

  function actualizarFiltro(campo, valor) {
    setFiltros(prev => ({ ...prev, [campo]: valor }));
  }

  function limpiarFiltros() {
    setFiltros(FILTROS_VACIOS);
  }

  const accesosFiltrados = aplicarFiltros(accesosManuales, filtros);
  const listaVacia       = !cargando && !error && accesosManuales.length === 0;
  const sinResultados    = !cargando && !error && accesosManuales.length > 0 && accesosFiltrados.length === 0;

  return (
    <div style={s.contenedor}>
      <div style={s.encabezado}>
        <p style={s.titulo}>
          {!cargando && generarTextoConteo(accesosFiltrados.length, accesosManuales.length, 'acceso', 'creado')}
        </p>
        <button style={s.btnActualizar} onClick={cargarAccesos} disabled={cargando} type="button">
          {cargando ? 'Cargando…' : 'Actualizar'}
        </button>
      </div>

      <BarraFiltros filtros={filtros} onCambiar={actualizarFiltro} onLimpiar={limpiarFiltros} />

      {error      && <Alert mensaje={error} />}
      {cargando   && !error && <Spinner texto="Cargando accesos…" />}
      {listaVacia && <div style={s.estadoVacio}>{mensajeVacio}</div>}
      {sinResultados && <div style={s.estadoVacio}>{MENSAJE_SIN_RESULTADOS}</div>}

      {!cargando && accesosFiltrados.map(acceso => (
        <TarjetaAccesoManual key={acceso.id} acceso={acceso} />
      ))}
    </div>
  );
}
