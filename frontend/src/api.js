const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

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

  const response = await fetch(url, {
    method,
    headers: body ? { 'Content-Type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  })
  const data = await response.json().catch(() => null)
  if (!response.ok) throw new Error(errorMessage(data, response.status))
  return data
}

export const api = {
  vendors: {
    list: () => request('/vendors'),
    create: (data) => request('/vendors', { method: 'POST', body: data }),
    update: (id, data) => request(`/vendors/${id}`, { method: 'PATCH', body: data }),
  },
  policies: {
    list: () => request('/policies'),
    active: () => request('/policies/active'),
    budget: () => request('/policies/active/budget'),
    create: (data) => request('/policies', { method: 'POST', body: data }),
    activate: (id) => request(`/policies/${id}/activate`, { method: 'POST' }),
  },
  invoices: {
    list: (params) => request('/invoices', { params }),
    get: (id) => request(`/invoices/${id}`),
    create: (data) => request('/invoices', { method: 'POST', body: data }),
    evaluate: (id) => request(`/invoices/${id}/evaluate`, { method: 'POST' }),
    review: (id, data) => request(`/invoices/${id}/review`, { method: 'POST', body: data }),
  },
  decisions: {
    list: (params) => request('/decisions', { params }),
  },
}
