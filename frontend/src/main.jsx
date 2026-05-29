import { StrictMode } from 'react';
import ReactDOM from 'react-dom/client';
import App from './App.jsx';
import { configurarTokenPortal } from './services/api.js';
import './index.css';

async function inicializar() {
  const params     = new URLSearchParams(window.location.search);
  const esPortal   = params.get('portal') === 'interno';
  const keycloakUrl = import.meta.env.VITE_KEYCLOAK_URL;

  const root = ReactDOM.createRoot(document.getElementById('root'));

  if (esPortal && keycloakUrl) {
    const { default: keycloak } = await import('./keycloak.js');
    try {
      await keycloak.init({
        onLoad:           'login-required',
        pkceMethod:       'S256',
        checkLoginIframe: false,
      });

      configurarTokenPortal(() => keycloak.token);

      keycloak.onTokenExpired = () =>
        keycloak.updateToken(60).catch(() => keycloak.login());

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
  } else {
    root.render(
      <StrictMode>
        <App />
      </StrictMode>
    );
  }
}

inicializar();
