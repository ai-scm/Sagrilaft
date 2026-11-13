/**
 * VistaExpedientes — Bandeja de formularios enviados por clientes y proveedores.
 *
 * Muestra todos los formularios en estado no-borrador organizados por tipo
 * de contraparte. Permite filtrar por CLIENTE/PROVEEDOR y buscar por razón social.
 * Al seleccionar un expediente, abre DetalleExpediente como vista superpuesta.
 */

import { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import DetalleExpediente from '../DetalleExpediente';
import TarjetaExpediente from '../TarjetaExpediente';
import { estilosBandeja } from '../../ui/listaStyles';
import InputBusqueda from '../../ui/InputBusqueda';
import ControlsPaginacion from '../../ui/ControlsPaginacion';
import useExpedientes from '../../../hooks/useExpedientes';
import Spinner from '@shared/components/ui/Spinner';
import Alert from '@shared/components/ui/Alert';
import { OPCIONES_ESTADOS_FORMULARIO } from '../../badges/BadgeEstadoFormulario';
import {
  TIPOS_CONTRAPARTE,
  generarTextoConteo,
} from '../../../config/constantes';
import { ELEMENTOS_POR_PAGINA } from '../../../config/constantesPaginacion';
import { usePaginacion } from '../../../hooks/usePaginacion';

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
};

// ── Componente principal ──────────────────────────────────────────────────────

export default function VistaExpedientes() {
  const { id: expedienteIdFromUrl } = useParams();

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

  // Filtra expedientes y maneja paginación
  const expedientesFiltrados = expedientes.filter(e => {
    const coincideTipo    = !filtroTipo   || e.tipo_contraparte === filtroTipo;
    const coincideEstado  = !filtroEstado || e.estado           === filtroEstado;
    const terminoBusqueda = busquedaDebounced.trim().toLowerCase();
    const coincideBusqueda = !terminoBusqueda ||
      (e.razon_social ?? '').toLowerCase().includes(terminoBusqueda) ||
      (e.codigo_peticion ?? '').toLowerCase().includes(terminoBusqueda);
    return coincideTipo && coincideEstado && coincideBusqueda;
  });

  const paginacion = usePaginacion(expedientesFiltrados, ELEMENTOS_POR_PAGINA);

  // Si hay un ID en la URL, busca automáticamente ese expediente
  useEffect(() => {
    if (expedienteIdFromUrl && expedientes.length > 0 && !expedienteDetalle) {
      const expediente = expedientes.find(e => e.formulario_id === expedienteIdFromUrl);
      if (expediente) {
        setExpedienteDetalle(expediente);
      }
    }
  }, [expedienteIdFromUrl, expedientes, expedienteDetalle]);

  // Reinicia paginación cuando cambian los filtros
  useEffect(() => {
    paginacion.reiniciarPaginacion();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filtroTipo, filtroEstado, busquedaDebounced]);

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
          <InputBusqueda
            valor={busqueda}
            onChange={setBusqueda}
            placeholder="Buscar por razón social o código…"
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

      {/* Lista de tarjetas de la página actual */}
      {!cargando && paginacion.elementosPagina.map(expediente => (
        <TarjetaExpediente
          key={expediente.formulario_id}
          expediente={expediente}
          onClick={setExpedienteDetalle}
        />
      ))}

      {/* Controles de paginación */}
      {!cargando && !error && expedientesFiltrados.length > 0 && (
        <ControlsPaginacion {...paginacion} />
      )}
    </div>
  );
}
