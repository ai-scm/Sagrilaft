import FormularioSagrilaft from './components/FormularioSagrilaft';
import PantallaIngreso from './components/PantallaIngreso';
import Alert from '@shared/components/ui/Alert';
import { DiligenciamientoProvider, useDiligenciamiento } from './context/DiligenciamientoContext';

function obtenerUrlPortalInterno() {
  return import.meta.env.VITE_PORTAL_INTERNO_URL || null;
}

function AppContent() {
  const { sesionActiva } = useDiligenciamiento();

  if (!sesionActiva) {
    return <PantallaIngreso />;
  }

  return <FormularioSagrilaft />;
}

/**
 * App pública del formulario SAGRILAFT.
 * Utiliza el DiligenciamientoContext como guard.
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

  return (
    <DiligenciamientoProvider>
      <AppContent />
    </DiligenciamientoProvider>
  );
}

export default App;
