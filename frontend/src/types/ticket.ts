/**
 * Ticket types — Phase 2.
 * Extended from types/index.ts with comments support.
 */

export type TicketStatus =
  | 'open'
  | 'investigating'
  | 'waiting_approval'
  | 'in_progress'
  | 'resolved'
  | 'closed'

export type TicketPriority = 'low' | 'medium' | 'high' | 'critical'
export type TicketSeverity = 's1' | 's2' | 's3' | 's4'

export interface TicketComment {
  id: string
  ticket_id: string
  author_id: string
  body: string
  is_ai_generated: boolean
  created_at: string
}

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
  ai_diagnosis: Record<string, unknown> | null
  comments: TicketComment[]
  created_at: string
  updated_at: string
}

export interface TicketListResponse {
  items: Ticket[]
  total: number
  page: number
  total_pages: number
}

export interface TicketCreate {
  title: string
  description: string
  category?: string
  priority: TicketPriority
  severity?: TicketSeverity
  affected_service?: string
}

export interface TicketUpdate {
  title?: string
  description?: string
  category?: string
  priority?: TicketPriority
  severity?: TicketSeverity
  status?: TicketStatus
  affected_service?: string
  assigned_agent_id?: string | null
}

export interface CommentCreate {
  body: string
}
