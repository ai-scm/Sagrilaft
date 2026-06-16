/**
 * tablaFormStyles.js — Constantes de estilo para tablas editables.
 *
 * Se mantienen en un archivo .js separado (sin JSX) para que Vite Fast Refresh
 * pueda refrescar TablaFormComponents.jsx sin advertencias. Un módulo con
 * exports mezclados (componentes React + valores planos) rompe el HMR.
 */

export const ESTILO_CELDA_ERROR = { borderColor: 'var(--error, #e53e3e)' };

export const ESTILO_BTN_ELIMINAR = {
  background: 'none',
  border: '1px solid var(--error, #e53e3e)',
  color: 'var(--error, #e53e3e)',
  borderRadius: '4px',
  cursor: 'pointer',
  padding: '2px 8px',
  fontSize: '0.85rem',
  lineHeight: '1',
};
