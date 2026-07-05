import React, { useState } from 'react'
import { CreditCard, Loader2 } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import paymentService, { type PaymentResponse } from '@/services/payment'

interface PaymentButtonProps {
  type: 'subscription' | 'package' | 'quota_purchase'
  packageId?: string
  packageName?: string
  tierNumber?: number
  units?: number
  amount?: number
  currency?: string
  provider?: 'alipay' | 'stripe'
  onSuccess?: () => void
  onError?: (error: string) => void
  buttonText?: string
  buttonType?: 'primary' | 'default' | 'dashed' | 'link' | 'text'
  size?: 'small' | 'middle' | 'large'
  block?: boolean
  disabled?: boolean
}

const variants = { primary: 'default', default: 'outline', dashed: 'outline', link: 'link', text: 'outline' } as const
const sizes = { small: 'sm', middle: 'default', large: 'lg' } as const

const PaymentButton: React.FC<PaymentButtonProps> = ({
  type,
  packageId,
  packageName,
  tierNumber,
  units,
  amount = 0,
  currency = 'USD',
  provider = 'stripe',
  onSuccess,
  onError,
  buttonText,
  buttonType = 'primary',
  size = 'middle',
  block = false,
  disabled = false,
}) => {
  const { t } = useTranslation()
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)

  const createPayment = (): Promise<PaymentResponse> => {
    if (type === 'subscription') return paymentService.createSubscriptionPayment(tierNumber)
    if (type === 'package' && packageId) return paymentService.createPackagePayment(packageId)
    if (type === 'quota_purchase' && units) return paymentService.createQuotaPurchasePayment(units)
    return Promise.reject(new Error('Invalid payment type or missing required parameters'))
  }
  const fail = (message: string) => {
    toast.error(message)
    onError?.(message)
    setLoading(false)
    setOpen(false)
  }
  const pay = async () => {
    setLoading(true)
    try {
      const response = await createPayment()
      if (!response.success) return fail(response.error || t('payment.error.createFailed'))
      setTimeout(() => {
        paymentService.redirectToPayment(response)
        onSuccess?.()
      }, 500)
    } catch (error) {
      const apiError = error as { response?: { data?: { detail?: string } }; message?: string }
      fail(apiError.response?.data?.detail || apiError.message || t('payment.error.unknown'))
    }
  }
  const price = paymentService.formatPrice(amount, currency)
  const title = t(`payment.confirm.${type === 'subscription' ? 'subscriptionTitle' : type === 'quota_purchase' ? 'quotaTitle' : 'packageTitle'}`)
  const description = type === 'package'
    ? t('payment.confirm.packageContent', { name: packageName, price })
    : t(`payment.confirm.${type === 'subscription' ? 'subscriptionContent' : 'quotaContent'}`, { price })

  return <>
    <Button variant={variants[buttonType]} size={sizes[size]} className={block ? 'w-full' : ''} disabled={disabled} onClick={() => setOpen(true)}>
      <CreditCard className="mr-2 h-4 w-4" />{buttonText || t(type === 'subscription' ? 'payment.button.subscribe' : 'payment.button.purchase')}
    </Button>
    <Dialog open={open} onOpenChange={loading ? undefined : setOpen}>
      <DialogContent className={loading ? 'max-w-md' : 'max-w-lg'}>
        {loading ? <div className="py-10 text-center">
          <Loader2 className="mx-auto h-12 w-12 animate-spin text-indigo-500" />
          <div className="mt-6 text-base font-medium">{t(provider === 'alipay' ? 'payment.redirecting.alipay' : 'payment.redirecting.stripe')}</div>
          <div className="mt-3 text-sm text-muted-foreground">{t('payment.processing.pleaseWait')}</div>
        </div> : <>
          <DialogHeader><DialogTitle>{title}</DialogTitle><DialogDescription>{description}</DialogDescription></DialogHeader>
          <DialogFooter><Button variant="outline" onClick={() => setOpen(false)}>{t('common.cancel')}</Button><Button onClick={() => void pay()}>{t('payment.confirm.proceed')}</Button></DialogFooter>
        </>}
      </DialogContent>
    </Dialog>
  </>
}

export default PaymentButton
