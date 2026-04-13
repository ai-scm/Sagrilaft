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

  // Recuperación de sesión
  async recuperarSesion(correo, numeroIdentificacion) {
    const res = await fetch(`${API_BASE}/formularios/sesion/recuperar`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ correo, numero_identificacion: numeroIdentificacion }),
    });
    // 404 = ningún formulario con esas credenciales → resultado esperado, no un error
    if (res.status === 404) return null;
    // 409 = formulario existe pero ya fue enviado → error de dominio conocido
    if (res.status === 409) {
      const err = new Error('El formulario asociado a esas credenciales ya fue enviado.');
      err.code = 'FORMULARIO_YA_ENVIADO';
      throw err;
    }
    // Cualquier otro error (400, 500, red) se propaga como excepción genérica
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
