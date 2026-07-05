import api, { responseBody as body } from '@/core/api/client'
import type { KnowledgeBase, KnowledgeBaseFileInfo, SimilarQuestionResult } from '@/types'

type MessageResult = { success: boolean; message: string }
type ScannerOption = { value: string; label: string }
type KnowledgeBaseMutation = {
  category?: string
  scanner_type?: string
  scanner_identifier?: string
  name: string
  description?: string
  similarity_threshold?: number
  is_active: boolean
  is_global?: boolean
}
const path = (id?: number) => `/api/v1/config/knowledge-bases${id === undefined ? '' : `/${id}`}`
const multipart = { headers: { 'Content-Type': 'multipart/form-data' } }

export const knowledgeBaseApi = {
  list: (category?: string): Promise<KnowledgeBase[]> =>
    body(api.get(category ? `${path()}?category=${category}` : path())),
  create: (data: FormData): Promise<MessageResult> => body(api.post(path(), data, multipart)),
  update: (id: number, data: KnowledgeBaseMutation): Promise<MessageResult> => body(api.put(path(id), data)),
  delete: (id: number): Promise<MessageResult> => body(api.delete(path(id))),
  replaceFile: (id: number, file: File): Promise<MessageResult> => {
    const data = new FormData()
    data.append('file', file)
    return body(api.post(`${path(id)}/replace-file`, data, multipart))
  },
  getInfo: (id: number): Promise<KnowledgeBaseFileInfo> => body(api.get(`${path(id)}/info`)),
  search: (id: number, query: string, topK?: number): Promise<SimilarQuestionResult[]> => {
    const params = new URLSearchParams({ query })
    if (topK) params.append('top_k', topK.toString())
    return body(api.post(`${path(id)}/search?${params}`))
  },
  getByCategory: (category: string): Promise<KnowledgeBase[]> =>
    body(api.get(`/api/v1/config/categories/${category}/knowledge-bases`)),
  toggleDisable: (id: number): Promise<MessageResult> => body(api.post(`${path(id)}/toggle-disable`)),
  checkDisabled: (id: number): Promise<{ kb_id: number; is_global: boolean; is_disabled: boolean }> =>
    body(api.get(`${path(id)}/is-disabled`)),
  getAvailableScanners: (): Promise<{
    blacklists: ScannerOption[]
    whitelists: ScannerOption[]
    official_scanners: ScannerOption[]
    marketplace_scanners: ScannerOption[]
    custom_scanners: ScannerOption[]
  }> => body(api.get(`${path()}/available-scanners`)),
}
