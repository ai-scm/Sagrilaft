import { useCallback, useEffect, useRef, useState } from 'react';
import { listas } from '../../../services/listas';
import ResultadoConsultaListas from './ResultadoConsultaListas';
import ConsultaForm from './ConsultaForm';
import RevisionHistorial from './RevisionHistorial';
import { etiquetasListas as etiquetas } from './presentacionListas';
import { usePaginacion } from '../../../hooks/usePaginacion';
import { ELEMENTOS_POR_PAGINA } from '../../../config/constantesPaginacion';
import ControlsPaginacion from '../../ui/ControlsPaginacion';
import '../../modals/Modals.css';
import './ConsultasListas.css';

const pendientes = new Set(['PENDIENTE', 'EN_CURSO']);

export default function ConsultasListas({ expediente, enModal = false }) {
  const [capacidades, setCapacidades] = useState({});
  const [historial, setHistorial] = useState([]);
  const [siguiente, setSiguiente] = useState(null);
  const [legado, setLegado] = useState(null);
  const [detalle, setDetalle] = useState(null);
  const [error, setError] = useState('');
  const [fallosSeguimiento, setFallosSeguimiento] = useState(0);
  const [aviso, setAviso] = useState('');
  const [ocupado, setOcupado] = useState(false);
  const [avanzarAlCargarHistorial, setAvanzarAlCargarHistorial] = useState(false);
  const seleccion = useRef(null);

  // Paginación del historial: reutiliza el mismo hook/componente de controles
  // que el resto del Portal Interno. El historial ya acumula en memoria todo
  // lo que se ha traído del servidor; "Siguiente" solo pide más páginas al
  // servidor (vía `siguiente`) cuando el usuario llega al final de lo cargado.
  const paginacionHistorial = usePaginacion(historial, ELEMENTOS_POR_PAGINA);

  useEffect(() => {
    if (!avanzarAlCargarHistorial) return;
    paginacionHistorial.irAPaginaSiguiente();
    setAvanzarAlCargarHistorial(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [historial]);

  const cargar = useCallback(async function cargar(antes) {
    const pagina = await listas.historial(expediente.id, antes);
    setHistorial(anterior => antes ? [...anterior, ...pagina.consultas] : pagina.consultas);
    setSiguiente(pagina.siguiente);
    setLegado(pagina.legado);
  }, [expediente.id]);

  function irASiguientePaginaHistorial() {
    if (paginacionHistorial.esUltimaPagina && siguiente) {
      setAvanzarAlCargarHistorial(true);
      cargar(siguiente).catch(e => { setError(e.message); setAvanzarAlCargarHistorial(false); });
      return;
    }
    paginacionHistorial.irAPaginaSiguiente();
  }

  useEffect(() => {
    let vigente = true;
    listas.disponibilidad().then(async datos => {
      if (!vigente) return;
      setCapacidades(datos);
      if (datos.historial) await cargar();
    }).catch(e => vigente && setError(e.message));
    return () => { vigente = false; };
  }, [expediente.id, cargar]);

  useEffect(() => {
    if (!capacidades.historial || !historial.some(c => pendientes.has(c.estado)) || fallosSeguimiento >= 3) return;
    let vigente = true;
    const temporizador = setTimeout(async () => {
      try {
        const id = seleccion.current;
        // Solo se vuelve a pedir el detalle (y a re-renderizar el resultado, que es
        // pesado: candidatos, motivos, trazabilidad, evidencias) cuando el registro
        // abierto sigue pendiente. Antes se repetía en cada ciclo mientras CUALQUIER
        // consulta del historial estuviera pendiente, aunque la abierta ya hubiera
        // terminado, lo que generaba recargas y renderizados innecesarios cada 2s.
        const detalleAbiertoPendiente = id && detalle?.consulta?.consulta_id === id
          && pendientes.has(detalle.consulta.estado_ejecucion);
        const [pagina, datos] = await Promise.all([
          listas.historial(expediente.id), detalleAbiertoPendiente ? listas.detalle(id) : Promise.resolve(null),
        ]);
        if (!vigente) return;
        setFallosSeguimiento(0);
        setHistorial(pagina.consultas);
        setSiguiente(pagina.siguiente);
        if (datos && seleccion.current === id) setDetalle(datos);
      } catch {
        if (vigente) setFallosSeguimiento(anterior => anterior + 1);
      }
    }, 2000 * (2 ** fallosSeguimiento));
    return () => { vigente = false; clearTimeout(temporizador); };
  }, [historial, capacidades.historial, expediente.id, fallosSeguimiento, detalle]);

  const ver = useCallback(async function ver(id) {
    seleccion.current = id;
    try {
      const datos = await listas.detalle(id);
      if (seleccion.current === id) setDetalle(datos);
    } catch (e) { setError(e.message); }
  }, []);

  const consultar = useCallback(async function consultar(criterio, ambos) {
    setOcupado(true); setError(''); setAviso('');
    const datos = { ...(capacidades.version_contrato === '2.1' ? { version_contrato: '2.1' } : {}), sujeto_rol: 'CONTRAPARTE', criterio };
    const operacion = ambos ? 'grupo' : JSON.stringify(datos);
    const almacenamiento = `listas-pendiente:${expediente.id}:${ambos ? 'grupo' : 'individual'}`;
    try {
      const anterior = JSON.parse(sessionStorage.getItem(almacenamiento) || 'null');
      const clave = anterior?.operacion === operacion ? anterior.clave : crypto.randomUUID();
      sessionStorage.setItem(almacenamiento, JSON.stringify({ operacion, clave }));
      const respuesta = ambos ? await listas.grupo(expediente.id, clave) : await listas.crear(expediente.id, datos, clave);
      sessionStorage.removeItem(almacenamiento);
      setAviso(ambos && respuesta.no_consultados.length ? respuesta.no_consultados.map(s => `${s.sujeto_rol}: ${s.motivo}`).join('. ') : 'Consulta registrada.');
      if (capacidades.historial) {
        await cargar();
        const id = ambos ? respuesta.consultas[0]?.consulta_id : respuesta.consulta_id;
        if (id) await ver(id);
      }
    } catch (e) { setError(e.message); }
    finally { setOcupado(false); }
  }, [capacidades.version_contrato, capacidades.historial, expediente.id, cargar, ver]);

  const revisar = useCallback(async function revisar(datosRevision) {
    setOcupado(true); setError('');
    try {
      await listas.revisar(detalle.consulta.consulta_id, datosRevision);
      await ver(detalle.consulta.consulta_id);
    } catch (e) { setError(e.message); }
    finally { setOcupado(false); }
  }, [detalle, ver]);

  const descargar = useCallback(
    id => listas.evidencia(seleccion.current, id).catch(err => setError(err.message)),
    [],
  );

  const cerrarDetalle = useCallback(() => {
    seleccion.current = null;
    setDetalle(null);
  }, []);

  const consulta = detalle?.consulta;
  return <section id="consultas-listas" aria-label="Consultas de listas" className={`listas-panel${enModal ? ' listas-en-modal' : ''}`}>
    <h3 className="listas-panel__titulo">Consultas de listas cautelares</h3>
    <p className="listas-aviso">Las coincidencias requieren revisión humana. No determinan aprobación, rechazo ni nivel de riesgo.</p>
    {capacidades.implementacion === 'simulado' && <p className="listas-simulado"><strong>SIMULADO: datos ficticios, sin consulta OFAC.</strong></p>}
    {error && <p role="alert" className="listas-error">{error}</p>}{aviso && <p role="status" className="listas-ok">{aviso}</p>}
    {fallosSeguimiento > 0 && <p role="alert" className="listas-error">{fallosSeguimiento < 3
      ? 'No se pudo actualizar el seguimiento. Reintentaremos automáticamente.'
      : 'El seguimiento está pausado tras tres intentos fallidos. La consulta permanece registrada.'}</p>}
    {fallosSeguimiento >= 3 && <button type="button" className="btn-modal btn-modal-secondary listas-mas" onClick={() => setFallosSeguimiento(0)}>Reintentar seguimiento</button>}
    {capacidades.consultar && (
      <ConsultaForm expediente={expediente} disabled={ocupado} onConsultar={consultar} />
    )}
    {!capacidades.consultar && <p className="listas-nota">Las nuevas consultas no están disponibles para esta sesión.</p>}
    {capacidades.historial && <>
      <h4>Historial</h4>
      {legado?.reporte_id && <p className="listas-nota">Reporte heredado: {legado.reporte_id}. Evidencia heredada no disponible en la custodia nueva.</p>}
      {!!legado?.validaciones?.length && <details><summary>Antecedentes de listas del circuito anterior</summary><p>Información heredada sin versiones verificables; no constituye una nueva decisión.</p><ul>{legado.validaciones.map((v, i) => <li key={i}>{v.campo}: {v.resultado_original}. {v.detalle}</li>)}</ul></details>}
      {!historial.length && <p className="listas-vacio">No hay consultas registradas en el módulo nuevo.</p>}
      <ul className="listas-historial">{paginacionHistorial.elementosPagina.map(c => <li key={c.consulta_id}><button type="button" className="listas-item" aria-current={consulta?.consulta_id === c.consulta_id} onClick={() => ver(c.consulta_id)}>
        {c.sujeto_rol} · <span className="listas-estado" data-estado={c.estado}>{etiquetas[c.estado]}</span> · {new Date(c.creado_en).toLocaleString()}
      </button></li>)}</ul>
      <ControlsPaginacion
        {...paginacionHistorial}
        esUltimaPagina={paginacionHistorial.esUltimaPagina && !siguiente}
        hayMultiplesPaginas={paginacionHistorial.hayMultiplesPaginas || !!siguiente}
        irAPaginaSiguiente={irASiguientePaginaHistorial}
      />
    </>}
    {consulta && <article className="listas-detalle" aria-label="Detalle de consulta">
      <div className="listas-detalle-encabezado">
        <h4>Detalle de la consulta seleccionada</h4>
        <button type="button" className="btn-modal btn-modal-secondary" onClick={cerrarDetalle}>✕ Cerrar</button>
      </div>
      {pendientes.has(consulta.estado_ejecucion) && <p role="status" className="listas-progreso">La consulta se está procesando. Esta pantalla se actualiza sola.</p>}
      <ResultadoConsultaListas consulta={consulta} descargar={descargar} />
      <h4>Revisiones humanas</h4>
      {!detalle.revisiones.length && <p className="listas-vacio">Aún no hay revisiones humanas registradas.</p>}
      <ul className="listas-revisiones">{detalle.revisiones.map(r => <li key={r.id}>{r.resultado}: {r.justificacion}{r.revision_previa_id && ' (corrección de revisión anterior)'}</li>)}</ul>
      {capacidades.revisar && !pendientes.has(consulta.estado_ejecucion) && (
        <RevisionHistorial
          key={consulta.consulta_id}
          consulta={consulta}
          revisiones={detalle.revisiones}
          ocupado={ocupado}
          onRevisar={revisar}
        />
      )}
    </article>}
  </section>;
}
