/**
 * TablaFormComponents — Primitivos de UI compartidos por tablas editables.
 *
 * DRY : fuente única de verdad para estilos y mensajes de error de tabla.
 * ISP : cada tabla importa solo los primitivos que necesita.
 * OCP : nuevos primitivos se agregan aquí sin tocar los consumidores existentes.
 */

export const ESTILO_CELDA_ERROR = { borderColor: 'var(--error, #e53e3e)' };

export const HR = () => (
  <hr style={{ border: 'none', borderTop: '1px solid var(--gray-200)', margin: '24px 0' }} />
);

export const SectionTitle = ({ children }) => (
  <h3 style={{ fontSize: '1rem', fontWeight: '600', color: 'var(--gray-800)', marginBottom: '12px' }}>
    {children}
  </h3>
);

export const SubLabel = ({ children }) => (
  <p style={{ fontSize: '0.875rem', color: 'var(--gray-600)', marginBottom: '8px' }}>
    {children}
  </p>
);

export const MensajeError = ({ msg }) =>
  msg ? (
    <span style={{ color: 'var(--error, #e53e3e)', fontSize: '0.75rem', display: 'block' }}>
      {msg}
    </span>
  ) : null;
