import Keycloak from 'keycloak-js';

export default new Keycloak({
  url:      import.meta.env.VITE_KEYCLOAK_URL,
  realm:    import.meta.env.VITE_KEYCLOAK_REALM    || 'sagrilaft',
  clientId: import.meta.env.VITE_KEYCLOAK_CLIENT_ID || 'sagrilaft-portal',
});
