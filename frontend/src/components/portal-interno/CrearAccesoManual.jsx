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
import {
  TIPOS_CONTRAPARTE,
  AREAS_RESPONSABLES,
  formatearFechaLarga,
  ETIQUETA_TIPO_CONTRAPARTE,
} from './constantes';

// ── Constantes ────────────────────────────────────────────────────────────────

const ESTADO_INICIAL_FORM = {
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
};

// ── Estilos ───────────────────────────────────────────────────────────────────

const s = {
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
    borderColor: 'var(--primary-500, #3b82f6)',
  },
  inputError: {
    borderColor: 'var(--error, #ef4444)',
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
};

// ── Validación de formulario ──────────────────────────────────────────────────

function validarCamposAcceso(formData) {
  const errores = {};
  if (!formData.tipo_contraparte)          errores.tipo_contraparte    = 'Seleccione el tipo de contraparte';
  if (!formData.razon_social.trim())       errores.razon_social        = 'Ingrese la razón social';
  if (!formData.correo_destinatario.trim()) errores.correo_destinatario = 'Ingrese el correo del destinatario';
  if (!formData.area_responsable)          errores.area_responsable    = 'Seleccione el área responsable';

  const correoRegex = /^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$/;
  if (formData.correo_destinatario && !correoRegex.test(formData.correo_destinatario)) {
    errores.correo_destinatario = 'Formato de correo inválido';
  }
  return errores;
}

// ── Sub-componentes ───────────────────────────────────────────────────────────

function EncabezadoConTabs({ vistaEfectiva, onCambiarVista }) {
  return (
    <>
      <div style={s.encabezado}>
        <div style={s.badge}>Portal Interno</div>
        <h1 style={s.titulo}>{TEXTOS_VISTA[vistaEfectiva].titulo}</h1>
        <p style={s.subtitulo}>{TEXTOS_VISTA[vistaEfectiva].subtitulo}</p>
      </div>

      <div style={s.navTabs}>
        <button
          style={s.tab(vistaEfectiva === 'crear' || vistaEfectiva === 'exito')}
          onClick={() => onCambiarVista('crear')}
          type="button"
        >
          Crear acceso
        </button>
        <button
          style={s.tab(vistaEfectiva === 'listar')}
          onClick={() => onCambiarVista('listar')}
          type="button"
        >
          Ver accesos
        </button>
      </div>
    </>
  );
}

// ── Componente ────────────────────────────────────────────────────────────────

export default function CrearAccesoManual() {
  const [vistaActual, setVistaActual]   = useState('crear');
  const [formData, setFormData]         = useState(ESTADO_INICIAL_FORM);
  const [erroresCampo, setErroresCampo] = useState({});
  const [errorGlobal, setErrorGlobal]   = useState(null);
  const [cargando, setCargando]         = useState(false);
  const [resultado, setResultado]       = useState(null);
  const [copiado, setCopiado]           = useState(false);
  const [focusField, setFocusField]     = useState(null);

  const timeoutRef = useRef(null);

  const vistaEfectiva = vistaActual === 'crear' && resultado ? 'exito' : vistaActual;

  useEffect(() => () => clearTimeout(timeoutRef.current), []);

  const handleCambiarVista = useCallback((vista) => {
    if (vista === 'crear' && resultado) {
      setResultado(null);
      setFormData(ESTADO_INICIAL_FORM);
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

  const handleSubmit = async (e) => {
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
    } catch (err) {
      setErrorGlobal('Error al crear el acceso. Verifique los datos e intente nuevamente.');
    } finally {
      setCargando(false);
    }
  };

  const handleCopiarEnlace = () => {
    if (!resultado) return;
    navigator.clipboard.writeText(resultado.enlace_diligenciamiento).then(() => {
      setCopiado(true);
      clearTimeout(timeoutRef.current);
      timeoutRef.current = setTimeout(() => setCopiado(false), 2500);
    });
  };

  const estiloInput = (campo) => ({
    ...s.input,
    ...(focusField === campo ? s.inputFocus : {}),
    ...(erroresCampo[campo] ? s.inputError : {}),
  });

  // ── Vista: listado ────────────────────────────────────────────────────────
  if (vistaEfectiva === 'listar') {
    return (
      <div style={s.pagina}>
        <div style={s.contenedor}>
          <EncabezadoConTabs vistaEfectiva={vistaEfectiva} onCambiarVista={handleCambiarVista} />
          <ListaAccesosManuales mensajeVacio="No hay accesos creados aún. Crea el primero desde la pestaña Crear acceso." />
        </div>
      </div>
    );
  }

  // ── Vista: resultado exitoso ──────────────────────────────────────────────
  if (vistaEfectiva === 'exito') {
    return (
      <div style={s.pagina}>
        <div style={s.contenedor}>
          <EncabezadoConTabs vistaEfectiva={vistaEfectiva} onCambiarVista={handleCambiarVista} />

          <div style={s.panelExito}>
            <div style={s.encabezadoExito}>
              <p style={s.tituloExito}>Acceso manual generado exitosamente</p>
              <p style={s.subtituloExito}>
                {resultado.razon_social} · {ETIQUETA_TIPO_CONTRAPARTE[resultado.tipo_contraparte] ?? resultado.tipo_contraparte}
              </p>
            </div>

            <div style={s.cuerpoExito}>
              <div style={s.advertenciaPIN}>
                <strong>Nota de seguridad:</strong> El PIN se muestra una sola vez. Anótelo o compártalo
                de forma segura antes de cerrar esta pantalla. El sistema nunca lo vuelve a mostrar.
              </div>

              <div style={s.credencial}>
                <span style={s.credencialLabel}>Código de petición</span>
                <span style={s.credencialValor}>{resultado.codigo_peticion}</span>
              </div>

              <div style={s.credencial}>
                <span style={s.credencialLabel}>PIN de acceso</span>
                <span style={s.credencialValor}>{resultado.pin}</span>
              </div>

              <div style={s.credencial}>
                <span style={s.credencialLabel}>Destinatario</span>
                <span style={{ ...s.credencialValor, fontFamily: 'inherit', letterSpacing: 0 }}>
                  {resultado.correo_destinatario}
                </span>
              </div>

              <div style={s.credencial}>
                <span style={s.credencialLabel}>Válido hasta</span>
                <span style={{ ...s.credencialValor, fontFamily: 'inherit', letterSpacing: 0 }}>
                  {formatearFechaLarga(resultado.expires_at)}
                </span>
              </div>

              <div style={s.enlaceBox}>
                <p style={s.enlaceLabel}>Enlace de diligenciamiento</p>
                <p style={s.enlaceTexto}>{resultado.enlace_diligenciamiento}</p>
                <button style={s.btnCopiar} onClick={handleCopiarEnlace} type="button">
                  {copiado ? 'Copiado' : 'Copiar enlace'}
                </button>
              </div>

              <button
                style={s.btnPrincipal}
                onClick={() => handleCambiarVista('listar')}
                type="button"
              >
                Ver todos los accesos
              </button>
              <button style={s.btnNuevo} onClick={() => handleCambiarVista('crear')} type="button">
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
    <div style={s.pagina}>
      <div style={s.contenedor}>
        <EncabezadoConTabs vistaEfectiva={vistaEfectiva} onCambiarVista={handleCambiarVista} />

        <form onSubmit={handleSubmit} noValidate>
          <div style={s.tarjeta}>

            {errorGlobal && <div style={s.errorGlobal}>{errorGlobal}</div>}

            <div style={s.fila}>
              <div style={s.campo}>
                <label style={s.label} htmlFor="tipo_contraparte">
                  Tipo de contraparte <span style={{ color: 'var(--error, #ef4444)' }}>*</span>
                </label>
                <select
                  id="tipo_contraparte"
                  value={formData.tipo_contraparte}
                  onChange={e => handleChange('tipo_contraparte', e.target.value)}
                  style={{
                    ...s.select,
                    ...(erroresCampo.tipo_contraparte ? s.inputError : {}),
                  }}
                  disabled={cargando}
                >
                  <option value="">Seleccionar…</option>
                  {TIPOS_CONTRAPARTE.map(({ valor, etiqueta }) => (
                    <option key={valor} value={valor}>{etiqueta}</option>
                  ))}
                </select>
                {erroresCampo.tipo_contraparte && (
                  <span style={{ fontSize: '0.78rem', color: 'var(--error, #ef4444)', marginTop: '4px', display: 'block' }}>
                    {erroresCampo.tipo_contraparte}
                  </span>
                )}
              </div>

              <div style={s.campo}>
                <label style={s.label} htmlFor="area_responsable">
                  Área responsable <span style={{ color: 'var(--error, #ef4444)' }}>*</span>
                </label>
                <select
                  id="area_responsable"
                  value={formData.area_responsable}
                  onChange={e => handleChange('area_responsable', e.target.value)}
                  style={{
                    ...s.select,
                    ...(erroresCampo.area_responsable ? s.inputError : {}),
                  }}
                  disabled={cargando}
                >
                  <option value="">Seleccionar…</option>
                  {AREAS_RESPONSABLES.map(({ valor, etiqueta }) => (
                    <option key={valor} value={valor}>{etiqueta}</option>
                  ))}
                </select>
                {erroresCampo.area_responsable && (
                  <span style={{ fontSize: '0.78rem', color: 'var(--error, #ef4444)', marginTop: '4px', display: 'block' }}>
                    {erroresCampo.area_responsable}
                  </span>
                )}
              </div>
            </div>

            <div style={s.campo}>
              <label style={s.label} htmlFor="razon_social">
                Razón social empresa <span style={{ color: 'var(--error, #ef4444)' }}>*</span>
              </label>
              <input
                id="razon_social"
                type="text"
                placeholder="Nombre completo de la empresa"
                value={formData.razon_social}
                onChange={e => handleChange('razon_social', e.target.value)}
                onFocus={() => setFocusField('razon_social')}
                onBlur={() => setFocusField(null)}
                style={estiloInput('razon_social')}
                disabled={cargando}
              />
              {erroresCampo.razon_social && (
                <span style={{ fontSize: '0.78rem', color: 'var(--error, #ef4444)', marginTop: '4px', display: 'block' }}>
                  {erroresCampo.razon_social}
                </span>
              )}
            </div>

            <div style={s.campo}>
              <label style={s.label} htmlFor="correo_destinatario">
                Correo destinatario <span style={{ color: 'var(--error, #ef4444)' }}>*</span>
              </label>
              <input
                id="correo_destinatario"
                type="email"
                placeholder="contacto@empresa.com"
                value={formData.correo_destinatario}
                onChange={e => handleChange('correo_destinatario', e.target.value)}
                onFocus={() => setFocusField('correo_destinatario')}
                onBlur={() => setFocusField(null)}
                style={estiloInput('correo_destinatario')}
                disabled={cargando}
              />
              {erroresCampo.correo_destinatario && (
                <span style={{ fontSize: '0.78rem', color: 'var(--error, #ef4444)', marginTop: '4px', display: 'block' }}>
                  {erroresCampo.correo_destinatario}
                </span>
              )}
            </div>

            <div style={s.fila}>
              <div style={s.campo}>
                <label style={s.label}>Código de petición</label>
                <input
                  type="text"
                  value="Se genera automáticamente"
                  readOnly
                  style={{ ...s.input, ...s.inputReadonly }}
                />
              </div>
              <div style={s.campo}>
                <label style={s.label}>PIN de acceso</label>
                <input
                  type="text"
                  value="Se genera automáticamente"
                  readOnly
                  style={{ ...s.input, ...s.inputReadonly }}
                />
              </div>
            </div>

          </div>

          <button
            type="submit"
            style={{
              ...s.btnPrincipal,
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
