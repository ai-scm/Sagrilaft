import FormularioSagrilaft from './components/FormularioSagrilaft';
import CrearAccesoManual from './components/portal-interno/CrearAccesoManual';

/**
 * Determina qué vista renderizar según los parámetros de la URL:
 *
 *   /?portal=interno   → Portal interno (Crear acceso manual)
 *   /?token=<token>    → Formulario externo via enlace tokenizado
 *                        (el token es resuelto dentro de useFormulario)
 *   /                  → Formulario externo (flujo normal)
 */
function App() {
  const params = new URLSearchParams(window.location.search);
  const esPortalInterno = params.get('portal') === 'interno';

  if (esPortalInterno) {
    return <CrearAccesoManual />;
  }

  // El parámetro ?token= es detectado y resuelto internamente por useFormulario
  return <FormularioSagrilaft />;
}

export default App;
