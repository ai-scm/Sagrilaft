import { useEffect, useState } from 'react';
import { DISCLAIMER_RADICACION } from '../hooks/radicacion';

/**
 * Disclaimer obligatorio previo a la radicación del formulario.
 *
 * Se muestra como modal para que aparezca "de la nada" al llegar al Paso 8
 * y no permanezca incrustado dentro del contenido del formulario.
 */
export default function DisclaimerRadicacion({
  visible,
  aceptado,
  mensajeError,
  onCambiarAceptacion,
}) {
  const [mostrado, setMostrado] = useState(false);

  useEffect(() => {
    if (visible) {
      setMostrado(true);
      return;
    }

    setMostrado(false);
  }, [visible]);

  if (!mostrado) return null;

  return (
    <div
      className={`disclaimer-radicacion__overlay ${visible ? 'disclaimer-radicacion__overlay--visible' : ''}`}
      role="dialog"
      aria-modal="true"
      aria-labelledby="disclaimer-radicacion-titulo"
    >
      <div className="disclaimer-radicacion">
        <div className="disclaimer-radicacion__cabecera">
          <span className="disclaimer-radicacion__icono" aria-hidden="true">
            {DISCLAIMER_RADICACION.badge}
          </span>
          <h3 id="disclaimer-radicacion-titulo" className="disclaimer-radicacion__titulo">
            {DISCLAIMER_RADICACION.titulo}
          </h3>
        </div>

        <p className="disclaimer-radicacion__resumen">
          {DISCLAIMER_RADICACION.resumen}
        </p>

        <ul className="disclaimer-radicacion__lista">
          {DISCLAIMER_RADICACION.puntos.map((punto) => (
            <li key={punto} className="disclaimer-radicacion__item">
              {punto}
            </li>
          ))}
        </ul>

        <div className="disclaimer-radicacion__confirmacion">
          <label className="checkbox-field disclaimer-radicacion__checkbox">
            <input
              type="checkbox"
              checked={aceptado}
              onChange={(event) => onCambiarAceptacion(event.target.checked)}
            />
            <span>
              {DISCLAIMER_RADICACION.confirmacion}
              <strong style={{ color: 'var(--error)' }}> *</strong>
            </span>
          </label>
        </div>

        {mensajeError && <div className="field-error">{mensajeError}</div>}
      </div>
    </div>
  );
}
