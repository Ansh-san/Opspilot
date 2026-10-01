import { apiClient } from './client'

export interface EvaluationResult {
  metric_name: string
  score: number | null
  status: string
  explanation: string
  metadata: any
}

export interface EvaluationRun {
  ai_run_id: string
  ticket_id: string | null
  created_at: string
  evaluation_results: EvaluationResult[]
}

export const evaluationsApi = {
  listEvaluations: async (limit: number = 50, offset: number = 0): Promise<{ items: EvaluationRun[] }> => {
    const { data } = await apiClient.get('/evaluations', { params: { limit, offset } })
    return data
  },

  getEvaluation: async (aiRunId: string): Promise<EvaluationRun> => {
    const { data } = await apiClient.get(`/evaluations/${aiRunId}`)
    return data
  },

  runEvaluation: async (aiRunId: string): Promise<{ ai_run_id: string, evaluation_results: EvaluationResult[] }> => {
    const { data } = await apiClient.post(`/evaluations/run/${aiRunId}`)
    return data
  }
}
