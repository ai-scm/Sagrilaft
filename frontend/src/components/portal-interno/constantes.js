/**
 * Constantes y utilidades compartidas del portal interno SAGRILAFT.
 *
 * Centraliza valores de dominio (tipos de contraparte, áreas) y helpers de
 * formateo usados por CrearAccesoManual y ListaAccesosManuales.
 */

const LOCALE_FECHA = 'es-CO';
const TEXTO_SIN_DATO = '—';

function crearMapaEtiquetas(opciones) {
  return Object.fromEntries(
    opciones.map(({ valor, etiqueta }) => [valor, etiqueta]),
  );
}

function formatearFecha(isoString, { month }) {
  if (!isoString) return TEXTO_SIN_DATO;
  return new Date(isoString).toLocaleDateString(LOCALE_FECHA, {
    year: 'numeric',
    month,
    day: 'numeric',
  });
}

// ── Datos de dominio ──────────────────────────────────────────────────────────
// Fuente de verdad: TipoContraparte y AreaResponsable en backend/infrastructure/persistencia/models.py.
// Actualizar ambos archivos si se añaden o eliminan valores del enum.

export const ESTADOS_ACCESO = [
  { valor: 'activo',    etiqueta: 'Activo'    },
  { valor: 'consumido', etiqueta: 'Consumido' },
  { valor: 'expirado',  etiqueta: 'Expirado'  },
];

export const TIPOS_CONTRAPARTE = [
  { valor: 'cliente',   etiqueta: 'Cliente'   },
  { valor: 'proveedor', etiqueta: 'Proveedor' },
];

export const AREAS_RESPONSABLES = [
  { valor: 'ventas',   etiqueta: 'Ventas'   },
  { valor: 'legal',    etiqueta: 'Legal'    },
  { valor: 'finanzas', etiqueta: 'Finanzas' },
];

// Mapas derivados de los arrays anteriores — única fuente de verdad.
export const ETIQUETA_TIPO_CONTRAPARTE = crearMapaEtiquetas(TIPOS_CONTRAPARTE);

export const ETIQUETA_AREA_RESPONSABLE = crearMapaEtiquetas(AREAS_RESPONSABLES);

// ── Formateo de fechas ────────────────────────────────────────────────────────

/** Formato compacto: "23 ene. 2026" — para listas y chips. */
export function formatearFechaCorta(isoString) {
  return formatearFecha(isoString, { month: 'short' });
}

/** Formato completo: "23 de enero de 2026" — para paneles de detalle. */
export function formatearFechaLarga(isoString) {
  return formatearFecha(isoString, { month: 'long' });
}
