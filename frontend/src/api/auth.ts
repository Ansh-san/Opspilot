/**
 * Auth API module — typed wrappers for /api/v1/auth/* endpoints.
 */

import { apiClient } from './client'
import type { LoginRequest, RegisterRequest, TokenResponse, User } from '@/types'

export const authApi = {
  register(data: RegisterRequest) {
    return apiClient.post<User>('/api/v1/auth/register', data)
  },

  login(data: LoginRequest) {
    return apiClient.post<TokenResponse>('/api/v1/auth/login', data)
  },

  refresh(refreshToken: string) {
    return apiClient.post<TokenResponse>('/api/v1/auth/refresh', {
      refresh_token: refreshToken,
    })
  },

  logout() {
    return apiClient.post('/api/v1/auth/logout')
  },

  me() {
    return apiClient.get<User>('/api/v1/auth/me')
  },
}
