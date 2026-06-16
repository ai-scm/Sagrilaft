import FormularioSagrilaft from './components/FormularioSagrilaft';
import ModalCorreoDestinatario from './components/ModalCorreoDestinatario';
import Alert from '@shared/components/ui/Alert';
import { useCapturaCorreoDestinatario } from './hooks/useCapturaCorreoDestinatario';

function obtenerUrlPortalInterno() {
  return import.meta.env.VITE_PORTAL_INTERNO_URL || null;
}

/**
 * App pública del formulario SAGRILAFT.
 * El parámetro ?token= es detectado y resuelto internamente por useFormulario.
 * Los parámetros legacy ?portal=interno y ?portalinterno redirigen a la app separada del portal.
 *
 * Interceptación de correo:
 *   Si el token corresponde a un acceso sin correo registrado, se muestra primero
 *   el ModalCorreoDestinatario. Solo al confirmar el correo se revela el formulario.
 */
function App() {
  const parametros = new URLSearchParams(window.location.search);
  const esEntradaPortalInterno =
    parametros.get('portal') === 'interno' ||
    parametros.has('portalinterno');

  const { verificando, correoRequerido, enviando, error, registrarCorreo } = useCapturaCorreoDestinatario();

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

  if (verificando) {
    return null; // O un skeleton/spinner si se prefiere, aunque es rápido
  }

  return (
    <>
      <ModalCorreoDestinatario
        visible={correoRequerido}
        enviando={enviando}
        error={error}
        onConfirmar={registrarCorreo}
      />
      {!correoRequerido && <FormularioSagrilaft />}
    </>
  );
}

export default App;
