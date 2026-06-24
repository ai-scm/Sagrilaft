import { StrictMode } from 'react';
import ReactDOM from 'react-dom/client';
import App from './App.jsx';
import keycloak from './keycloak.js';
import { configurarTokenPortal, configurarManejadorAuthError } from './services/api.js';
import './styles/global.css';

async function inicializarPortal() {
  const root = ReactDOM.createRoot(document.getElementById('root'));

  if (!import.meta.env.VITE_KEYCLOAK_URL) {
    root.render(
      <StrictMode>
        <App keycloak={null} />
      </StrictMode>
    );
    return;
  }

  try {
    await keycloak.init({
      onLoad: 'login-required',
      pkceMethod: 'S256',
      checkLoginIframe: false,
    });

    configurarTokenPortal(async () => {
      try {
        await keycloak.updateToken(30);
      } catch (err) {
        keycloak.login();
      }
      return keycloak.token;
    });

    configurarManejadorAuthError(() => {
      keycloak.login();
    });

    keycloak.onTokenExpired = () =>
      keycloak.updateToken(30).catch(() => keycloak.login());

    root.render(
      <StrictMode>
        <App keycloak={keycloak} />
      </StrictMode>
    );
  } catch {
    root.render(
      <div style={{ padding: '2rem', color: '#ef4444' }}>
        Error al conectar con el servidor de autenticación. Verifique que Keycloak esté disponible.
      </div>
    );
  }
}

inicializarPortal();
