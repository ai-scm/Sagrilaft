import { ShieldCheck, Upload } from 'lucide-react';
import BadgeEstadoFormulario from '../../badges/BadgeEstadoFormulario';
import {
  ETIQUETA_CAUSAL_CIERRE,
  formatearFechaHora,
} from '../../../config/constantes';

export default function DetalleExpedienteHeader({
  expediente,
  razonSocial,
  tipoLabel,
  tipoSolicitudLabel,
  estaCerrado,
  permiteReaperturaActualizacion,
  onReabrirActualizacion,
  onCargarManual,
  onCerrarExpediente,
}) {
  return (
    <header className="expediente-header">
      <div className="header-left">
        <div className="title-group">
          <h1 className="company-name">{expediente.razon_social ?? razonSocial ?? '(Sin razón social)'}</h1>
          <span className="case-code">{expediente.codigo_peticion}</span>
        </div>
        <div className="badge-group">
          {tipoLabel && <span className="badge badge-neutral">{tipoLabel}</span>}
          {tipoSolicitudLabel && <span className="badge badge-neutral">{tipoSolicitudLabel}</span>}
          <BadgeEstadoFormulario estado={expediente.estado} />
          {expediente.causal_cierre && (
            <span className="badge badge-neutral">
              Causal: {ETIQUETA_CAUSAL_CIERRE[expediente.causal_cierre] || expediente.causal_cierre}
            </span>
          )}
          {expediente.updated_at && (
            <span className="badge badge-neutral">
              {estaCerrado ? 'Cerrado' : 'Enviado'} {formatearFechaHora(expediente.updated_at)}
            </span>
          )}
          {expediente.correo_destinatario && (
            <span
              className="badge badge-neutral"
              title={`Correo del representante legal: ${expediente.correo_destinatario}`}
              style={{ maxWidth: '280px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
            >
              {expediente.correo_destinatario}
            </span>
          )}
        </div>
      </div>
      <div className="header-actions">
        {permiteReaperturaActualizacion && (
          <button
            className="btn btn-outline-green"
            onClick={onReabrirActualizacion}
            type="button"
          >
            Reabrir Actualización
          </button>
        )}
        <button
          className="btn btn-secondary"
          onClick={onCargarManual}
          disabled={estaCerrado}
          type="button"
          title={estaCerrado ? 'No se puede modificar un expediente cerrado' : ''}
        >
          <Upload size={16} />
          Cargar Formulario Manual
        </button>
        <button
          className="btn btn-primary"
          onClick={onCerrarExpediente}
          type="button"
        >
          <ShieldCheck size={16} />
          Cerrar Expediente
        </button>
      </div>
    </header>
  );
}
