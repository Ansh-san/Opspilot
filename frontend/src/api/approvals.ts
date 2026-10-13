import { apiClient } from '@/api/client'

export interface ApprovalRequestResponse {
  id: string
  org_id: string
  ticket_id: string
  ai_run_id: string | null
  
  proposed_action: string
  action_args: Record<string, unknown>
  reason: string
  evidence: string[]
  confidence: number | null
  risk_level: string
  
  status: 'pending' | 'approved' | 'rejected' | 'executed' | 'failed'
  requested_by_id: string
  reviewed_by_id: string | null
  reviewed_at: string | null
  review_note: string | null
  
  created_at: string
}

export interface CreateApprovalPayload {
  ticket_id: string
  ai_run_id: string | null
  recommended_action: string
  risk_level?: string
  reason?: string
  confidence?: number | null
  evidence?: string[]
}

export const approvalsApi = {
  createApproval: (payload: CreateApprovalPayload) =>
    apiClient.post<ApprovalRequestResponse>('/api/v1/approvals', payload),

  listApprovals: (status?: string) =>
    apiClient.get<ApprovalRequestResponse[]>('/api/v1/approvals', { params: { status } }),

  getApproval: (id: string) =>
    apiClient.get<ApprovalRequestResponse>(`/api/v1/approvals/${id}`),

  approve: (id: string, note: string = '') =>
    apiClient.post<{ success: boolean; result: unknown; error: string | null }>(
      `/api/v1/approvals/${id}/approve`,
      { note }
    ),

  reject: (id: string, note: string = '') =>
    apiClient.post<{ status: string }>(`/api/v1/approvals/${id}/reject`, { note }),
}
