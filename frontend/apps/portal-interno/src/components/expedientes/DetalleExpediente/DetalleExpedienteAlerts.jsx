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

    </>
  );
}
