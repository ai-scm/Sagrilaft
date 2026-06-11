/**
 * BadgeEstadoAcceso — indicador visual del estado de un acceso manual.
 *
 * Props:
 *   estado {string} "activo" | "consumido" | "expirado"
 */

import { ETIQUETA_ESTADO_ACCESO, ESTILO_ESTADO_ACCESO } from '../../config/constantes';

const _FALLBACK_ESTILO = ESTILO_ESTADO_ACCESO.expirado;

const estiloBadge = ({ bg, color, borde }) => ({
  display:       'inline-block',
  padding:       '3px 10px',
  borderRadius:  '999px',
  fontSize:      '0.72rem',
  fontWeight:    '700',
  letterSpacing: '0.04em',
  background:    bg,
  color,
  border:        `1px solid ${borde}`,
  whiteSpace:    'nowrap',
});

export default function BadgeEstadoAcceso({ estado }) {
  if (process.env.NODE_ENV !== 'production' && !ESTILO_ESTADO_ACCESO[estado]) {
    console.warn(`BadgeEstadoAcceso: estado desconocido "${estado}". Valores válidos: activo, consumido, expirado.`);
  }
  const estilo   = ESTILO_ESTADO_ACCESO[estado]   ?? _FALLBACK_ESTILO;
  const etiqueta = ETIQUETA_ESTADO_ACCESO[estado] ?? estado;
  return <span style={estiloBadge(estilo)}>{etiqueta}</span>;
}
