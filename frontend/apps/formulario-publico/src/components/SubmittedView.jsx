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
          <div style={{ marginBottom: '16px', display: 'flex', justifyContent: 'center' }}>
            <img src="/check_final.gif" alt="¡Éxito!" style={{ width: '80px', height: '80px', objectFit: 'contain' }} />
          </div>
          <h2 style={{ color: 'var(--gray-900)', marginBottom: '12px' }}>¡Formulario Enviado!</h2>
          <p style={{ color: 'var(--gray-500)', fontSize: '0.95rem', maxWidth: '500px', margin: '0 auto' }}>
            Su formulario ha sido recibido exitosamente. Se realizarán las validaciones
            correspondientes y será notificado del resultado, ya puede cerrar esta pestaña.
          </p>
          {codigoPeticion && (
            <>
              <div style={{
                marginTop: '24px', padding: '16px 24px',
                background: 'var(--primary-50)', borderRadius: 'var(--radius-md)',
                display: 'inline-block',
                marginBottom: '24px'
              }}>
                <span style={{ fontSize: '0.82rem', color: 'var(--gray-500)' }}>Código de seguimiento</span>
                <div style={{ fontSize: '1.3rem', fontWeight: '700', color: 'var(--primary-700)', marginTop: '4px' }}>
                  {codigoPeticion}
                </div>
              </div>

              <div>
                <a 
                  href={`/api/formularios/${codigoPeticion}/pdf`}
                  download={`formulario_SAG-${codigoPeticion}.pdf`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="btn btn-primary"
                  style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', textDecoration: 'none' }}
                >
                  <svg width="20" height="20" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-3 3m0 0l-3-3m3 3V4" />
                  </svg>
                  Descargar formulario en PDF
                </a>
              </div>
            </>
          )}
        </div>
      </main>
    </div>
  );
}
