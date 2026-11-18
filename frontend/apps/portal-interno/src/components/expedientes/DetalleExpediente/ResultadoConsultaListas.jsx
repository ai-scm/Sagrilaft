import { memo, useMemo, useState } from 'react';
import { etiquetaLista, valorLista } from './presentacionListas';
import './ResultadoConsultaListas.css';

// Avisos sobre el documento consultado que el revisor no debe pasar por alto.
const AVISOS_DESTACADOS = {
  DOCUMENTO_NO_VALIDADO: 'Documento no validado',
  DOCUMENTO_NO_VIGENTE: 'Documento no vigente',
};

const NOMBRES_EVIDENCIA = {
  PDF_PROVEEDOR: 'PDF del proveedor',
  CAPTURA_PROVEEDOR: 'Captura de pantalla del proveedor',
  INFORME_INTERNO: 'Informe interno',
};
const esDelProveedor = e => e.tipo === 'PDF_PROVEEDOR' || e.tipo === 'CAPTURA_PROVEEDOR';

const Datos = memo(function Datos({ pares }) {
  return <dl className="listas-datos">{pares.map(([nombre, valor]) => <div key={nombre}><dt>{nombre}</dt><dd>{valorLista(valor)}</dd></div>)}</dl>;
});

function Referencia({ referencia }) {
  if (!referencia) return null;
  return <small>Origen: {referencia.campo_original} · Identidad: {referencia.identidad_origen ?? 'No informada'}</small>;
}

// La "Información conservada de la fuente" puede incluir muchos alias,
// identificadores, hechos y relaciones por candidato (listas reales de
// cautelares suelen traer decenas de entradas). Se difiere su render hasta
// que la persona abre el <details>, en vez de construir ese árbol siempre,
// para evitar bloquear el hilo principal al abrir un resultado.
function InformacionConservada({ candidato, clasificado }) {
  const [abierta, setAbierta] = useState(false);
  return (
    <details onToggle={e => setAbierta(e.target.open)}>
      <summary>Información conservada de la fuente</summary>
      {abierta && <>
        {(candidato.nombres ?? []).map((nombre, i) => <div key={`nombre-${i}`}>
          <Datos pares={typeof nombre === 'string' ? [['Nombre o alias', nombre]] : [
            ['Nombre o alias', nombre.valor], ['Tipo', nombre.tipo], ['Alias débil', nombre.alias_debil], ['Calidad', etiquetaLista(nombre.calidad)],
          ]} /><Referencia referencia={nombre.referencia} />
        </div>)}
        {(candidato.identificadores ?? []).map((documento, i) => <div key={`doc-${i}`}>
          <Datos pares={[
            ['Documento', valorLista(documento)], ['Esquema', documento.esquema], ['Calidad', etiquetaLista(documento.calidad)],
          ]} /><Referencia referencia={documento.referencia} />
        </div>)}
        {(candidato.hechos ?? []).map((hecho, i) => <div key={`hecho-${i}`}>
          <Datos pares={[[etiquetaLista(hecho.campo), valorLista(hecho.valor)], ['Calidad', etiquetaLista(hecho.calidad)]]} />
          <Referencia referencia={hecho.referencia} />
        </div>)}
        {(candidato.direcciones ?? []).map((direccion, i) => <p key={`direccion-${i}`}>Dirección: {valorLista(direccion)}</p>)}
        {(candidato.discrepancias ?? []).map((discrepancia, i) => <p key={`discrepancia-${i}`}>{discrepancia}</p>)}
        {(candidato.relaciones ?? []).map((relacion, i) => <div key={`relacion-${i}`}>
          <Datos pares={[
            ['Relación publicada', relacion.tipo], ['Dirección de la relación', relacion.direccion], ['Fuente relacionada', relacion.fuente_destino],
            ['Versión relacionada', relacion.version_destino_id], ['Registro relacionado', relacion.registro_destino_id],
          ]} /><Referencia referencia={relacion.referencia} />
        </div>)}
        {!!candidato.relaciones?.length && <p>Una relación publicada no confirma identidad ni implica sanción o riesgo por asociación.</p>}
        {clasificado && <Datos pares={[
          ['Regla aplicada', candidato.regla_codigo], ['Versión de reglas', candidato.regla_version], ['Versión de algoritmo', candidato.algoritmo_version],
        ]} />}
      </>}
    </details>
  );
}

const CandidatoLista = memo(function CandidatoLista({ candidato, fuente, clasificado }) {
  return <section className="listas-candidato" data-nivel={clasificado ? candidato.nivel : undefined} aria-label={`Candidato ${candidato.nombre_principal}`}>
    <h5>{candidato.nombre_principal}</h5>
    {clasificado ? <>
      <p className="listas-nivel"><strong>Clasificación de coincidencia: {candidato.nivel}</strong></p>
      <p>{candidato.explicacion}</p>
      {candidato.revision_prioritaria && <p><strong>Revisión prioritaria: hay datos contradictorios que deben revisarse.</strong></p>}
    </> : <p>Resultado del contrato anterior, sin clasificación ALTA/MEDIA/BAJA.</p>}
    <Datos pares={[
      ['Tipo de sujeto', etiquetaLista(candidato.tipo_sujeto)], ['Fuente', fuente?.nombre_origen],
      ['Versión consultada', fuente?.version_id ?? fuente?.version_declarada], ['Registro', candidato.registro_id ?? candidato.uid_origen],
    ]} />
    <h6>Comparación de datos</h6>
    {candidato.motivos.map((motivo, i) => <div className="listas-motivo" key={i}>
      <Datos pares={[
        ['Campo', etiquetaLista(motivo.campo)], ['Resultado', clasificado ? etiquetaLista(motivo.resultado) : 'Coincidencia reportada'],
        ['Dato consultado', motivo.valor_consultado], ['Dato de la fuente', motivo.valor_fuente ?? motivo.valor_registro],
        ...(clasificado ? [['Explicación', motivo.explicacion], ['Calidad publicada', etiquetaLista(motivo.calidad_fuente)]] : []),
        ['Método', motivo.metodo],
      ]} />
      <Referencia referencia={motivo.referencia} />
    </div>)}
    <InformacionConservada candidato={candidato} clasificado={clasificado} />
  </section>;
});

function ResultadoConsultaListas({ consulta, descargar, puedeVerPdfProveedor = false }) {
  const clasificado = consulta.version_contrato === '2.1';
  const fuentes = useMemo(() => new Map(consulta.cobertura.map(f => [f.id, f])), [consulta.cobertura]);
  const trazabilidad = consulta.trazabilidad;
  return <div className="listas-resultado">
    <h4>{etiquetaLista(consulta.estado_ejecucion)}</h4>
    <p>{etiquetaLista(consulta.conclusion_busqueda)}</p>
    <p className="listas-nota">La clasificación describe una posible coincidencia. No es un nivel de riesgo ni una decisión de cumplimiento.</p>
    {consulta.implementacion === 'simulado' && <p className="listas-simulado"><strong>Resultado simulado: datos ficticios.</strong></p>}
    <Datos pares={[
      ['Consulta', consulta.consulta_id], ['Expediente', consulta.contexto.expediente_id], ['Sujeto consultado', etiquetaLista(consulta.contexto.sujeto_rol)],
      ['Fecha de consulta', consulta.fecha_inicio], ['Proveedor', consulta.proveedor],
    ]} />
    {consulta.error && <p role="alert" className="listas-error">{consulta.error.mensaje} ({consulta.error.codigo})</p>}
    <details><summary>Criterios utilizados</summary><Datos pares={Object.entries(consulta.criterio)
      .filter(([,v]) => v != null && (!Array.isArray(v) || v.length)).map(([k,v]) => [etiquetaLista(k), valorLista(v)])} /></details>
    <h5>Fuentes y versiones consultadas</h5>
    {consulta.cobertura.map(f => <div key={f.id}><Datos pares={[
      ['Fuente', f.nombre_origen], ['Cobertura', etiquetaLista(f.estado)], ['Versión consultada', f.version_id ?? f.version_declarada],
      ['Revisión activa al admitir', f.revision_activa], ['Hash del contenido', f.hash_contenido],
    ]} />{f.motivo && <p>{f.motivo}</p>}</div>)}
    {consulta.advertencias.map((a, i) => AVISOS_DESTACADOS[a.codigo]
      ? <p key={`aviso-${i}`} role="alert" className="listas-error"><strong>{AVISOS_DESTACADOS[a.codigo]}:</strong> {a.descripcion}</p>
      : <p key={`aviso-${i}`}>Advertencia: {a.descripcion}</p>)}
    {consulta.criterios_no_aplicados.map((a, i) => <p key={`criterio-${i}`}>Criterio no aplicado: {a.descripcion}</p>)}
    {consulta.candidatos.map(c => <CandidatoLista key={c.id} candidato={c} fuente={fuentes.get(c.cobertura_id)} clasificado={clasificado} />)}
    {!consulta.candidatos.length && !['PENDIENTE', 'EN_CURSO'].includes(consulta.estado_ejecucion) && <p>
      No se presentan candidatos. Esto no constituye aprobación ni certificación de ausencia de riesgo.
    </p>}
    {consulta.hallazgos_no_estructurados.map(h => <p key={h.id}>Información adicional: {h.descripcion}</p>)}
    {trazabilidad && <details><summary>Trazabilidad de la búsqueda</summary>
      <Datos pares={[
        ['Política', trazabilidad.politica_version], ['Versión de reglas', trazabilidad.reglas_version],
        ['Versión de algoritmo', trazabilidad.algoritmo_version], ['Hash de catálogo', trazabilidad.catalogos_hash], ['Hash de parámetros', trazabilidad.parametros_internos_hash],
      ]} />
      {trazabilidad.fuentes.map(f => <Datos key={f.fuente_codigo} pares={[
        ['Fuente', f.fuente_codigo], ['Generación de búsqueda', f.generacion_id], ['Hash de generación', f.generacion_hash],
        ['Adaptador', f.version_adaptador], ['Normalización', f.version_normalizacion],
      ]} />)}
    </details>}
    <h5>Evidencias conservadas</h5>
    <p>El informe conserva el resultado original; las revisiones humanas posteriores se muestran por separado.</p>
    {!consulta.evidencias.length && <p>No hay un informe disponible para esta consulta.</p>}
    {consulta.evidencias.map(e => <div key={e.id}>
      <Datos pares={[
        ['Evidencia', NOMBRES_EVIDENCIA[e.tipo] ?? e.tipo], ...(e.fuente_codigo ? [['Fuente', e.fuente_codigo]] : []),
        ['Identificador', e.id], ['Estado', etiquetaLista(e.estado)], ['Fecha', e.creada_en], ['Generador', e.generador_version],
        [e.tipo === 'CAPTURA_PROVEEDOR' ? 'SHA-256 de la imagen' : 'SHA-256 del PDF', e.sha256],
      ]} />
      {e.tipo === 'PDF_PROVEEDOR' && <p className="listas-nota">PDF entregado por el proveedor. Contiene información de otras fuentes; su acceso queda registrado.</p>}
      {e.tipo === 'CAPTURA_PROVEEDOR' && <p className="listas-nota">Pantalla de la fuente tal como la vio el proveedor al consultar. Su acceso queda registrado.</p>}
      {e.estado === 'DISPONIBLE' && !esDelProveedor(e) && <button type="button" className="btn-modal btn-modal-secondary" onClick={() => descargar(e.id, e.tipo)}>Descargar informe conservado</button>}
      {e.estado === 'DISPONIBLE' && esDelProveedor(e) && puedeVerPdfProveedor && <button type="button" className="btn-modal btn-modal-secondary" onClick={() => descargar(e.id, e.tipo, e.fuente_codigo)}>
        {e.tipo === 'PDF_PROVEEDOR' ? 'Descargar PDF del proveedor' : `Descargar captura (${e.fuente_codigo})`}
      </button>}
    </div>)}
  </div>;
}

export default memo(ResultadoConsultaListas);
