export function createApi(token: () => string, unauthorized: () => void) {
  return async function api<T>(path: string, method = 'GET', body?: unknown, key?: string): Promise<T> {
    const headers: Record<string, string> = {}
    if (token()) headers.Authorization = `Bearer ${token()}`
    if (key) headers['Idempotency-Key'] = key
    if (body && !(body instanceof FormData)) headers['Content-Type'] = 'application/json'
    const response = await fetch(`/api${path}`, {method, headers,
      body: body instanceof FormData ? body : body ? JSON.stringify(body) : undefined})
    const result = await response.json()
    if (!response.ok) {
      if (response.status === 401 && path !== '/auth/login') unauthorized()
      throw new Error(`${result.error?.message || '请求失败'}（${result.request_id || ''}）`)
    }
    return result.data as T
  }
}
export type Api = ReturnType<typeof createApi>
