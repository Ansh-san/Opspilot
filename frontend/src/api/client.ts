/**
 * Axios HTTP client — configured with base URL, auth headers, and
 * automatic 401 handling.
 */

import axios, { type AxiosError } from 'axios'
import { useAuthStore } from '@/stores/authStore'

export const apiClient = axios.create({
  // VITE_API_URL is the source of truth (e.g. the Render backend URL in production).
  // Falls back to the local backend for development.
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000',
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 60000, // 60s — accommodates Render free-tier cold starts
})

// ─── Request interceptor — attach Bearer token ────────────────────────────────
apiClient.interceptors.request.use((config) => {
  const token = useAuthStore.getState().accessToken
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// ─── Response interceptor — handle 401 globally ──────────────────────────────
apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const url = error.config?.url ?? ''
    const isLogoutCall = url.includes('/auth/logout')
    const isAlreadyLoggedOut = !useAuthStore.getState().isAuthenticated

    if (error.response?.status === 401 && !isLogoutCall && !isAlreadyLoggedOut) {
      // Token expired — clear local state and redirect to login
      useAuthStore.getState().logout()
    }
    return Promise.reject(error)
  }
)

/** Shape of a single FastAPI / Pydantic validation error (422). */
interface FastAPIValidationError {
  loc?: (string | number)[]
  msg?: string
  type?: string
}

/**
 * Extract a user-friendly error message from an Axios error.
 *
 * Always returns a plain string — never an object/array — so it is safe to
 * render directly in React. FastAPI returns `detail` in two shapes:
 *   - string:  {"detail": "Incorrect email or password."}         (HTTPException)
 *   - array:   {"detail": [{"loc": [...], "msg": "...", ...}]}    (422 validation)
 */
export function getErrorMessage(err: unknown, fallback = 'An unexpected error occurred.'): string {
  if (axios.isAxiosError(err)) {
    const detail = (err.response?.data as { detail?: unknown } | undefined)?.detail

    if (typeof detail === 'string' && detail.trim()) return detail

    if (Array.isArray(detail) && detail.length > 0) {
      const first = detail[0] as FastAPIValidationError
      if (first && typeof first.msg === 'string') {
        // Pydantic v2 prefixes custom validator messages with "Value error, "
        const msg = first.msg.replace(/^Value error,\s*/i, '')
        const field = Array.isArray(first.loc)
          ? first.loc.filter((p) => p !== 'body').join('.')
          : ''
        return field ? `${field}: ${msg}` : msg
      }
      return fallback
    }

    if (err.code === 'ECONNABORTED') return 'Request timed out. The server may be waking up — please try again.'
    if (!err.response) return 'Unable to reach the server. Please check your connection.'
    return err.message || fallback
  }
  if (err instanceof Error) return err.message
  return fallback
}
