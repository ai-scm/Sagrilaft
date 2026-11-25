import { memo, useState } from 'react';

/**
 * ConsultaForm — Formulario "Datos de la contraparte" de Verificar SAGRILAFT.
 *
 * Mantiene su propio estado de campos (en vez de vivir en ConsultasListas) y
 * está envuelto en `memo` para que escribir aquí no fuerce la re-renderización
 * del historial ni del resultado de consulta abierto, que pueden ser pesados.
 */
// Tipos de documento por modalidad. Tusdatos (externo) también consulta cédula de extranjería,
// que exige la fecha de expedición (en CC es opcional); el formulario guarda el pasaporte como PAS.
const TIPOS_BASE = ['CC', 'NIT', 'PASAPORTE'];
const TIPOS_EXTERNO = ['CC', 'CE', 'NIT', 'PASAPORTE'];

function tipoInicial(tipoExpediente, tipos) {
  const tipo = tipoExpediente === 'PAS' ? 'PASAPORTE' : tipoExpediente;
  return tipos.includes(tipo) ? tipo : 'CC';
}

function ConsultaForm({ expediente, disabled, onConsultar, implementacion }) {
  // Tusdatos consulta por documento: no usa país ni fecha de nacimiento, y el nombre solo lo
  // pide con pasaporte. Esos campos se muestran solo en la búsqueda propia (simulada).
  const externo = implementacion === 'externo';
  const tipos = externo ? TIPOS_EXTERNO : TIPOS_BASE;
  const natural = expediente.tipo_persona === 'natural';
  const [nombre, setNombre] = useState(expediente.razon_social || '');
  const [documento, setDocumento] = useState(expediente.numero_identificacion || '');
  const [tipo, setTipo] = useState(() => tipoInicial(expediente.tipo_identificacion, tipos));
  // La fecha guardada es la del documento del paso 3 del formulario (representante legal o, en
  // persona natural, la propia persona): solo se precarga cuando la contraparte es esa persona.
  const [fechaExpedicion, setFechaExpedicion] = useState(natural ? (expediente.fecha_expedicion || '') : '');
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

  const pideNombre = !externo || tipo === 'PASAPORTE';
  // CE: obligatoria en Tusdatos. CC: opcional; con ella Tusdatos valida la fecha y consulta más fuentes.
  const pideExpedicion = tipo === 'CE' || (externo && tipo === 'CC');

  function construirCriterio() {
    return {
      tipo_sujeto: 'NO_DETERMINADO',
      ...(pideNombre && nombre.trim() ? { nombre: nombre.trim() } : {}),
      ...(documento.trim() ? { identificadores: [{ tipo, valor: documento.trim(),
        ...(!externo && paisDocumento.trim() ? { pais_emisor: paisDocumento.trim().toUpperCase() } : {}) }] } : {}),
      ...(!externo && fechaNacimiento ? { fecha_nacimiento: fechaNacimiento } : {}),
      ...(pideExpedicion && fechaExpedicion ? { fecha_expedicion: fechaExpedicion } : {}),
    };
  }

  return (
    <fieldset className="listas-formulario" disabled={disabled}>
      <legend>Datos de la contraparte</legend>
      <div className="listas-campos">
        <label className="listas-campo">Tipo de documento <select className="form-input" value={tipo} onChange={e => setTipo(e.target.value)}>{tipos.map(t => <option key={t}>{t}</option>)}</select></label>
        <label className="listas-campo">Documento <input className="form-input" aria-label="Documento para listas"
          placeholder={externo && tipo === 'NIT' ? 'Sin dígito de verificación' : undefined}
          value={documento} onChange={e => setDocumento(e.target.value)} /></label>
        {pideNombre && <label className="listas-campo">{externo ? 'Nombre completo' : 'Nombre'} <input className="form-input" aria-label="Nombre para listas"
          required={externo} minLength={externo ? 5 : undefined} value={nombre} onChange={e => setNombre(e.target.value)} /></label>}
        {pideExpedicion && <label className="listas-campo">Fecha de expedición{tipo === 'CC' ? ' (opcional)' : ''} <input className="form-input" type="date"
          aria-label="Fecha de expedición para listas" required={tipo === 'CE'} value={fechaExpedicion} onChange={e => setFechaExpedicion(e.target.value)} /></label>}
        {!externo && <label className="listas-campo">País del documento <input className="form-input" aria-label="País del documento para listas"
          maxLength={2} placeholder="CO" value={paisDocumento} onChange={e => setPaisDocumento(e.target.value.toUpperCase())} /></label>}
        {!externo && <label className="listas-campo">Fecha de nacimiento <input className="form-input" type="date" aria-label="Fecha de nacimiento para listas"
          value={fechaNacimiento} onChange={e => setFechaNacimiento(e.target.value)} /></label>}
      </div>
      <div className="listas-acciones">
        <button type="button" className="btn-modal btn-modal-primary" onClick={() => onConsultar(construirCriterio(), true)}>Consultar contraparte y representante</button>
        <button type="button" className="btn-modal btn-modal-secondary" onClick={() => onConsultar(construirCriterio(), false)}>Consultar contraparte</button>
      </div>
      <p className="listas-ayuda">{externo
        ? 'El NIT va sin dígito de verificación. El pasaporte exige el nombre completo y la cédula de extranjería, la fecha de expedición. '
        : 'Código ISO de dos letras (ejemplo: CO, GT, VE). Sin este país, un documento no puede confirmar jurisdicción ni llegar a ALTA. '}
        La consulta de ambos utiliza los datos guardados del expediente.</p>
    </fieldset>
  );
}

export default memo(ConsultaForm);
