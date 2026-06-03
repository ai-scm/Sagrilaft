/**
 * CrearAccesoManual — Vista del portal interno SAGRILAFT.
 *
 * Permite a equipos de Ventas, Legal y Finanzas generar un enlace único
 * de diligenciamiento vinculado a un formulario SAGRILAFT para un cliente
 * o proveedor específico.
 *
 * Flujo:
 *   1. Usuario interno completa el formulario con datos de la contraparte.
 *   2. Al confirmar, el backend genera: código de petición, PIN hasheado y
 *      token de diligenciamiento.
 *   3. Se muestra el resultado con las credenciales para referencia del área
 *      y el enlace tokenizado para enviar al destinatario externo.
 *
 * SRP: solo gestiona creación de accesos manuales y visualización del resultado.
 */

import { useState, useCallback, useRef, useEffect } from 'react';
import { api } from '../../services/api';
import ListaAccesosManuales from './ListaAccesosManuales';
import VistaExpedientes from './VistaExpedientes';
import {
  TIPOS_CONTRAPARTE,
  AREAS_RESPONSABLES,
  formatearFechaLarga,
  ETIQUETA_TIPO_CONTRAPARTE,
} from './constantes';
import { REGEX_CORREO } from '../../utils/constantes';

// ── Constantes ────────────────────────────────────────────────────────────────

const ESTADO_INICIAL_ACCESO = {
  tipo_contraparte:    '',
  razon_social:        '',
  correo_destinatario: '',
  area_responsable:    '',
};

const TEXTOS_VISTA = {
  crear: {
    titulo:    'Crear acceso manual',
    subtitulo: 'Genere credenciales únicas para que un cliente o proveedor pueda diligenciar el formulario SAGRILAFT.',
  },
  exito: {
    titulo:    'Acceso creado',
    subtitulo: 'Comparta las credenciales con el destinatario de forma segura.',
  },
  listar: {
    titulo:    'Accesos creados',
    subtitulo: 'Consulte el estado de todos los accesos manuales generados.',
  },
  expedientes: {
    titulo:    'Formularios recibidos',
    subtitulo: 'Aqui puede consultar los formularios enviados por la contraparte, con sus documentos adjuntos.',
  },
};

// ── Estilos ───────────────────────────────────────────────────────────────────

const ESTILOS = {
  pagina: {
    minHeight: '100vh',
    background: 'var(--gray-50, #f8fafc)',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    padding: '40px 16px',
  },
  contenedor: {
    width: '100%',
    maxWidth: '560px',
  },
  encabezado: {
    marginBottom: '32px',
  },
  badge: {
    display: 'inline-block',
    fontSize: '0.75rem',
    fontWeight: '700',
    letterSpacing: '0.06em',
    textTransform: 'uppercase',
    color: 'var(--primary-700, #1d4ed8)',
    background: 'var(--primary-50, #eff6ff)',
    borderRadius: '999px',
    padding: '4px 12px',
    marginBottom: '12px',
  },
  titulo: {
    fontSize: '1.6rem',
    fontWeight: '800',
    color: 'var(--gray-900, #0f172a)',
    margin: '0 0 8px',
  },
  subtitulo: {
    fontSize: '0.9rem',
    color: 'var(--gray-500, #64748b)',
    margin: 0,
  },
  tarjeta: {
    background: '#fff',
    borderRadius: 'var(--radius-lg, 12px)',
    boxShadow: '0 1px 3px rgba(0,0,0,0.08), 0 4px 16px rgba(0,0,0,0.05)',
    padding: '32px',
    marginBottom: '24px',
  },
  campo: {
    marginBottom: '20px',
  },
  label: {
    display: 'block',
    fontSize: '0.82rem',
    fontWeight: '600',
    color: 'var(--gray-700, #334155)',
    marginBottom: '6px',
  },
  input: {
    width: '100%',
    padding: '10px 14px',
    border: '1.5px solid var(--gray-200, #e2e8f0)',
    borderRadius: 'var(--radius-md, 8px)',
    fontSize: '0.9rem',
    color: 'var(--gray-800, #1e293b)',
    outline: 'none',
    transition: 'border-color 0.15s',
    boxSizing: 'border-box',
  },
  inputFocus: {
    border: '1.5px solid var(--primary-500, #3b82f6)',
  },
  inputError: {
    border: '1.5px solid var(--error, #ef4444)',
  },
  inputReadonly: {
    background: 'var(--gray-50, #f8fafc)',
    color: 'var(--gray-500, #64748b)',
    cursor: 'not-allowed',
    fontFamily: 'monospace',
    letterSpacing: '0.08em',
  },
  select: {
    width: '100%',
    padding: '10px 14px',
    border: '1.5px solid var(--gray-200, #e2e8f0)',
    borderRadius: 'var(--radius-md, 8px)',
    fontSize: '0.9rem',
    color: 'var(--gray-800, #1e293b)',
    outline: 'none',
    background: '#fff',
    cursor: 'pointer',
    transition: 'border-color 0.15s',
    boxSizing: 'border-box',
    appearance: 'none',
  },
  fila: {
    display: 'grid',
    gridTemplateColumns: '1fr 1fr',
    gap: '16px',
  },
  btnPrincipal: {
    width: '100%',
    padding: '13px 0',
    background: 'var(--primary-600, #2563eb)',
    color: '#fff',
    border: 'none',
    borderRadius: 'var(--radius-md, 8px)',
    fontSize: '0.95rem',
    fontWeight: '700',
    cursor: 'pointer',
    transition: 'background 0.15s',
  },
  // Panel de resultado exitoso
  panelExito: {
    background: '#fff',
    borderRadius: 'var(--radius-lg, 12px)',
    boxShadow: '0 1px 3px rgba(0,0,0,0.08), 0 4px 16px rgba(0,0,0,0.05)',
    overflow: 'hidden',
  },
  encabezadoExito: {
    background: 'linear-gradient(135deg, #059669 0%, #047857 100%)',
    padding: '24px 32px',
    color: '#fff',
  },
  tituloExito: {
    fontSize: '1.1rem',
    fontWeight: '700',
    margin: '0 0 4px',
  },
  subtituloExito: {
    fontSize: '0.85rem',
    opacity: 0.85,
    margin: 0,
  },
  cuerpoExito: {
    padding: '28px 32px',
  },
  credencial: {
    background: 'var(--gray-50, #f8fafc)',
    borderRadius: 'var(--radius-md, 8px)',
    border: '1px solid var(--gray-200, #e2e8f0)',
    padding: '16px 20px',
    marginBottom: '12px',
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
  },
  credencialLabel: {
    fontSize: '0.75rem',
    fontWeight: '700',
    color: 'var(--gray-500, #64748b)',
    textTransform: 'uppercase',
    letterSpacing: '0.06em',
  },
  credencialValor: {
    fontSize: '1.1rem',
    fontWeight: '700',
    color: 'var(--gray-900, #0f172a)',
    fontFamily: 'monospace',
    letterSpacing: '0.08em',
  },
  advertenciaPIN: {
    background: '#fefce8',
    border: '1px solid #fde047',
    borderRadius: 'var(--radius-md, 8px)',
    padding: '12px 16px',
    fontSize: '0.82rem',
    color: '#854d0e',
    marginBottom: '20px',
  },
  enlaceBox: {
    background: '#f0fdf4',
    border: '1px solid #bbf7d0',
    borderRadius: 'var(--radius-md, 8px)',
    padding: '14px 16px',
    marginBottom: '20px',
  },
  enlaceLabel: {
    fontSize: '0.75rem',
    fontWeight: '700',
    color: '#15803d',
    textTransform: 'uppercase',
    letterSpacing: '0.06em',
    marginBottom: '6px',
  },
  enlaceTexto: {
    fontSize: '0.82rem',
    color: '#166534',
    wordBreak: 'break-all',
    fontFamily: 'monospace',
  },
  btnCopiar: {
    marginTop: '8px',
    padding: '6px 14px',
    background: '#dcfce7',
    color: '#15803d',
    border: '1px solid #86efac',
    borderRadius: 'var(--radius-sm, 6px)',
    fontSize: '0.8rem',
    fontWeight: '600',
    cursor: 'pointer',
  },
  btnNuevo: {
    width: '100%',
    padding: '11px 0',
    background: 'transparent',
    color: 'var(--primary-600, #2563eb)',
    border: '1.5px solid var(--primary-200, #bfdbfe)',
    borderRadius: 'var(--radius-md, 8px)',
    fontSize: '0.9rem',
    fontWeight: '600',
    cursor: 'pointer',
    marginTop: '8px',
  },
  // Navegación por tabs
  navTabs: {
    display:       'flex',
    gap:           '4px',
    background:    'var(--gray-100, #f1f5f9)',
    borderRadius:  'var(--radius-md, 8px)',
    padding:       '4px',
    marginBottom:  '24px',
  },
  tab: (activo) => ({
    flex:         1,
    padding:      '8px 0',
    background:   activo ? '#fff' : 'transparent',
    color:        activo ? 'var(--gray-900, #0f172a)' : 'var(--gray-500, #64748b)',
    border:       'none',
    borderRadius: 'var(--radius-sm, 6px)',
    fontSize:     '0.85rem',
    fontWeight:   activo ? '700' : '500',
    cursor:       'pointer',
    boxShadow:    activo ? '0 1px 3px rgba(0,0,0,0.08)' : 'none',
    transition:   'all 0.15s',
  }),
  errorGlobal: {
    background: '#fef2f2',
    border: '1px solid #fca5a5',
    borderRadius: 'var(--radius-md, 8px)',
    padding: '12px 16px',
    fontSize: '0.85rem',
    color: '#991b1b',
    marginBottom: '16px',
  },
  errorCampo: {
    fontSize: '0.78rem',
    color: 'var(--error, #ef4444)',
    marginTop: '4px',
    display: 'block',
  },
};

// ── Constante de campo requerido ──────────────────────────────────────────────

const ASTERISCO = <span style={{ color: 'var(--error, #ef4444)' }}>*</span>;

// ── Validación de formulario ──────────────────────────────────────────────────

function validarCamposAcceso(formData) {
  const errores = {};
  if (!formData.tipo_contraparte)          errores.tipo_contraparte    = 'Seleccione el tipo de contraparte';
  if (!formData.razon_social.trim())       errores.razon_social        = 'Ingrese la razón social';
  if (!formData.correo_destinatario.trim()) errores.correo_destinatario = 'Ingrese el correo del destinatario';
  if (!formData.area_responsable)          errores.area_responsable    = 'Seleccione el área responsable';

  if (formData.correo_destinatario && !REGEX_CORREO.test(formData.correo_destinatario)) {
    errores.correo_destinatario = 'Formato de correo inválido';
  }
  return errores;
}

// ── Sub-componentes ───────────────────────────────────────────────────────────

function EncabezadoConTabs({ vistaEfectiva, onCambiarVista }) {
  return (
    <>
      <div style={ESTILOS.encabezado}>
        <div style={ESTILOS.badge}>Portal Interno</div>
        <h1 style={ESTILOS.titulo}>{TEXTOS_VISTA[vistaEfectiva].titulo}</h1>
        <p style={ESTILOS.subtitulo}>{TEXTOS_VISTA[vistaEfectiva].subtitulo}</p>
      </div>

      <div style={ESTILOS.navTabs}>
        <button
          style={ESTILOS.tab(vistaEfectiva === 'crear' || vistaEfectiva === 'exito')}
          onClick={() => onCambiarVista('crear')}
          type="button"
        >
          Crear acceso
        </button>
        <button
          style={ESTILOS.tab(vistaEfectiva === 'listar')}
          onClick={() => onCambiarVista('listar')}
          type="button"
        >
          Ver accesos
        </button>
        <button
          style={ESTILOS.tab(vistaEfectiva === 'expedientes')}
          onClick={() => onCambiarVista('expedientes')}
          type="button"
        >
          Formularios
        </button>
      </div>
    </>
  );
}

function CampoSelect({ id, label, value, onChange, options, error, disabled }) {
  return (
    <div style={ESTILOS.campo}>
      <label style={ESTILOS.label} htmlFor={id}>
        {label} {ASTERISCO}
      </label>
      <select
        id={id}
        value={value}
        onChange={e => onChange(id, e.target.value)}
        style={{ ...ESTILOS.select, ...(error ? ESTILOS.inputError : {}) }}
        disabled={disabled}
      >
        <option value="">Seleccionar…</option>
        {options.map(({ valor, etiqueta }) => (
          <option key={valor} value={valor}>{etiqueta}</option>
        ))}
      </select>
      {error && <span style={ESTILOS.errorCampo}>{error}</span>}
    </div>
  );
}

function CampoInput({ id, label, type = 'text', placeholder, value, onChange,
                      onFocus, onBlur, style, error, disabled }) {
  return (
    <div style={ESTILOS.campo}>
      <label style={ESTILOS.label} htmlFor={id}>
        {label} {ASTERISCO}
      </label>
      <input
        id={id} type={type} placeholder={placeholder}
        value={value} onChange={e => onChange(id, e.target.value)}
        onFocus={onFocus} onBlur={onBlur}
        style={style} disabled={disabled}
      />
      {error && <span style={ESTILOS.errorCampo}>{error}</span>}
    </div>
  );
}

function ItemCredencial({ label, valor, monospace = true }) {
  const estiloValor = monospace
    ? ESTILOS.credencialValor
    : { ...ESTILOS.credencialValor, fontFamily: 'inherit', letterSpacing: 0 };
  return (
    <div style={ESTILOS.credencial}>
      <span style={ESTILOS.credencialLabel}>{label}</span>
      <span style={estiloValor}>{valor}</span>
    </div>
  );
}

// ── Componente ────────────────────────────────────────────────────────────────

function BarraUsuario({ keycloak }) {
  const email = keycloak.tokenParsed?.email ?? keycloak.tokenParsed?.preferred_username ?? '';
  return (
    <div style={{
      position: 'fixed', top: 0, left: 0, right: 0, zIndex: 200,
      background: 'var(--gray-900, #0f172a)', color: '#fff',
      display: 'flex', justifyContent: 'flex-end', alignItems: 'center',
      padding: '7px 24px', fontSize: '0.78rem', gap: '14px',
    }}>
      <span style={{ opacity: 0.65 }}>{email}</span>
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
    </div>
  );
}

export default function CrearAccesoManual({ keycloak }) {
  const [vistaActual, setVistaActual]   = useState('crear');
  const [formData, setFormData]         = useState(ESTADO_INICIAL_ACCESO);
  const [erroresCampo, setErroresCampo] = useState({});
  const [errorGlobal, setErrorGlobal]   = useState(null);
  const [cargando, setCargando]         = useState(false);
  const [resultado, setResultado]       = useState(null);
  const [copiado, setCopiado]           = useState(false);
  const [campoEnfocado, setCampoEnfocado]  = useState(null);

  const temporizadorRef = useRef(null);

  const vistaEfectiva = vistaActual === 'crear' && resultado ? 'exito' : vistaActual;

  useEffect(() => () => clearTimeout(temporizadorRef.current), []);

  const handleCambiarVista = useCallback((vista) => {
    if (vista === 'crear' && resultado) {
      setResultado(null);
      setFormData(ESTADO_INICIAL_ACCESO);
      setErroresCampo({});
      setErrorGlobal(null);
    }
    setVistaActual(vista);
  }, [resultado]);

  const handleChange = useCallback((campo, valor) => {
    setFormData(prev => ({ ...prev, [campo]: valor }));
    setErroresCampo(prev => ({ ...prev, [campo]: null }));
    setErrorGlobal(null);
  }, []);

  const handleSubmit = useCallback(async (e) => {
    e.preventDefault();
    const errores = validarCamposAcceso(formData);
    if (Object.keys(errores).length > 0) {
      setErroresCampo(errores);
      return;
    }

    setCargando(true);
    setErrorGlobal(null);
    try {
      const acceso = await api.crearAccesoManual(formData);
      setResultado(acceso);
    } catch (errorCreacion) {
      setErrorGlobal('Error al crear el acceso. Verifique los datos e intente nuevamente.');
    } finally {
      setCargando(false);
    }
  }, [formData]);

  const handleCopiarEnlace = () => {
    if (!resultado) return;
    navigator.clipboard.writeText(resultado.enlace_diligenciamiento).then(() => {
      setCopiado(true);
      clearTimeout(temporizadorRef.current);
      temporizadorRef.current = setTimeout(() => setCopiado(false), 2500);
    });
  };

  const estiloInput = (campo) => ({
    ...ESTILOS.input,
    ...(campoEnfocado === campo ? ESTILOS.inputFocus : {}),
    ...(erroresCampo[campo] ? ESTILOS.inputError : {}),
  });

  // ── Vista: formularios recibidos ──────────────────────────────────────────
  if (vistaEfectiva === 'expedientes') {
    return (
      <div style={ESTILOS.pagina}>
        {keycloak && <BarraUsuario keycloak={keycloak} />}
        <div style={ESTILOS.contenedor}>
          <EncabezadoConTabs vistaEfectiva={vistaEfectiva} onCambiarVista={handleCambiarVista} />
          <VistaExpedientes />
        </div>
      </div>
    );
  }

  // ── Vista: listado ────────────────────────────────────────────────────────
  if (vistaEfectiva === 'listar') {
    return (
      <div style={ESTILOS.pagina}>
        {keycloak && <BarraUsuario keycloak={keycloak} />}
        <div style={ESTILOS.contenedor}>
          <EncabezadoConTabs vistaEfectiva={vistaEfectiva} onCambiarVista={handleCambiarVista} />
          <ListaAccesosManuales mensajeVacio="No hay accesos creados aún. Crea el primero desde la pestaña Crear acceso." />
        </div>
      </div>
    );
  }

  // ── Vista: resultado exitoso ──────────────────────────────────────────────
  if (vistaEfectiva === 'exito') {
    return (
      <div style={ESTILOS.pagina}>
        {keycloak && <BarraUsuario keycloak={keycloak} />}
        <div style={ESTILOS.contenedor}>
          <EncabezadoConTabs vistaEfectiva={vistaEfectiva} onCambiarVista={handleCambiarVista} />

          <div style={ESTILOS.panelExito}>
            <div style={ESTILOS.encabezadoExito}>
              <p style={ESTILOS.tituloExito}>Acceso manual generado exitosamente</p>
              <p style={ESTILOS.subtituloExito}>
                {resultado.razon_social} · {ETIQUETA_TIPO_CONTRAPARTE[resultado.tipo_contraparte] ?? resultado.tipo_contraparte}
              </p>
            </div>

            <div style={ESTILOS.cuerpoExito}>
              <div style={ESTILOS.advertenciaPIN}>
                <strong>Nota de seguridad:</strong> El PIN se muestra una sola vez. Anótelo o compártalo
                de forma segura antes de cerrar esta pantalla. El sistema nunca lo vuelve a mostrar.
              </div>

              <ItemCredencial label="Código de petición" valor={resultado.codigo_peticion} />
              <ItemCredencial label="PIN de acceso"       valor={resultado.pin} />
              <ItemCredencial label="Destinatario"        valor={resultado.correo_destinatario} monospace={false} />
              <ItemCredencial label="Válido hasta"        valor={formatearFechaLarga(resultado.expires_at)} monospace={false} />

              <div style={ESTILOS.enlaceBox}>
                <p style={ESTILOS.enlaceLabel}>Enlace de diligenciamiento</p>
                <p style={ESTILOS.enlaceTexto}>{resultado.enlace_diligenciamiento}</p>
                <button style={ESTILOS.btnCopiar} onClick={handleCopiarEnlace} type="button">
                  {copiado ? 'Copiado' : 'Copiar enlace'}
                </button>
              </div>

              <button
                style={ESTILOS.btnPrincipal}
                onClick={() => handleCambiarVista('listar')}
                type="button"
              >
                Ver todos los accesos
              </button>
              <button style={ESTILOS.btnNuevo} onClick={() => handleCambiarVista('crear')} type="button">
                Crear otro acceso
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // ── Vista: formulario de creación ─────────────────────────────────────────
  return (
    <div style={ESTILOS.pagina}>
      {keycloak && <BarraUsuario keycloak={keycloak} />}
      <div style={ESTILOS.contenedor}>
        <EncabezadoConTabs vistaEfectiva={vistaEfectiva} onCambiarVista={handleCambiarVista} />

        <form onSubmit={handleSubmit} noValidate>
          <div style={ESTILOS.tarjeta}>

            {errorGlobal && <div style={ESTILOS.errorGlobal}>{errorGlobal}</div>}

            <div style={ESTILOS.fila}>
              <CampoSelect
                id="tipo_contraparte" label="Tipo de contraparte"
                value={formData.tipo_contraparte} onChange={handleChange}
                options={TIPOS_CONTRAPARTE} error={erroresCampo.tipo_contraparte} disabled={cargando}
              />
              <CampoSelect
                id="area_responsable" label="Área responsable"
                value={formData.area_responsable} onChange={handleChange}
                options={AREAS_RESPONSABLES} error={erroresCampo.area_responsable} disabled={cargando}
              />
            </div>

            <CampoInput
              id="razon_social" label="Nombre o Razón social empresa"
              placeholder="Nombre completo de la empresa"
              value={formData.razon_social} onChange={handleChange}
              onFocus={() => setCampoEnfocado('razon_social')} onBlur={() => setCampoEnfocado(null)}
              style={estiloInput('razon_social')} error={erroresCampo.razon_social} disabled={cargando}
            />

            <CampoInput
              id="correo_destinatario" label="Correo destinatario" type="email"
              placeholder="contacto@empresa.com"
              value={formData.correo_destinatario} onChange={handleChange}
              onFocus={() => setCampoEnfocado('correo_destinatario')} onBlur={() => setCampoEnfocado(null)}
              style={estiloInput('correo_destinatario')} error={erroresCampo.correo_destinatario} disabled={cargando}
            />

            <div style={ESTILOS.fila}>
              <div style={ESTILOS.campo}>
                <label style={ESTILOS.label}>Código de petición</label>
                <input
                  type="text"
                  value="Se genera automáticamente"
                  readOnly
                  style={{ ...ESTILOS.input, ...ESTILOS.inputReadonly }}
                />
              </div>
              <div style={ESTILOS.campo}>
                <label style={ESTILOS.label}>PIN de acceso</label>
                <input
                  type="text"
                  value="Se genera automáticamente"
                  readOnly
                  style={{ ...ESTILOS.input, ...ESTILOS.inputReadonly }}
                />
              </div>
            </div>

          </div>

          <button
            type="submit"
            style={{
              ...ESTILOS.btnPrincipal,
              opacity: cargando ? 0.6 : 1,
              cursor: cargando ? 'not-allowed' : 'pointer',
            }}
            disabled={cargando}
          >
            {cargando ? 'Generando acceso…' : 'Crear acceso'}
          </button>
        </form>
      </div>
    </div>
  );
}
