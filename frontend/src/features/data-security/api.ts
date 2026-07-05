import api, { responseBody as body } from '@/core/api/client'

type RegexPrompt = { description: string; entity_type: string; sample_data?: string }
type RegexResult = { success: boolean; regex_pattern: string; explanation: string }
type MatchResult = {
  success: boolean
  matched: boolean
  matches: string[]
  match_count?: number
  error?: string
  processing_time_ms?: number
}
type LeakageDefaults = {
  default_input_high_risk_action: string
  default_input_medium_risk_action: string
  default_input_low_risk_action: string
  default_output_high_risk_anonymize: boolean
  default_output_medium_risk_anonymize: boolean
  default_output_low_risk_anonymize: boolean
  default_private_model_id?: string | null
  default_enable_format_detection: boolean
  default_enable_smart_segmentation: boolean
}
type LeakagePolicy = {
  input_high_risk_action?: string | null
  input_medium_risk_action?: string | null
  input_low_risk_action?: string | null
  output_high_risk_anonymize?: boolean | null
  output_medium_risk_anonymize?: boolean | null
  output_low_risk_anonymize?: boolean | null
  private_model_id?: string | null
  enable_format_detection?: boolean | null
  enable_smart_segmentation?: boolean | null
}
type GatewayDefaults = {
  default_general_high_risk_action: string
  default_general_medium_risk_action: string
  default_general_low_risk_action: string
  default_input_high_risk_action: string
  default_input_medium_risk_action: string
  default_input_low_risk_action: string
  default_output_high_risk_action: string
  default_output_medium_risk_action: string
  default_output_low_risk_action: string
}
type GatewayPolicy = {
  general_high_risk_action?: string | null
  general_medium_risk_action?: string | null
  general_low_risk_action?: string | null
  input_high_risk_action?: string | null
  input_medium_risk_action?: string | null
  input_low_risk_action?: string | null
  output_high_risk_action?: string | null
  output_medium_risk_action?: string | null
  output_low_risk_action?: string | null
  private_model_id?: string | null
}

const entityRoot = '/api/v1/config/data-security'
const entityPath = (suffix = '') => `${entityRoot}/entity-types${suffix}`
const applicationHeader = (applicationId: string) => ({
  headers: { 'X-Application-ID': applicationId },
})

const policyApi = <Defaults, Policy>(name: string) => {
  const path = `/api/v1/config/${name}`
  return {
    getTenantDefaults: (): Promise<any> => body(api.get(`${path}/tenant-defaults`)),
    updateTenantDefaults: (data: Defaults): Promise<any> => body(api.put(`${path}/tenant-defaults`, data)),
    getPolicy: (applicationId: string): Promise<any> => body(api.get(path, applicationHeader(applicationId))),
    updatePolicy: (applicationId: string, data: Policy): Promise<any> =>
      body(api.put(path, data, applicationHeader(applicationId))),
  }
}

export const dataSecurityApi = {
  getEntityTypes: (): Promise<{ items: any[] }> => body(api.get(entityPath())),
  list: (): Promise<{ items: any[] }> => body(api.get(entityPath())),
  getEntityType: (id: string) => body(api.get(entityPath(`/${id}`))),
  createEntityType: (data: any) => body(api.post(entityPath(), data)),
  updateEntityType: (id: string, data: any) => body(api.put(entityPath(`/${id}`), data)),
  deleteEntityType: (id: string) => body(api.delete(entityPath(`/${id}`))),
  createGlobalEntityType: (data: any) => body(api.post(`${entityRoot}/global-entity-types`, data)),
  generateAnonymizationRegex: (data: RegexPrompt):
    Promise<RegexResult & { replacement_template: string }> =>
    body(api.post(`${entityRoot}/generate-anonymization-regex`, data)),
  testAnonymization: (data: { method: string; config: Record<string, any>; test_input: string }):
    Promise<{ success: boolean; result: string; processing_time_ms: number }> =>
    body(api.post(`${entityRoot}/test-anonymization`, data)),
  generateRecognitionRegex: (data: RegexPrompt): Promise<RegexResult> =>
    body(api.post(`${entityRoot}/generate-recognition-regex`, data)),
  generateEntityTypeCode: (data: { entity_type_name: string }):
    Promise<{ success: boolean; entity_type_code: string; error?: string }> =>
    body(api.post(`${entityRoot}/generate-entity-type-code`, data)),
  testRecognitionRegex: (data: { pattern: string; test_input: string }): Promise<MatchResult> =>
    body(api.post(`${entityRoot}/test-recognition-regex`, data)),
  testEntityDefinition: (data: { entity_definition: string; entity_type_name: string; test_input: string }):
    Promise<MatchResult> => body(api.post(`${entityRoot}/test-entity-definition`, data)),
  generateGenaiCode: (data: { natural_description: string; sample_data?: string }):
    Promise<{ success: boolean; code_generated: boolean; genai_code?: string; message: string; error?: string }> =>
    body(api.post(`${entityRoot}/generate-genai-code`, data)),
  testGenaiCode: (data: { code: string; test_input: string }):
    Promise<{ success: boolean; anonymized_text: string; error?: string; processing_time_ms: number }> =>
    body(api.post(`${entityRoot}/test-genai-code`, data)),
  saveRestoreConfig: (id: string, data: { restore_enabled: boolean; restore_natural_desc: string }):
    Promise<{ success: boolean; message: string; error?: string }> =>
    body(api.put(entityPath(`/${id}/restore-config`), data)),
  getDetectionResults: (limit: number, offset: number): Promise<{ items: any[]; total: number }> =>
    body(api.get(`/api/v1/results?per_page=${limit}&page=${Math.floor(offset / limit) + 1}`)),
  getDetectionResult: (requestId: string) => body(api.get(`/api/v1/results/${requestId}`)),
  getFeatureAvailability: (): Promise<{
    is_enterprise: boolean
    is_subscribed: boolean
    features: {
      genai_recognition: boolean
      genai_code_anonymization: boolean
      natural_language_desc: boolean
      format_detection: boolean
      smart_segmentation: boolean
      custom_scanners: boolean
    }
  }> => body(api.get(`${entityRoot}/feature-availability`)),
}

export const dataLeakagePolicyApi = {
  ...policyApi<LeakageDefaults, LeakagePolicy>('data-leakage-policy'),
  getPrivateModels: (): Promise<any[]> => body(api.get('/api/v1/config/private-models')),
}

export const gatewayPolicyApi = policyApi<GatewayDefaults, GatewayPolicy>('gateway-policy')
