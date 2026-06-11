import FormularioSagrilaft from './components/FormularioSagrilaft';
import Alert from '@shared/components/ui/Alert';

function obtenerUrlPortalInterno() {
  return import.meta.env.VITE_PORTAL_INTERNO_URL || null;
}

/**
 * App pública del formulario SAGRILAFT.
 * El parámetro ?token= es detectado y resuelto internamente por useFormulario.
 * Los parámetros legacy ?portal=interno y ?portalinterno redirigen a la app separada del portal.
 */
function App() {
  const parametros = new URLSearchParams(window.location.search);
  const esEntradaPortalInterno =
    parametros.get('portal') === 'interno' ||
    parametros.has('portalinterno');

  if (esEntradaPortalInterno) {
    const urlPortal = obtenerUrlPortalInterno();
    if (urlPortal) {
      window.location.replace(urlPortal);
      return null;
    }

    // SI LLEGA AQUÍ, ES PORQUE LA VARIABLE NO EXISTE. 
    // Utilizamos el diseño base y el componente compartido para no duplicar estilos.
    return (
      <div className="app-container">
        <header className="app-header">
          <h1>SAGRILAFT</h1>
          <p className="subtitle">Redirección al Portal Interno</p>
        </header>
        <main className="main-content" style={{ display: 'flex', justifyContent: 'center', marginTop: '3rem' }}>
          <Alert 
            mensaje="Error de configuración: No se ha definido la ruta del portal interno. Por favor, reporte este incidente al soporte técnico."
            style={{ maxWidth: '600px', fontSize: '1rem', padding: '20px' }}
          />
        </main>
      </div>
    );
  }

  return <FormularioSagrilaft />;
}

export default App;
