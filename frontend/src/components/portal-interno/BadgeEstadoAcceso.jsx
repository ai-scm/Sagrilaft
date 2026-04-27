/**
 * BadgeEstadoAcceso — indicador visual del estado de un acceso manual.
 *
 * Props:
 *   estado {string} "activo" | "consumido" | "expirado"
 */

const CONFIGURACION_POR_ESTADO = {
  activo: {
    etiqueta: 'Activo',
    fondo:    '#dcfce7',
    texto:    '#15803d',
    borde:    '#86efac',
  },
  consumido: {
    etiqueta: 'Consumido',
    fondo:    '#dbeafe',
    texto:    '#1d4ed8',
    borde:    '#93c5fd',
  },
  expirado: {
    etiqueta: 'Expirado',
    fondo:    '#fee2e2',
    texto:    '#dc2626',
    borde:    '#fca5a5',
  },
};

const estiloBadge = (config) => ({
  display:       'inline-block',
  padding:       '3px 10px',
  borderRadius:  '999px',
  fontSize:      '0.72rem',
  fontWeight:    '700',
  letterSpacing: '0.04em',
  background:    config.fondo,
  color:         config.texto,
  border:        `1px solid ${config.borde}`,
  whiteSpace:    'nowrap',
});

export default function BadgeEstadoAcceso({ estado }) {
  if (process.env.NODE_ENV !== 'production' && !CONFIGURACION_POR_ESTADO[estado]) {
    console.warn(`BadgeEstadoAcceso: estado desconocido "${estado}". Valores válidos: activo, consumido, expirado.`);
  }
  const config = CONFIGURACION_POR_ESTADO[estado] ?? CONFIGURACION_POR_ESTADO.expirado;
  return <span style={estiloBadge(config)}>{config.etiqueta}</span>;
}
