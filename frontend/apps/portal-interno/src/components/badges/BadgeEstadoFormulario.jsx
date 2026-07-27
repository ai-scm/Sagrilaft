import {
  ESTADO_FORM_ENVIADO,
  ESTADO_FORM_EN_CORRECCION,
  ESTADO_FORM_VALIDADO,
  ESTADO_FORM_RECHAZADO,
  ESTADO_FORM_PENDIENTE_FIRMA,
  ESTADO_FORM_FIRMADO,
  ESTADO_FORM_CERRADO,
} from '@shared/utils/constantes';

export const CONFIG_ESTADOS_FORMULARIO = {
  [ESTADO_FORM_ENVIADO]:         { etiqueta: 'Enviado',          bg: '#eff6ff', color: '#1d4ed8', borde: '#bfdbfe' },
  [ESTADO_FORM_EN_CORRECCION]:   { etiqueta: 'En corrección',    bg: '#fff7ed', color: '#c2410c', borde: '#fed7aa' },
  [ESTADO_FORM_VALIDADO]:        { etiqueta: 'Validado',         bg: '#f0fdf4', color: '#15803d', borde: '#bbf7d0' },
  [ESTADO_FORM_RECHAZADO]:       { etiqueta: 'Rechazado',        bg: '#fef2f2', color: '#dc2626', borde: '#fca5a5' },
  [ESTADO_FORM_PENDIENTE_FIRMA]: { etiqueta: 'Pendiente firma',  bg: '#fefce8', color: '#854d0e', borde: '#fde047' },
  [ESTADO_FORM_FIRMADO]:         { etiqueta: 'Firmado',          bg: '#f5f3ff', color: '#6d28d9', borde: '#c4b5fd' },
  [ESTADO_FORM_CERRADO]:         { etiqueta: 'Cerrado',          bg: '#f3f4f6', color: '#374151', borde: '#d1d5db' },
};

// Para selects/filtros
export const OPCIONES_ESTADOS_FORMULARIO = Object.entries(CONFIG_ESTADOS_FORMULARIO).map(([valor, config]) => ({
  valor,
  etiqueta: config.etiqueta
}));

const ESTILO_POR_DEFECTO = { bg: '#f1f5f9', color: '#64748b', borde: '#e2e8f0' };

export default function BadgeEstadoFormulario({ estado, overrides = {}, className = '' }) {
  const config = CONFIG_ESTADOS_FORMULARIO[estado];
  if (process.env.NODE_ENV !== 'production' && !config) {
    console.warn(`BadgeEstadoFormulario: estado desconocido "${estado}".`);
  }

  const estiloBase = config ?? ESTILO_POR_DEFECTO;
  const etiqueta = config?.etiqueta ?? estado;

  const estiloFinal = {
    display:       'inline-flex',
    alignItems:    'center',
    padding:       '4px 12px',
    fontSize:      '13px',
    fontWeight:    '600',
    background:    estiloBase.bg,
    color:         estiloBase.color,
    border:        `1px solid ${estiloBase.borde}`,
    borderRadius:  '9999px',
    whiteSpace:    'nowrap',
    letterSpacing: '0.01em',
    ...overrides,
  };

  return <span style={estiloFinal} className={className}>{etiqueta}</span>;
}
