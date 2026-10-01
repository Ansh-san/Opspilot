/**
 * Agents API — all Axios calls for /api/v1/agents/*
 * and the run-agent action on tickets.
 */

import { apiClient } from '@/api/client'

// ─── Types ────────────────────────────────────────────────────────────────────

export interface AgentClassification {
  category: string
  priority: string
  severity: string
  confidence: number
  reasoning: string
}

export interface AgentDiagnosis {
  root_cause: string
  affected_components: string[]
  impact_summary: string
  evidence: string[]
  confidence: number
}

export interface AgentRecommendation {
  action: string
  steps: string[]
  estimated_resolution_time: string
  risk_level: 'low' | 'medium' | 'high' | 'blocked'
  requires_approval: boolean
  runbook_references: string[]
  confidence: number
}

export interface AgentRunResult {
  ai_run_id: string
  ticket_id: string
  classification: AgentClassification | null
  diagnosis: AgentDiagnosis | null
  recommendation: AgentRecommendation | null
  confidence: number | null
  risk_level: string | null
  requires_approval: boolean
  insufficient_evidence: boolean
  latency_ms: number | null
  model_used: string | null
  errors: string[]
  approval_id: string | null
  approval_status: string | null
}

export interface RetrievedDocument {
  chunk_id: string
  document_id: string
  document_title: string
  content: string
  similarity_score: number
  page: number | null
  section: string | null
  source_title: string | null
}

export interface AIRunSummary {
  id: string
  ticket_id: string | null
  confidence: number | null
  risk_level: string | null
  decision: string | null
  latency_ms: number | null
  model_used: string | null
  created_at: string
  approval_status: string | null
  execution_result: string | null
}

export interface AIRunDetail extends AIRunSummary {
  org_id: string
  agent_trace: Record<string, unknown> | null
  decision: string | null
  reasoning: string | null
  evidence: string[] | null
  policy_result: Record<string, unknown> | null
  classification: AgentClassification | null
  diagnosis: AgentDiagnosis | null
  recommendation: AgentRecommendation | null
  input_tokens: number | null
  output_tokens: number | null
}

export interface AIRunListResponse {
  items: AIRunSummary[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

// ─── API calls ────────────────────────────────────────────────────────────────

export const agentsApi = {
  /** Trigger the AI agent pipeline on a ticket */
  runOnTicket: (ticketId: string) =>
    apiClient.post<AgentRunResult>(`/api/v1/tickets/${ticketId}/run-agent`),

  /** List paginated run history */
  listRuns: (params: {
    ticket_id?: string
    min_confidence?: number
    page?: number
    page_size?: number
  } = {}) =>
    apiClient.get<AIRunListResponse>('/api/v1/agents/runs', { params }),

  /** Get a single run by ID */
  getRun: (runId: string) =>
    apiClient.get<AIRunDetail>(`/api/v1/agents/runs/${runId}`),
}
