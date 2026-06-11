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

export default function ProgressBar({ currentStep, totalSteps, onStepClick }) {
  const { activa, camposIdentificados } = useCorreccion();
  const pasosConCorrecciones = activa ? _pasosConCorrección(camposIdentificados) : new Set();

  const percentage = ((currentStep) / totalSteps) * 100;

  return (
    <div className="progress-container">
      <div className="progress-header">
        <span className="progress-title">Progreso del formulario</span>
        <span className="progress-step-info">Paso {currentStep} de {totalSteps}</span>
      </div>

      <div className="progress-bar-track">
        <div
          className="progress-bar-fill"
          style={{ width: `${percentage}%` }}
        />
      </div>

      <div className="progress-steps">
        {STEP_LABELS.map((label, index) => {
          const stepNum = index + 1;
          const isActive    = stepNum === currentStep;
          const isCompleted = stepNum < currentStep;
          const tieneCorrecciones = pasosConCorrecciones.has(stepNum);

          return (
            <div
              key={index}
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
