/**
 * FormularioSagrilaft — Orquestador del formulario multipágina SAGRILAFT.
 *
 * SRP : solo compone pasos y conecta el hook con los componentes.
 * DIP : depende de abstracciones (useFormulario, Paso*, Navegacion…),
 *       no de lógica concreta.
 */

import HelpPanel from './HelpPanel';
import ProgressBar from './ProgressBar';
import ModalRecuperacionSesion from './ModalRecuperacionSesion';
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
import PasoClasificacionContactoBancario from './pasos/PasoClasificacionContactoBancario';
import PasoDeclaraciones from './pasos/PasoDeclaraciones';

export default function FormularioSagrilaft() {
  const {
    step, formData, errors, helpField, setHelpField,
    recuperacion,
    codigoPeticion, documentos, saving, uploadingDoc,
    juntaDirectiva, accionistas, beneficiarios, submitted, lastSaved,
    referenciasComerciales, handleReferenciaChange, addReferencia,
    referenciasBancarias, handleReferenciaBancariaChange, addReferenciaBancaria,
    infoBancariaPagos, handleInfoBancariaPagosChange, addInfoBancariaPagos,
    handleChange, handleFileChange, handleRemoveFile, handleSaveDraft,
    handleNext, handlePrev, handleStepClick, handleSubmit,
    handleJuntaChange, handleJuntaTipoIdChange, addJuntaMember,
    handleAccionistaChange, handleAccionistaTipoIdChange, addAccionista,
    handleBeneficiarioChange, handleBeneficiarioTipoIdChange, addBeneficiario,
    alertasRazonSocial,
    alertasNit,
    alertasNombreRepresentante,
    alertasNumeroDocRepresentante,
    alertasDireccion,
    hayAlertasActivas,
  } = useFormulario();

  if (submitted) {
    return <SubmittedView codigoPeticion={codigoPeticion} />;
  }

  // Props compartidos por todos los pasos de formulario
  const pasoProps = { formData, onChange: handleChange, onOpenHelp: setHelpField, errors };

  return (
    <div className="app-container">
      <ModalRecuperacionSesion
        visible={recuperacion.visible}
        error={recuperacion.error}
        cargando={recuperacion.cargando}
        fechaBorrador={recuperacion.fechaBorrador}
        onRecuperar={recuperacion.recuperarSesion}
        onDescartar={recuperacion.descartar}
      />

      <header className="app-header">
        <h1>FORMULARIO DE VINCULACIÓN O ACTUALIZACIÓN DE CONTRAPARTE</h1>
        <p className="subtitle">SAGRILAFT - Sistema de Autocontrol de Riesgo de LA/FT</p>
        {!recuperacion.visible && (
          <button
            type="button"
            onClick={recuperacion.abrirModal}
            style={{
              marginTop: '8px',
              background: 'transparent',
              border: '1px solid rgba(255,255,255,0.35)',
              color: 'rgba(255,255,255,0.85)',
              borderRadius: 'var(--radius-sm)',
              padding: '4px 14px',
              fontSize: '0.78rem',
              cursor: 'pointer',
            }}
          >
            ¿Tiene un formulario previo? Recuperar sesión
          </button>
        )}
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
            alertasRazonSocial={alertasRazonSocial}
            alertasNit={alertasNit}
            alertasNombreRepresentante={alertasNombreRepresentante}
            alertasNumeroDocRepresentante={alertasNumeroDocRepresentante}
            alertasDireccion={alertasDireccion}
          />
        )}

        {step === 2 && <PasoInfoBasica {...pasoProps} alertasRazonSocial={alertasRazonSocial} alertasNit={alertasNit} alertasDireccion={alertasDireccion} />}

        {step === 3 && <PasoRepresentante {...pasoProps} alertasNombreRepresentante={alertasNombreRepresentante} alertasNumeroDocRepresentante={alertasNumeroDocRepresentante} />}

        {step === 4 && (
          <PasoJuntaAccionistas
            {...pasoProps}
            juntaDirectiva={juntaDirectiva}
            onJuntaChange={handleJuntaChange}
            onJuntaTipoIdChange={handleJuntaTipoIdChange}
            onAddJuntaMember={addJuntaMember}
            accionistas={accionistas}
            onAccionistaChange={handleAccionistaChange}
            onAccionistaTipoIdChange={handleAccionistaTipoIdChange}
            onAddAccionista={addAccionista}
            beneficiarios={beneficiarios}
            onBeneficiarioChange={handleBeneficiarioChange}
            onBeneficiarioTipoIdChange={handleBeneficiarioTipoIdChange}
            onAddBeneficiario={addBeneficiario}
          />
        )}

        {step === 5 && <PasoFinanciero {...pasoProps} />}

        {step === 6 && (
          <PasoContactosBancaria
            {...pasoProps}
            referenciasComerciales={referenciasComerciales}
            onReferenciaChange={handleReferenciaChange}
            onAddReferencia={addReferencia}
            referenciasBancarias={referenciasBancarias}
            onReferenciaBancariaChange={handleReferenciaBancariaChange}
            onAddReferenciaBancaria={addReferenciaBancaria}
          />
        )}

        {step === 7 && (
          <PasoClasificacionContactoBancario
            {...pasoProps}
            infoBancariaPagos={infoBancariaPagos}
            onInfoBancariaPagosChange={handleInfoBancariaPagosChange}
            onAddInfoBancariaPagos={addInfoBancariaPagos}
          />
        )}

        {step === 8 && <PasoDeclaraciones {...pasoProps} />}

        <NavegacionFormulario
          step={step}
          totalSteps={TOTAL_STEPS}
          saving={saving}
          lastSaved={lastSaved}
          onPrev={handlePrev}
          onNext={handleNext}
          onSaveDraft={handleSaveDraft}
          onSubmit={handleSubmit}
          bloqueadoPorAnalisis={Object.values(uploadingDoc).some(Boolean)}
          bloqueadoPorAlertas={hayAlertasActivas}
        />
      </main>

      {helpField && (
        <HelpPanel fieldKey={helpField} onClose={() => setHelpField(null)} />
      )}
    </div>
  );
}
