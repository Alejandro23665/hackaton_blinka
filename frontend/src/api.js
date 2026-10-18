// Desarrollo: la API corre aparte en :8000. Producción: FastAPI sirve el frontend, misma URL.
const BASE_URL = import.meta.env.VITE_API_URL || (import.meta.env.PROD ? window.location.origin : 'http://localhost:8000')

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

export const api = {
  health: () => request('/health'),
  vendors: {
    list: () => request('/vendors'),
    create: (data) => request('/vendors', { method: 'POST', body: data }),
    update: (id, data) => request(`/vendors/${id}`, { method: 'PATCH', body: data }),
    remove: (id) => request(`/vendors/${id}`, { method: 'DELETE' }),
  },
  policies: {
    list: () => request('/policies'),
    active: () => request('/policies/active'),
    budget: () => request('/policies/active/budget'),
    create: (data) => request('/policies', { method: 'POST', body: data }),
    activate: (id) => request(`/policies/${id}/activate`, { method: 'POST' }),
    remove: (id) => request(`/policies/${id}`, { method: 'DELETE' }),
  },
  invoices: {
    list: (params) => request('/invoices', { params }),
    get: (id) => request(`/invoices/${id}`),
    create: (data) => request('/invoices', { method: 'POST', body: data }),
    evaluate: (id) => request(`/invoices/${id}/evaluate`, { method: 'POST' }),
    review: (id, data) => request(`/invoices/${id}/review`, { method: 'POST', body: data }),
    remove: (id) => request(`/invoices/${id}`, { method: 'DELETE' }),
  },
  exchangeRates: {
    list: () => request('/exchange-rates'),
    save: (currency, usdPerUnit) => request(`/exchange-rates/${currency}`, { method: 'PUT', body: { usd_per_unit: usdPerUnit } }),
    remove: (currency) => request(`/exchange-rates/${currency}`, { method: 'DELETE' }),
  },
  decisions: {
    list: (params) => request('/decisions', { params }),
    log: (params) => request('/decisions/log', { params }),
    exportUrl: (params) => {
      const url = new URL('/decisions/export.csv', BASE_URL)
      Object.entries(params ?? {}).forEach(([k, v]) => v && url.searchParams.set(k, v))
      return url.toString()
    },
  },
  documents: {
    list: (params) => request('/documents', { params }),
    upload: (file) => {
      const form = new FormData()
      form.append('file', file)
      return request('/documents', { method: 'POST', body: form })
    },
    uploadText: (text, source) => request('/documents/text', { method: 'POST', body: { text, source } }),
    fileUrl: (id) => new URL(`/documents/${id}/file`, BASE_URL).toString(),
  },
}
