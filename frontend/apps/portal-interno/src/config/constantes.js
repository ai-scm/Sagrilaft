/**
 * Constantes y utilidades compartidas del portal interno SAGRILAFT.
 *
 * Centraliza valores de dominio (tipos de contraparte, estados, áreas) y
 * helpers de formateo usados por todos los componentes del portal.
 */
import {
  ESTADO_ACCESO_ACTIVO, ESTADO_ACCESO_CONSUMIDO, ESTADO_ACCESO_EXPIRADO,
  TIPO_CONTRAPARTE_CLIENTE, TIPO_CONTRAPARTE_PROVEEDOR,
  TIPO_DOCUMENTO_FORMULARIO_PDF, TIPO_DOCUMENTO_CERTIFICADO_SAGRILAFT,
  TIPO_DOCUMENTO_REPORTE_FINAL
} from '@shared/utils/constantes';

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

function formatearFecha(isoString, { month, hour, minute, hour12 } = {}) {
  if (!isoString) return TEXTO_SIN_DATO;
  const fecha = new Date(isoString);
  if (isNaN(fecha.getTime())) return TEXTO_SIN_DATO;
  const opciones = { year: 'numeric', month, day: 'numeric' };
  if (hour !== undefined) {
    opciones.hour = hour;
    opciones.minute = minute;
    opciones.hour12 = hour12;
    return fecha.toLocaleString(LOCALE_FECHA, opciones);
  }
  return fecha.toLocaleDateString(LOCALE_FECHA, opciones);
}

// ── Datos de dominio ──────────────────────────────────────────────────────────
// Fuente de verdad: TipoContraparte y AreaResponsable en backend/infrastructure/persistencia/models.py.
// Actualizar ambos archivos si se añaden o eliminan valores del enum.

export const ESTADOS_ACCESO = [
  { valor: ESTADO_ACCESO_ACTIVO,    etiqueta: 'Activo',    bg: '#dcfce7', color: '#15803d', borde: '#86efac' },
  { valor: ESTADO_ACCESO_CONSUMIDO, etiqueta: 'Consumido', bg: '#dbeafe', color: '#1d4ed8', borde: '#93c5fd' },
  { valor: ESTADO_ACCESO_EXPIRADO,  etiqueta: 'Expirado',  bg: '#fee2e2', color: '#dc2626', borde: '#fca5a5' },
];

export const ETIQUETA_ESTADO_ACCESO = crearMapaEtiquetas(ESTADOS_ACCESO);
export const ESTILO_ESTADO_ACCESO   = crearMapaEstilos(ESTADOS_ACCESO);

export const TIPOS_CONTRAPARTE = [
  { valor: TIPO_CONTRAPARTE_CLIENTE,   etiqueta: 'Cliente',   etiquetaPlural: 'Clientes'   },
  { valor: TIPO_CONTRAPARTE_PROVEEDOR, etiqueta: 'Proveedor', etiquetaPlural: 'Proveedores' },
];

export const AREAS_RESPONSABLES = [
  { valor: 'ventas',   etiqueta: 'Ventas'   },
  { valor: 'legal',    etiqueta: 'Legal'    },
  { valor: 'finanzas', etiqueta: 'Finanzas' },
  { valor: 'recursos_humanos', etiqueta: 'Recursos Humanos' },
];

export const ETIQUETA_TIPO_CONTRAPARTE = crearMapaEtiquetas(TIPOS_CONTRAPARTE);
export const ETIQUETA_AREA_RESPONSABLE = crearMapaEtiquetas(AREAS_RESPONSABLES);



// ── Constantes de documentos ──────────────────────────────────────────────────
// Sincronizar con: backend/domain/constantes.py

export { TIPO_DOCUMENTO_FORMULARIO_PDF, TIPO_DOCUMENTO_CERTIFICADO_SAGRILAFT, TIPO_DOCUMENTO_REPORTE_FINAL };



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

/** Formato con hora: "23 ene. 2026, 14:32" — para metadata de versiones. */
export function formatearFechaHora(isoString) {
  return formatearFecha(isoString, {
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  });
}
