import { Outlet, NavLink, useLocation } from 'react-router-dom';
import { ESTILOS } from '../accesos/CrearAccesoManualStyles';

const TEXTOS_VISTA = {
  '/crear': {
    titulo:    'Crear acceso manual',
    subtitulo: 'Genere credenciales únicas para que un cliente o proveedor pueda diligenciar el formulario SAGRILAFT.',
  },
  '/accesos': {
    titulo:    'Accesos creados',
    subtitulo: 'Consulte el estado de todos los accesos manuales generados.',
  },
  '/expedientes': {
    titulo:    'Formularios recibidos',
    subtitulo: 'Aqui puede consultar los formularios enviados por la contraparte, con sus documentos adjuntos.',
  },
};

function BarraUsuario({ keycloak }) {
  const email = keycloak?.tokenParsed?.email ?? keycloak?.tokenParsed?.preferred_username ?? '';
  return (
    <div style={{
      position: 'fixed', top: 0, left: 0, right: 0, zIndex: 200,
      background: 'var(--gray-900, #0f172a)', color: '#fff',
      display: 'flex', justifyContent: 'flex-end', alignItems: 'center',
      padding: '7px 24px', fontSize: '0.78rem', gap: '14px',
    }}>
      <span style={{ opacity: 0.65 }}>{email}</span>
      {keycloak && (
        <button
          onClick={() => keycloak.logout()}
          style={{
            background: 'none', border: '1px solid rgba(255,255,255,0.25)',
            color: '#fff', borderRadius: '6px', padding: '3px 10px',
            cursor: 'pointer', fontSize: '0.78rem',
          }}
        >
          Cerrar sesión
        </button>
      )}
    </div>
  );
}

function EncabezadoConTabs() {
  const location = useLocation();
  const rutaActual = location.pathname;
  const infoVista = TEXTOS_VISTA[rutaActual === '/' ? '/crear' : rutaActual] || TEXTOS_VISTA['/crear'];

  const navLinkStyle = ({ isActive }) => ESTILOS.tab(isActive);

  return (
    <>
      <div style={ESTILOS.encabezado}>
        <div style={ESTILOS.badge}>Portal Interno</div>
        <h1 style={ESTILOS.titulo}>{infoVista.titulo}</h1>
        <p style={ESTILOS.subtitulo}>{infoVista.subtitulo}</p>
      </div>

      <div style={ESTILOS.navTabs}>
        <NavLink to="/crear" style={navLinkStyle}>
          Crear acceso
        </NavLink>
        <NavLink to="/accesos" style={navLinkStyle}>
          Ver accesos
        </NavLink>
        <NavLink to="/expedientes" style={navLinkStyle}>
          Formularios
        </NavLink>
      </div>
    </>
  );
}

export default function PortalLayout({ keycloak }) {
  return (
    <div style={ESTILOS.pagina}>
      <BarraUsuario keycloak={keycloak} />
      <div style={ESTILOS.contenedor}>
        <EncabezadoConTabs />
        <Outlet />
      </div>
    </div>
  );
}
