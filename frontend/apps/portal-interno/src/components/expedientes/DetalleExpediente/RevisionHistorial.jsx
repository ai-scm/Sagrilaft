import { memo, useState } from 'react';

/**
 * RevisionHistorial — Formulario de revisión humana de una consulta abierta.
 *
 * Igual que ConsultaForm, aísla su propio estado de edición (decisión,
 * justificación, alcance) para que escribir aquí no obligue a re-renderizar
 * el resultado de la consulta (candidatos, motivos, evidencias), que es la
 * parte más pesada del árbol.
 */
function RevisionHistorial({ opciones, revisiones, ocupado, onRevisar }) {
  const [decision, setDecision] = useState('REQUIERE_INFORMACION');
  const [justificacion, setJustificacion] = useState('');
  const [candidato, setCandidato] = useState('');
  const [revisionPrevia, setRevisionPrevia] = useState('');

  function manejarEnvio(e) {
    e.preventDefault();
    onRevisar({
      resultado: decision,
      justificacion,
      coincidencia_id: candidato || null,
      revision_previa_id: revisionPrevia || null,
    });
  }

  return (
    <form className="listas-revision-form" onSubmit={manejarEnvio}>
      <label className="listas-campo">Alcance <select className="form-input" value={candidato} onChange={e => setCandidato(e.target.value)}>
        <option value="">Consulta completa</option>
        {opciones.map(o => <option key={o.id} value={o.id}>{o.etiqueta}</option>)}
      </select></label>
      <label className="listas-campo">Corrige una revisión <select className="form-input" value={revisionPrevia} onChange={e => setRevisionPrevia(e.target.value)}>
        <option value="">Nueva revisión</option>
        {revisiones.map(r => <option key={r.id} value={r.id}>{r.resultado}: {r.justificacion}</option>)}
      </select></label>
      <label className="listas-campo">Decisión <select className="form-input" aria-label="Decisión" value={decision} onChange={e => setDecision(e.target.value)}>
        <option value="REQUIERE_INFORMACION">Requiere información</option>
        <option value="DESCARTADA">Coincidencia descartada</option>
        <option value="IDENTIDAD_CORROBORADA">Identidad corroborada</option>
      </select></label>
      <label className="listas-campo">Justificación <textarea className="form-input form-textarea" required maxLength={2000} value={justificacion} onChange={e => setJustificacion(e.target.value)} /></label>
      <div className="listas-acciones"><button className="btn-modal btn-modal-primary" disabled={ocupado || !justificacion.trim()}>Guardar revisión</button></div>
    </form>
  );
}

export default memo(RevisionHistorial);
