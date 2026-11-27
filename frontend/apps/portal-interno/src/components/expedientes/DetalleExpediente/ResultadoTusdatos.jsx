import { memo, useMemo, useState } from 'react';
import { etiquetaLista } from './presentacionListas';
import './ResultadoConsultaListas.css';
import './ResultadoTusdatos.css';

/**
 * ResultadoTusdatos — Resultado de una consulta en Tusdatos (contrato `tusdatos-1`).
 *
 * Tusdatos no compara datos ni clasifica coincidencias: informa, por fuente, si encontró
 * registros y el detalle que publica la fuente. Esta pantalla muestra solo eso. La de la
 * búsqueda propia sobre archivos de listas (ResultadoConsultaListas) no se usa aquí.
 */

const ESTADOS_FUENTE = {
  CON_REGISTRO: 'Con registro',
  SIN_REGISTRO: 'Sin registro',
  NO_CONSULTADA: 'No se pudo consultar',
  NO_INCLUIDA: 'No incluida en el reporte',
};

// Fuentes que Tusdatos consulta por documento y por nombre: se muestran juntas.
const FAMILIAS = { ofac: 'ofac', ofac_nombre: 'ofac', peps: 'peps', peps_denom: 'peps' };
const NOMBRES_FAMILIA = { ofac: 'OFAC (Lista Clinton)', peps: 'Listas y PEP' };
const VARIANTE = { ofac: 'Por documento', ofac_nombre: 'Por nombre', peps: 'Por documento', peps_denom: 'Por nombre' };
const CATEGORIAS = {
  listas_restrictivas: 'Lista restrictiva', listas_vinculantes: 'Lista vinculante', peps_internacionales: 'PEP internacional',
};
const AVISOS_DESTACADOS = new Set(['DOCUMENTO_NO_VALIDADO']);
const NOMBRES_EVIDENCIA = { PDF_PROVEEDOR: 'PDF del proveedor (reporte oficial de Tusdatos)', INFORME_INTERNO: 'Constancia técnica del sistema' };
// El PDF de Tusdatos es el documento principal; la constancia del sistema va después.
const ORDEN_EVIDENCIA = { PDF_PROVEEDOR: 0, INFORME_INTERNO: 1 };

// Nombres legibles de campos documentados por Tusdatos («Listas y PEPS»); el resto se muestra limpio.
const CAMPOS = {
  NOMBRECOMPLETO: 'Nombre completo', TIPO_ID: 'Tipo de documento', ID: 'Documento', CODIGO: 'Código en la lista',
  FECHA_UPDATE: 'Fecha de actualización', NOMBRE_LISTA: 'Lista', NOMBRE_DESCRIPTIVO_LISTA: 'Descripción de la lista',
  ORIGEN_LISTA: 'Origen de la lista', TIPO_LISTA: 'Tipo de lista', ROL_O_DESCRIPCION1: 'Rol o descripción',
  ROL_O_DESCRIPCION2: 'Rol o descripción (2)', RELACIONADO_CON: 'Relacionado con', FECHA_FINAL_ROL: 'Fecha final del rol',
  NACIONALIDAD_PAISDEORIGEN: 'Nacionalidad o país de origen', TIPO_PERSONA: 'Tipo de persona', AKA: 'Alias',
  LLAVEIMAGEN: 'Referencia de imagen', DENOMINACION_CARGO: 'Cargo', NOMBRE_ENTIDAD: 'Entidad', NOMBRE_PEP: 'Nombre',
  FECHA_INICIO_PEP: 'Inicio como PEP', FECHA_FIN_PEP: 'Fin como PEP', ENLACE_HV_SIGEP: 'Hoja de vida en SIGEP',
};

function etiquetaCampo(clave) {
  if (CAMPOS[clave]) return CAMPOS[clave];
  const limpia = String(clave).replace(/[:_]+/g, ' ').trim();
  return limpia ? limpia.charAt(0).toUpperCase() + limpia.slice(1).toLowerCase() : 'Otro dato';
}

function vacio(valor) {
  if (valor === null || valor === undefined || valor === false) return true;
  if (typeof valor === 'string') return !valor.trim();
  if (Array.isArray(valor)) return valor.every(vacio);
  if (typeof valor === 'object') return Object.values(valor).every(vacio);
  return false;
}

function Valor({ valor }) {
  if (typeof valor === 'string' && /^https?:\/\//i.test(valor.trim())) {
    return <a href={valor.trim()} target="_blank" rel="noopener noreferrer">{valor.trim()}</a>;
  }
  if (typeof valor === 'boolean') return valor ? 'Sí' : 'No';
  return String(valor);
}

// Muestra el detalle tal como lo publica la fuente (objetos, listas y textos anidados) en forma legible.
function Detalle({ datos, nivel = 0 }) {
  if (vacio(datos)) return null;
  if (Array.isArray(datos)) {
    const visibles = datos.filter(v => !vacio(v));
    if (visibles.every(v => typeof v !== 'object')) return <Valor valor={visibles.join('; ')} />;
    return <ol className="tusdatos-lista">{visibles.map((v, i) => <li key={i}><Detalle datos={v} nivel={nivel + 1} /></li>)}</ol>;
  }
  if (typeof datos === 'object') {
    return <dl className={nivel ? 'tusdatos-datos tusdatos-datos--anidado' : 'listas-datos'}>
      {Object.entries(datos).filter(([, v]) => !vacio(v)).map(([clave, valor]) => <div key={clave}>
        <dt>{etiquetaCampo(clave)}</dt><dd><Detalle datos={valor} nivel={nivel + 1} /></dd>
      </div>)}
    </dl>;
  }
  return <Valor valor={datos} />;
}

const Registro = memo(function Registro({ registro }) {
  return <section className="tusdatos-registro" aria-label={`Registro ${registro.titulo}`}>
    <h6>{registro.titulo}</h6>
    {registro.categoria && <p className="tusdatos-etiqueta">{CATEGORIAS[registro.categoria] ?? etiquetaCampo(registro.categoria)}</p>}
    {registro.sin_detalle
      ? <p>La fuente informa que hay un registro, pero Tusdatos no entrega el detalle. Revise la captura de la fuente o el PDF del proveedor.</p>
      : <Detalle datos={registro.detalle} />}
    {registro.detalle_recortado && <p className="listas-nota">El detalle era demasiado extenso y se conservó parcialmente; el completo está en el PDF del proveedor.</p>}
  </section>;
});

function Captura({ evidencia, descargar, puedeVer }) {
  if (!evidencia || !puedeVer || evidencia.estado !== 'DISPONIBLE') return null;
  return <button type="button" className="btn-modal btn-modal-secondary tusdatos-captura"
    onClick={() => descargar(evidencia.id, evidencia.tipo, evidencia.fuente_codigo)}>Ver captura de la fuente</button>;
}

const Fuente = memo(function Fuente({ fuente, conVariante, captura, descargar, puedeVerEvidencias }) {
  const [abierta, setAbierta] = useState(fuente.estado === 'CON_REGISTRO');
  return <details className="tusdatos-fuente" data-estado={fuente.estado} open={abierta} onToggle={e => setAbierta(e.target.open)}>
    <summary>
      <span>{conVariante ? VARIANTE[fuente.codigo] : fuente.nombre}</span>
      <span className="tusdatos-estado" data-estado={fuente.estado}>
        {ESTADOS_FUENTE[fuente.estado]}{fuente.registros.length > 1 ? ` (${fuente.registros.length})` : ''}
      </span>
    </summary>
    {abierta && <div className="tusdatos-fuente__cuerpo">
      {conVariante && <p className="listas-nota">{fuente.nombre}</p>}
      {fuente.motivo && <p>{fuente.motivo}</p>}
      {fuente.hallazgos.map((h, i) => <p key={`${h.codigo}-${i}`} className="tusdatos-hallazgo">
        <strong>{h.descripcion}</strong>{h.nivel && <> · nivel en la cuenta: {h.nivel}</>}
      </p>)}
      {!!fuente.resumen.length && <div>
        <p><strong>Listas en las que aparece:</strong></p>
        <ul>{fuente.resumen.map((r, i) => <li key={i}>{[r.nombre_lista, r.categoria, r.origen].filter(Boolean).join(' · ')}</li>)}</ul>
      </div>}
      {fuente.version_base && <p className="listas-nota">Versión de la base consultada: {fuente.version_base}</p>}
      {!fuente.estructura_documentada && !!fuente.registros.length && <p className="listas-nota">
        Tusdatos no publica el modelo de esta fuente: el detalle se muestra tal como llega.
      </p>}
      {fuente.registros.map(r => <Registro key={r.id} registro={r} />)}
      <Captura evidencia={captura} descargar={descargar} puedeVer={puedeVerEvidencias} />
    </div>}
  </details>;
});

function agrupar(fuentes) {
  const grupos = [];
  for (const fuente of fuentes) {
    const familia = FAMILIAS[fuente.codigo];
    const existente = familia && grupos.find(g => g.familia === familia);
    if (existente) existente.fuentes.push(fuente);
    else grupos.push({ familia, nombre: familia ? NOMBRES_FAMILIA[familia] : fuente.nombre, fuentes: [fuente] });
  }
  return grupos;
}

function documentoConsultado(criterio) {
  const documento = criterio?.identificadores?.[0];
  return documento ? `${documento.tipo} ${documento.valor}` : null;
}

function ResultadoTusdatos({ consulta, descargar, puedeVerPdfProveedor = false }) {
  const grupos = useMemo(() => agrupar(consulta.fuentes), [consulta.fuentes]);
  const capturas = useMemo(() => new Map(consulta.evidencias.filter(e => e.tipo === 'CAPTURA_PROVEEDOR')
    .map(e => [e.fuente_codigo, e])), [consulta.evidencias]);
  const conRegistro = consulta.fuentes.filter(f => f.estado === 'CON_REGISTRO').length;
  const validado = consulta.documento_validado;
  return <div className="listas-resultado tusdatos-resultado">
    <h4>{etiquetaLista(consulta.estado_ejecucion)}</h4>
    <p>{consulta.conclusion_busqueda === 'CON_CANDIDATOS'
      ? `Tusdatos informa registros en ${conRegistro} ${conRegistro === 1 ? 'fuente' : 'fuentes'}. Cada registro requiere revisión humana.`
      : etiquetaLista(consulta.conclusion_busqueda)}</p>
    <p className="listas-nota">Un registro indica que la fuente reporta algo sobre el documento consultado. No es un nivel de riesgo ni una decisión de cumplimiento.</p>
    <dl className="listas-datos">
      {[['Documento consultado', documentoConsultado(consulta.criterio)],
        ['Nombre según Tusdatos', consulta.titular_nombre],
        ['Documento validado', validado === null || validado === undefined ? 'No aplica' : (validado ? 'Sí' : 'No')],
        ['Sujeto consultado', etiquetaLista(consulta.contexto.sujeto_rol)],
        ['Fecha de consulta', consulta.fecha_inicio && new Date(consulta.fecha_inicio).toLocaleString()],
        ['Nivel informado por Tusdatos', consulta.nivel_informado_proveedor && `${consulta.nivel_informado_proveedor} (lo configura la cuenta; solo referencia)`],
        ['Consulta', consulta.consulta_id],
      ].filter(([, v]) => v).map(([k, v]) => <div key={k}><dt>{k}</dt><dd>{v}</dd></div>)}
    </dl>
    {consulta.error && <p role="alert" className="listas-error">{consulta.error.mensaje} ({consulta.error.codigo})</p>}
    {consulta.avisos.map((a, i) => AVISOS_DESTACADOS.has(a.codigo)
      ? <p key={`${a.codigo}-${i}`} role="alert" className="listas-error"><strong>Documento no validado:</strong> {a.descripcion}</p>
      : <p key={`${a.codigo}-${i}`} className="listas-nota">{a.descripcion}</p>)}
    {!!grupos.length && <>
      <h5>Fuentes consultadas</h5>
      {grupos.map(g => g.fuentes.length > 1
        ? <section key={g.familia} className="tusdatos-familia" aria-label={g.nombre}>
            <h6>{g.nombre}</h6>
            {g.fuentes.map(f => <Fuente key={f.id} fuente={f} conVariante captura={capturas.get(f.codigo)}
              descargar={descargar} puedeVerEvidencias={puedeVerPdfProveedor} />)}
          </section>
        : <Fuente key={g.fuentes[0].id} fuente={g.fuentes[0]} captura={capturas.get(g.fuentes[0].codigo)}
            descargar={descargar} puedeVerEvidencias={puedeVerPdfProveedor} />)}
    </>}
    <h5>Evidencias conservadas</h5>
    {!consulta.evidencias.some(e => e.tipo !== 'CAPTURA_PROVEEDOR') && <p>No hay un informe disponible para esta consulta.</p>}
    {consulta.evidencias.filter(e => e.tipo !== 'CAPTURA_PROVEEDOR')
      .sort((x, y) => (ORDEN_EVIDENCIA[x.tipo] ?? 9) - (ORDEN_EVIDENCIA[y.tipo] ?? 9))
      .map(e => <div key={e.id} className="tusdatos-evidencia">
      <span>{NOMBRES_EVIDENCIA[e.tipo] ?? e.tipo} · {e.creada_en && new Date(e.creada_en).toLocaleString()}</span>
      {e.estado === 'DISPONIBLE' && (e.tipo !== 'PDF_PROVEEDOR' || puedeVerPdfProveedor) && <button type="button"
        className="btn-modal btn-modal-secondary" onClick={() => descargar(e.id, e.tipo)}>Descargar</button>}
    </div>)}
    {consulta.evidencias.some(e => e.tipo === 'PDF_PROVEEDOR' || e.tipo === 'CAPTURA_PROVEEDOR') && <p className="listas-nota">
      El PDF y las capturas del proveedor contienen datos de la fuente; su acceso queda registrado.
    </p>}
  </div>;
}

/** Opciones de «alcance» de la revisión humana: cada registro es una coincidencia revisable. */
export function opcionesRevisionTusdatos(consulta) {
  return consulta.fuentes.flatMap(f => f.registros.map(r => ({ id: r.id, etiqueta: `${f.nombre}: ${r.titulo}` })));
}

export default memo(ResultadoTusdatos);
