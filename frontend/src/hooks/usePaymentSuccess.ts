import { useCallback, useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useSearchParams } from 'react-router-dom'
import { toast } from 'sonner'
import { PaymentVerificationResult, paymentService } from '../services/payment'

export interface PaymentSuccessOptions {
  onSuccess?: (result: PaymentVerificationResult) => void
  onError?: (error: string) => void
  maxAttempts?: number
  pollingInterval?: number
  showToast?: boolean
}
export interface PaymentSuccessState {
  isVerifying: boolean
  result: PaymentVerificationResult | null
  error: string | null
}
const initialState: PaymentSuccessState = { isVerifying: false, result: null, error: null }

export function usePaymentSuccess(options: PaymentSuccessOptions = {}): PaymentSuccessState {
  const { onSuccess, onError, maxAttempts = 15, pollingInterval = 2000, showToast = true } = options
  const { t } = useTranslation()
  const [params, setParams] = useSearchParams()
  const [state, setState] = useState(initialState)
  const visited = useRef(new Set<string>())

  const clear = useCallback(() => setParams({}), [setParams])
  const fail = useCallback((message: string, result: PaymentVerificationResult | null = null) => {
    if (showToast) toast.error(message, { id: 'payment-verify' })
    setState({ isVerifying: false, result, error: message })
    onError?.(message)
    clear()
  }, [clear, onError, showToast])

  const verify = useCallback(async (sessionId: string) => {
    if (showToast) toast.loading(t('payment.verifying'), { id: 'payment-verify' })
    setState({ isVerifying: true, result: null, error: null })
    for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
      try {
        const result = await paymentService.verifyPaymentSession(sessionId)
        if (result.status === 'completed') {
          if (showToast) toast.success(t('payment.success'), { id: 'payment-verify' })
          setState({ isVerifying: false, result, error: null })
          onSuccess?.(result)
          clear()
          return
        }
        if (result.status === 'failed' || result.status === 'not_found') {
          fail(result.message || t('payment.failed'), result)
          return
        }
      } catch (error) {
        fail(error instanceof Error ? error.message : t('payment.verificationError'))
        return
      }
      if (attempt + 1 < maxAttempts) await new Promise(resolve => setTimeout(resolve, pollingInterval))
    }
    const message = t('payment.verificationTimeout')
    if (showToast) toast.warning(message, { id: 'payment-verify' })
    setState({ isVerifying: false, result: null, error: message })
    onError?.(message)
    clear()
  }, [clear, fail, maxAttempts, onError, onSuccess, pollingInterval, showToast, t])

  useEffect(() => {
    const sessionId = params.get('session_id')
    if (params.get('payment') !== 'success' || !sessionId || state.isVerifying || visited.current.has(sessionId)) return
    visited.current.add(sessionId)
    void verify(sessionId)
  }, [params, state.isVerifying, verify])
  return state
}
export default usePaymentSuccess
