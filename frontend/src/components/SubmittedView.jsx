/**
 * Vista de confirmación tras enviar exitosamente el formulario.
 */
export default function SubmittedView({ codigoPeticion }) {
  return (
    <div className="app-container">
      <header className="app-header">
        <h1>FORMULARIO DE VINCULACIÓN DE CONTRAPARTE</h1>
        <p className="subtitle">SAGRILAFT - Sistema de Autocontrol de Riesgo de LA/FT</p>
        {codigoPeticion && <div className="codigo-peticion">Código: {codigoPeticion}</div>}
      </header>
      <main className="main-content">
        <div className="form-card" style={{ textAlign: 'center', padding: '60px 40px' }}>
          <div style={{ fontSize: '3rem', marginBottom: '16px' }}>✅</div>
          <h2 style={{ color: 'var(--gray-900)', marginBottom: '12px' }}>¡Formulario Enviado!</h2>
          <p style={{ color: 'var(--gray-500)', fontSize: '0.95rem', maxWidth: '500px', margin: '0 auto' }}>
            Su formulario ha sido recibido exitosamente. Se realizarán las validaciones
            correspondientes y será notificado del resultado.
          </p>
          {codigoPeticion && (
            <div style={{
              marginTop: '24px', padding: '16px 24px',
              background: 'var(--primary-50)', borderRadius: 'var(--radius-md)',
              display: 'inline-block',
            }}>
              <span style={{ fontSize: '0.82rem', color: 'var(--gray-500)' }}>Código de seguimiento</span>
              <div style={{ fontSize: '1.3rem', fontWeight: '700', color: 'var(--primary-700)', marginTop: '4px' }}>
                {codigoPeticion}
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
