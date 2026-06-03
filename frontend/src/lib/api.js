const API_BASE = import.meta.env.VITE_API_URL ?? "/api"

export async function api(path, options = {}) {
  const { body, headers, ...rest } = options
  const isFormData = typeof FormData !== "undefined" && body instanceof FormData
  const response = await fetch(`${API_BASE}${path}`, {
    ...rest,
    headers: isFormData
      ? {
          ...headers
        }
      : {
          "Content-Type": "application/json",
          ...headers
        },
    body: body ? (isFormData ? body : JSON.stringify(body)) : undefined
  })

  if (!response.ok) {
    let detail = response.statusText
    try {
      const payload = await response.json()
      detail = payload.detail ?? payload.message ?? detail
    } catch {
      detail = response.statusText
    }
    throw new Error(detail || "La solicitud falló")
  }

  if (response.status === 204) {
    return null
  }

  return response.json()
}
