import api from '@/core/api/client'
import type {
  ApiResponse,
  Blacklist,
  DashboardStats,
  GuardrailRequest,
  GuardrailResponse,
  ResponseTemplate,
  Whitelist,
} from '../types'

type RequestOptions = Record<string, unknown>
type Editable<T> = Omit<T, 'id' | 'created_at' | 'updated_at'>
type MessageResult = { success: boolean; message: string }
type DataResult<T = any> = MessageResult & { data: T }
type OptionalDataResult<T = any> = MessageResult & { data?: T }
type StatusDataResult<T = any> = { status: string; message: string; data: T }

const unwrap = <T>(request: Promise<{ data: T }>): Promise<T> =>
  request.then(({ data }) => data)
const get = <T = any>(url: string, options?: RequestOptions): Promise<T> =>
  unwrap(api.get(url, options))
const post = <T = any>(url: string, data?: unknown, options?: RequestOptions): Promise<T> =>
  unwrap(api.post(url, data, options))
const put = <T = any>(url: string, data?: unknown): Promise<T> =>
  unwrap(api.put(url, data))
const remove = <T = any>(url: string): Promise<T> => unwrap(api.delete(url))

const editableResource = <T>(path: string) => ({
  list: (): Promise<T[]> => get(path),
  create: (data: Editable<T>): Promise<ApiResponse> => post(path, data),
  update: (id: number, data: Editable<T>): Promise<ApiResponse> => put(`${path}/${id}`, data),
  delete: (id: number): Promise<ApiResponse> => remove(`${path}/${id}`),
})

export const guardrailsApi = {
  check: (data: GuardrailRequest): Promise<GuardrailResponse> => post('/v1/guardrails', data),
  health: () => get('/v1/guardrails/health'),
  models: () => get('/v1/guardrails/models'),
}

export const dashboardApi = {
  getStats: (): Promise<DashboardStats> => get('/api/v1/dashboard/stats'),
  getCategoryDistribution: (params?: { start_date?: string; end_date?: string }):
    Promise<{ categories: { name: string; value: number }[] }> =>
    get('/api/v1/dashboard/category-distribution', { params }),
}

type AppealConfig = {
  id?: string
  enabled: boolean
  message_template: string
  appeal_base_url: string
  final_reviewer_email?: string
  created_at?: string
  updated_at?: string
}
type AppealRecord = {
  id: string
  request_id: string
  user_id?: string
  application_id?: string
  application_name?: string
  original_content: string
  original_risk_level: string
  original_categories: string[]
  status: string
  ai_approved?: boolean
  ai_review_result?: string
  processor_type?: string
  processor_id?: string
  processor_reason?: string
  created_at?: string
  ai_reviewed_at?: string
  processed_at?: string
}

export const configApi = {
  blacklist: editableResource<Blacklist>('/api/v1/config/blacklist'),
  whitelist: editableResource<Whitelist>('/api/v1/config/whitelist'),
  responses: editableResource<ResponseTemplate>('/api/v1/config/responses'),
  getSystemInfo: (): Promise<{ support_email: string | null; app_name: string; app_version: string }> =>
    get('/api/v1/config/system-info'),
  banPolicy: {
    get: () => get('/api/v1/ban-policy'),
    update: (data: {
      enabled: boolean
      risk_level: string
      trigger_count: number
      time_window_minutes: number
      ban_duration_minutes: number
    }) => put('/api/v1/ban-policy', data),
    getBannedUsers: (skip?: number, limit?: number): Promise<{ users: any[] }> =>
      get('/api/v1/ban-policy/banned-users', { params: { skip, limit } }),
    unbanUser: (userId: string) => post('/api/v1/ban-policy/unban', { user_id: userId }),
    getUserHistory: (userId: string, days?: number): Promise<{ history: any[] }> =>
      get(`/api/v1/ban-policy/user-history/${userId}`, { params: { days } }),
    checkUserStatus: (userId: string) => get(`/api/v1/ban-policy/check-status/${userId}`),
  },
  appealConfig: {
    get: (): Promise<AppealConfig> => get('/api/v1/config/appeal'),
    update: (data: Omit<AppealConfig, 'id' | 'created_at' | 'updated_at'>) =>
      put('/api/v1/config/appeal', data),
    getRecords: (params?: { status?: string; page?: number; page_size?: number }):
      Promise<{ items: AppealRecord[]; total: number; page: number; page_size: number; pages: number }> =>
      get('/api/v1/config/appeal/records', { params }),
    reviewAppeal: (appealId: string, data: { action: 'approve' | 'reject'; reason?: string }):
      Promise<MessageResult & { status: string }> =>
      post(`/api/v1/config/appeal/records/${appealId}/review`, data),
    exportRecords: (params?: { status?: string }): Promise<Blob> =>
      get('/api/v1/config/appeal/records/export', { params, responseType: 'blob' }),
  },
}

type UserMutation = {
  email?: string
  password?: string
  is_active?: boolean
  is_verified?: boolean
  is_super_admin?: boolean
}
type SwitchUser = { id: string; email: string; api_key: string }

export const adminApi = {
  getAdminStats: (): Promise<{
    status: string
    data: {
      total_users: number
      total_detections: number
      user_detection_counts: Array<{ tenant_id: string; email: string; detection_count: number }>
    }
  }> => get('/api/v1/admin/stats'),
  getUsers: (params?: {
    sort_by?: string
    sort_order?: string
    skip?: number
    limit?: number
    search?: string
  }): Promise<{ status: string; users: any[]; total: number }> => get('/api/v1/admin/users', { params }),
  switchToUser: (tenantId: string):
    Promise<{ status: string; message: string; switch_session_token: string; target_user: SwitchUser }> =>
    post(`/api/v1/admin/switch-user/${tenantId}`),
  exitSwitch: (): Promise<{ status: string; message: string }> => post('/api/v1/admin/exit-switch'),
  getCurrentSwitch: ():
    Promise<{ is_switched: boolean; admin_user?: Pick<SwitchUser, 'id' | 'email'>; target_user?: SwitchUser }> =>
    get('/api/v1/admin/current-switch'),
  createUser: (data: UserMutation & { email: string; password: string }): Promise<ApiResponse> =>
    post('/api/v1/admin/create-user', data),
  updateUser: (tenantId: string, data: Omit<UserMutation, 'password'>): Promise<ApiResponse> =>
    put(`/api/v1/admin/users/${tenantId}`, data),
  deleteUser: (tenantId: string): Promise<ApiResponse> => remove(`/api/v1/admin/users/${tenantId}`),
  resetUserApiKey: (tenantId: string): Promise<ApiResponse> =>
    post(`/api/v1/admin/users/${tenantId}/reset-api-key`),
  getRateLimits: (params?: {
    skip?: number
    limit?: number
    search?: string
    sort_by?: string
    sort_order?: string
  }): Promise<{ status: string; data: any[]; total: number }> =>
    get('/api/v1/admin/rate-limits', { params }),
  setUserRateLimit: (data: { tenant_id: string; requests_per_second: number }):
    Promise<StatusDataResult> => post('/api/v1/admin/rate-limits', data),
  removeUserRateLimit: (tenantId: string): Promise<{ status: string; message: string }> =>
    remove(`/api/v1/admin/rate-limits/${tenantId}`),
  getTenantAnalytics: (days?: number): Promise<{
    status: string
    data: {
      latest_created_tenants: Array<{
        id: string
        email: string
        created_at: string | null
        is_active: boolean
        is_verified: boolean
      }>
      recently_active_tenants: Array<{
        id: string
        email: string
        last_activity: string | null
        is_active: boolean
        is_verified: boolean
      }>
      creation_trend: Array<{ date: string; count: number }>
      usage_trend: Array<{ date: string; count: number }>
    }
  }> => get('/api/v1/admin/tenant-analytics', { params: { days } }),
}

export const testModelsApi = {
  getModels: () => get('/api/v1/test/models'),
  updateSelection: (model_selections: Array<{ id: string; selected: boolean }>) =>
    post('/api/v1/test/models/selection', { model_selections }),
}

export const sensitivityThresholdApi = {
  get: () => get('/api/v1/config/sensitivity-thresholds'),
  update: (config: {
    high_sensitivity_threshold: number
    medium_sensitivity_threshold: number
    low_sensitivity_threshold: number
    sensitivity_trigger_level: string
  }) => put('/api/v1/config/sensitivity-thresholds', config),
  reset: () => post('/api/v1/config/sensitivity-thresholds/reset'),
}

type ProxyModelCreate = {
  config_name: string
  api_base_url: string
  api_key: string
  is_active?: boolean
  enable_reasoning_detection?: boolean
  stream_chunk_size?: number
}

export const proxyModelsApi = {
  list: (): Promise<{ success: boolean; data: any[] }> => get('/api/v1/proxy/upstream-apis'),
  get: (id: string): Promise<{ success: boolean; data: any }> => get(`/api/v1/proxy/upstream-apis/${id}`),
  create: (data: ProxyModelCreate): Promise<OptionalDataResult> =>
    post('/api/v1/proxy/upstream-apis', data),
  update: (id: string, data: Partial<ProxyModelCreate>): Promise<MessageResult> =>
    put(`/api/v1/proxy/upstream-apis/${id}`, data),
  delete: (id: string): Promise<MessageResult> => remove(`/api/v1/proxy/upstream-apis/${id}`),
  test: (id: string): Promise<OptionalDataResult> => post(`/api/v1/proxy/upstream-apis/${id}/test`),
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

export const modelRoutesApi = {
  list: (includeInactive = false): Promise<ModelRoute[]> =>
    get(`/api/v1/model-routes?include_inactive=${includeInactive}`),
  get: (id: string): Promise<ModelRoute> => get(`/api/v1/model-routes/${id}`),
  create: (data: ModelRouteCreateData): Promise<ModelRoute> => post('/api/v1/model-routes', data),
  update: (id: string, data: ModelRouteUpdateData): Promise<ModelRoute> =>
    put(`/api/v1/model-routes/${id}`, data),
  delete: (id: string): Promise<MessageResult> => remove(`/api/v1/model-routes/${id}`),
  test: (modelName: string, applicationId?: string): Promise<{
    matched: boolean
    model_name: string
    message?: string
    upstream_api_config?: ModelRouteUpstreamApi & { api_base_url: string }
  }> => {
    const params = applicationId ? `?application_id=${applicationId}` : ''
    return get(`/api/v1/model-routes/test/${encodeURIComponent(modelName)}${params}`)
  },
}

export const scannerPackagesApi = {
  getAll: (packageType?: 'basic' | 'purchasable'): Promise<any[]> =>
    get('/api/v1/scanner-packages/', { params: { package_type: packageType } }),
  getDetail: (packageId: string) => get(`/api/v1/scanner-packages/${packageId}`),
  getMarketplace: (): Promise<any[]> => get('/api/v1/scanner-packages/marketplace/list'),
  getMarketplaceDetail: (packageId: string) => get(`/api/v1/scanner-packages/marketplace/${packageId}`),
  getAllAdmin: (packageType?: 'basic' | 'purchasable', includeArchived?: boolean): Promise<any[]> =>
    get('/api/v1/scanner-packages/admin/packages', {
      params: { package_type: packageType, include_archived: includeArchived },
    }),
  uploadPackage: (packageData: any) => post('/api/v1/scanner-packages/admin/upload', packageData),
  updatePackage: (packageId: string, updates: any) => put(`/api/v1/scanner-packages/admin/${packageId}`, updates),
  archivePackage: (packageId: string, reason?: string): Promise<MessageResult> =>
    post(`/api/v1/scanner-packages/admin/${packageId}/archive`, reason ? { reason } : {}),
  unarchivePackage: (packageId: string): Promise<MessageResult> =>
    post(`/api/v1/scanner-packages/admin/${packageId}/unarchive`),
  deletePackage: (packageId: string): Promise<MessageResult> =>
    remove(`/api/v1/scanner-packages/admin/${packageId}`),
  getStatistics: (packageId: string) => get(`/api/v1/scanner-packages/admin/${packageId}/statistics`),
}

export const scannerConfigsApi = {
  getAll: (includeDisabled = true): Promise<any[]> =>
    get('/api/v1/scanner-configs', { params: { include_disabled: includeDisabled } }),
  getEnabled: (scanType?: 'prompt' | 'response'): Promise<any[]> =>
    get('/api/v1/scanner-configs/enabled', { params: { scan_type: scanType } }),
  update: (scannerId: string, updates: any): Promise<DataResult> =>
    put(`/api/v1/scanner-configs/${scannerId}`, updates),
  bulkUpdate: (updates: Array<{ scanner_id: string; [key: string]: any }>): Promise<DataResult> =>
    post('/api/v1/scanner-configs/bulk-update', { updates }),
  reset: (scannerId: string): Promise<MessageResult> => post(`/api/v1/scanner-configs/${scannerId}/reset`),
  resetAll: (): Promise<DataResult> => post('/api/v1/scanner-configs/reset-all'),
  initialize: (): Promise<DataResult> => post('/api/v1/scanner-configs/initialize'),
}

export const customScannersApi = {
  getAll: (): Promise<any[]> => get('/api/v1/custom-scanners'),
  get: (scannerId: string) => get(`/api/v1/custom-scanners/${scannerId}`),
  create: (scannerData: {
    scanner_type: 'genai' | 'regex' | 'keyword'
    name: string
    definition: string
    risk_level: 'high_risk' | 'medium_risk' | 'low_risk'
    scan_prompt?: boolean
    scan_response?: boolean
    notes?: string
  }) => post('/api/v1/custom-scanners', scannerData),
  update: (scannerId: string, updates: any) => put(`/api/v1/custom-scanners/${scannerId}`, updates),
  delete: (scannerId: string): Promise<MessageResult> => remove(`/api/v1/custom-scanners/${scannerId}`),
}

export const purchasesApi = {
  directPurchase: (packageId: string, email: string) =>
    post('/api/v1/purchases/direct', { package_id: packageId, email }),
  request: (packageId: string, email: string, message?: string) =>
    post('/api/v1/purchases/request', { package_id: packageId, email, message }),
  getMyPurchases: (status?: 'pending' | 'approved' | 'rejected'): Promise<any[]> =>
    get('/api/v1/purchases/my-purchases', { params: { status_filter: status } }),
  cancel: (purchaseId: string): Promise<MessageResult> => remove(`/api/v1/purchases/${purchaseId}`),
  getPending: (): Promise<any[]> => get('/api/v1/purchases/admin/pending'),
  approve: (purchaseId: string) => post(`/api/v1/purchases/admin/${purchaseId}/approve`),
  reject: (purchaseId: string, rejectionReason: string) =>
    post(`/api/v1/purchases/admin/${purchaseId}/reject`, { rejection_reason: rejectionReason }),
  getStatistics: (packageId?: string): Promise<DataResult> =>
    get('/api/v1/purchases/admin/statistics', { params: { package_id: packageId } }),
}

export const fixedAnswerTemplatesApi = {
  get: (): Promise<{
    security_risk_template: { en: string; zh: string }
    data_leakage_template: { en: string; zh: string }
  }> => get('/api/v1/config/fixed-answer-templates'),
  update: (templates: {
    security_risk_template?: { en?: string; zh?: string }
    data_leakage_template?: { en?: string; zh?: string }
  }): Promise<MessageResult> => put('/api/v1/config/fixed-answer-templates', templates),
}

type PluginSummary = {
  name: string
  version: string
  description: string
  author: string
  plugin_type: string
  deployment_mode: string
  priority: number
  display_name: string
  display_name_en: string
  icon: string
  category: string
  tags: string[]
  documentation: string
  enabled: boolean
  hooks: {
    on_input_check: boolean
    on_output_check: boolean
    on_detection_check: boolean
    on_stream_complete: boolean
  } | null
}

export const pluginsApi = {
  list: (): Promise<{ total: number; plugins: PluginSummary[] }> => get('/api/v1/plugins'),
  get: (name: string) => get(`/api/v1/plugins/${name}`),
}

const scannerApi = (root: string) => ({
  scan: (data: { tools?: any[]; servers?: any[]; policy_mode?: string }) => post(`${root}/scan`, data),
  scanDirectory: (data: { directory: string; max_tools?: number }) => post(`${root}/scan-directory`, data),
})

export const skillScannerApi = scannerApi('/api/v1/skill-scanner')
export const mcpScannerApi = scannerApi('/api/v1/mcp-scanner')

export default api
