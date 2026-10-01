import { apiClient } from '@/api/client'

export interface AuditLog {
  id: string
  actor_id: string | null
  actor_type: string
  event_type: string
  resource_type: string
  resource_id: string | null
  details: Record<string, unknown>
  ip_address: string | null
  created_at: string
}

export interface AuditLogListResponse {
  items: AuditLog[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export const auditApi = {
  list: (params: {
    page?: number
    page_size?: number
    event_type?: string
    resource_type?: string
  } = {}) => apiClient.get<AuditLogListResponse>('/api/v1/audit', { params }),
}
