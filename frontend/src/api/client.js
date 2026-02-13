const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

function headers(token, hasJson = true) {
  const h = {}
  if (hasJson) h['Content-Type'] = 'application/json'
  if (token) h.Authorization = `Bearer ${token}`
  return h
}

export async function apiRequest(path, { method = 'GET', body, token } = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    method,
    headers: headers(token, body !== undefined),
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })

  if (!response.ok) {
    let message = `Request failed (${response.status})`
    try {
      const data = await response.json()
      if (data.detail) message = data.detail
    } catch {
      // ignore json parsing failures
    }
    throw new Error(message)
  }

  if (response.status === 204) return null
  return response.json()
}
