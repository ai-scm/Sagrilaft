/**
 * Barra de progreso del formulario multipágina.
 */

const STEP_LABELS = [
  "Documentos",
  "Clasificación",
  "Representante",
  "Junta / Accionistas",
  "Financiera",
  "Referencias",
  "Declaraciones"
];

export default function ProgressBar({ currentStep, totalSteps, onStepClick }) {
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
          const isActive = stepNum === currentStep;
          const isCompleted = stepNum < currentStep;

          return (
            <div
              key={index}
              className={`progress-step-dot ${isActive ? 'active' : ''} ${isCompleted ? 'completed' : ''}`}
              onClick={() => onStepClick && onStepClick(stepNum)}
            >
              <div className="dot" />
              <span className="step-label">{label}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
