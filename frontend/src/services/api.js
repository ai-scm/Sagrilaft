const API_BASE = '/api';

let _tokenGetter = null;

export function configurarTokenPortal(getter) {
  _tokenGetter = getter;
}

async function leerDetalleError(res) {
  const contentType = res.headers.get('content-type') ?? '';

  const leerComoJson = async () => {
    const data = await res.json();
    if (data && typeof data === 'object') {
      return data.detail ?? JSON.stringify(data);
    }
    return String(data ?? '');
  };

  const leerComoTexto = async () => {
    const texto = await res.text();
    if (!texto) return '';
    try {
      const data = JSON.parse(texto);
      return data?.detail ?? texto;
    } catch {
      return texto;
    }
  };

  try {
    if (contentType.includes('application/json')) return await leerComoJson();
    const texto = await leerComoTexto();
    return texto || res.statusText || `HTTP ${res.status}`;
  } catch {
    return res.statusText || `HTTP ${res.status}`;
  }
}

async function requestJson(path, options = {}) {
  const token = _tokenGetter?.();
  if (token) {
    options = { ...options, headers: { 'Authorization': `Bearer ${token}`, ...options.headers } };
  }
  const res = await fetch(`${API_BASE}${path}`, options);
  if (!res.ok) {
    const err = new Error(await leerDetalleError(res));
    err.status = res.status;
    throw err;
  }
  if (res.status === 204) return null;
  return res.json();
}

export const api = {
  // Formularios
  async crearFormulario(data = {}) {
    return requestJson('/formularios/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
  },

  async obtenerFormulario(codigo) {
    try {
      return await requestJson(`/formularios/${codigo}`);
    } catch (err) {
      if (err.status === 404) throw new Error('Formulario no encontrado');
      throw err;
    }
  },

  async actualizarFormulario(id, data) {
    return requestJson(`/formularios/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
  },

  async enviarFormulario(id, credenciales = null) {
    const opciones = { method: 'POST' };
    if (credenciales) {
      opciones.headers = { 'Content-Type': 'application/json' };
      opciones.body = JSON.stringify(credenciales);
    }
    const resultado = await requestJson(`/formularios/${id}/enviar`, opciones);
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

    return requestJson(`/formularios/${formularioId}/documentos`, {
      method: 'POST',
      body: formData,
    });
  },

  async eliminarDocumento(formularioId, docId) {
    return requestJson(`/formularios/${formularioId}/documentos/${docId}`, {
      method: 'DELETE',
    });
  },

  // Validación
  async validarFormulario(id) {
    return requestJson(`/validar/${id}`, {
      method: 'POST',
    });
  },

  // Listas de cautela
  async buscarListasCautela(nombre, numeroIdentificacion = null) {
    return requestJson('/listas-cautela/buscar', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ nombre, numero_identificacion: numeroIdentificacion }),
    });
  },

  // Recuperación de sesión por acceso manual (código de petición + PIN)
  async recuperarSesionPorAcceso(codigoPeticion, pin) {
    try {
      return await requestJson('/formularios/sesion/recuperar-por-acceso', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ codigo_peticion: codigoPeticion, pin }),
      });
    } catch (err) {
      if (err.status === 401) { err.code = 'CREDENCIALES_INVALIDAS'; throw err; }
      if (err.status === 409) { err.code = 'FORMULARIO_YA_ENVIADO';  throw err; }
      if (err.status === 410) { err.code = 'ACCESO_EXPIRADO';        throw err; }
      throw err;
    }
  },

  // Acceso via token de diligenciamiento (enlace recibido por correo)
  async resolverTokenDiligenciamiento(token) {
    try {
      return await requestJson(`/accesos-manuales/token/${token}`);
    } catch (err) {
      if (err.status === 404) { err.code = 'TOKEN_INVALIDO';  throw err; }
      if (err.status === 410) { err.code = 'ACCESO_EXPIRADO'; throw err; }
      throw err;
    }
  },

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

  async obtenerExpediente(formularioId) {
    return requestJson(`/expedientes/${formularioId}`);
  },

  urlDescargaDocumento(formularioId, docId) {
    return `${API_BASE}/expedientes/${formularioId}/documentos/${docId}/descargar`;
  },

  async descargarDocumento(formularioId, docId, nombreArchivo) {
    const token = _tokenGetter?.();
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

  async rechazarExpediente(formularioId) {
    return requestJson(`/expedientes/${formularioId}/rechazar`, { method: 'POST' });
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
    const token = _tokenGetter?.();
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

  // Pre-llenado IA
  async prefillDocumento(formularioId, docId) {
    return requestJson(`/formularios/${formularioId}/documentos/${docId}/prefill`, {
      method: 'POST',
    });
  },

  async prefillAll(formularioId) {
    return requestJson(`/formularios/${formularioId}/prefill-all`, {
      method: 'POST',
    });
  },
};
