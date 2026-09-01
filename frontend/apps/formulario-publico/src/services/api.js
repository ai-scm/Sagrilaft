import { requestJson, configurarTokenPortal } from '@shared/services/apiClient';

export { configurarTokenPortal };

export const api = {
  // Formularios
  async obtenerFechaServidor() {
    return requestJson('/formularios/fecha-servidor');
  },

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

  async enviarFormulario(id, credenciales = null, alertasIgnoradas = []) {
    const payload = {
      alertas_ignoradas: alertasIgnoradas,
    };
    if (credenciales) {
      payload.credenciales = credenciales;
    }
    const opciones = {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    };
    
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

  // Compatibilidad historica: el flujo principal actual recibe el correo desde
  // la creacion del acceso manual en el portal interno.
  async actualizarCorreoPorToken(token, correo) {
    try {
      return await requestJson(`/accesos-manuales/token/${token}/correo`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ correo_destinatario: correo }),
      });
    } catch (err) {
      if (err.status === 404) { err.code = 'TOKEN_INVALIDO';  throw err; }
      if (err.status === 410) { err.code = 'ACCESO_EXPIRADO'; throw err; }
      throw err;
    }
  },

  /**
   * Compatibilidad historica para accesos anteriores al correo obligatorio.
   * Endpoint liviano: solo devuelve { correo_registrado: bool }.
   * No carga el snapshot del formulario.
   */
  async verificarEstadoCorreo(token) {
    try {
      return await requestJson(`/accesos-manuales/token/${token}/estado-correo`);
    } catch (err) {
      if (err.status === 404) { err.code = 'TOKEN_INVALIDO';  throw err; }
      if (err.status === 410) { err.code = 'ACCESO_EXPIRADO'; throw err; }
      throw err;
    }
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
