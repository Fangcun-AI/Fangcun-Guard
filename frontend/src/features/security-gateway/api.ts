import api, { responseBody as body } from '@/core/api/client'

type MessageResult = { success: boolean; message: string }
type ProxyModelCreateData = {
  config_name: string
  api_base_url: string
  api_key?: string
  provider?: string
  model_name?: string
  is_active?: boolean
  enabled?: boolean
  enable_reasoning_detection?: boolean
  reasoning_format?: string
  stream_chunk_size?: number
  is_private_model?: boolean
  is_default_private_model?: boolean
  private_model_names?: string[]
  default_private_model_name?: string | null
}

export interface ModelRouteApplication { id: string; name: string }
export interface ModelRouteUpstreamApi { id: string; config_name: string; provider?: string }
export interface ModelRoute {
  id: string
  name: string
  description?: string
  model_pattern: string
  match_type: 'exact' | 'prefix'
  upstream_api_config: ModelRouteUpstreamApi
  priority: number
  is_active: boolean
  applications: ModelRouteApplication[]
  created_at: string
  updated_at: string
}
export interface ModelRouteCreateData {
  name: string
  description?: string
  model_pattern: string
  match_type: 'exact' | 'prefix'
  upstream_api_config_id: string
  priority?: number
  application_ids?: string[]
}
export interface ModelRouteUpdateData extends Partial<ModelRouteCreateData> { is_active?: boolean }

const upstreamPath = (id = '') => `/api/v1/proxy/upstream-apis${id ? `/${id}` : ''}`
const routePath = (id = '') => `/api/v1/model-routes${id ? `/${id}` : ''}`

export const proxyModelsApi = {
  list: (): Promise<{ success: boolean; data: any[] }> => body(api.get(upstreamPath())),
  get: (id: string): Promise<{ success: boolean; data: any }> => body(api.get(upstreamPath(id))),
  create: (data: ProxyModelCreateData): Promise<MessageResult & { data?: any }> =>
    body(api.post(upstreamPath(), data)),
  update: (id: string, data: Partial<ProxyModelCreateData>): Promise<MessageResult> =>
    body(api.put(upstreamPath(id), data)),
  delete: (id: string): Promise<MessageResult> => body(api.delete(upstreamPath(id))),
  test: (id: string): Promise<MessageResult & { data?: any }> => body(api.post(`${upstreamPath(id)}/test`)),
}

export const modelRoutesApi = {
  list: (includeInactive = false): Promise<ModelRoute[]> =>
    body(api.get(`${routePath()}?include_inactive=${includeInactive}`)),
  get: (id: string): Promise<ModelRoute> => body(api.get(routePath(id))),
  create: (data: ModelRouteCreateData): Promise<ModelRoute> => body(api.post(routePath(), data)),
  update: (id: string, data: ModelRouteUpdateData): Promise<ModelRoute> =>
    body(api.put(routePath(id), data)),
  delete: (id: string): Promise<MessageResult> => body(api.delete(routePath(id))),
  test: (modelName: string, applicationId?: string): Promise<{
    matched: boolean
    model_name: string
    message?: string
    upstream_api_config?: ModelRouteUpstreamApi & { api_base_url: string }
  }> => body(api.get(`${routePath(`test/${encodeURIComponent(modelName)}`)}${applicationId ? `?application_id=${applicationId}` : ''}`)),
}
