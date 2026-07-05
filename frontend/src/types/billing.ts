type SubscriptionKind = 'free' | 'subscribed'

export interface UsageBreakdown {
  guardrails_proxy: number
  direct_model_access: number
}

interface UsageMeter {
  monthly_quota: number
  current_month_usage: number
  usage_reset_at: string
  usage_percentage: number
  plan_name: string
}

export interface Subscription extends UsageMeter {
  id: string
  tenant_id: string
  subscription_type: SubscriptionKind
  subscription_tier: number
  usage_breakdown?: UsageBreakdown
  billing_period_start?: string
  billing_period_end?: string
  purchased_quota: number
  purchased_quota_expires_at: string | null
}

export interface UsageInfo extends UsageMeter {
  remaining: number
  subscription_type: string
}

export interface SubscriptionListItem extends UsageMeter {
  id: string
  tenant_id: string
  email: string
  subscription_type: SubscriptionKind
}

export interface UpdateSubscriptionRequest {
  subscription_type: SubscriptionKind
}
