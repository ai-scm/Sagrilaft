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
  ETIQUETA_AREA_RESPONSABLE,
  MENSAJE_ENLACE_NOTA,
} from '../../config/constantes';
import { guardarCredenciales } from '../../utils/credenciales';
import { esCorreoValido, normalizarCorreo } from '../../utils/validadores';
import ModalConfirmacion from '../modals/ModalConfirmacion';

import { ESTILOS } from './CrearAccesoManualStyles';

const ESTADO_INICIAL_ACCESO = {
  tipo_contraparte: '',
  razon_social: '',
  area_responsable: '',
  correo_destinatario: '',
};

const ASTERISCO = <span style={{ color: 'var(--error, #ef4444)' }}>*</span>;

function validarCamposAcceso(formData) {
  const errores = {};
  if (!formData.tipo_contraparte) errores.tipo_contraparte = 'Seleccione el tipo de contraparte';
  if (!formData.razon_social.trim()) errores.razon_social = 'Ingrese la razón social';
  if (!formData.area_responsable) errores.area_responsable = 'Seleccione el área de contacto';
  if (!formData.correo_destinatario.trim()) {
    errores.correo_destinatario = 'Ingrese el correo electrónico';
  } else if (!esCorreoValido(formData.correo_destinatario)) {
    errores.correo_destinatario = 'Ingrese un correo electrónico válido';
  }

  return errores;
}

function normalizarDatosAcceso(formData) {
  return {
    ...formData,
    razon_social: formData.razon_social.trim(),
    correo_destinatario: normalizarCorreo(formData.correo_destinatario),
  };
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

function ItemResumenConfirmacion({ label, valor, destacado = false, ultimo = false }) {
  return (
    <div
      style={{
        ...ESTILOS.itemResumen,
        ...(destacado ? ESTILOS.itemResumenCorreo : {}),
        ...(ultimo ? ESTILOS.itemResumenFinal : {}),
      }}
    >
      <span style={ESTILOS.resumenLabel}>{label}</span>
      <span style={ESTILOS.resumenValor}>{valor}</span>
    </div>
  );
}

function ResumenConfirmacionAcceso({ datos }) {
  const datosNormalizados = normalizarDatosAcceso(datos);

  return (
    <>
      <p style={ESTILOS.confirmacionTexto}>
        Revise cuidadosamente estos datos antes de generar y enviar el acceso.
      </p>
      <div style={ESTILOS.resumenConfirmacion}>
        <ItemResumenConfirmacion
          label="Correo"
          valor={datosNormalizados.correo_destinatario}
          destacado
        />
        <ItemResumenConfirmacion
          label="Contraparte"
          valor={ETIQUETA_TIPO_CONTRAPARTE[datosNormalizados.tipo_contraparte] ?? datosNormalizados.tipo_contraparte}
        />
        <ItemResumenConfirmacion
          label="Razón social"
          valor={datosNormalizados.razon_social}
        />
        <ItemResumenConfirmacion
          label="Área"
          valor={ETIQUETA_AREA_RESPONSABLE[datosNormalizados.area_responsable] ?? datosNormalizados.area_responsable}
          ultimo
        />
      </div>
      <div style={ESTILOS.avisoConfirmacion}>
        El correo indicado recibirá el acceso para diligenciar el formulario.
      </div>
    </>
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
  const [mostrarConfirmacion, setMostrarConfirmacion] = useState(false);
  const [mostrarConfirmacionReenvio, setMostrarConfirmacionReenvio] = useState(false);
  const [accesoIdReenvio, setAccesoIdReenvio] = useState(null);

  const temporizadorRef = useRef(null);

  useEffect(() => () => clearTimeout(temporizadorRef.current), []);

  const handleChange = useCallback((campo, valor) => {
    setFormData(prev => ({ ...prev, [campo]: valor }));
    setErroresCampo(prev => ({ ...prev, [campo]: null }));
    setErrorGlobal(null);
  }, []);

  const handleSubmit = useCallback((e) => {
    e.preventDefault();
    const errores = validarCamposAcceso(formData);
    if (Object.keys(errores).length > 0) {
      setErroresCampo(errores);
      return;
    }

    setMostrarConfirmacion(true);
  }, [formData]);

  const handleConfirmarCreacion = useCallback(async () => {
    if (cargando) return;

    const errores = validarCamposAcceso(formData);
    if (Object.keys(errores).length > 0) {
      setErroresCampo(errores);
      setMostrarConfirmacion(false);
      return;
    }

    setCargando(true);
    setErrorGlobal(null);
    try {
      const acceso = await api.crearAccesoManual(normalizarDatosAcceso(formData));
      guardarCredenciales(acceso);
      setResultado(acceso);
      setMostrarConfirmacion(false);
    } catch (errorCreacion) {
      setMostrarConfirmacion(false);
      if (errorCreacion.status === 409 && errorCreacion.data?.acceso_id) {
        setAccesoIdReenvio(errorCreacion.data.acceso_id);
        setMostrarConfirmacionReenvio(true);
      } else if (errorCreacion.status === 429) {
        const segundos = errorCreacion.data?.segundos_restantes || 120;
        setErrorGlobal(`Demasiadas solicitudes. Debe esperar ${segundos} segundos antes de solicitar otro acceso para este correo.`);
      } else {
        setErrorGlobal(errorCreacion.message || 'Error al crear el acceso. Verifique los datos e intente nuevamente.');
      }
    } finally {
      setCargando(false);
    }
  }, [cargando, formData]);

  const handleReenviar = useCallback(async () => {
    if (cargando || !accesoIdReenvio) return;
    setCargando(true);
    setErrorGlobal(null);
    try {
      const acceso = await api.reenviarAccesoManual(accesoIdReenvio);
      guardarCredenciales(acceso);
      setResultado(acceso);
      setMostrarConfirmacionReenvio(false);
    } catch (errorCreacion) {
      setMostrarConfirmacionReenvio(false);
      if (errorCreacion.status === 429) {
        const segundos = errorCreacion.data?.segundos_restantes || 120;
        setErrorGlobal(`Debe esperar ${segundos} segundos antes de solicitar otro correo.`);
      } else {
        setErrorGlobal(errorCreacion.message || 'Error al reenviar el acceso. Verifique los datos e intente nuevamente.');
      }
    } finally {
      setCargando(false);
    }
  }, [cargando, accesoIdReenvio]);

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
    setMostrarConfirmacion(false);
    setMostrarConfirmacionReenvio(false);
    setAccesoIdReenvio(null);
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
            de forma segura antes de cerrar esta pantalla si no le llego al correo del responsable legal las credenciales. Tiene una ventana de 10 min para verlo en "Ver accesos" después de creado, pero luego se ocultará por seguridad.
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
    <>
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
          <CampoInput
            id="correo_destinatario" label="Correo electrónico representante legal"
            type="email"
            placeholder="ejemplo@empresa.com"
            value={formData.correo_destinatario} onChange={handleChange}
            onFocus={() => setCampoEnfocado('correo_destinatario')} onBlur={() => setCampoEnfocado(null)}
            style={estiloInput('correo_destinatario')} error={erroresCampo.correo_destinatario} disabled={cargando}
            autoComplete="email"
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
      <ModalConfirmacion
        visible={mostrarConfirmacion}
        titulo="Confirmar creación del acceso"
        textoConfirmar="Crear acceso"
        textoCancelar="Editar datos"
        onConfirmar={handleConfirmarCreacion}
        onCancelar={() => setMostrarConfirmacion(false)}
        ocupado={cargando}
      >
        <ResumenConfirmacionAcceso datos={formData} />
      </ModalConfirmacion>
      <ModalConfirmacion
        visible={mostrarConfirmacionReenvio}
        titulo="Acceso activo existente"
        textoConfirmar="Sí, reenviar y generar nuevo PIN"
        textoCancelar="Cancelar"
        onConfirmar={handleReenviar}
        onCancelar={() => setMostrarConfirmacionReenvio(false)}
        ocupado={cargando}
      >
        <div style={ESTILOS.confirmacionTexto}>
          <p>Ya existe un acceso activo para <strong>{formData.correo_destinatario}</strong>.</p>
          <p>¿Desea reenviar las credenciales generando un nuevo PIN e invalidando el anterior?</p>
        </div>
      </ModalConfirmacion>
    </>
  );
}
