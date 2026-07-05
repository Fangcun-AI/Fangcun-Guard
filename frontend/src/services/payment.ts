import api from './api'

const root = '/api/v1/payment'
export interface SubscriptionTier { tier_number: number; tier_name: string; monthly_quota: number; price: number; display_order: number }
export interface QuotaPurchaseConfig { price_per_unit: number; calls_per_unit: number; min_units: number; validity_days: number; currency: string }
export interface PaymentConfig {
  provider: 'alipay' | 'stripe'
  currency: string
  subscription_price: number
  stripe_publishable_key?: string
  tiers?: SubscriptionTier[]
  quota_purchase?: QuotaPurchaseConfig
}
export interface PaymentResponse {
  success: boolean
  payment_id?: string
  order_id?: string
  provider?: string
  payment_url?: string
  checkout_url?: string
  session_id?: string
  amount?: number
  currency?: string
  error?: string
  package_name?: string
}
export interface PaymentOrder {
  id: string
  order_type: 'subscription' | 'package'
  amount: number
  currency: string
  payment_provider: string
  status: string
  paid_at: string | null
  created_at: string
  package_id: string | null
}
export interface SubscriptionStatus {
  subscription_type: 'free' | 'subscribed'
  is_active: boolean
  started_at: string | null
  expires_at: string | null
  cancel_at_period_end: boolean
  next_payment_date: string | null
}
export interface PaymentVerificationResult {
  status: 'pending' | 'completed' | 'failed' | 'not_found'
  order_type?: 'subscription' | 'package'
  order_id?: string
  payment_status?: string
  details?: { package_id?: string; purchase_status?: string }
  paid_at?: string | null
  message?: string
}

const data = async <T>(request: Promise<{ data: T }>) => (await request).data
export const paymentService = {
  getConfig: () => data<PaymentConfig>(api.get(`${root}/config`)),
  getTiers: () => data<{ tiers: SubscriptionTier[]; currency: string }>(api.get(`${root}/tiers`)),
  createSubscriptionPayment: (tierNumber?: number) =>
    data<PaymentResponse>(api.post(`${root}/subscription/create`, { tier_number: tierNumber || null })),
  createQuotaPurchasePayment: (units: number) => data<PaymentResponse>(api.post(`${root}/quota/create`, { units })),
  createPackagePayment: (packageId: string) => data<PaymentResponse>(api.post(`${root}/package/create`, { package_id: packageId })),
  cancelSubscription: () => data<{ success: boolean; cancel_at?: string }>(api.post(`${root}/subscription/cancel`)),
  getOrders: (params?: { order_type?: string; status?: string; limit?: number }) =>
    data<{ orders: PaymentOrder[] }>(api.get(`${root}/orders`, { params })),
  getSubscriptionStatus: () => data<SubscriptionStatus>(api.get(`${root}/subscription/status`)),
  verifyPaymentSession: (sessionId: string) => data<PaymentVerificationResult>(api.get(`${root}/verify-session/${sessionId}`)),
  formatPrice: (amount: number, currency: string) => `${currency === 'CNY' ? '¥' : '$'}${amount}`,
  redirectToPayment(response: PaymentResponse) {
    const target = response.payment_url || response.checkout_url
    if (target) window.location.href = target
  }
}
export default paymentService
