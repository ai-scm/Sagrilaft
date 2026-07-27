import { useEffect, useState } from 'react';
import Alert from '@shared/components/ui/Alert';

export default function ModalSagrilaft({ visible, onConfirmar, onCancelar, ocupado, error, expediente }) {
  const [datos, setDatos] = useState({
    tipo_identificacion: expediente?.tipo_identificacion || '',
    numero_identificacion: expediente?.numero_identificacion || '',
    nombre_completo: expediente?.razon_social || '',
    fecha_expedicion: '',
  });

  useEffect(() => {
    if (visible && expediente) {
      setDatos({
        tipo_identificacion: expediente.tipo_identificacion || '',
        numero_identificacion: expediente.numero_identificacion || '',
        nombre_completo: expediente.razon_social || '',
        fecha_expedicion: '',
      });
    }
  }, [visible, expediente]);

  if (!visible) return null;

  return (
    <div className="modal-overlay" role="dialog" aria-modal="true">
      <div className="modal-container" style={{ maxWidth: '460px' }}>
        <div className="modal-header">
          <h3 className="modal-title">Consultar SAGRILAFT</h3>
          <p className="modal-desc">
            Confirma o edita los datos que se enviarán a la central de riesgo.
          </p>
        </div>

        <div className="modal-body">
          {error && <Alert mensaje={error} style={{ marginBottom: '16px' }} />}

          <div className="form-group" style={{ marginBottom: '12px' }}>
            <label className="field-label" style={{ display: 'block', marginBottom: '4px' }}>Tipo de Identificación</label>
            <input
              className="input-base"
              type="text"
              value={datos.tipo_identificacion}
              onChange={e => setDatos({ ...datos, tipo_identificacion: e.target.value })}
              disabled={ocupado}
              style={{ width: '100%', padding: '8px', border: '1px solid #d1d5db', borderRadius: '4px' }}
            />
          </div>

          <div className="form-group" style={{ marginBottom: '12px' }}>
            <label className="field-label" style={{ display: 'block', marginBottom: '4px' }}>Número de Identificación</label>
            <input
              className="input-base"
              type="text"
              value={datos.numero_identificacion}
              onChange={e => setDatos({ ...datos, numero_identificacion: e.target.value })}
              disabled={ocupado}
              style={{ width: '100%', padding: '8px', border: '1px solid #d1d5db', borderRadius: '4px' }}
            />
          </div>

          <div className="form-group" style={{ marginBottom: '12px' }}>
            <label className="field-label" style={{ display: 'block', marginBottom: '4px' }}>Nombre / Razón Social</label>
            <input
              className="input-base"
              type="text"
              value={datos.nombre_completo}
              onChange={e => setDatos({ ...datos, nombre_completo: e.target.value })}
              disabled={ocupado}
              style={{ width: '100%', padding: '8px', border: '1px solid #d1d5db', borderRadius: '4px' }}
            />
          </div>

          <div className="form-group" style={{ marginBottom: '16px' }}>
            <label className="field-label" style={{ display: 'block', marginBottom: '4px' }}>
              Fecha de Expedición <span style={{ color: '#6b7280', fontSize: '0.85em', fontWeight: 'normal' }}>(dd/mm/yyyy - Obligatorio para CE y PPT)</span>
            </label>
            <input
              className="input-base"
              type="text"
              placeholder="Ej: 01/12/2017"
              value={datos.fecha_expedicion}
              onChange={e => setDatos({ ...datos, fecha_expedicion: e.target.value })}
              disabled={ocupado}
              style={{ width: '100%', padding: '8px', border: '1px solid #d1d5db', borderRadius: '4px' }}
            />
          </div>
        </div>

        <div className="modal-footer" style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', padding: '16px', borderTop: '1px solid #f3f4f6' }}>
          <button className="btn btn-secondary" onClick={onCancelar} disabled={ocupado} type="button">
            Cancelar
          </button>
          <button
            className="btn btn-primary"
            onClick={() => onConfirmar(datos)}
            disabled={ocupado || !datos.tipo_identificacion || !datos.numero_identificacion || !datos.nombre_completo}
            type="button"
          >
            {ocupado ? 'Consultando...' : 'Verificar en Tusdatos'}
          </button>
        </div>
      </div>
    </div>
  );
}
