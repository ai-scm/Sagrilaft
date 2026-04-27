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

  async enviarFormulario(id, credenciales = null) {
    const opciones = { method: 'POST' };
    if (credenciales) {
      opciones.headers = { 'Content-Type': 'application/json' };
      opciones.body = JSON.stringify(credenciales);
    }
    const res = await fetch(`${API_BASE}/formularios/${id}/enviar`, opciones);
    if (!res.ok) {
      const err = new Error(await res.text());
      err.status = res.status;
      throw err;
    }
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

  // Recuperación de sesión por acceso manual (código de petición + PIN)
  async recuperarSesionPorAcceso(codigoPeticion, pin) {
    const res = await fetch(`${API_BASE}/formularios/sesion/recuperar-por-acceso`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ codigo_peticion: codigoPeticion, pin }),
    });
    if (res.status === 401) {
      const err = new Error('Código de petición o PIN incorrecto.');
      err.code = 'CREDENCIALES_INVALIDAS';
      throw err;
    }
    if (res.status === 409) {
      const err = new Error('El formulario asociado a ese código ya fue enviado.');
      err.code = 'FORMULARIO_YA_ENVIADO';
      throw err;
    }
    if (res.status === 410) {
      const err = new Error('El acceso ha expirado. Solicite un nuevo enlace al área responsable.');
      err.code = 'ACCESO_EXPIRADO';
      throw err;
    }
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  // Acceso via token de diligenciamiento (enlace recibido por correo)
  async resolverTokenDiligenciamiento(token) {
    const res = await fetch(`${API_BASE}/accesos-manuales/token/${token}`);
    if (res.status === 404) {
      const err = new Error('El enlace de diligenciamiento no es válido o ya fue consumido.');
      err.code = 'TOKEN_INVALIDO';
      throw err;
    }
    if (res.status === 410) {
      const err = new Error('El acceso ha expirado. Solicite un nuevo enlace al área responsable.');
      err.code = 'ACCESO_EXPIRADO';
      throw err;
    }
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  // Portal interno — accesos manuales
  async crearAccesoManual(datos) {
    const res = await fetch(`${API_BASE}/accesos-manuales/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(datos),
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  async listarAccesosManuales() {
    const res = await fetch(`${API_BASE}/accesos-manuales/`);
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
