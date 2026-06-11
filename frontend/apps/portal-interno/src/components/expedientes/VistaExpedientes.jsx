/**
 * VistaExpedientes — Bandeja de formularios enviados por clientes y proveedores.
 *
 * Muestra todos los formularios en estado no-borrador organizados por tipo
 * de contraparte. Permite filtrar por CLIENTE/PROVEEDOR y buscar por razón social.
 * Al seleccionar un expediente, abre DetalleExpediente como vista superpuesta.
 */

import { useState } from 'react';
import DetalleExpediente from './DetalleExpediente';
import { estilosBandeja } from '../ui/listaStyles';
import useExpedientes from '../../hooks/useExpedientes';
import Spinner from '@shared/components/ui/Spinner';
import Alert from '@shared/components/ui/Alert';
import BadgeEstadoFormulario, { OPCIONES_ESTADOS_FORMULARIO } from '../badges/BadgeEstadoFormulario';
import {
  TIPOS_CONTRAPARTE,
  ETIQUETA_TIPO_CONTRAPARTE,
  formatearFechaCorta,
  generarTextoConteo,
} from '../../config/constantes';

// ── Constantes ────────────────────────────────────────────────────────────────

const FILTRO_TODOS = '';

// ── Lógica de presentación ────────────────────────────────────────────────────

function contarPorTipo(expedientes, tipo) {
  return expedientes.filter(e => e.tipo_contraparte === tipo).length;
}

// ── Estilos ───────────────────────────────────────────────────────────────────

const s = {
  ...estilosBandeja,
  tituloConteo: {
    fontSize:   '0.9rem',
    fontWeight: '600',
    color:      'var(--gray-700, #334155)',
    margin:     0,
  },
  // Resumen de carpetas
  carpetas: {
    display:             'grid',
    gridTemplateColumns: '1fr 1fr',
    gap:                 '10px',
    marginBottom:        '8px',
  },
  carpeta: (activa) => ({
    padding:       '14px 16px',
    background:    activa ? 'var(--primary-50, #eff6ff)' : '#fff',
    border:        `1.5px solid ${activa ? 'var(--primary-300, #93c5fd)' : 'var(--gray-200, #e2e8f0)'}`,
    borderRadius:  'var(--radius-md, 8px)',
    cursor:        'pointer',
    transition:    'all 0.15s',
  }),
  carpetaTitulo: (activa) => ({
    fontSize:   '0.78rem',
    fontWeight: '700',
    color:      activa ? 'var(--primary-700, #1d4ed8)' : 'var(--gray-500, #64748b)',
    textTransform: 'uppercase',
    letterSpacing: '0.06em',
    margin:     '0 0 4px',
  }),
  carpetaConteo: (activa) => ({
    fontSize:   '1.4rem',
    fontWeight: '800',
    color:      activa ? 'var(--primary-700, #1d4ed8)' : 'var(--gray-900, #0f172a)',
    margin:     0,
    lineHeight: 1,
  }),
  // Barra de búsqueda y filtros
  inputBusqueda: {
    flex:         1,
    minWidth:     '160px',
    padding:      '7px 12px',
    border:       '1.5px solid var(--gray-200, #e2e8f0)',
    borderRadius: 'var(--radius-sm, 6px)',
    fontSize:     '0.82rem',
    color:        'var(--gray-800, #1e293b)',
    outline:      'none',
  },
  // Tarjetas de expedientes
  tarjeta: {
    background:    '#fff',
    borderRadius:  'var(--radius-md, 8px)',
    border:        '1px solid var(--gray-200, #e2e8f0)',
    padding:       '14px 18px',
    cursor:        'pointer',
    transition:    'border-color 0.15s, box-shadow 0.15s',
    display:       'flex',
    flexDirection: 'column',
    gap:           '6px',
  },
  filaSuperior: {
    display:        'flex',
    alignItems:     'flex-start',
    justifyContent: 'space-between',
    gap:            '8px',
  },
  razonSocial: {
    fontSize:   '0.92rem',
    fontWeight: '700',
    color:      'var(--gray-900, #0f172a)',
    margin:     0,
    lineHeight: 1.3,
  },
  codigo: {
    fontSize:      '0.75rem',
    color:         'var(--gray-400, #94a3b8)',
    fontFamily:    'monospace',
    letterSpacing: '0.04em',
  },
  metadatos: {
    display:    'flex',
    gap:        '8px',
    flexWrap:   'wrap',
    alignItems: 'center',
  },
  chip: {
    fontSize:     '0.72rem',
    color:        'var(--gray-500, #64748b)',
    background:   'var(--gray-50, #f8fafc)',
    border:       '1px solid var(--gray-200, #e2e8f0)',
    borderRadius: '999px',
    padding:      '2px 9px',
    whiteSpace:   'nowrap',
  },
  chipDocs: (cantidad) => ({
    fontSize:     '0.72rem',
    color:        cantidad > 0 ? '#15803d' : 'var(--gray-400, #94a3b8)',
    background:   cantidad > 0 ? '#f0fdf4' : 'var(--gray-50, #f8fafc)',
    border:       `1px solid ${cantidad > 0 ? '#bbf7d0' : 'var(--gray-200, #e2e8f0)'}`,
    borderRadius: '999px',
    padding:      '2px 9px',
    whiteSpace:   'nowrap',
  }),
};

// ── Sub-componentes ───────────────────────────────────────────────────────────

function TarjetaExpediente({ expediente, onClick }) {
  const tipoLabel  = ETIQUETA_TIPO_CONTRAPARTE[expediente.tipo_contraparte] ?? expediente.tipo_contraparte ?? '—';
  const cantidadDocs = expediente.cantidad_documentos ?? 0;

  return (
    <div
      style={s.tarjeta}
      onClick={() => onClick(expediente)}
      onMouseEnter={e => {
        e.currentTarget.style.borderColor = 'var(--primary-300, #93c5fd)';
        e.currentTarget.style.boxShadow   = '0 2px 8px rgba(37,99,235,0.08)';
      }}
      onMouseLeave={e => {
        e.currentTarget.style.borderColor = 'var(--gray-200, #e2e8f0)';
        e.currentTarget.style.boxShadow   = 'none';
      }}
    >
      <div style={s.filaSuperior}>
        <div>
          <p style={s.razonSocial}>{expediente.razon_social ?? '(Sin razón social)'}</p>
          <span style={s.codigo}>{expediente.codigo_peticion}</span>
        </div>
        <BadgeEstadoFormulario
          estado={expediente.estado}
          overrides={{ fontSize: '0.7rem', padding: '2px 10px' }}
        />
      </div>

      <div style={s.metadatos}>
        <span style={s.chip}>{tipoLabel}</span>
        {expediente.numero_identificacion && (
          <span style={s.chip}>NIT {expediente.numero_identificacion}</span>
        )}
        <span style={s.chipDocs(cantidadDocs)}>
          {cantidadDocs} doc{cantidadDocs !== 1 ? 's' : ''}
        </span>
        <span style={{ ...s.chip, marginLeft: 'auto' }}>
          {formatearFechaCorta(expediente.updated_at)}
        </span>
      </div>
    </div>
  );
}

// ── Componente principal ──────────────────────────────────────────────────────

export default function VistaExpedientes() {
  const [filtroTipo, setFiltroTipo]                 = useState(FILTRO_TODOS);
  const [filtroEstado, setFiltroEstado]             = useState(FILTRO_TODOS);
  const [busqueda, setBusqueda]                     = useState('');
  const [expedienteDetalle, setExpedienteDetalle]   = useState(null);

  const {
    expedientes,
    expedientesParaConteos,
    cargando,
    error,
    recargar,
    busquedaDebounced,
  } = useExpedientes({ filtroTipo, busqueda });

  const expedientesFiltrados = expedientes.filter(e => {
    const coincideTipo    = !filtroTipo   || e.tipo_contraparte === filtroTipo;
    const coincideEstado  = !filtroEstado || e.estado           === filtroEstado;
    const terminoBusqueda = busquedaDebounced.trim().toLowerCase();
    const coincideBusqueda = !terminoBusqueda ||
      (e.razon_social ?? '').toLowerCase().includes(terminoBusqueda) ||
      (e.codigo_peticion ?? '').toLowerCase().includes(terminoBusqueda);
    return coincideTipo && coincideEstado && coincideBusqueda;
  });

  const totalClientes    = contarPorTipo(expedientesParaConteos, 'cliente');
  const totalProveedores = contarPorTipo(expedientesParaConteos, 'proveedor');

  if (expedienteDetalle) {
    return (
      <DetalleExpediente
        formularioId={expedienteDetalle.formulario_id}
        razonSocial={expedienteDetalle.razon_social}
        onVolver={() => setExpedienteDetalle(null)}
      />
    );
  }

  return (
    <div style={s.contenedor}>
      {/* Encabezado con conteo y botón actualizar */}
      <div style={s.encabezado}>
        <p style={s.tituloConteo}>
          {!cargando && generarTextoConteo(expedientesFiltrados.length, expedientes.length, 'formulario', 'recibido')}
        </p>
        <button
          style={s.btnActualizar}
          onClick={recargar}
          disabled={cargando}
          type="button"
        >
          {cargando ? 'Cargando…' : 'Actualizar'}
        </button>
      </div>

      {/* Carpetas CLIENTES / PROVEEDORES */}
      {!cargando && !error && (
        <div style={s.carpetas}>
          {TIPOS_CONTRAPARTE.map(({ valor, etiqueta, etiquetaPlural }) => {
            const conteo  = valor === 'cliente' ? totalClientes : totalProveedores;
            const activa  = filtroTipo === valor;
            return (
              <div
                key={valor}
                style={s.carpeta(activa)}
                onClick={() => setFiltroTipo(activa ? FILTRO_TODOS : valor)}
              >
                <p style={s.carpetaTitulo(activa)}>{etiquetaPlural}</p>
                <p style={s.carpetaConteo(activa)}>{conteo}</p>
              </div>
            );
          })}
        </div>
      )}

      {/* Barra de búsqueda */}
      {!cargando && !error && (
        <div style={s.barraFiltros}>
          <input
            type="search"
            placeholder="Buscar por razón social o código…"
            value={busqueda}
            onChange={e => setBusqueda(e.target.value)}
            style={s.inputBusqueda}
          />
          <select
            style={s.selectFiltro}
            value={filtroTipo}
            onChange={e => setFiltroTipo(e.target.value)}
          >
            <option value={FILTRO_TODOS}>Todos los tipos</option>
            {TIPOS_CONTRAPARTE.map(({ valor, etiqueta }) => (
              <option key={valor} value={valor}>{etiqueta}</option>
            ))}
          </select>
          <select
            style={s.selectFiltro}
            value={filtroEstado}
            onChange={e => setFiltroEstado(e.target.value)}
          >
            <option value="">Todos los estados</option>
            {OPCIONES_ESTADOS_FORMULARIO.map(({ valor, etiqueta }) => (
              <option key={valor} value={valor}>{etiqueta}</option>
            ))}
          </select>
        </div>
      )}

      {/* Estados de carga / error / vacío */}
      {error    && <Alert mensaje={error} />}
      {cargando && !error && <Spinner texto="Cargando formularios…" />}
      {!cargando && !error && expedientes.length === 0 && (
        <div style={s.estadoVacio}>
          Aún no hay formularios enviados. Aparecerán aquí cuando los destinatarios completen y envíen el formulario SAGRILAFT.
        </div>
      )}
      {!cargando && !error && expedientes.length > 0 && expedientesFiltrados.length === 0 && (
        <div style={s.estadoVacio}>Ningún formulario coincide con los filtros seleccionados.</div>
      )}

      {/* Lista de tarjetas */}
      {!cargando && expedientesFiltrados.map(expediente => (
        <TarjetaExpediente
          key={expediente.formulario_id}
          expediente={expediente}
          onClick={setExpedienteDetalle}
        />
      ))}
    </div>
  );
}
