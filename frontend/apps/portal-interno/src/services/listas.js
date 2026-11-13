import { API_BASE, getToken, leerDetalleError, requestJson } from '@shared/services/apiClient';

export const listas = {
  disponibilidad: () => requestJson('/listas/disponibilidad'),
  historial: (id, antes) => requestJson(`/expedientes/${id}/consultas-listas${antes ? `?antes=${antes}` : ''}`),
  detalle: id => requestJson(`/consultas-listas/${id}`),
  crear: (id, datos, clave) => requestJson(`/expedientes/${id}/consultas-listas`, {
    method: 'POST', headers: { 'Content-Type': 'application/json', 'Idempotency-Key': clave }, body: JSON.stringify(datos),
  }),
  grupo: (id, clave) => requestJson(`/expedientes/${id}/consultas-listas/grupos`, {
    method: 'POST', headers: { 'Idempotency-Key': clave },
  }),
  revisar: (id, datos) => requestJson(`/consultas-listas/${id}/revisiones`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(datos),
  }),
  async evidencia(consulta, evidencia, tipo) {
    const token = await getToken();
    const respuesta = await fetch(`${API_BASE}/consultas-listas/${consulta}/evidencias/${evidencia}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!respuesta.ok) throw new Error(await leerDetalleError(respuesta));
    const direccion = URL.createObjectURL(await respuesta.blob());
    const enlace = document.createElement('a');
    enlace.href = direccion;
    enlace.download = tipo === 'PDF_PROVEEDOR' ? `proveedor_${consulta}.pdf` : `listas_${consulta}.pdf`;
    enlace.click();
    URL.revokeObjectURL(direccion);
  },
};
