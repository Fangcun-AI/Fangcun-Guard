import api, { responseBody as body } from '@/core/api/client'
import type { DetectionResult, PaginatedResponse } from '@/types'

type ResultQuery = {
  page?: number
  per_page?: number
  risk_level?: string
  security_risk_level?: string
  compliance_risk_level?: string
  category?: string
  data_entity_type?: string
  start_date?: string
  end_date?: string
  content_search?: string
  request_id_search?: string
}

export const resultsApi = {
  getResults: (params?: ResultQuery): Promise<PaginatedResponse<DetectionResult>> =>
    body(api.get('/api/v1/results', { params })),
  getResult: (id: number): Promise<DetectionResult> => body(api.get(`/api/v1/results/${id}`)),
  exportResults: (params?: Omit<ResultQuery, 'page' | 'per_page'>): Promise<Blob> =>
    body(api.get('/api/v1/results/export', { params, responseType: 'blob' })),
}
