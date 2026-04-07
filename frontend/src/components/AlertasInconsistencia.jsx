/**
 * AlertasInconsistencia — Panel de bloqueo por inconsistencia de campo entre
 * formulario y documentos adjuntos.
 *
 * Reemplaza los cinco componentes específicos anteriores:
 *   AlertasRazonSocial, AlertasNit, AlertasDireccion,
 *   AlertasNombreRepresentante, AlertasNumeroDocRepresentante.
 *
 * La estructura HTML, accesibilidad y comportamiento son idénticos en todos
 * los casos; solo varían el tipo de campo referenciado en el título y el
 * nombre del campo que el usuario debe corregir en el formulario.
 *
 * SRP : única responsabilidad — mostrar alertas de inconsistencia de un campo.
 * DIP : recibe datos y configuración por props; no accede a hooks ni estado global.
 * DRY : la lógica de renderizado vive en un único lugar en lugar de repetirse
 *       en cinco archivos.
 *
 * @param {{
 *   alertas:     import('../utils/calcularAlertasInconsistencia').AlertaInconsistencia[],
 *   tipoCampo:   string,
 *   nombreCampo: string,
 * }} props
 *
 * @param {string} tipoCampo   Describe qué hay sin resolver en el título del panel.
 *                             Ejemplos: "nombre sin resolver", "NIT sin resolver",
 *                             "dirección sin resolver".
 * @param {string} nombreCampo Nombre exacto del campo que el usuario debe corregir.
 *                             Ejemplos: "Nombre o Razón Social", "Número de Identificación",
 *                             "Dirección", "Nombres y Apellidos", "No. de Identificación".
 */
export default function AlertasInconsistencia({ alertas, tipoCampo, nombreCampo }) {
  if (!alertas || alertas.length === 0) return null;

  return (
    <div className="alertas-razon-social" role="alert" aria-live="polite">

      <div className="alertas-razon-social__encabezado">
        <span aria-hidden="true">🚫</span>
        <strong>
          No puedes avanzar: hay {alertas.length === 1 ? 'una inconsistencia' : `${alertas.length} inconsistencias`} de {tipoCampo}
        </strong>
      </div>

      <p className="alertas-razon-social__instruccion">
        Para cada documento marcado, debes <strong>corregir el campo "{nombreCampo}"</strong> en
        el formulario para que coincida con el documento, o bien <strong>reemplazar el archivo adjunto</strong> con
        uno que contenga el valor correcto. El bloqueo se libera automáticamente al corregir.
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
