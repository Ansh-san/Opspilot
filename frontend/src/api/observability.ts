import { apiClient } from './client'

export interface ObservabilityKPIs {
  total_runs: number
  success_rate: number
  avg_latency: number
  p50_latency: number
  p95_latency: number
  total_tokens: number
  total_cost: number
  approval_rate: number
  rejection_rate: number
  tool_success_rate: number
  blocked_count: number
}

export interface AIRunTrace {
  id: string
  ticket_id: string
  confidence: number
  risk_level: string
  latency_ms: number
  created_at: string
  agent_trace?: any
  evaluation_results?: any[]
  input_tokens?: number
  output_tokens?: number
  estimated_cost_usd?: number
  model_used?: string
}

export const observabilityApi = {
  getKPIs: async (): Promise<ObservabilityKPIs> => {
    const { data } = await apiClient.get('/observability/metrics')
    return data
  },

  getTraces: async (limit: number = 50, offset: number = 0): Promise<AIRunTrace[]> => {
    const { data } = await apiClient.get('/observability/runs', { params: { limit, offset } })
    // Backend returns a plain list, but guard against paginated wrapper shapes
    return Array.isArray(data) ? data : (Array.isArray(data?.items) ? data.items : [])
  },
  
  getRunDetails: async (aiRunId: string): Promise<AIRunTrace> => {
    const { data } = await apiClient.get(`/observability/traces/${aiRunId}`)
    return data
  }
}
