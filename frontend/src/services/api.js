const API_BASE = '/api';

export const api = {
  // Formularios
  async crearFormulario(data = {}) {
    const res = await fetch(`${API_BASE}/formularios/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  async obtenerFormulario(codigo) {
    const res = await fetch(`${API_BASE}/formularios/${codigo}`);
    if (!res.ok) throw new Error('Formulario no encontrado');
    return res.json();
  },

  async actualizarFormulario(id, data) {
    const res = await fetch(`${API_BASE}/formularios/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  async enviarFormulario(id) {
    const res = await fetch(`${API_BASE}/formularios/${id}/enviar`, {
      method: 'POST',
    });
    if (!res.ok) throw new Error(await res.text());
    const resultado = await res.json();
    if (!resultado.valido) {
      const detalle = resultado.errores?.map(e => e.mensaje).join('\n') ?? 'El formulario no pudo enviarse';
      throw new Error(detalle);
    }
    return resultado;
  },

  // Documentos
  async subirDocumento(formularioId, tipoDocumento, archivo) {
    const formData = new FormData();
    formData.append('tipo_documento', tipoDocumento);
    formData.append('archivo', archivo);

    const res = await fetch(`${API_BASE}/formularios/${formularioId}/documentos`, {
      method: 'POST',
      body: formData,
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  async eliminarDocumento(formularioId, docId) {
    const res = await fetch(`${API_BASE}/formularios/${formularioId}/documentos/${docId}`, {
      method: 'DELETE',
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  // Validación
  async validarFormulario(id) {
    const res = await fetch(`${API_BASE}/validar/${id}`, {
      method: 'POST',
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  // Listas de cautela
  async buscarListasCautela(nombre, numeroIdentificacion = null) {
    const res = await fetch(`${API_BASE}/listas-cautela/buscar`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ nombre, numero_identificacion: numeroIdentificacion }),
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  // Pre-llenado IA
  async prefillDocumento(formularioId, docId) {
    const res = await fetch(`${API_BASE}/formularios/${formularioId}/documentos/${docId}/prefill`, {
      method: 'POST',
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  async prefillAll(formularioId) {
    const res = await fetch(`${API_BASE}/formularios/${formularioId}/prefill-all`, {
      method: 'POST',
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },
};
