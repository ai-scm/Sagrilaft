/**
 * Barra de navegación del formulario multipágina.
 * Controla: Anterior, Guardar Borrador, Siguiente / Radicar.
 *
 * La navegación se bloquea completamente cuando:
 * - `bloqueadoPorAnalisis`: hay documentos siendo procesados por IA.
 * - `bloqueadoPorAlertas`: hay alertas de inconsistencia activas sin resolver.
 */
export default function NavegacionFormulario({
  step, totalSteps, saving, lastSaved,
  onPrev, onNext, onSaveDraft, onSubmit,
  bloqueadoPorAnalisis = false,
  bloqueadoPorAlertas = false,
}) {
  const navegacionBloqueada = bloqueadoPorAnalisis || bloqueadoPorAlertas;
  const estiloBotonBloqueado = navegacionBloqueada
    ? { opacity: 0.5, cursor: 'not-allowed', pointerEvents: 'none' }
    : undefined;

  return (
    <div className="form-card">
      {lastSaved && (
        <div style={{ fontSize: '0.78rem', color: 'var(--gray-400)', textAlign: 'right', marginBottom: '8px' }}>
          Guardado automáticamente: {lastSaved.toLocaleTimeString('es-CO')}
        </div>
      )}
      <div className="form-actions">
        <div>
          {step > 1 && (
            <button
              type="button"
              className="btn btn-outline"
              onClick={onPrev}
              disabled={navegacionBloqueada}
              style={estiloBotonBloqueado}
            >
              ← Anterior
            </button>
          )}
        </div>
        <div className="form-actions-right">
          <button
            type="button"
            className="btn btn-secondary"
            onClick={onSaveDraft}
            disabled={saving}
          >
            {saving ? '⏳ Guardando...' : '💾 Guardar Borrador'}
          </button>

          {step < totalSteps ? (
            <button
              type="button"
              className="btn btn-primary"
              onClick={onNext}
              disabled={navegacionBloqueada}
              style={estiloBotonBloqueado}
            >
              Siguiente →
            </button>
          ) : (
            <button
              type="button"
              className="btn btn-success"
              onClick={onSubmit}
              disabled={saving}
            >
              {saving ? '⏳ Enviando...' : '✅ Radicar Formulario'}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
