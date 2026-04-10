import { CARGOS_JUNTA_DIRECTIVA } from '../../data/formularioConfig';
import {
  onlyTextKeyDown, onlyTextPaste,
  onlyAlphanumericKeyDown, onlyAlphanumericPaste,
  getIdPropsByTipoDocumento, sanitizeIdValue
} from '../../utils/inputValidation';
import { HR, ESTILO_CELDA_ERROR } from '../TablaFormComponents';

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

/**
 * Paso 4 — Junta Directiva y Composición Accionaria.
 * Solo aplica a Persona Jurídica; muestra mensaje alternativo para Natural.
 */
const TIPOS_ID_BENEFICIARIO = [
  { value: 'CC',  label: 'CC'  },
  { value: 'CE',  label: 'CE'  },
  { value: 'PAS', label: 'PAS' },
];

export default function PasoJuntaAccionistas({
  formData,
  errors = {},
  juntaDirectiva, onJuntaChange, onJuntaTipoIdChange, onAddJuntaMember,
  accionistas, onAccionistaChange, onAccionistaTipoIdChange, onAddAccionista,
  beneficiarios, onBeneficiarioChange, onBeneficiarioTipoIdChange, onAddBeneficiario,
}) {
  const erroresFilasJunta = errors.junta_directiva_filas ?? [];
  const erroresFilasAcc   = errors.accionistas_filas     ?? [];
  const erroresFilasBen   = errors.beneficiarios_filas   ?? [];
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
      <h2 className="section-title">INFORMACIÓN JUNTA DIRECTIVA, REPRESENTANTES LEGALES Y REVISORES FISCALES</h2>
      <p className="section-subtitle">Registrar los datos de las personas que conforman la Junta Directiva Principal, Junta Directiva suplente y Revisores Fiscales, que se encuentran registradas en Cámara de Comercio.</p>
      <p className="section-subtitle">Para responder las preguntas respecto a PEP´s, tenga en cuenta que corresponden a personas expuestas políticamente o públicamente que: Manejan recursos públicos, tienen algún grado de poder público o gozan dereconocimiento público.</p>
      {/* Junta Directiva */}
      <h3 style={{ fontSize: '1rem', fontWeight: '800', color: 'var(--gray-800)', marginBottom: '12px' }}>
        Junta Directiva y Representantes
      </h3>

      <div className="info-box">
        <p> PEP: Persona Expuesta Políticamente — persona que maneja recursos públicos, tiene poder público o reconocimiento público.</p>
        <p> ¿Vínculos con PEP? Si es asi, describa, de lo contrario colocar No.</p>
      </div>
      {errors.junta_directiva_tabla && (
        <div className="field-error" style={{ marginBottom: '8px' }}>{errors.junta_directiva_tabla}</div>
      )}

      <div className="data-table-container">
        <table className="data-table">
          <thead>
            <tr>
              <th>Cargo</th><th>Nombre</th><th>Tipo ID</th>
              <th>Número ID</th><th>¿PEP?</th><th>Vínculos PEP</th>
            </tr>
          </thead>
          <tbody>
            {juntaDirectiva.map((miembro, idx) => {
              const err = erroresFilasJunta[idx] ?? {};
              return (
                <tr key={idx}>
                  <td>
                    <select
                      value={miembro.cargo || ''}
                      onChange={(e) => onJuntaChange(idx, 'cargo', e.target.value)}
                      style={err.cargo ? ESTILO_CELDA_ERROR : undefined}
                    >
                      <option value="">Seleccione...</option>
                      {CARGOS_JUNTA_DIRECTIVA.map(cargo => <option key={cargo} value={cargo}>{cargo}</option>)}
                    </select>
                  </td>
                  <td>
                    <input
                      value={miembro.nombre || ''} placeholder="Nombre completo"
                      onChange={(e) => onJuntaChange(idx, 'nombre', e.target.value)}
                      onKeyDown={onlyTextKeyDown} onPaste={onlyTextPaste}
                      style={err.nombre ? ESTILO_CELDA_ERROR : undefined}
                    />
                  </td>
                  <td>
                    <select
                      value={miembro.tipo_id || ''}
                      onChange={(e) => onJuntaTipoIdChange(idx, e.target.value)}
                      style={err.tipo_id ? ESTILO_CELDA_ERROR : undefined}
                    >
                      <option value="">-</option>
                      {TIPOS_ID_JUNTA.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                    </select>
                  </td>
                  <td>
                    <input
                      value={miembro.numero_id || ''} placeholder="Número"
                      onChange={(e) => onJuntaChange(idx, 'numero_id', sanitizeIdValue(e.target.value, miembro.tipo_id))}
                      {...getIdPropsByTipoDocumento(miembro.tipo_id)}
                      maxLength={10}
                      disabled={!miembro.tipo_id}
                      style={err.numero_id ? ESTILO_CELDA_ERROR : undefined}
                    />
                  </td>
                  <td>
                    <select
                      value={miembro.es_pep || ''}
                      onChange={(e) => onJuntaChange(idx, 'es_pep', e.target.value)}
                      style={err.es_pep ? ESTILO_CELDA_ERROR : undefined}
                    >
                      <option value="">-</option>
                      {OPCIONES_PEP.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                    </select>
                  </td>
                  <td>
                    <input
                      value={miembro.vinculos_pep || ''} placeholder="Describa:"
                      onChange={(e) => onJuntaChange(idx, 'vinculos_pep', e.target.value)}
                      style={err.vinculos_pep ? ESTILO_CELDA_ERROR : undefined}
                    />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <button type="button" className="btn btn-sm btn-outline" onClick={onAddJuntaMember}>
        + Agregar miembro
      </button>

      <HR />

      {/* Composición Accionaria */}
      <h3 style={{ fontSize: '1rem', fontWeight: '800', color: 'var(--gray-800)', marginBottom: '12px' }}>
        Composición Accionaria
      </h3>
      <div className="info-box">
        <p>Registrar todos los accionistas o asociados que tengan directa o indirectamente mas del 5% de su capital social, aporte o participación.</p>
        <p>  ¿Vínculos con PEP? Si es asi, describa, de lo contrario colocar No.</p>
      </div>
      {errors.accionistas_tabla && (
        <div className="field-error" style={{ marginBottom: '8px' }}>{errors.accionistas_tabla}</div>
      )}
      {errors.accionistas_suma && (
        <div className="field-error" style={{ marginBottom: '8px' }}>{errors.accionistas_suma}</div>
      )}
      <div className="data-table-container">
        <table className="data-table">
          <thead>
            <tr>
              <th>Nombre o Razón Social</th><th>% Participación</th><th>Tipo ID</th>
              <th>Número ID</th><th>¿PEP?</th><th>Vínculos PEP</th>
            </tr>
          </thead>
          <tbody>
            {accionistas.map((acc, idx) => {
              const err = erroresFilasAcc[idx] ?? {};
              return (
                <tr key={idx}>
                  <td>
                    <input
                      value={acc.nombre || ''} placeholder="Nombre"
                      onChange={(e) => onAccionistaChange(idx, 'nombre', e.target.value)}
                      onKeyDown={onlyAlphanumericKeyDown} onPaste={onlyAlphanumericPaste}
                      style={err.nombre ? ESTILO_CELDA_ERROR : undefined}
                    />
                  </td>
                  <td>
                    <input
                      type="number" step="0.01" min="5.01" max="99.99"
                      value={acc.porcentaje || ''} placeholder="%"
                      onChange={(e) => onAccionistaChange(idx, 'porcentaje', e.target.value)}
                      style={err.porcentaje ? ESTILO_CELDA_ERROR : undefined}
                    />
                    {err.porcentaje && (
                      <span style={{ color: 'var(--error, #e53e3e)', fontSize: '0.75rem', display: 'block' }}>{err.porcentaje}</span>
                    )}
                  </td>
                  <td>
                    <select
                      value={acc.tipo_id || ''}
                      onChange={(e) => onAccionistaTipoIdChange(idx, e.target.value)}
                      style={err.tipo_id ? ESTILO_CELDA_ERROR : undefined}
                    >
                      <option value="">-</option>
                      {TIPOS_ID_ACCIONISTA.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                    </select>
                  </td>
                  <td>
                    <input
                      value={acc.numero_id || ''} placeholder="Número"
                      onChange={(e) => onAccionistaChange(idx, 'numero_id', sanitizeIdValue(e.target.value, acc.tipo_id))}
                      {...getIdPropsByTipoDocumento(acc.tipo_id)}
                      maxLength={10}
                      disabled={!acc.tipo_id}
                      style={err.numero_id ? ESTILO_CELDA_ERROR : undefined}
                    />
                  </td>
                  <td>
                    <select
                      value={acc.es_pep || ''}
                      onChange={(e) => onAccionistaChange(idx, 'es_pep', e.target.value)}
                      style={err.es_pep ? ESTILO_CELDA_ERROR : undefined}
                    >
                      <option value="">-</option>
                      {OPCIONES_PEP.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                    </select>
                  </td>
                  <td>
                    <input
                      value={acc.vinculos_pep || ''} placeholder="Describa:"
                      onChange={(e) => onAccionistaChange(idx, 'vinculos_pep', e.target.value)}
                      style={err.vinculos_pep ? ESTILO_CELDA_ERROR : undefined}
                    />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <button type="button" className="btn btn-sm btn-outline" onClick={onAddAccionista}>
        + Agregar accionista
      </button>

      <HR />

      {/* Beneficiario Final */}
      <h3 style={{ fontSize: '1rem', fontWeight: '800', color: 'var(--gray-800)', marginBottom: '12px' }}>
        Beneficiario Final
      </h3>
      <div className="info-box">
        <p>En caso de que los socios sean personas jurídicas, describa la(s) persona(s) natural(es) que ejercen el control efectivo directo o indirecto sobre los socios persona(s) jurídica(s), o que sea titular del <strong>25% o más del capital</strong> de los socios.</p>
      </div>
      {errors.beneficiarios_tabla && (
        <div className="field-error" style={{ marginBottom: '8px' }}>{errors.beneficiarios_tabla}</div>
      )}
      {errors.beneficiarios_suma && (
        <div className="field-error" style={{ marginBottom: '8px' }}>{errors.beneficiarios_suma}</div>
      )}
      <div className="data-table-container">
        <table className="data-table">
          <thead>
            <tr>
              <th>Nombre / Razón Social</th><th>% Control</th><th>Tipo ID</th>
              <th>Número ID</th><th>¿PEP?</th><th>Vínculos PEP</th>
            </tr>
          </thead>
          <tbody>
            {beneficiarios.map((ben, idx) => {
              const err = erroresFilasBen[idx] ?? {};
              return (
                <tr key={idx}>
                  <td>
                    <input
                      value={ben.nombre || ''} placeholder="Nombre"
                      onChange={(e) => onBeneficiarioChange(idx, 'nombre', e.target.value)}
                      onKeyDown={onlyAlphanumericKeyDown} onPaste={onlyAlphanumericPaste}
                      style={err.nombre ? ESTILO_CELDA_ERROR : undefined}
                    />
                  </td>
                  <td>
                    <input
                      type="number" step="0.01" min="25.01" max="99.99"
                      value={ben.porcentaje || ''} placeholder="%"
                      onChange={(e) => onBeneficiarioChange(idx, 'porcentaje', e.target.value)}
                      style={err.porcentaje ? ESTILO_CELDA_ERROR : undefined}
                    />
                    {err.porcentaje && (
                      <span style={{ color: 'var(--error, #e53e3e)', fontSize: '0.75rem', display: 'block' }}>{err.porcentaje}</span>
                    )}
                  </td>
                  <td>
                    <select
                      value={ben.tipo_id || ''}
                      onChange={(e) => onBeneficiarioTipoIdChange(idx, e.target.value)}
                      style={err.tipo_id ? ESTILO_CELDA_ERROR : undefined}
                    >
                      <option value="">-</option>
                      {TIPOS_ID_BENEFICIARIO.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                    </select>
                  </td>
                  <td>
                    <input
                      value={ben.numero_id || ''} placeholder="Número"
                      onChange={(e) => onBeneficiarioChange(idx, 'numero_id', sanitizeIdValue(e.target.value, ben.tipo_id))}
                      {...getIdPropsByTipoDocumento(ben.tipo_id)}
                      maxLength={10}
                      disabled={!ben.tipo_id}
                      style={err.numero_id ? ESTILO_CELDA_ERROR : undefined}
                    />
                  </td>
                  <td>
                    <select
                      value={ben.es_pep || ''}
                      onChange={(e) => onBeneficiarioChange(idx, 'es_pep', e.target.value)}
                      style={err.es_pep ? ESTILO_CELDA_ERROR : undefined}
                    >
                      <option value="">-</option>
                      {OPCIONES_PEP.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                    </select>
                  </td>
                  <td>
                    <input
                      value={ben.vinculos_pep || ''} placeholder="Detalle"
                      onChange={(e) => onBeneficiarioChange(idx, 'vinculos_pep', e.target.value)}
                      style={err.vinculos_pep ? ESTILO_CELDA_ERROR : undefined}
                    />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <button type="button" className="btn btn-sm btn-outline" onClick={onAddBeneficiario}>
        + Agregar beneficiario
      </button>
    </div>
  );
}
