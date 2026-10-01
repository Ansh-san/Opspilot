/**
 * Auth Zustand store — manages authentication state and token persistence.
 *
 * Tokens are stored in localStorage for simplicity. In a high-security
 * production setup, move access tokens to memory and refresh tokens to
 * HttpOnly cookies.
 */

import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { authApi } from '@/api/auth'
import { getErrorMessage } from '@/api/client'
import type { LoginRequest, RegisterRequest, User } from '@/types'

const TOKEN_KEY = 'opspilot_tokens'

interface AuthState {
  user: User | null
  accessToken: string | null
  refreshToken: string | null
  isAuthenticated: boolean
  isLoading: boolean
  error: string | null

  // Actions
  register: (data: RegisterRequest) => Promise<void>
  login: (data: LoginRequest) => Promise<void>
  logout: () => void
  loadUser: () => Promise<void>
  clearError: () => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      accessToken: null,
      refreshToken: null,
      isAuthenticated: false,
      isLoading: false,
      error: null,

      register: async (data) => {
        set({ isLoading: true, error: null })
        try {
          // Register creates the user + org — then auto-login
          await authApi.register(data)
          await get().login({ email: data.email, password: data.password })
        } catch (err) {
          set({ error: getErrorMessage(err), isLoading: false })
          throw err
        }
      },

      login: async (data) => {
        set({ isLoading: true, error: null })
        try {
          const { data: tokens } = await authApi.login(data)
          set({
            accessToken: tokens.access_token,
            refreshToken: tokens.refresh_token,
          })
          // Fetch user profile
          await get().loadUser()
          set({ isAuthenticated: true, isLoading: false })
        } catch (err) {
          set({ error: getErrorMessage(err), isLoading: false })
          throw err
        }
      },

      logout: () => {
        // Clear local state immediately — don't wait on the server
        set({
          user: null,
          accessToken: null,
          refreshToken: null,
          isAuthenticated: false,
          error: null,
        })
        // Fire-and-forget: tell the server to invalidate the refresh token
        authApi.logout().catch(() => { /* server error is fine */ })
      },

      loadUser: async () => {
        try {
          const { data: user } = await authApi.me()
          set({ user })
        } catch {
          get().logout()
        }
      },

      clearError: () => set({ error: null }),
    }),
    {
      name: TOKEN_KEY,
      partialize: (state) => ({
        accessToken: state.accessToken,
        refreshToken: state.refreshToken,
        user: state.user,
        isAuthenticated: state.isAuthenticated,
      }),
    }
  )
)
