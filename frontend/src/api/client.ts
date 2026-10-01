/**
 * Axios HTTP client — configured with base URL, auth headers, and
 * automatic 401 handling.
 */

import axios, { type AxiosError } from 'axios'
import { useAuthStore } from '@/stores/authStore'

export const apiClient = axios.create({
  // Use relative URL so requests go through the Vite dev proxy (/api → backend).
  // This avoids CORS entirely — the browser only talks to localhost:3000.
  baseURL: '',
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30_000,
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

/** Extract a user-friendly error message from an Axios error. */
export function getErrorMessage(err: unknown): string {
  if (axios.isAxiosError(err)) {
    const data = err.response?.data as { detail?: string } | undefined
    return data?.detail ?? err.message ?? 'An unexpected error occurred.'
  }
  if (err instanceof Error) return err.message
  return 'An unexpected error occurred.'
}
