import { useState, useEffect } from 'react';
import { api } from '../services/api';

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

  const recargarExpediente = () => setRecargar(n => n + 1);

  return { expediente, cargando, error, recargarExpediente };
}
