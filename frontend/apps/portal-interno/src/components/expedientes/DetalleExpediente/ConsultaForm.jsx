import { memo, useState } from 'react';

/**
 * ConsultaForm — Formulario de consulta de listas de Verificar SAGRILAFT.
 *
 * Mantiene su propio estado de campos (en vez de vivir en ConsultasListas) y
 * está envuelto en `memo` para que escribir aquí no fuerce la re-renderización
 * del historial ni del resultado de consulta abierto, que pueden ser pesados.
 */
// Búsqueda propia (archivos de listas y simulada): sin cambios. El formulario guarda el pasaporte como PAS.
const TIPOS_BASE = ['CC', 'NIT', 'PASAPORTE'];
// Tusdatos: alcance aprobado CC, CE, NIT y pasaporte.
const TIPOS_TUSDATOS = ['CC', 'CE', 'NIT', 'PASAPORTE'];
const NOMBRES_TIPO = { CC: 'Cédula de ciudadanía', CE: 'Cédula de extranjería', NIT: 'NIT', PASAPORTE: 'Pasaporte' };

function tipoInicial(tipoExpediente, tipos) {
  const tipo = tipoExpediente === 'PAS' ? 'PASAPORTE' : tipoExpediente;
  return tipos.includes(tipo) ? tipo : 'CC';
}

function hoy() {
  return new Date().toISOString().slice(0, 10);
}

/**
 * Modo Tusdatos: campos vacíos que el equipo llena a mano (no se precarga nada del expediente),
 * un solo botón «Generar reporte» y un resumen para verificar los datos antes de consultar.
 * Cada reporte es una consulta de un solo documento.
 */
function FormularioTusdatos({ disabled, onConsultar }) {
  const [tipo, setTipo] = useState('CC');
  const [documento, setDocumento] = useState('');
  const [nombre, setNombre] = useState('');
  const [fechaExpedicion, setFechaExpedicion] = useState('');
  const [confirmando, setConfirmando] = useState(false);

  const pideNombre = tipo === 'PASAPORTE';
  const pideExpedicion = tipo === 'CC' || tipo === 'CE';
  // Lo mismo que hace el servidor: el NIT va sin dígito de verificación («900.123.456-7» → «900.123.456»).
  const numeroEnviado = tipo === 'NIT' ? documento.trim().replace(/\s*-\s*\d$/, '') : documento.trim();

  const faltantes = [
    !documento.trim() && 'el número de documento',
    pideNombre && nombre.trim().length < 5 && 'el nombre completo (mínimo 5 caracteres)',
    tipo === 'CE' && !fechaExpedicion && 'la fecha de expedición',
    pideExpedicion && fechaExpedicion > hoy() && 'una fecha de expedición que no sea futura',
  ].filter(Boolean);

  function cambiar(asignar) {
    return e => { asignar(e.target.value); setConfirmando(false); };
  }

  function generar() {
    setConfirmando(false);
    onConsultar({
      tipo_sujeto: 'NO_DETERMINADO',
      identificadores: [{ tipo, valor: documento.trim() }],
      ...(pideNombre ? { nombre: nombre.trim() } : {}),
      ...(pideExpedicion && fechaExpedicion ? { fecha_expedicion: fechaExpedicion } : {}),
    }, false);
  }

  return (
    <fieldset className="listas-formulario" disabled={disabled}>
      <legend>Datos a consultar en Tusdatos</legend>
      <div className="listas-campos">
        <label className="listas-campo">Tipo de documento <select className="form-input" value={tipo} onChange={cambiar(setTipo)}>
          {TIPOS_TUSDATOS.map(t => <option key={t} value={t}>{NOMBRES_TIPO[t]}</option>)}
        </select></label>
        <label className="listas-campo">Número de documento <input className="form-input" aria-label="Documento para listas"
          placeholder={tipo === 'NIT' ? 'Sin dígito de verificación' : undefined} value={documento} onChange={cambiar(setDocumento)} /></label>
        {pideNombre && <label className="listas-campo">Nombre completo <input className="form-input" aria-label="Nombre para listas"
          value={nombre} onChange={cambiar(setNombre)} /></label>}
        {pideExpedicion && <label className="listas-campo">Fecha de expedición{tipo === 'CC' ? ' (opcional)' : ''} <input className="form-input"
          type="date" max={hoy()} aria-label="Fecha de expedición para listas" value={fechaExpedicion} onChange={cambiar(setFechaExpedicion)} /></label>}
      </div>
      {!confirmando && <div className="listas-acciones">
        <button type="button" className="btn-modal btn-modal-primary" disabled={faltantes.length > 0} onClick={() => setConfirmando(true)}>Generar reporte</button>
      </div>}
      {!confirmando && faltantes.length > 0 && documento.trim() && <p className="listas-ayuda">Falta {faltantes.join(', ')}.</p>}
      {confirmando && <div className="listas-confirmacion" role="group" aria-label="Verifique los datos antes de consultar">
        <p><strong>Verifique los datos antes de consultar:</strong></p>
        <dl className="listas-datos">
          <div><dt>Tipo de documento</dt><dd>{NOMBRES_TIPO[tipo]}</dd></div>
          <div><dt>Número que se consultará</dt><dd>{numeroEnviado}{numeroEnviado !== documento.trim() && ' (sin dígito de verificación)'}</dd></div>
          {pideNombre && <div><dt>Nombre completo</dt><dd>{nombre.trim()}</dd></div>}
          {pideExpedicion && <div><dt>Fecha de expedición</dt><dd>{fechaExpedicion || 'No informada (opcional)'}</dd></div>}
        </dl>
        <p className="listas-nota">Se consume un crédito de Tusdatos, salvo que este documento se haya consultado en este expediente en las últimas 6 horas: en ese caso se muestra esa consulta.</p>
        <div className="listas-acciones">
          <button type="button" className="btn-modal btn-modal-primary" onClick={generar}>Confirmar y generar reporte</button>
          <button type="button" className="btn-modal btn-modal-secondary" onClick={() => setConfirmando(false)}>Corregir datos</button>
        </div>
      </div>}
      <p className="listas-ayuda">El NIT va sin dígito de verificación. El pasaporte exige el nombre completo y la cédula de extranjería, la fecha de expedición. Cada reporte consulta un solo documento.</p>
    </fieldset>
  );
}

function ConsultaForm({ expediente, disabled, onConsultar, implementacion }) {
  if (implementacion === 'externo') return <FormularioTusdatos disabled={disabled} onConsultar={onConsultar} />;
  return <FormularioBusquedaPropia expediente={expediente} disabled={disabled} onConsultar={onConsultar} />;
}

// Búsqueda propia (archivos de listas y simulada): igual que antes del modo Tusdatos.
function FormularioBusquedaPropia({ expediente, disabled, onConsultar }) {
  const natural = expediente.tipo_persona === 'natural';
  const [nombre, setNombre] = useState(expediente.razon_social || '');
  const [documento, setDocumento] = useState(expediente.numero_identificacion || '');
  const [tipo, setTipo] = useState(() => tipoInicial(expediente.tipo_identificacion, TIPOS_BASE));
  // País que expide el documento: el de nacionalidad para una persona, el de domicilio para una
  // empresa (su NIT). Se precarga del expediente, pero nunca se asume: la persona que consulta
  // puede corregirlo, y sin un código válido el documento no puede confirmar jurisdicción.
  const [paisDocumento, setPaisDocumento] = useState(
    ((natural ? expediente.nacionalidad : expediente.pais) || '').toUpperCase());
  // Fecha de nacimiento: solo aplica a persona natural. Se precarga del expediente, editable.
  // A diferencia de nacionalidad/ciudad/residencia (que el motor solo usa como contexto y
  // nunca cambian el nivel), la fecha de nacimiento sí puede cambiarlo: sostiene una vía
  // alterna a ALTA sin documento fuerte, y detecta contradicciones que bajan el nivel aunque
  // el documento coincida. Por eso es la única que se agrega aquí.
  const [fechaNacimiento, setFechaNacimiento] = useState(natural ? (expediente.fecha_nacimiento || '') : '');

  function construirCriterio() {
    return {
      tipo_sujeto: 'NO_DETERMINADO',
      ...(nombre.trim() ? { nombre: nombre.trim() } : {}),
      ...(documento.trim() ? { identificadores: [{ tipo, valor: documento.trim(),
        ...(paisDocumento.trim() ? { pais_emisor: paisDocumento.trim().toUpperCase() } : {}) }] } : {}),
      ...(fechaNacimiento ? { fecha_nacimiento: fechaNacimiento } : {}),
    };
  }

  return (
    <fieldset className="listas-formulario" disabled={disabled}>
      <legend>Datos de la contraparte</legend>
      <div className="listas-campos">
        <label className="listas-campo">Nombre <input className="form-input" aria-label="Nombre para listas" value={nombre} onChange={e => setNombre(e.target.value)} /></label>
        <label className="listas-campo">Tipo de documento <select className="form-input" value={tipo} onChange={e => setTipo(e.target.value)}>{TIPOS_BASE.map(t => <option key={t}>{t}</option>)}</select></label>
        <label className="listas-campo">Documento <input className="form-input" aria-label="Documento para listas" value={documento} onChange={e => setDocumento(e.target.value)} /></label>
        <label className="listas-campo">País del documento <input className="form-input" aria-label="País del documento para listas"
          maxLength={2} placeholder="CO" value={paisDocumento} onChange={e => setPaisDocumento(e.target.value.toUpperCase())} /></label>
        <label className="listas-campo">Fecha de nacimiento <input className="form-input" type="date" aria-label="Fecha de nacimiento para listas"
          value={fechaNacimiento} onChange={e => setFechaNacimiento(e.target.value)} /></label>
      </div>
      <div className="listas-acciones">
        <button type="button" className="btn-modal btn-modal-primary" onClick={() => onConsultar(construirCriterio(), true)}>Consultar contraparte y representante</button>
        <button type="button" className="btn-modal btn-modal-secondary" onClick={() => onConsultar(construirCriterio(), false)}>Consultar contraparte</button>
      </div>
      <p className="listas-ayuda">Código ISO de dos letras (ejemplo: CO, GT, VE). Sin este país, un documento no puede confirmar jurisdicción ni llegar a ALTA. La consulta de ambos utiliza los datos guardados del expediente.</p>
    </fieldset>
  );
}

export default memo(ConsultaForm);
