import { API_BASE, getToken, leerDetalleError, requestJson, configurarTokenPortal, configurarManejadorAuthError } from '@shared/services/apiClient';

export { configurarTokenPortal, configurarManejadorAuthError };

export const api = {
  // Portal interno — accesos manuales
  async crearAccesoManual(datos) {
    return requestJson('/accesos-manuales/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(datos),
    });
  },

  async listarAccesosManuales() {
    return requestJson('/accesos-manuales/');
  },

  // Portal interno — expedientes (formularios enviados)
  async listarExpedientes(tipo = null, busqueda = null, opcionesFetch = null) {
    const params = new URLSearchParams();
    if (tipo)     params.append('tipo_contraparte', tipo);
    if (busqueda) params.append('busqueda', busqueda);
    const query = params.toString() ? `?${params.toString()}` : '';
    return requestJson(`/expedientes/${query}`, opcionesFetch);
  },

  async cargarFormularioManual(formularioId, archivoFile, justificacion) {
    const formData = new FormData();
    formData.append('archivo', archivoFile);
    formData.append('justificacion', justificacion);
    return requestJson(`/expedientes/${formularioId}/carga-manual`, {
      method: 'POST',
      body: formData,
    });
  },

  async cargarReporteFinal(formularioId, archivoFile, justificacion) {
    const formData = new FormData();
    formData.append('archivo', archivoFile);
    if (justificacion) {
      formData.append('justificacion', justificacion);
    }
    return requestJson(`/expedientes/${formularioId}/reporte-final`, {
      method: 'POST',
      body: formData,
    });
  },

  async obtenerExpediente(formularioId) {
    return requestJson(`/expedientes/${formularioId}`);
  },

  async compararVersionesFormulario(formularioId) {
    return requestJson(`/expedientes/${formularioId}/comparacion-versiones`);
  },

  async descargarReporteComparacion(formularioId) {
    const token = await getToken();
    const headers = token ? { Authorization: `Bearer ${token}` } : {};
    const res = await fetch(`${API_BASE}/expedientes/${formularioId}/comparacion-versiones/reporte-pdf`, { headers });
    if (!res.ok) throw new Error(await leerDetalleError(res));
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `comparacion_${formularioId.slice(0, 8)}.pdf`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  },

  urlDescargaDocumento(formularioId, docId) {
    return `${API_BASE}/expedientes/${formularioId}/documentos/${docId}/descargar`;
  },

  async descargarDocumento(formularioId, docId, nombreArchivo) {
    const token = await getToken();
    const headers = token ? { Authorization: `Bearer ${token}` } : {};
    const res = await fetch(`${API_BASE}/expedientes/${formularioId}/documentos/${docId}/descargar`, { headers });
    if (!res.ok) throw new Error(await leerDetalleError(res));
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = nombreArchivo;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  },

  async aprobarExpediente(formularioId) {
    return requestJson(`/expedientes/${formularioId}/aprobar`, { method: 'POST' });
  },

  async rechazarExpediente(formularioId, solicitud) {
    return requestJson(`/expedientes/${formularioId}/rechazar`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(solicitud),
    });
  },

  async devolverExpediente(formularioId, solicitud) {
    return requestJson(`/expedientes/${formularioId}/devolver`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(solicitud),
    });
  },

  async enviarAFirma(formularioId) {
    return requestJson(`/expedientes/${formularioId}/enviar-a-firma`, {
      method: 'POST',
    });
  },

  async verificarFirma(formularioId) {
    return requestJson(`/expedientes/${formularioId}/verificar-firma`, {
      method: 'POST',
    });
  },

  async cancelarFirma(formularioId) {
    return requestJson(`/expedientes/${formularioId}/cancelar-firma`, {
      method: 'POST',
    });
  },

  urlDocumentoFirmado(formularioId) {
    return `${API_BASE}/expedientes/${formularioId}/documento-firmado`;
  },

  async descargarDocumentoFirmado(formularioId) {
    const token = await getToken();
    const headers = token ? { Authorization: `Bearer ${token}` } : {};
    const res = await fetch(`${API_BASE}/expedientes/${formularioId}/documento-firmado`, { headers });
    if (!res.ok) throw new Error(await leerDetalleError(res));
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'formulario_firmado.pdf';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  },
};
