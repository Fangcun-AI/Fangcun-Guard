import api, { responseBody as body } from '@/core/api/client'

export interface PluginHooks {
  on_input_check: boolean
  on_output_check: boolean
  on_detection_check: boolean
  on_stream_complete: boolean
}
export interface PluginRecord {
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
  hooks: PluginHooks | null
}

export const pluginsApi = {
  list: (): Promise<{ total: number; plugins: PluginRecord[] }> => body(api.get('/api/v1/plugins')),
  get: (name: string) => body(api.get(`/api/v1/plugins/${name}`)),
}
