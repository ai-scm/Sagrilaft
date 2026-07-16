import { useState } from 'react';
import { AlertTriangle, CheckCircle, XCircle, ShieldAlert } from 'lucide-react';
import { api } from '../../services/api';
import { usePaginacion } from '../../hooks/usePaginacion';
import ControlsPaginacion from '../ui/ControlsPaginacion';
import './PanelAlertasAuditoria.css';

const DICCIONARIO_CAMPOS = {
  razon_social: 'Razón Social',
  numero_identificacion: 'NIT / Número de Identificación',
  nombre_representante: 'Nombre Representante Legal',
  numero_doc_representante: 'Doc. Representante Legal',
  direccion: 'Dirección',
};

const DICCIONARIO_ESTADOS = {
  PENDIENTE: { label: 'Pendiente', icon: AlertTriangle, color: 'text-amber-500', bg: 'bg-amber-50' },
  FALSO_POSITIVO_IA: { label: 'Falso Positivo IA', icon: XCircle, color: 'text-gray-500', bg: 'bg-gray-50' },
  CORREGIDO: { label: 'Corregido', icon: CheckCircle, color: 'text-green-500', bg: 'bg-green-50' },
  RIESGO_ACEPTADO: { label: 'Riesgo Aceptado', icon: ShieldAlert, color: 'text-blue-500', bg: 'bg-blue-50' },
};

export default function PanelAlertasAuditoria({ alertas = [], formularioId, onAlertaActualizada }) {
  const [actualizando, setActualizando] = useState(null);
  const paginacion = usePaginacion(alertas, 3);

  if (!alertas || alertas.length === 0) {
    return null;
  }

  const handleCambiarEstado = async (alertaId, nuevoEstado) => {
    setActualizando(alertaId);
    try {
      await api.actualizarEstadoAlerta(formularioId, alertaId, nuevoEstado);
      onAlertaActualizada();
    } catch (err) {
      alert(err.message || 'Error al actualizar el estado de la alerta.');
    } finally {
      setActualizando(null);
    }
  };

  return (
    <div className="card alertas-card">
      <div className="alertas-header" style={{ padding: '20px 24px', borderBottom: '1px solid #e5e7eb' }}>
        <h3 className="doc-title" style={{ display: 'flex', alignItems: 'center', gap: '8px', margin: 0 }}>
          <AlertTriangle color="#f59e0b" size={20} />
          Alertas de Inconsistencia Documental
        </h3>
        <p style={{ margin: '8px 0 0', fontSize: '13px', color: '#6b7280' }}>
          Inconsistencias detectadas entre el formulario y los documentos adjuntos que la contraparte ignoró al enviar.
        </p>
      </div>

      <div className="alertas-list" style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
        {paginacion.elementosPagina.map((alerta) => {
          const EstadoInfo = DICCIONARIO_ESTADOS[alerta.estado_auditoria] || DICCIONARIO_ESTADOS.PENDIENTE;
          const EstadoIcon = EstadoInfo.icon;
          const nombreCampo = DICCIONARIO_CAMPOS[alerta.tipo_campo] || alerta.tipo_campo;

          return (
            <div key={alerta.id} className={`alerta-item ${alerta.estado_auditoria.toLowerCase()}`} style={{ border: '1px solid #e5e7eb', borderRadius: '8px', padding: '16px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <EstadoIcon size={18} />
                  <strong style={{ fontSize: '14px', color: '#111827' }}>{nombreCampo}</strong>
                  <span style={{ fontSize: '12px', color: '#6b7280' }}>({alerta.nombre_documento})</span>
                </div>
                <div style={{ textAlign: 'right' }}>
                  <select
                    style={{ padding: '4px 8px', fontSize: '13px', borderRadius: '4px', border: '1px solid #d1d5db', background: '#fff', width: '100%' }}
                    value={alerta.estado_auditoria}
                    onChange={(e) => handleCambiarEstado(alerta.id, e.target.value)}
                    disabled={actualizando === alerta.id}
                  >
                    <option value="PENDIENTE">Pendiente</option>
                    <option value="FALSO_POSITIVO_IA">Marcar como Falso Positivo</option>
                    <option value="RIESGO_ACEPTADO">Aceptar Riesgo</option>
                    <option value="CORREGIDO">Marcar como Corregido</option>
                  </select>
                  {alerta.actualizado_por && alerta.estado_auditoria !== 'PENDIENTE' && (
                    <div style={{ marginTop: '4px', fontSize: '11px', color: '#9ca3af' }}>
                      por {alerta.actualizado_por}
                    </div>
                  )}
                </div>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', background: '#f9fafb', padding: '12px', borderRadius: '6px' }}>
                <div>
                  <span style={{ display: 'block', fontSize: '11px', fontWeight: '600', color: '#6b7280', textTransform: 'uppercase', marginBottom: '4px' }}>Valor en Formulario:</span>
                  <p style={{ margin: 0, fontSize: '13px', color: '#1f2937', wordBreak: 'break-word' }}>{alerta.valor_formulario || '(Vacío)'}</p>
                </div>
                <div>
                  <span style={{ display: 'block', fontSize: '11px', fontWeight: '600', color: '#6b7280', textTransform: 'uppercase', marginBottom: '4px' }}>Extraído del Doc:</span>
                  <p style={{ margin: 0, fontSize: '13px', color: '#1f2937', wordBreak: 'break-word' }}>{alerta.valor_documento || '(No detectado)'}</p>
                </div>
              </div>
            </div>
          );
        })}
        {alertas.length > 3 && (
          <div style={{ marginTop: '16px', borderTop: '1px solid #e5e7eb', paddingTop: '16px' }}>
            <ControlsPaginacion {...paginacion} />
          </div>
        )}
      </div>
    </div>
  );
}
