/**
 * AlertasNit — Panel de bloqueo por inconsistencia de NIT.
 *
 * Renderiza una tarjeta de error por cada documento cuyo NIT no coincide
 * con el número de identificación del formulario. El panel bloquea el avance:
 * no hay botón de descartar. El usuario debe corregir el campo en el formulario
 * o reemplazar el archivo adjunto.
 *
 * Solo se muestra cuando tipo_identificacion === 'NIT'; el hook useAlertasNit
 * ya filtra los demás tipos, por lo que si alertas está vacío el componente
 * no renderiza nada.
 *
 * SRP : única responsabilidad — mostrar alertas de inconsistencia de NIT.
 * DIP : recibe datos por props; no accede a ningún hook ni estado global.
 */

/**
 * @param {{
 *   alertas: import('../hooks/useAlertasNit').AlertaInconsistenciaNit[],
 * }} props
 */
export default function AlertasNit({ alertas }) {
  if (!alertas || alertas.length === 0) return null;

  return (
    <div className="alertas-razon-social" role="alert" aria-live="polite">

      <div className="alertas-razon-social__encabezado">
        <span aria-hidden="true">🚫</span>
        <strong>
          No puedes avanzar: hay {alertas.length === 1 ? 'una inconsistencia' : `${alertas.length} inconsistencias`} de NIT sin resolver
        </strong>
      </div>

      <p className="alertas-razon-social__instruccion">
        Para cada documento marcado, debes <strong>corregir el campo "Número de Identificación"</strong> en
        el formulario para que coincida con el documento, o bien <strong>reemplazar el archivo adjunto</strong> con
        uno que contenga el NIT correcto. El bloqueo se libera automáticamente al corregir.
      </p>

      {alertas.map((alerta) => (
        <div key={alerta.tipoDoc} className="alerta-inconsistencia">

          <div className="alerta-header">
            <span className="alerta-icono" aria-hidden="true">⚠️</span>
            <span className="alerta-titulo">
              <strong>{alerta.nombreDocumento}</strong>
            </span>
          </div>

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
            Ubicación en el documento: <em>{alerta.seccionReferencia}</em>
          </p>

        </div>
      ))}

    </div>
  );
}
