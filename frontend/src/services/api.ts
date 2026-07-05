import api from '@/core/api/client'

export { applicationsApi } from '@/features/applications/api'
export { dashboardApi } from '@/features/dashboard/api'
export { dataLeakagePolicyApi, dataSecurityApi, gatewayPolicyApi } from '@/features/data-security/api'
export { knowledgeBaseApi } from '@/features/knowledge-base/api'
export { onlineTestApi, testModelsApi } from '@/features/online-test/api'
export { resultsApi } from '@/features/results/api'
export {
  modelRoutesApi,
  proxyModelsApi,
} from '@/features/security-gateway/api'
export { pluginsApi } from '@/features/tool-center/api'
export {
  adminApi,
  configApi,
  customScannersApi,
  fixedAnswerTemplatesApi,
  guardrailsApi,
  mcpScannerApi,
  purchasesApi,
  scannerConfigsApi,
  scannerPackagesApi,
  sensitivityThresholdApi,
  skillScannerApi,
} from './platformApi'
export type {
  ModelRoute,
  ModelRouteApplication,
  ModelRouteCreateData,
  ModelRouteUpdateData,
  ModelRouteUpstreamApi,
} from '@/features/security-gateway/api'

export default api
