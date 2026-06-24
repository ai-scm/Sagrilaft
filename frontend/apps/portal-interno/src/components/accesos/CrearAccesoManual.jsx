/**
 * CrearAccesoManual — Vista del portal interno SAGRILAFT.
 * SRP: solo gestiona creación de accesos manuales y visualización del resultado.
 */

import { useState, useCallback, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../../services/api';
import {
  TIPOS_CONTRAPARTE,
  AREAS_RESPONSABLES,
  formatearFechaLarga,
  ETIQUETA_TIPO_CONTRAPARTE,
  MENSAJE_ENLACE_NOTA,
} from '../../config/constantes';
import { guardarCredenciales } from '../../utils/credenciales';

import { ESTILOS } from './CrearAccesoManualStyles';

const ESTADO_INICIAL_ACCESO = {
  tipo_contraparte: '',
  razon_social: '',
  area_responsable: '',
};

const ASTERISCO = <span style={{ color: 'var(--error, #ef4444)' }}>*</span>;

function validarCamposAcceso(formData) {
  const errores = {};
  if (!formData.tipo_contraparte) errores.tipo_contraparte = 'Seleccione el tipo de contraparte';
  if (!formData.razon_social.trim()) errores.razon_social = 'Ingrese la razón social';
  if (!formData.area_responsable) errores.area_responsable = 'Seleccione el área de contacto';

  return errores;
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

function CampoInput({ id, label, type = 'text', placeholder, value, onChange, onFocus, onBlur, style, error, disabled, autoComplete }) {
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
        autoComplete={autoComplete}
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

export default function CrearAccesoManual() {
  const navigate = useNavigate();
  const [formData, setFormData] = useState(ESTADO_INICIAL_ACCESO);
  const [erroresCampo, setErroresCampo] = useState({});
  const [errorGlobal, setErrorGlobal] = useState(null);
  const [cargando, setCargando] = useState(false);
  const [resultado, setResultado] = useState(null);
  const [copiado, setCopiado] = useState(false);
  const [campoEnfocado, setCampoEnfocado] = useState(null);

  const temporizadorRef = useRef(null);

  useEffect(() => () => clearTimeout(temporizadorRef.current), []);

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
      guardarCredenciales(acceso);
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

  const handleCrearOtro = () => {
    setResultado(null);
    setFormData(ESTADO_INICIAL_ACCESO);
    setErroresCampo({});
    setErrorGlobal(null);
  };

  const estiloInput = (campo) => ({
    ...ESTILOS.input,
    ...(campoEnfocado === campo ? ESTILOS.inputFocus : {}),
    ...(erroresCampo[campo] ? ESTILOS.inputError : {}),
  });

  if (resultado) {
    return (
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
            de forma segura antes de cerrar esta pantalla. Tiene una ventana de 10 min para verlo en "Ver accesos" después de creado, pero luego se ocultará por seguridad.
          </div>

          <ItemCredencial label="Código de petición" valor={resultado.codigo_peticion} />
          <ItemCredencial label="PIN de acceso" valor={resultado.pin} />
          {resultado.correo_destinatario && <ItemCredencial label="Destinatario" valor={resultado.correo_destinatario} monospace={false} />}
          <ItemCredencial label="Válido hasta" valor={formatearFechaLarga(resultado.expires_at)} monospace={false} />

          <div style={ESTILOS.enlaceBox}>
            <p style={ESTILOS.enlaceLabel}>Enlace de diligenciamiento</p>
            <p style={ESTILOS.enlaceTexto}>{resultado.enlace_diligenciamiento}</p>
            <p style={ESTILOS.enlaceNota}>{MENSAJE_ENLACE_NOTA}</p>
            <button style={ESTILOS.btnCopiar} onClick={handleCopiarEnlace} type="button">
              {copiado ? 'Copiado' : 'Copiar enlace'}
            </button>
          </div>

          <button
            style={ESTILOS.btnPrincipal}
            onClick={() => navigate('/accesos')}
            type="button"
          >
            Ver todos los accesos
          </button>
          <button style={ESTILOS.btnNuevo} onClick={handleCrearOtro} type="button">
            Crear otro acceso
          </button>
        </div>
      </div>
    );
  }

  return (
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
            id="area_responsable" label="Área de Contacto"
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
          autoComplete="off"
        />
        <div style={ESTILOS.fila}>
          <div style={ESTILOS.campo}>
            <label style={ESTILOS.label}>Código de petición</label>
            <input type="text" value="Se genera automáticamente" readOnly style={{ ...ESTILOS.input, ...ESTILOS.inputReadonly }} />
          </div>
          <div style={ESTILOS.campo}>
            <label style={ESTILOS.label}>PIN de acceso</label>
            <input type="text" value="Se genera automáticamente" readOnly style={{ ...ESTILOS.input, ...ESTILOS.inputReadonly }} />
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
  );
}
