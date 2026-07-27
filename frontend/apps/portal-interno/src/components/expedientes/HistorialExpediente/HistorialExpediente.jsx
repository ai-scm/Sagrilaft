import { useState, useEffect } from 'react';
import { api } from '../../../services/api';
import { Clock, FileText, CheckCircle2, User, ArrowUp } from 'lucide-react';
import { usePaginacion } from '../../../hooks/usePaginacion';
import ControlsPaginacion from '../../ui/ControlsPaginacion';

export default function HistorialExpediente({ formularioId }) {
  const [descargandoReporte, setDescargandoReporte] = useState(false);
  const [error, setError] = useState(null);

  async function handleDescargarReporte() {
    setDescargandoReporte(true);
    setError(null);
    try {
      await api.descargarReporteAuditoria(formularioId);
    } catch (err) {
      setError(err.message || 'No se pudo descargar el reporte de auditoría.');
    } finally {
      setDescargandoReporte(false);
    }
  }

  const [eventos, setEventos] = useState([]);
  const [cargando, setCargando] = useState(true);
  
  const paginacionEventos = usePaginacion(eventos, 4);

  useEffect(() => {
    async function loadEventos() {
      try {
        setCargando(true);
        setError(null);
        const data = await api.listarEventosExpediente(formularioId);
        setEventos(data);
      } catch (err) {
        console.error("Error al cargar historial:", err);
        setError('No se pudo cargar el historial del expediente.');
      } finally {
        setCargando(false);
      }
    }
    loadEventos();
  }, [formularioId]);

  function formatearFecha(isoString) {
    if (!isoString) return '';
    const date = new Date(isoString);
    return date.toLocaleString('es-CO', {
      day: '2-digit', month: 'short', year: 'numeric',
      hour: '2-digit', minute: '2-digit'
    });
  }

  function formatTipoEvento(tipo) {
    const mapa = {
      'FORMULARIO_CREADO': 'Formulario creado',
      'FORMULARIO_ENVIADO': 'Formulario enviado',
      'FORMULARIO_APROBADO': 'Formulario aprobado',
      'FORMULARIO_RECHAZADO': 'Formulario rechazado',
      'FORMULARIO_DEVUELTO': 'Formulario devuelto',
      'FORMULARIO_DEVOLUCION_REVERTIDA': 'Devolución revertida',
      'FORMULARIO_CARGADO_MANUALMENTE': 'Formulario cargado manual',
      'REPORTE_FINAL_CARGADO': 'Reporte final cargado',
      'REPORTE_FINAL_ELIMINADO': 'Reporte final eliminado',
      'EXPEDIENTE_CERRADO': 'Expediente cerrado',
      'EXPEDIENTE_REABIERTO_ACTUALIZACION': 'Expediente reabierto',
      'FIRMA_INICIADA': 'Firma iniciada',
      'FIRMA_COMPLETADA': 'Firma completada',
      'FIRMA_CANCELADA': 'Firma cancelada',
      'DOCUMENTO_CARGADO': 'Documento cargado',
      'DOCUMENTO_ELIMINADO': 'Documento eliminado',
      'CAMBIO_DIRECTO_BD': 'Alerta de integridad'
    };
    return mapa[tipo] || tipo;
  }

  function getUIProps(evento) {
    let tipoUI = 'system';
    let icon = <Clock size={16} />;
    
    if (evento.tipo_evento.includes('APROBADO') || evento.tipo_evento.includes('COMPLETADA') || evento.tipo_evento.includes('CERRADO')) {
      tipoUI = 'success';
      icon = <CheckCircle2 size={16} />;
    } else if (evento.tipo_evento.includes('CARGADO')) {
      tipoUI = 'upload';
      icon = <ArrowUp size={16} />;
    } else if (evento.tipo_evento.includes('RECHAZADO') || evento.tipo_evento.includes('CANCELADA') || evento.tipo_evento.includes('DEVUELTO')) {
      tipoUI = 'alert';
      icon = <FileText size={16} />;
    } else {
      tipoUI = 'system';
      icon = <FileText size={16} />;
    }

    const cssClass = {
      'success': 'audit-icon green',
      'upload': 'audit-icon blue',
      'alert': 'audit-icon red',
      'system': 'audit-icon purple'
    }[tipoUI] || 'audit-icon purple';

    return { icon, cssClass };
  }


  return (
    <>
      <div className="section-header">
        <h2 className="section-title">Historial del Expediente</h2>
        <button
          type="button"
          className="btn-outline"
          disabled={descargandoReporte}
          onClick={handleDescargarReporte}
          style={{ opacity: descargandoReporte ? 0.6 : 1 }}
        >
          <Clock size={14} /> {descargandoReporte ? 'Descargando...' : 'Ver auditoría completa'}
        </button>
      </div>

      <div className="card timeline-card">
        {error && <div style={{ padding: '16px', color: '#DC2626', background: '#FEF2F2' }}>{error}</div>}
        {cargando ? (
          <div style={{ padding: '24px', textAlign: 'center', color: '#6B7280' }}>Cargando historial...</div>
        ) : (
          <div className="timeline-list">
            {paginacionEventos.elementosPagina.map((evento) => {
              const { icon, cssClass } = getUIProps(evento);
              const actor = evento.actor_tipo === 'SISTEMA' ? 'SISTEMA' : evento.actor_id || 'Desconocido';
              const titulo = formatTipoEvento(evento.tipo_evento);
              const descripcion = evento.estado_anterior 
                ? `Cambio de estado: ${evento.estado_anterior} → ${evento.estado_nuevo}`
                : `Estado actualizado a ${evento.estado_nuevo}`;

              return (
                <div key={evento.id} className="timeline-row">
                  <div className="timeline-marker">
                    <div className={cssClass}>
                      {icon}
                    </div>
                  </div>
                  <div className="timeline-content">
                    <div className="audit-info">
                      <h4 className="audit-title">{titulo}</h4>
                      <p className="audit-desc">{descripcion}</p>
                      {evento.metadata?.causal_cierre && (
                        <div style={{ marginTop: '4px', fontSize: '13px', color: '#4B5563', background: '#F3F4F6', padding: '4px 8px', borderRadius: '4px', display: 'inline-block' }}>
                          <strong>Causal:</strong> {
                            {
                              'informe_final': 'Cierre aprobado con informe final',
                              'no_continuacion_dialogos': 'No continuación de diálogos',
                              'rechazado_con_informe_final': 'Cierre rechazado con informe final'
                            }[evento.metadata.causal_cierre] || evento.metadata.causal_cierre
                          }
                        </div>
                      )}
                    </div>
                    <div className="audit-meta">
                      <span>{formatearFecha(evento.created_at)}</span>
                      <div className="audit-user">
                        {evento.actor_tipo === 'SISTEMA' ? (
                          <Clock size={14} className="text-gray-400" />
                        ) : (
                          <User size={14} className="text-gray-400" />
                        )}
                        <span>{actor}</span>
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
            {eventos.length === 0 && !error && (
              <div style={{ padding: '24px', textAlign: 'center', color: '#6B7280' }}>No hay eventos registrados.</div>
            )}
          </div>
        )}

        <div style={{ padding: '8px 24px 16px' }}>
          <ControlsPaginacion {...paginacionEventos} />
        </div>
      </div>
    </>
  );
}
