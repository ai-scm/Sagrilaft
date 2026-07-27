import Alert from '@shared/components/ui/Alert';

export default function DetalleExpedienteAlerts({
  avisoReapertura,
  errorCertificado,
  resultadoSagrilaft,
}) {
  return (
    <>
      {avisoReapertura && (
        <Alert
          mensaje={avisoReapertura}
          style={{ marginBottom: '16px', background: '#fffbeb', borderColor: '#fbbf24', color: '#92400e' }}
        />
      )}

      {errorCertificado && (
        <Alert
          mensaje={errorCertificado}
          style={{ marginBottom: '16px', background: '#fef2f2', borderColor: '#f87171', color: '#b91c1c' }}
        />
      )}

      {resultadoSagrilaft && (
        <Alert
          mensaje={`SAGRILAFT: ${resultadoSagrilaft.estado || resultadoSagrilaft.error}. ${resultadoSagrilaft.riesgo ? `Riesgo: ${resultadoSagrilaft.riesgo}.` : ''} ${resultadoSagrilaft.detalles || ''}`}
          style={{
            marginBottom: '16px',
            background: resultadoSagrilaft.estado === 'APROBADO_SAGRILAFT' ? '#ecfdf5' : '#fef2f2',
            borderColor: resultadoSagrilaft.estado === 'APROBADO_SAGRILAFT' ? '#10b981' : '#ef4444',
            color: resultadoSagrilaft.estado === 'APROBADO_SAGRILAFT' ? '#065f46' : '#991b1b',
          }}
        />
      )}
    </>
  );
}
