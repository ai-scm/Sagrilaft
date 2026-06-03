/**
 * Constantes y utilidades compartidas del portal interno SAGRILAFT.
 *
 * Centraliza valores de dominio (tipos de contraparte, estados, áreas) y
 * helpers de formateo usados por todos los componentes del portal.
 */

const LOCALE_FECHA = 'es-CO';
const TEXTO_SIN_DATO = '—';

function crearMapaEtiquetas(opciones) {
  return Object.fromEntries(
    opciones.map(({ valor, etiqueta }) => [valor, etiqueta]),
  );
}

function crearMapaEstilos(opciones) {
  return Object.fromEntries(
    opciones.map(({ valor, bg, color, borde }) => [valor, { bg, color, borde }]),
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
  { valor: 'activo',    etiqueta: 'Activo',    bg: '#dcfce7', color: '#15803d', borde: '#86efac' },
  { valor: 'consumido', etiqueta: 'Consumido', bg: '#dbeafe', color: '#1d4ed8', borde: '#93c5fd' },
  { valor: 'expirado',  etiqueta: 'Expirado',  bg: '#fee2e2', color: '#dc2626', borde: '#fca5a5' },
];

export const ETIQUETA_ESTADO_ACCESO = crearMapaEtiquetas(ESTADOS_ACCESO);
export const ESTILO_ESTADO_ACCESO   = crearMapaEstilos(ESTADOS_ACCESO);

export const TIPOS_CONTRAPARTE = [
  { valor: 'cliente',   etiqueta: 'Cliente',   etiquetaPlural: 'Clientes'   },
  { valor: 'proveedor', etiqueta: 'Proveedor', etiquetaPlural: 'Proveedores' },
];

export const AREAS_RESPONSABLES = [
  { valor: 'ventas',   etiqueta: 'Ventas'   },
  { valor: 'legal',    etiqueta: 'Legal'    },
  { valor: 'finanzas', etiqueta: 'Finanzas' },
];

export const ETIQUETA_TIPO_CONTRAPARTE = crearMapaEtiquetas(TIPOS_CONTRAPARTE);
export const ETIQUETA_AREA_RESPONSABLE = crearMapaEtiquetas(AREAS_RESPONSABLES);

export const ESTADOS_FORMULARIO = [
  // Los valores deben coincidir con `EstadoFormulario` del backend (minúsculas):
  // backend/infrastructure/persistencia/models.py
  { valor: 'enviado',         etiqueta: 'Enviado',          bg: '#eff6ff', color: '#1d4ed8', borde: '#bfdbfe' },
  { valor: 'en_correccion',   etiqueta: 'En corrección',    bg: '#fff7ed', color: '#c2410c', borde: '#fed7aa' },
  { valor: 'validado',        etiqueta: 'Validado',         bg: '#f0fdf4', color: '#15803d', borde: '#bbf7d0' },
  { valor: 'rechazado',       etiqueta: 'Rechazado',        bg: '#fef2f2', color: '#dc2626', borde: '#fca5a5' },
  { valor: 'pendiente_firma', etiqueta: 'Pendiente firma',  bg: '#fefce8', color: '#854d0e', borde: '#fde047' },
  { valor: 'firmado',         etiqueta: 'Firmado',          bg: '#f5f3ff', color: '#6d28d9', borde: '#c4b5fd' },
];

export const ETIQUETA_ESTADO_FORMULARIO = crearMapaEtiquetas(ESTADOS_FORMULARIO);
export const ESTILO_ESTADO_FORMULARIO   = crearMapaEstilos(ESTADOS_FORMULARIO);

// ── Constantes de documentos ──────────────────────────────────────────────────
// Sincronizar con: backend/domain/constantes.py

export const TIPO_DOCUMENTO_FORMULARIO_PDF       = 'FORMULARIO_PDF';
export const TIPO_DOCUMENTO_CERTIFICADO_SAGRILAFT = 'CERTIFICADO_SAGRILAFT';

// ── Estilos reutilizables ─────────────────────────────────────────────────────

const ESTILO_ESTADO_POR_DEFECTO = { bg: '#f1f5f9', color: '#64748b', borde: '#e2e8f0' };

/**
 * Estilo base para badges de estado del formulario.
 *
 * Permite overrides (fontSize/padding, etc.) para reutilizar el mismo
 * estilo semántico (color/borde) en distintas densidades de UI.
 */
export function estiloBadgeEstado(estado, overrides = {}) {
  const estilo = ESTILO_ESTADO_FORMULARIO[estado] ?? ESTILO_ESTADO_POR_DEFECTO;
  return {
    fontWeight:    '700',
    background:    estilo.bg,
    color:         estilo.color,
    border:        `1px solid ${estilo.borde}`,
    borderRadius:  '999px',
    whiteSpace:    'nowrap',
    letterSpacing: '0.03em',
    ...overrides,
  };
}

// ── Formateo general ──────────────────────────────────────────────────────────

/**
 * Texto de conteo para listas filtradas.
 * Ej: generarTextoConteo(3, 10, 'formulario', 'recibido') → "3 de 10 formularios"
 *     generarTextoConteo(10, 10, 'acceso', 'creado')      → "10 accesos creados"
 */
export function generarTextoConteo(filtrados, total, sustantivo, verboEnPasado = null) {
  const plural = total !== 1 ? 's' : '';
  if (filtrados === total) {
    const verboSufijo = verboEnPasado ? ` ${verboEnPasado}${plural}` : '';
    return `${total} ${sustantivo}${plural}${verboSufijo}`;
  }
  return `${filtrados} de ${total} ${sustantivo}${total !== 1 ? 's' : ''}`;
}

/** Convierte bytes a representación legible: "1.2 MB", "340 KB", "512 B". */
export function formatearBytes(bytes) {
  if (!bytes) return '';
  if (bytes < 1024)        return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

// ── Formateo de fechas ────────────────────────────────────────────────────────

/** Formato compacto: "23 ene. 2026" — para listas y chips. */
export function formatearFechaCorta(isoString) {
  return formatearFecha(isoString, { month: 'short' });
}

/** Formato completo: "23 de enero de 2026" — para paneles de detalle. */
export function formatearFechaLarga(isoString) {
  return formatearFecha(isoString, { month: 'long' });
}
