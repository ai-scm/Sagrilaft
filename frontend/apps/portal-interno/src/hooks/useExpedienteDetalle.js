import { useState, useEffect } from 'react';
import { api } from '../services/api';
import { ESTADO_FORM_PENDIENTE_FIRMA } from '@shared/utils/constantes';

// Mientras se espera la firma, el webhook de ZohoSign actualiza el backend de
// forma asíncrona sin avisar al frontend. Se consulta en segundo plano cada
// 10s para reflejar el cambio sin que el usuario tenga que recargar la página.
const INTERVALO_POLL_FIRMA_MS = 10000;

export function useExpedienteDetalle(formularioId) {
  const [expediente, setExpediente] = useState(null);
  const [cargando, setCargando]     = useState(true);
  const [error, setError]           = useState(null);
  const [recargar, setRecargar]     = useState(0);

  useEffect(() => {
    let activo = true;
    setCargando(true);
    setError(null);

    api.obtenerExpediente(formularioId)
      .then(datos => { if (activo) setExpediente(datos); })
      .catch(() => { if (activo) setError('No se pudo cargar el formulario. Intente nuevamente.'); })
      .finally(() => { if (activo) setCargando(false); });

    return () => { activo = false; };
  }, [formularioId, recargar]);

  useEffect(() => {
    if (expediente?.estado !== ESTADO_FORM_PENDIENTE_FIRMA) return undefined;

    let activo = true;
    const id = setInterval(() => {
      api.obtenerExpediente(formularioId)
        .then(datos => { if (activo) setExpediente(datos); })
        .catch(() => { /* se reintenta en el próximo ciclo; no se muestra error */ });
    }, INTERVALO_POLL_FIRMA_MS);

    return () => { activo = false; clearInterval(id); };
  }, [formularioId, expediente?.estado]);

  const recargarExpediente = () => setRecargar(n => n + 1);

  return { expediente, cargando, error, recargarExpediente };
}
