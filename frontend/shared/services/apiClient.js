export const API_BASE = '/api';

let _tokenGetter = null;

export function configurarTokenPortal(getter) {
  _tokenGetter = getter;
}

export async function getToken() {
  return _tokenGetter ? await _tokenGetter() : null;
}

export async function leerDetalleError(res) {
  const contentType = res.headers.get('content-type') ?? '';

  const leerComoJson = async () => {
    const data = await res.json();
    if (data && typeof data === 'object') {
      const detail = data.detail;
      // Pydantic 422: detail es un array de objetos [{loc, msg, type}, ...]
      if (Array.isArray(detail)) {
        return detail
          .map(e => {
            const campo = e.loc?.filter(l => l !== 'body').join(' → ') || '';
            const msg   = e.msg || JSON.stringify(e);
            return campo ? `${campo}: ${msg}` : msg;
          })
          .join('\n');
      }
      if (detail !== undefined && detail !== null) return String(detail);
      return JSON.stringify(data);
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

export async function requestJson(path, options = {}) {
  const token = await getToken();
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
