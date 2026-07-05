import api, { responseBody as body } from '@/core/api/client'

export interface TestModelSelection { id: string; selected: boolean; model_name?: string | null }
export interface OnlineTestModel {
  id: string
  config_name: string
  api_base_url: string
  model_name: string
  enabled: boolean
  selected: boolean
}

export const testModelsApi = {
  getModels: (): Promise<OnlineTestModel[]> => body(api.get('/api/v1/test/models')),
  updateSelection: (modelSelections: TestModelSelection[]) =>
    body(api.post('/api/v1/test/models/selection', { model_selections: modelSelections })),
}
export const onlineTestApi = {
  run: (data: { content: string; input_type: 'question' | 'qa_pair'; selected_models?: string[] }) =>
    body(api.post('/api/v1/test/online', data)),
}
