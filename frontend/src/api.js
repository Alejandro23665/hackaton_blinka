// Desarrollo: la API corre aparte en :8000. Producción: FastAPI sirve el frontend, misma URL.
export const BASE_URL = import.meta.env.VITE_API_URL || (import.meta.env.PROD ? window.location.origin : 'http://localhost:8000')

function errorMessage(body, status) {
  const detail = body?.detail
  if (typeof detail === 'string') return detail
  // Errores de validación de FastAPI: [{loc, msg}, ...]
  if (Array.isArray(detail)) {
    return detail.map((e) => `${e.loc?.slice(1).join('.') || 'body'}: ${e.msg}`).join(' · ')
  }
  return `Error ${status}`
}

async function request(path, { method = 'GET', body, params } = {}) {
  const url = new URL(path, BASE_URL)
  Object.entries(params ?? {}).forEach(([k, v]) => v != null && v !== '' && url.searchParams.set(k, v))

  const isForm = body instanceof FormData
  const response = await fetch(url, {
    method,
    headers: body && !isForm ? { 'Content-Type': 'application/json' } : undefined,
    body: body ? (isForm ? body : JSON.stringify(body)) : undefined,
  })
  const data = await response.json().catch(() => null)
  if (!response.ok) throw new Error(errorMessage(data, response.status))
  return data
}

const fileUrl = (path) => new URL(path, BASE_URL).toString()

export const api = {
  health: () => request('/health'),
  submissions: {
    list: () => request('/submissions'),
    get: (id) => request(`/submissions/${id}`),
    upload: (files) => {
      const form = new FormData()
      files.forEach((file) => form.append('files', file))
      return request('/submissions', { method: 'POST', body: form })
    },
    process: (id) => request(`/submissions/${id}/process`, { method: 'POST' }),
  },
  documents: {
    list: (params) => request('/documents', { params }),
    stats: () => request('/documents/stats'),
    get: (id) => request(`/documents/${id}`),
    reprocess: (id) => request(`/documents/${id}/reprocess`, { method: 'POST' }),
  },
  fileUrl: (id) => fileUrl(`/files/${id}`),
  pageImageUrl: (id) => fileUrl(`/pages/${id}/image`),
  cropUrl: (id) => fileUrl(`/regions/${id}/crop`),
}
