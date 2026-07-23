/**
 * ModalReaperturaActualizacion — panel para reabrir una actualización de expediente.
 *
 * Funciona de manera idéntica al modal de devolución, permitiendo especificar
 * qué debe corregirse y seleccionar campos del formulario.
 */

import { useState } from 'react';
import { api } from '../../services/api';
import ModalConfirmacion from './ModalConfirmacion';
import FormularioEspecificacionesCorreccion from '../formularios/FormularioEspecificacionesCorreccion';

const LONGITUD_MINIMA_ESPECIFICACIONES = 20;

// ── Estilos (mismos que Devolucion) ──────────────────────────────────────────

const s = {
  fondo: {
    position:        'fixed',
    inset:           0,
    background:      'rgba(15, 23, 42, 0.5)',
    display:         'flex',
    alignItems:      'center',
    justifyContent:  'center',
    zIndex:          200,
    padding:         '16px',
  },
  modal: {
    background:   '#fff',
    borderRadius: 'var(--radius-md, 10px)',
    boxShadow:    '0 20px 60px rgba(0,0,0,0.2)',
    width:        '100%',
    maxWidth:     '560px',
    maxHeight:    '90vh',
    overflowY:    'auto',
    display:      'flex',
    flexDirection: 'column',
  },
  encabezado: {
    padding:      '24px 24px 0',
  },
  titulo: {
    fontSize:   '1.15rem',
    fontWeight: '800',
    color:      'var(--gray-900, #0f172a)',
    margin:     '0 0 8px',
  },
  descripcion: {
    fontSize:    '0.85rem',
    color:       'var(--gray-500, #64748b)',
    margin:      '0 0 24px',
    lineHeight:  1.5,
  },
  cuerpo: {
    padding:    '0 24px',
    flex:       1,
  },
  bannerError: {
    marginTop:    '16px',
    padding:      '10px 14px',
    background:   '#fef2f2',
    border:       '1px solid #fca5a5',
    borderRadius: 'var(--radius-sm, 6px)',
    fontSize:     '0.85rem',
    color:        '#dc2626',
  },
  pie: {
    display:        'flex',
    justifyContent: 'flex-end',
    gap:            '10px',
    padding:        '20px 24px 24px',
    borderTop:      '1px solid var(--gray-100, #f1f5f9)',
    marginTop:      '20px',
  },
  btnCancelar: {
    padding:      '9px 20px',
    background:   '#fff',
    color:        'var(--gray-600, #475569)',
    border:       '1.5px solid var(--gray-300, #cbd5e1)',
    borderRadius: 'var(--radius-sm, 6px)',
    fontSize:     '0.88rem',
    fontWeight:   '600',
    cursor:       'pointer',
  },
  btnConfirmar: {
    padding:      '9px 20px',
    background:   '#c2410c',
    color:        '#fff',
    border:       'none',
    borderRadius: 'var(--radius-sm, 6px)',
    fontSize:     '0.88rem',
    fontWeight:   '700',
    cursor:       'pointer',
    transition:   'opacity 0.15s',
  },
  btnDeshabilitado: {
    opacity:  0.5,
    cursor:   'not-allowed',
  },
};

// ── Componente ────────────────────────────────────────────────────────────────

export default function ModalReaperturaActualizacion({ visible, formularioId, tipoPersona, onReabierto, onCancelar }) {
  const [especificaciones, setEspecificaciones]     = useState('');
  const [camposSeleccionados, setCamposSeleccionados] = useState(new Set());
  const [enviando, setEnviando]                     = useState(false);
  const [error, setError]                           = useState(null);
  const [mostrarConfirmacion, setMostrarConfirmacion] = useState(false);

  function resetearEstado() {
    setEspecificaciones('');
    setCamposSeleccionados(new Set());
    setError(null);
  }

  function limpiarYCerrar() {
    resetearEstado();
    onCancelar();
  }

  function validarEspecificaciones() {
    const longitudTexto = especificaciones.trim().length;
    if (longitudTexto < LONGITUD_MINIMA_ESPECIFICACIONES) {
      return `Mínimo ${LONGITUD_MINIMA_ESPECIFICACIONES} caracteres (actual: ${longitudTexto}).`;
    }
    return null;
  }

  function handleValidarYMostrarConfirmacion() {
    const errorValidacion = validarEspecificaciones();
    if (errorValidacion) {
      setError(errorValidacion);
      return;
    }
    setMostrarConfirmacion(true);
  }

  async function handleConfirmar() {
    setEnviando(true);
    setError(null);

    try {
      const payload = {
        justificacion: especificaciones.trim(),
        campos_identificados: [...camposSeleccionados],
      };
      
      const resultado = await api.reabrirActualizacion(formularioId, payload);
      setMostrarConfirmacion(false);
      resetearEstado();
      onReabierto(resultado); // Se envía el resultado al padre (DetalleExpediente)
    } catch (err) {
      setError(err.message || 'Error al procesar la reapertura. Intente nuevamente.');
      setMostrarConfirmacion(false);
    } finally {
      setEnviando(false);
    }
  }

  if (!visible) return null;

  const longitudActual   = especificaciones.trim().length;
  const especificacionesValidas = longitudActual >= LONGITUD_MINIMA_ESPECIFICACIONES;
  const textoBoton       = enviando ? 'Reabriendo...' : 'Reabrir actualización';

  return (
    <div style={s.fondo} role="dialog" aria-modal="true" aria-labelledby="titulo-modal-reapertura">
      <div style={s.modal}>

        {/* Encabezado */}
        <div style={s.encabezado}>
          <h2 style={s.titulo} id="titulo-modal-reapertura">
            Reabrir actualización
          </h2>
          <p style={s.descripcion}>
            La carpeta volverá a estado En corrección para continuar el ciclo periódico. 
            Los documentos y reportes finales existentes se conservarán. Se notificará al destinatario.
          </p>
        </div>

        {/* Cuerpo */}
        <div style={s.cuerpo}>

          <FormularioEspecificacionesCorreccion
            especificaciones={especificaciones}
            setEspecificaciones={setEspecificaciones}
            camposSeleccionados={camposSeleccionados}
            setCamposSeleccionados={setCamposSeleccionados}
            tipoPersona={tipoPersona}
            deshabilitado={enviando}
            introduccionVistaPrevia="Se ha reabierto la actualización de su expediente. Para continuar, por favor proporcione/modifique la siguiente información:"
          />

          {/* Banner de error */}
          {error && <div style={s.bannerError}>{error}</div>}

        </div>

        {/* Pie con acciones */}
        <div style={s.pie}>
          <button
            style={s.btnCancelar}
            onClick={limpiarYCerrar}
            disabled={enviando}
            type="button"
          >
            Cancelar
          </button>
          <button
            style={{
              ...s.btnConfirmar,
              ...(!especificacionesValidas || enviando ? s.btnDeshabilitado : {}),
            }}
            onClick={handleValidarYMostrarConfirmacion}
            disabled={!especificacionesValidas || enviando}
            type="button"
          >
            {textoBoton}
          </button>
        </div>

        <ModalConfirmacion
          visible={mostrarConfirmacion}
          titulo="¿Confirmar reapertura?"
          mensaje="El expediente será reabierto para actualización y se notificará al remitente. ¿Desea continuar?"
          textoConfirmar="Sí, reabrir"
          colorConfirmar="#c2410c"
          onConfirmar={handleConfirmar}
          onCancelar={() => setMostrarConfirmacion(false)}
          ocupado={enviando}
        />
      </div>
    </div>
  );
}
