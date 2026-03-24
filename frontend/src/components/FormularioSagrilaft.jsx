/**
 * FormularioSagrilaft — Orquestador del formulario multipágina SAGRILAFT.
 *
 * SRP : solo compone pasos y conecta el hook con los componentes.
 * DIP : depende de abstracciones (useFormulario, Paso*, Navegacion…),
 *       no de lógica concreta.
 */

import HelpPanel from './HelpPanel';
import ProgressBar from './ProgressBar';
import { useFormulario } from '../hooks/useFormulario';
import { TOTAL_STEPS } from '../data/formularioConfig';

import SubmittedView from './SubmittedView';
import NavegacionFormulario from './NavegacionFormulario';
import PasoDocumentos from './pasos/PasoDocumentos';
import PasoInfoBasica from './pasos/PasoInfoBasica';
import PasoRepresentante from './pasos/PasoRepresentante';
import PasoJuntaAccionistas from './pasos/PasoJuntaAccionistas';
import PasoFinanciero from './pasos/PasoFinanciero';
import PasoContactosBancaria from './pasos/PasoContactosBancaria';
import PasoDeclaraciones from './pasos/PasoDeclaraciones';

export default function FormularioSagrilaft() {
  const {
    step, formData, errors, helpField, setHelpField,
    codigoPeticion, documentos, saving, uploadingDoc,
    juntaDirectiva, accionistas, submitted, lastSaved,
    handleChange, handleFileChange, handleRemoveFile, handleSaveDraft,
    handleNext, handlePrev, handleStepClick, handleSubmit,
    handleJuntaChange, addJuntaMember, handleAccionistaChange, addAccionista,
  } = useFormulario();

  if (submitted) {
    return <SubmittedView codigoPeticion={codigoPeticion} />;
  }

  // Props compartidos por todos los pasos de formulario
  const pasoProps = { formData, onChange: handleChange, onOpenHelp: setHelpField, errors };

  return (
    <div className="app-container">
      <header className="app-header">
        <h1>FORMULARIO DE VINCULACIÓN O ACTUALIZACIÓN DE CONTRAPARTE</h1>
        <p className="subtitle">SAGRILAFT - Sistema de Autocontrol de Riesgo de LA/FT</p>
        {codigoPeticion && <div className="codigo-peticion">Código: {codigoPeticion}</div>}
      </header>

      <main className="main-content">
        <ProgressBar currentStep={step} totalSteps={TOTAL_STEPS} onStepClick={handleStepClick} />

        {step === 1 && (
          <PasoDocumentos
            {...pasoProps}
            documentos={documentos}
            onFileChange={handleFileChange}
            onRemoveFile={handleRemoveFile}
            uploadingDoc={uploadingDoc}
          />
        )}

        {step === 2 && <PasoInfoBasica {...pasoProps} />}

        {step === 3 && <PasoRepresentante {...pasoProps} />}

        {step === 4 && (
          <PasoJuntaAccionistas
            {...pasoProps}
            juntaDirectiva={juntaDirectiva}
            onJuntaChange={handleJuntaChange}
            onAddJuntaMember={addJuntaMember}
            accionistas={accionistas}
            onAccionistaChange={handleAccionistaChange}
            onAddAccionista={addAccionista}
          />
        )}

        {step === 5 && <PasoFinanciero {...pasoProps} />}

        {step === 6 && <PasoContactosBancaria {...pasoProps} />}

        {step === 7 && <PasoDeclaraciones {...pasoProps} />}

        <NavegacionFormulario
          step={step}
          totalSteps={TOTAL_STEPS}
          saving={saving}
          lastSaved={lastSaved}
          onPrev={handlePrev}
          onNext={handleNext}
          onSaveDraft={handleSaveDraft}
          onSubmit={handleSubmit}
        />
      </main>

      {helpField && (
        <HelpPanel fieldKey={helpField} onClose={() => setHelpField(null)} />
      )}
    </div>
  );
}
