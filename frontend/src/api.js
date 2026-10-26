// Desarrollo: la API corre aparte en :8000. Producción: FastAPI sirve el frontend, misma URL.
export const BASE_URL = import.meta.env.VITE_API_URL || (import.meta.env.PROD ? window.location.origin : 'http://localhost:8000')

/* ---------- Sesión: el token se guarda en este navegador ---------- */

const TOKEN_KEY = 'sesion'
// Se avisa a la app cuando la sesión venció o no es válida (la API respondió 401)
export const SESSION_EXPIRED = 'sesion-expirada'

export function getToken() {
  try {
    return localStorage.getItem(TOKEN_KEY)
  } catch {
    return null
  }
}

export function setToken(token) {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token)
    else localStorage.removeItem(TOKEN_KEY)
  } catch {
    // Sin almacenamiento (modo privado): la sesión dura mientras la página esté abierta
  }
  memoryToken = token
}

let memoryToken = getToken()

function errorMessage(body, status) {
  const detail = body?.detail
  if (typeof detail === 'string') return detail
  // Errores de validación de FastAPI: [{loc, msg}, ...]
  if (Array.isArray(detail)) {
    return detail.map((e) => `${e.loc?.slice(1).join('.') || 'body'}: ${e.msg}`).join(' · ')
  }
  return `Error ${status}`
}

async function send(path, { method = 'GET', body, params } = {}) {
  const url = new URL(path, BASE_URL)
  Object.entries(params ?? {}).forEach(([k, v]) => v != null && v !== '' && url.searchParams.set(k, v))

  const isForm = body instanceof FormData
  const headers = {}
  if (body && !isForm) headers['Content-Type'] = 'application/json'
  if (memoryToken) headers.Authorization = `Bearer ${memoryToken}`
  const response = await fetch(url, {
    method,
    headers,
    body: body ? (isForm ? body : JSON.stringify(body)) : undefined,
  })
  if (response.status === 401 && memoryToken) {
    setToken(null)
    window.dispatchEvent(new Event(SESSION_EXPIRED))
  }
  return response
}

async function request(path, options) {
  const response = await send(path, options)
  const data = await response.json().catch(() => null)
  if (!response.ok) throw new Error(errorMessage(data, response.status))
  return data
}

export const api = {
  health: () => request('/health'),
  auth: {
    login: (email, contrasena) => request('/auth/login', { method: 'POST', body: { email, contrasena } }),
    me: () => request('/auth/yo'),
  },
  jobs: {
    list: () => request('/trabajos'),
    create: (files) => {
      const form = new FormData()
      files.forEach((file) => form.append('files', file))
      return request('/trabajos', { method: 'POST', body: form })
    },
  },
  metrics: (dias) => request('/metricas', { params: { dias } }),
  documents: {
    list: (params) => request('/documentos', { params }),
    summary: () => request('/documentos/resumen'),
    day: (fecha) => request('/documentos/dia', { params: { fecha } }),
    get: (id) => request(`/documentos/${id}`),
    correct: (id, data) => request(`/documentos/${id}/correccion`, { method: 'PUT', body: data }),
    /** El archivo original pide sesión: se descarga con el token y se muestra como blob. */
    image: async (id) => {
      const response = await send(`/documentos/${id}/imagen`)
      if (!response.ok) throw new Error(`No se pudo cargar el archivo (error ${response.status})`)
      return response.blob()
    },
  },
}
