import api from './api'
import type {
  Subscription,
  SubscriptionListItem,
  UpdateSubscriptionRequest,
  UsageInfo,
} from '../types/billing'

type SubscriptionQuery = {
  skip?: number
  limit?: number
  search?: string
  subscription_type?: 'free' | 'subscribed'
  sort_by?: 'current_month_usage' | 'usage_reset_at'
  sort_order?: 'asc' | 'desc'
}

const body = <T>(request: Promise<{ data: T }>): Promise<T> =>
  request.then(({ data }) => data)
const payload = <T>(request: Promise<{ data: { data: T } }>): Promise<T> =>
  request.then(({ data }) => data.data)
const subscriptionPath = (tenantId: string) =>
  `/api/v1/admin/billing/subscriptions/${tenantId}`

export const billingService = {
  getCurrentSubscription: (): Promise<Subscription> =>
    body(api.get('/api/v1/billing/subscription')),
  getCurrentUsage: (): Promise<UsageInfo> =>
    payload(api.get('/api/v1/billing/usage')),
  listAllSubscriptions: (params?: SubscriptionQuery):
    Promise<{ data: SubscriptionListItem[]; total: number }> =>
    body(api.get('/api/v1/admin/billing/subscriptions', { params })),
  async updateSubscription(tenantId: string, data: UpdateSubscriptionRequest): Promise<void> {
    await api.put(subscriptionPath(tenantId), data)
  },
  async resetTenantQuota(tenantId: string): Promise<void> {
    await api.post(`${subscriptionPath(tenantId)}/reset-quota`)
  },
  resetAllQuotas: (): Promise<{ reset_count: number }> =>
    payload(api.post('/api/v1/admin/billing/reset-all-quotas')),
}
