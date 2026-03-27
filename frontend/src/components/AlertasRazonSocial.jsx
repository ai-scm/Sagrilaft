/**
 * AlertasRazonSocial — Panel de alertas de inconsistencia de nombre/razón social.
 *
 * Renderiza una tarjeta de advertencia por cada documento cuya razón social
 * no coincide con el valor del formulario, mostrando:
 *   - Nombre del documento y sección de referencia.
 *   - Valor encontrado en el formulario vs. el encontrado en el documento.
 *   - Botón para descartar la alerta individualmente.
 *
 * SRP : única responsabilidad — mostrar alertas de inconsistencia de nombre.
 * DIP : recibe datos por props; no accede a ningún hook ni estado global.
 */

/**
 * @param {{
 *   alertas:     import('../hooks/useAlertasRazonSocial').AlertaInconsistencia[],
 *   onDescartar: (tipoDoc: string) => void,
 * }} props
 */
export default function AlertasRazonSocial({ alertas, onDescartar }) {
  if (!alertas || alertas.length === 0) return null;

  return (
    <div className="alertas-razon-social" role="alert" aria-live="polite">
      {alertas.map((alerta) => (
        <div key={alerta.tipoDoc} className="alerta-inconsistencia">

          <div className="alerta-header">
            <span className="alerta-icono" aria-hidden="true">⚠️</span>
            <span className="alerta-titulo">
              Inconsistencia detectada —{' '}
              <strong>{alerta.nombreDocumento}</strong>
            </span>
            <button
              className="alerta-btn-descartar"
              aria-label={`Descartar alerta de ${alerta.nombreDocumento}`}
              onClick={() => onDescartar(alerta.tipoDoc)}
            >
              ✕
            </button>
          </div>

          <p className="alerta-descripcion">
            El nombre o razón social encontrado en el documento no coincide con
            el registrado en el formulario.
          </p>

          <div className="alerta-valores">
            <div className="alerta-valor-fila">
              <span className="alerta-etiqueta">Formulario:</span>
              <span className="alerta-valor alerta-valor--formulario">
                {alerta.valorFormulario}
              </span>
            </div>
            <div className="alerta-valor-fila">
              <span className="alerta-etiqueta">Documento:</span>
              <span className="alerta-valor alerta-valor--documento">
                {alerta.valorDocumento}
              </span>
            </div>
          </div>

          <p className="alerta-referencia">
            Ubicación en el documento:{' '}
            <em>{alerta.seccionReferencia}</em>
          </p>

        </div>
      ))}
    </div>
  );
}
