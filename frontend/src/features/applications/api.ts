import api, { responseBody as body } from '@/core/api/client'

export interface ProtectionSummary {
  risk_types_enabled: number
  total_risk_types: number
  ban_policy_enabled: boolean
  sensitivity_level: string
  data_security_entities: number
  blacklist_count: number
  whitelist_count: number
  knowledge_base_count: number
}
export interface ApplicationRecord {
  id: string
  tenant_id: string
  name: string
  description: string | null
  is_active: boolean
  source?: 'manual' | 'auto_discovery'
  external_id?: string
  created_at: string
  updated_at: string
  api_keys_count: number
  protection_summary?: ProtectionSummary
}
export interface ApplicationKeyRecord {
  id: string
  application_id: string
  key: string
  name: string | null
  is_active: boolean
  last_used_at: string | null
  created_at: string
}

type ApplicationMutation = { name?: string; description?: string; is_active?: boolean }
const path = (applicationId = '') => `/api/v1/applications${applicationId ? `/${applicationId}` : ''}`

export const applicationsApi = {
  list: (): Promise<ApplicationRecord[]> => body(api.get(path())),
  create: (data: ApplicationMutation & { name: string }): Promise<ApplicationRecord> =>
    body(api.post(path(), data)),
  update: (id: string, data: ApplicationMutation): Promise<ApplicationRecord> =>
    body(api.put(path(id), data)),
  remove: (id: string): Promise<void> => api.delete(path(id)).then(() => undefined),
  listKeys: (id: string): Promise<ApplicationKeyRecord[]> => body(api.get(`${path(id)}/keys`)),
  createKey: (id: string, data: { application_id: string; name?: string }): Promise<ApplicationKeyRecord> =>
    body(api.post(`${path(id)}/keys`, data)),
  deleteKey: (id: string, keyId: string): Promise<void> =>
    api.delete(`${path(id)}/keys/${keyId}`).then(() => undefined),
  toggleKey: (id: string, keyId: string): Promise<void> =>
    api.put(`${path(id)}/keys/${keyId}/toggle`).then(() => undefined),
}
