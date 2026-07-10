/**
 * Barra de progreso del formulario multipágina.
 *
 * En modo EN_CORRECCION, los pasos que contienen campos marcados muestran
 * un punto naranja sobre su dot, indicando al usuario dónde debe actuar.
 */

import { PASO_POR_CAMPO } from '@shared/data/catalogoCorrecciones';
import { useCorreccion } from '../context/CorreccionContext';

const STEP_LABELS = [
  "Documentos",
  "Clasificación",
  "Representante",
  "Junta / Accionistas",
  "Financiera",
  "Referencias",
  "Contactos",
  "Declaraciones",
];

function _pasosConCorrección(camposIdentificados) {
  const pasos = new Set();
  for (const id of camposIdentificados) {
    const paso = PASO_POR_CAMPO[id];
    if (paso !== undefined) pasos.add(paso);
  }
  return pasos;
}

export default function ProgressBar({ currentStep, totalSteps, pasosVisibles, onStepClick }) {
  const { activa, camposIdentificados } = useCorreccion();
  const pasosConCorrecciones = activa ? _pasosConCorrección(camposIdentificados) : new Set();
  const pasos = pasosVisibles?.length ? pasosVisibles : Array.from({ length: totalSteps }, (_, i) => i + 1);
  const indiceActual = Math.max(pasos.indexOf(currentStep), 0);
  const totalVisible = pasos.length;
  const numeroPasoVisible = indiceActual + 1;

  const percentage = (numeroPasoVisible / totalVisible) * 100;

  return (
    <div className="progress-container">
      <div className="progress-header">
        <span className="progress-title">Progreso del formulario</span>
        <span className="progress-step-info">Paso {numeroPasoVisible} de {totalVisible}</span>
      </div>

      <div className="progress-bar-track">
        <div
          className="progress-bar-fill"
          style={{ width: `${percentage}%` }}
        />
      </div>

      <div className="progress-steps">
        {pasos.map((stepNum) => {
          const label = STEP_LABELS[stepNum - 1];
          const isActive    = stepNum === currentStep;
          const isCompleted = pasos.indexOf(stepNum) < indiceActual;
          const tieneCorrecciones = pasosConCorrecciones.has(stepNum);

          return (
            <div
              key={stepNum}
              className={[
                'progress-step-dot',
                isActive         ? 'active'             : '',
                isCompleted      ? 'completed'          : '',
                tieneCorrecciones ? 'tiene-correcciones' : '',
              ].filter(Boolean).join(' ')}
              onClick={() => onStepClick && onStepClick(stepNum)}
            >
              <div className="dot">
                {tieneCorrecciones && <span className="dot-correccion-badge" aria-hidden="true" />}
              </div>
              <span className="step-label">{label}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
