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

/** Extract a user-friendly error message from an Axios error. */
export function getErrorMessage(err: unknown): string {
  if (axios.isAxiosError(err)) {
    const data = err.response?.data as { detail?: string } | undefined
    return data?.detail ?? err.message ?? 'An unexpected error occurred.'
  }
  if (err instanceof Error) return err.message
  return 'An unexpected error occurred.'
}
