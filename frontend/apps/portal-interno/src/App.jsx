import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import PortalLayout from './components/layout/PortalLayout';
import CrearAccesoManual from './components/accesos/CrearAccesoManual';
import ListaAccesosManuales from './components/accesos/ListaAccesosManuales';
import VistaExpedientes from './components/expedientes/VistaExpedientes';

function App({ keycloak }) {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<PortalLayout keycloak={keycloak} />}>
          <Route index element={<Navigate to="/crear" replace />} />
          <Route path="crear" element={<CrearAccesoManual />} />
          <Route path="accesos" element={<ListaAccesosManuales />} />
          <Route path="expedientes" element={<VistaExpedientes />} />
          <Route path="expedientes/:id" element={<VistaExpedientes />} />
          <Route path="*" element={<Navigate to="/crear" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
