/**
 * ListaAccesosManuales — vista de todos los accesos manuales creados.
 *
 * Muestra código de petición, razón social, estado del acceso, fecha de
 * expiración y correo del destinatario. Se recarga al montar y permite
 * refresco manual.
 *
 * Props:
 *   mensajeVacio {string} Texto a mostrar cuando no hay accesos (opcional).
 *
 * SRP: únicamente gestiona la carga y presentación del listado.
 */

import { useState, useEffect, useCallback } from 'react';
import { api } from '../../services/api';
import BadgeEstadoAcceso from './BadgeEstadoAcceso';
import {
  ETIQUETA_TIPO_CONTRAPARTE,
  ETIQUETA_AREA_RESPONSABLE,
  formatearFechaCorta,
} from './constantes';

// ── Utilidades de dominio ─────────────────────────────────────────────────────

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

function textoConteoAccesos(cantidad) {
  const plural = cantidad !== 1;
  return `${cantidad} acceso${plural ? 's' : ''} creado${plural ? 's' : ''}`;
}

// ── Estilos ───────────────────────────────────────────────────────────────────

const s = {
  contenedor: {
    display:       'flex',
    flexDirection: 'column',
    gap:           '12px',
  },
  encabezado: {
    display:        'flex',
    justifyContent: 'space-between',
    alignItems:     'center',
    marginBottom:   '4px',
  },
  titulo: {
    fontSize:   '0.9rem',
    fontWeight: '600',
    color:      'var(--gray-700, #334155)',
    margin:     0,
  },
  btnActualizar: {
    padding:      '6px 14px',
    background:   'transparent',
    color:        'var(--primary-600, #2563eb)',
    border:       '1.5px solid var(--primary-200, #bfdbfe)',
    borderRadius: 'var(--radius-sm, 6px)',
    fontSize:     '0.8rem',
    fontWeight:   '600',
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
  fechaLimite: (estado) => ({
    fontSize:   '0.75rem',
    fontWeight: '500',
    color:      estado === 'expirado' ? '#dc2626' : 'var(--gray-500, #64748b)',
    whiteSpace: 'nowrap',
  }),
  estadoVacio: {
    textAlign: 'center',
    padding:   '48px 0',
    color:     'var(--gray-400, #94a3b8)',
    fontSize:  '0.9rem',
  },
  spinner: {
    textAlign: 'center',
    padding:   '48px 0',
    color:     'var(--gray-400, #94a3b8)',
    fontSize:  '0.88rem',
  },
  errorCarga: {
    background:   '#fef2f2',
    border:       '1px solid #fca5a5',
    borderRadius: 'var(--radius-md, 8px)',
    padding:      '12px 16px',
    fontSize:     '0.85rem',
    color:        '#991b1b',
    textAlign:    'center',
  },
};

// ── Sub-componente: tarjeta de un acceso ──────────────────────────────────────

function TarjetaAccesoManual({ acceso }) {
  const tipoLabel = obtenerEtiqueta(ETIQUETA_TIPO_CONTRAPARTE, acceso.tipo_contraparte);
  const areaLabel = obtenerEtiqueta(ETIQUETA_AREA_RESPONSABLE, acceso.area_responsable);
  const accesoExpirado = acceso.estado_acceso === 'expirado';
  const estiloTarjeta = accesoExpirado
    ? { ...s.tarjeta, ...s.tarjetaExpirada }
    : s.tarjeta;

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
        <span style={s.chip}>{acceso.correo_destinatario}</span>
        <span style={s.fechaLimite(acceso.estado_acceso)}>
          {formatearEtiquetaFechaLimite(acceso)}
        </span>
      </div>
    </div>
  );
}

// ── Componente principal ──────────────────────────────────────────────────────

const MENSAJE_VACIO_DEFAULT = 'No hay accesos creados aún.';

export default function ListaAccesosManuales({ mensajeVacio = MENSAJE_VACIO_DEFAULT }) {
  const [accesosManuales, setAccesosManuales] = useState([]);
  const [cargando, setCargando]               = useState(true);
  const [error, setError]                     = useState(null);

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

  const mostrarConteo = !cargando;
  const textoConteo = textoConteoAccesos(accesosManuales.length);

  return (
    <div style={s.contenedor}>
      <div style={s.encabezado}>
        <p style={s.titulo}>
          {mostrarConteo && textoConteo}
        </p>
        <button style={s.btnActualizar} onClick={cargarAccesos} disabled={cargando} type="button">
          {cargando ? 'Cargando…' : 'Actualizar'}
        </button>
      </div>

      {error && <div style={s.errorCarga}>{error}</div>}

      {cargando && !error && (
        <div style={s.spinner}>Cargando accesos…</div>
      )}

      {!cargando && !error && accesosManuales.length === 0 && (
        <div style={s.estadoVacio}>{mensajeVacio}</div>
      )}

      {!cargando && accesosManuales.map((acceso) => (
        <TarjetaAccesoManual key={acceso.id} acceso={acceso} />
      ))}
    </div>
  );
}
