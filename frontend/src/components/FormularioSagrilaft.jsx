/**
 * FormularioSagrilaft — Orquestador del formulario multipágina SAGRILAFT.
 *
 * SRP : solo compone pasos y conecta el hook con los componentes.
 * DIP : depende de abstracciones (useFormulario, Paso*, Navegacion…),
 *       no de lógica concreta.
 */

import { useEffect, useRef } from 'react';
import HelpPanel from './HelpPanel';
import ProgressBar from './ProgressBar';
import ModalRecuperacionSesion from './ModalRecuperacionSesion';
import ModalConfirmacion from './ModalConfirmacion';
import { useFormulario } from '../hooks/useFormulario';
import { TOTAL_STEPS } from '../data/formularioConfig';
import { CorreccionProvider, useCorreccion } from '../context/CorreccionContext';

import SubmittedView from './SubmittedView';
import NavegacionFormulario from './NavegacionFormulario';
import DisclaimerCamposNoAplicables from './DisclaimerCamposNoAplicables';
import PasoDocumentos from './pasos/PasoDocumentos';
import PasoInfoBasica from './pasos/PasoInfoBasica';
import PasoRepresentante from './pasos/PasoRepresentante';
import PasoJuntaAccionistas from './pasos/PasoJuntaAccionistas';
import PasoFinanciero from './pasos/PasoFinanciero';
import PasoContactosBancaria from './pasos/PasoContactosBancaria';
import PasoClasificacionContactoBancario from './pasos/PasoClasificacionContactoBancario';
import PasoDeclaraciones from './pasos/PasoDeclaraciones';

// ── Componentes auxiliares que consumen el contexto ───────────────────────────

/**
 * Componente nulo: detecta el paso inicial de corrección y navega a él
 * en cuanto el formulario carga desde el servidor.
 *
 * Separado de FormularioSagrilaft para poder llamar useCorreccion() desde
 * dentro del CorreccionProvider sin necesidad de prop drilling.
 * useRef garantiza que la referencia a irAPasoCorreccion nunca quede stale.
 */
function AutoNavegacion({ onNavegar }) {
  const { pasoInicialCorreccion } = useCorreccion();
  const onNavegarRef = useRef(onNavegar);
  useEffect(() => { onNavegarRef.current = onNavegar; });

  useEffect(() => {
    if (pasoInicialCorreccion !== null) {
      onNavegarRef.current(pasoInicialCorreccion);
    }
  }, [pasoInicialCorreccion]);

  return null;
}

/**
 * Banner superior que refleja el estado de la corrección en tiempo real.
 *
 * Estados mutuamente excluyentes:
 *   - Pendiente  : al menos un campo marcado sigue sin corregir → naranja / ⚠
 *   - Completada : todos los campos marcados fueron subsanados  → verde  / ✓
 *
 * Nunca muestra ambos estados simultáneamente (ver condicionales de retorno).
 */
function BannerCorreccionPendiente({ onNavegar }) {
  const {
    activa,
    especificaciones,
    camposIdentificados,
    camposPendientes,
    pasoInicialCorreccion,
    todasCorreccionesCompletadas,
  } = useCorreccion();

  if (!activa) return null;

  // ── Corrección completada ─────────────────────────────────────────────────
  if (todasCorreccionesCompletadas) {
    return (
      <div className="banner-correccion-completada" role="status" aria-live="polite">
        <div className="banner-correccion-completada__icono" aria-hidden="true">✓</div>
        <div className="banner-correccion-contenido">
          <p className="banner-correccion-completada__titulo">Corrección completada</p>
          <p className="banner-correccion-completada__texto">
            Todos los campos han sido corregidos. Puede proceder con el envío del formulario.
          </p>
        </div>
      </div>
    );
  }

  // ── Corrección pendiente ──────────────────────────────────────────────────
  return (
    <div className="banner-correccion-pendiente" role="alert">
      <div className="banner-correccion-icono" aria-hidden="true">⚠</div>
      <div className="banner-correccion-contenido">
        <p className="banner-correccion-titulo">Formulario devuelto para corrección</p>
        <p className="banner-correccion-texto">{especificaciones}</p>
        {camposIdentificados.size > 0 && (
          <p className="banner-correccion-hint">
            {camposPendientes.size} {camposPendientes.size === 1 ? 'campo requiere' : 'campos requieren'} su atención.
            {pasoInicialCorreccion !== null && (
              <button
                type="button"
                className="banner-correccion-link"
                onClick={() => onNavegar(pasoInicialCorreccion)}
              >
                Ir al primer campo →
              </button>
            )}
          </p>
        )}
      </div>
    </div>
  );
}

// ── Componente principal ──────────────────────────────────────────────────────

export default function FormularioSagrilaft() {
  const {
    step, formData, errors, helpField, setHelpField,
    recuperacion,
    codigoPeticion, estadoFormulario, camposACorregir, formDataOriginal, tablasOriginales,
    documentos, saving, uploadingDoc, eliminandoDoc,
    estadoConfirmacion, confirmarEliminacion, cancelarEliminacion,
    juntaDirectiva, accionistas, beneficiarios, submitted, lastSaved,
    referenciasComerciales, handleReferenciaChange, addReferencia, eliminarReferencia,
    referenciasBancarias, handleReferenciaBancariaChange, addReferenciaBancaria, eliminarReferenciaBancaria,
    infoBancariaPagos, handleInfoBancariaPagosChange, addInfoBancariaPagos, eliminarInfoBancariaPagos,
    handleChange, handleMonedaExtranjeraChange, handleActividadChange, handleTiposTransaccionChange,
    handleFileChange, handleRemoveFile, handleSaveDraft,
    handleNext, handlePrev, handleStepClick, irAPasoCorreccion, handleSubmit,
    handleJuntaChange, handleJuntaTipoIdChange, addJuntaMember, eliminarJuntaMember,
    handleAccionistaChange, handleAccionistaTipoIdChange, addAccionista, eliminarAccionista,
    handleBeneficiarioChange, handleBeneficiarioTipoIdChange, addBeneficiario, eliminarBeneficiario,
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

  const pasoProps = { formData, onChange: handleChange, onOpenHelp: setHelpField, errors };
  const bloqueadoPorAnalisis =
    Object.values(uploadingDoc).some(Boolean) ||
    Object.values(eliminandoDoc).some(Boolean);

  return (
    <CorreccionProvider
      estadoFormulario={estadoFormulario}
      camposACorregirRaw={camposACorregir}
      valoresOriginales={formDataOriginal ?? {}}
      formDataActual={formData}
      tablasActuales={{ juntaDirectiva, accionistas, beneficiarios, referenciasComerciales, referenciasBancarias, infoBancariaPagos }}
      tablasOriginales={tablasOriginales}
    >
      <AutoNavegacion onNavegar={irAPasoCorreccion} />

      <div className="app-container">
        <ModalRecuperacionSesion
          visible={recuperacion.visible}
          error={recuperacion.error}
          cargando={recuperacion.cargando}
          fechaBorrador={recuperacion.fechaBorrador}
          codigoInicial={codigoPeticion || recuperacion.codigoPeticionBorrador}
          onRecuperar={recuperacion.recuperarSesion}
          onDescartar={recuperacion.descartar}
        />

        <ModalConfirmacion
          visible={estadoConfirmacion.visible}
          titulo="Eliminar documento"
          mensaje="¿Está seguro de eliminar este documento? Los campos del formulario que fueron pre-llenados a partir de este documento también serán limpiados."
          onConfirm={confirmarEliminacion}
          onCancel={cancelarEliminacion}
        />

        <header className="app-header">
          <h1>FORMULARIO DE VINCULACIÓN O ACTUALIZACIÓN DE CONTRAPARTE</h1>
          <p className="subtitle">SAGRILAFT - Sistema de Autocontrol de Riesgo de LA/FT</p>
          {!recuperacion.visible && (
            <button
              type="button"
              onClick={recuperacion.abrirModal}
              className="btn-recuperar-sesion"
            >
              ¿Tiene un formulario previo? Recuperar sesión
            </button>
          )}
        </header>

        <main className="main-content">
          <BannerCorreccionPendiente onNavegar={irAPasoCorreccion} />
          <DisclaimerCamposNoAplicables />

          <ProgressBar currentStep={step} totalSteps={TOTAL_STEPS} onStepClick={handleStepClick} />

          {step === 1 && (
            <PasoDocumentos
              {...pasoProps}
              documentos={documentos}
              onFileChange={handleFileChange}
              onRemoveFile={handleRemoveFile}
              uploadingDoc={uploadingDoc}
              eliminandoDoc={eliminandoDoc}
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
              onEliminarJuntaMember={eliminarJuntaMember}
              accionistas={accionistas}
              onAccionistaChange={handleAccionistaChange}
              onAccionistaTipoIdChange={handleAccionistaTipoIdChange}
              onAddAccionista={addAccionista}
              onEliminarAccionista={eliminarAccionista}
              beneficiarios={beneficiarios}
              onBeneficiarioChange={handleBeneficiarioChange}
              onBeneficiarioTipoIdChange={handleBeneficiarioTipoIdChange}
              onAddBeneficiario={addBeneficiario}
              onEliminarBeneficiario={eliminarBeneficiario}
            />
          )}

          {step === 5 && <PasoFinanciero {...pasoProps} />}

          {step === 6 && (
            <PasoContactosBancaria
              {...pasoProps}
              onMonedaChange={handleMonedaExtranjeraChange}
              onTiposChange={handleTiposTransaccionChange}
              referenciasComerciales={referenciasComerciales}
              onReferenciaChange={handleReferenciaChange}
              onAddReferencia={addReferencia}
              onEliminarReferencia={eliminarReferencia}
              referenciasBancarias={referenciasBancarias}
              onReferenciaBancariaChange={handleReferenciaBancariaChange}
              onAddReferenciaBancaria={addReferenciaBancaria}
              onEliminarReferenciaBancaria={eliminarReferenciaBancaria}
            />
          )}

          {step === 7 && (
            <PasoClasificacionContactoBancario
              {...pasoProps}
              handleActividadChange={handleActividadChange}
              infoBancariaPagos={infoBancariaPagos}
              onInfoBancariaPagosChange={handleInfoBancariaPagosChange}
              onAddInfoBancariaPagos={addInfoBancariaPagos}
              onEliminarInfoBancariaPagos={eliminarInfoBancariaPagos}
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
            bloqueadoPorAnalisis={bloqueadoPorAnalisis}
            bloqueadoPorAlertas={hayAlertasActivas}
          />
        </main>

        {helpField && (
          <HelpPanel fieldKey={helpField} onClose={() => setHelpField(null)} />
        )}
      </div>
    </CorreccionProvider>
  );
}
