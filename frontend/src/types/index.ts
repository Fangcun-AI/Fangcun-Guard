export interface ApiResponse<T = any> {
  success: boolean
  message: string
  data?: T
}

export interface Message {
  role: 'user' | 'system' | 'assistant'
  content: string
}

export interface GuardrailRequest {
  model: string
  messages: Message[]
  max_tokens?: number
  temperature?: number
}

interface RiskSummary {
  risk_level: string
  categories: string[]
}

export interface GuardrailResponse {
  id: string
  result: { compliance: RiskSummary; security: RiskSummary; data: RiskSummary }
  overall_risk_level: string
  suggest_action: string
  suggest_answer?: string
  score?: number
}

export interface DetectionResult {
  id: number
  request_id: string
  content: string
  suggest_action?: string
  suggest_answer?: string
  hit_keywords?: string
  created_at: string
  ip_address?: string
  security_risk_level: string
  security_categories: string[]
  compliance_risk_level: string
  compliance_categories: string[]
  data_risk_level: string
  data_categories: string[]
  score?: number
  has_image?: boolean
  image_count?: number
  image_paths?: string[]
  image_urls?: string[]
  is_direct_model_access?: boolean
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  per_page: number
  pages: number
}

interface TimestampedRecord {
  id: number
  created_at: string
  updated_at: string
}

interface KeywordCollection extends TimestampedRecord {
  name: string
  keywords: string[]
  description?: string
  is_active: boolean
}

export interface Blacklist extends KeywordCollection {}
export interface Whitelist extends KeywordCollection {}

export interface ResponseTemplate extends TimestampedRecord {
  category: string
  scanner_type?: string | null
  scanner_identifier?: string | null
  scanner_name?: string | null
  risk_level: string
  template_content: Record<string, string>
  is_default: boolean
  is_active: boolean
}

export interface DailyTrend {
  date: string
  total: number
  high_risk: number
  medium_risk: number
  low_risk: number
  safe: number
}

export interface DashboardStats {
  total_requests: number
  security_risks: number
  compliance_risks: number
  data_leaks: number
  high_risk_count: number
  medium_risk_count: number
  low_risk_count: number
  safe_count: number
  risk_distribution: {
    high_risk: number
    medium_risk: number
    low_risk: number
    no_risk: number
  }
  daily_trends: DailyTrend[]
}

export interface KnowledgeBase extends TimestampedRecord {
  category?: string | null
  scanner_type?: string | null
  scanner_identifier?: string | null
  scanner_name?: string | null
  name: string
  description?: string
  file_path: string
  vector_file_path?: string
  total_qa_pairs: number
  similarity_threshold: number
  is_active: boolean
  is_global: boolean
  is_disabled_by_me?: boolean
}

export interface KnowledgeBaseFileInfo {
  original_file_exists: boolean
  vector_file_exists: boolean
  original_file_size: number
  vector_file_size: number
  total_qa_pairs: number
}

export interface SimilarQuestionResult {
  questionid: string
  question: string
  answer: string
  similarity_score: number
  rank: number
}

export interface DataSecurityEntityType {
  id: string
  entity_type: string
  entity_type_name: string
  risk_level: string
  pattern: string
  anonymization_method: string
  anonymization_config: Record<string, any>
  check_input: boolean
  check_output: boolean
  is_active: boolean
  is_global: boolean
  created_at: string
  updated_at: string
}
