/**
 * Shared TypeScript types for OpsPilot frontend.
 * Mirrors the backend Pydantic schemas.
 */

// ─── Auth ─────────────────────────────────────────────────────────────────────
export type UserRole = 'admin' | 'manager' | 'agent' | 'viewer'

export interface User {
  id: string
  org_id: string
  email: string
  full_name: string
  role: UserRole
  is_active: boolean
  created_at: string
  last_login: string | null
}

export interface TokenResponse {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
}

export interface RegisterRequest {
  org_name: string
  org_slug: string
  full_name: string
  email: string
  password: string
}

export interface LoginRequest {
  email: string
  password: string
}

// ─── Tickets (Phase 2) ────────────────────────────────────────────────────────
export type TicketStatus =
  | 'open'
  | 'investigating'
  | 'waiting_approval'
  | 'in_progress'
  | 'resolved'
  | 'closed'

export type TicketPriority = 'low' | 'medium' | 'high' | 'critical'
export type TicketSeverity = 's1' | 's2' | 's3' | 's4'

export interface Ticket {
  id: string
  org_id: string
  title: string
  description: string
  category: string | null
  priority: TicketPriority
  severity: TicketSeverity | null
  status: TicketStatus
  requester_id: string
  assigned_agent_id: string | null
  affected_service: string | null
  ai_confidence: number | null
  ai_recommendation: string | null
  created_at: string
  updated_at: string
}

// ─── Approvals (Phase 5) ──────────────────────────────────────────────────────
export type RiskLevel = 'low' | 'medium' | 'high' | 'blocked'
export type ApprovalStatus = 'pending' | 'approved' | 'rejected' | 'expired'

export interface ApprovalRequest {
  id: string
  ticket_id: string
  proposed_action: string
  reason: string
  evidence: unknown[]
  confidence: number | null
  risk_level: RiskLevel
  status: ApprovalStatus
  created_at: string
}

// ─── API Errors ───────────────────────────────────────────────────────────────
export interface ApiError {
  detail: string
}

// ─── Dashboard metrics (static for Phase 1) ──────────────────────────────────
export interface DashboardMetrics {
  total_tickets: number
  open_tickets: number
  resolved_tickets: number
  avg_resolution_hours: number
  ai_recommendations: number
  tool_call_success_rate: number
  avg_ai_latency_ms: number
  human_escalation_rate: number
  evaluation_score: number
}
