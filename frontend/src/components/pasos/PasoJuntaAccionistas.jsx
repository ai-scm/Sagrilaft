import FormField from '../FormField';

const TIPOS_ID_JUNTA = [
  { value: 'CC',  label: 'CC'  },
  { value: 'CE',  label: 'CE'  },
  { value: 'PAS', label: 'PAS' },
];

const TIPOS_ID_ACCIONISTA = [
  { value: 'CC',  label: 'CC'  },
  { value: 'NIT', label: 'NIT' },
  { value: 'CE',  label: 'CE'  },
  { value: 'PAS', label: 'PAS' },
];

const OPCIONES_PEP = [
  { value: 'si', label: 'Sí' },
  { value: 'no', label: 'No' },
];

const HR = () => (
  <hr style={{ border: 'none', borderTop: '1px solid var(--gray-200)', margin: '28px 0' }} />
);

/**
 * Paso 4 — Junta Directiva y Composición Accionaria.
 * Solo aplica a Persona Jurídica; muestra mensaje alternativo para Natural.
 */
export default function PasoJuntaAccionistas({
  formData, onChange, onOpenHelp,
  juntaDirectiva, onJuntaChange, onAddJuntaMember,
  accionistas, onAccionistaChange, onAddAccionista,
}) {
  if (formData.tipo_persona === 'natural') {
    return (
      <div className="form-card" style={{ textAlign: 'center', padding: '40px' }}>
        <p style={{ color: 'var(--gray-500)' }}>
          Esta sección aplica solo para Persona Jurídica. Haga clic en "Siguiente" para continuar.
        </p>
      </div>
    );
  }

  return (
    <div className="form-card">
      <h2 className="section-title">🏛️ Junta Directiva y Composición Accionaria</h2>
      <p className="section-subtitle">Información de directivos, representantes y accionistas</p>

      <div className="info-box">
        <p>📌 PEP: Persona Expuesta Políticamente — persona que maneja recursos públicos, tiene poder público o reconocimiento público.</p>
      </div>

      {/* Junta Directiva */}
      <h3 style={{ fontSize: '1rem', fontWeight: '600', color: 'var(--gray-800)', marginBottom: '12px' }}>
        Junta Directiva y Representantes
      </h3>
      <div className="data-table-container">
        <table className="data-table">
          <thead>
            <tr>
              <th>Cargo</th><th>Nombre</th><th>Tipo ID</th>
              <th>Número ID</th><th>¿PEP?</th><th>Vínculos PEP</th>
            </tr>
          </thead>
          <tbody>
            {juntaDirectiva.map((miembro, idx) => (
              <tr key={idx}>
                <td><input value={miembro.cargo || ''} placeholder="Cargo" onChange={(e) => onJuntaChange(idx, 'cargo', e.target.value)} /></td>
                <td><input value={miembro.nombre || ''} placeholder="Nombre completo" onChange={(e) => onJuntaChange(idx, 'nombre', e.target.value)} /></td>
                <td>
                  <select value={miembro.tipo_id || ''} onChange={(e) => onJuntaChange(idx, 'tipo_id', e.target.value)}>
                    <option value="">-</option>
                    {TIPOS_ID_JUNTA.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                  </select>
                </td>
                <td><input value={miembro.numero_id || ''} placeholder="Número" onChange={(e) => onJuntaChange(idx, 'numero_id', e.target.value)} /></td>
                <td>
                  <select value={miembro.es_pep || ''} onChange={(e) => onJuntaChange(idx, 'es_pep', e.target.value)}>
                    <option value="">-</option>
                    {OPCIONES_PEP.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                  </select>
                </td>
                <td><input value={miembro.vinculos_pep || ''} placeholder="Detalle" onChange={(e) => onJuntaChange(idx, 'vinculos_pep', e.target.value)} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <button type="button" className="btn btn-sm btn-outline" onClick={onAddJuntaMember}>
        + Agregar miembro
      </button>

      <HR />

      {/* Composición Accionaria */}
      <h3 style={{ fontSize: '1rem', fontWeight: '600', color: 'var(--gray-800)', marginBottom: '12px' }}>
        Composición Accionaria
      </h3>
      <div className="info-box">
        <p>📌 Registre accionistas o asociados con más del 5% del capital social.</p>
      </div>
      <div className="data-table-container">
        <table className="data-table">
          <thead>
            <tr>
              <th>Nombre / Razón Social</th><th>% Participación</th><th>Tipo ID</th>
              <th>Número ID</th><th>¿PEP?</th><th>Vínculos PEP</th>
            </tr>
          </thead>
          <tbody>
            {accionistas.map((acc, idx) => (
              <tr key={idx}>
                <td><input value={acc.nombre || ''} placeholder="Nombre" onChange={(e) => onAccionistaChange(idx, 'nombre', e.target.value)} /></td>
                <td>
                  <input
                    type="number" step="0.01" min="0" max="100"
                    value={acc.porcentaje || ''} placeholder="%"
                    onChange={(e) => onAccionistaChange(idx, 'porcentaje', e.target.value)}
                  />
                </td>
                <td>
                  <select value={acc.tipo_id || ''} onChange={(e) => onAccionistaChange(idx, 'tipo_id', e.target.value)}>
                    <option value="">-</option>
                    {TIPOS_ID_ACCIONISTA.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                  </select>
                </td>
                <td><input value={acc.numero_id || ''} placeholder="Número" onChange={(e) => onAccionistaChange(idx, 'numero_id', e.target.value)} /></td>
                <td>
                  <select value={acc.es_pep || ''} onChange={(e) => onAccionistaChange(idx, 'es_pep', e.target.value)}>
                    <option value="">-</option>
                    {OPCIONES_PEP.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                  </select>
                </td>
                <td><input value={acc.vinculos_pep || ''} placeholder="Detalle" onChange={(e) => onAccionistaChange(idx, 'vinculos_pep', e.target.value)} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <button type="button" className="btn btn-sm btn-outline" onClick={onAddAccionista}>
        + Agregar accionista
      </button>

      <div style={{ marginTop: '24px' }}>
        <FormField
          label="Beneficiario Final" name="beneficiario_final" type="textarea"
          value={formData.beneficiario_final} onChange={onChange}
          onOpenHelp={onOpenHelp}
          placeholder="Persona natural que ejerce control efectivo sobre socios jurídicos o titular del 25%+ del capital"
        />
      </div>
    </div>
  );
}
