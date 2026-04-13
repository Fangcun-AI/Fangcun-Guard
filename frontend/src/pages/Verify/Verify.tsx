import React, { useState, useEffect } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { useNavigate, Link, useSearchParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Mail, ShieldCheck, Shield } from 'lucide-react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardFooter, CardHeader } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form'
import LanguageSwitcher from '../../components/LanguageSwitcher/LanguageSwitcher'

import {
  emailVerificationSchema,
  type EmailVerificationFormData,
} from '@/lib/validators'

const Verify: React.FC = () => {
  const { t, i18n } = useTranslation()
  const [loading, setLoading] = useState(false)
  const [resendLoading, setResendLoading] = useState(false)
  const [countdown, setCountdown] = useState(0)
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()

  const initialEmail = searchParams.get('email') || ''

  // Countdown timer
  useEffect(() => {
    let timer: NodeJS.Timeout
    if (countdown > 0) {
      timer = setTimeout(() => {
        setCountdown(countdown - 1)
      }, 1000)
    }
    return () => {
      if (timer) clearTimeout(timer)
    }
  }, [countdown])

  const form = useForm<EmailVerificationFormData>({
    resolver: zodResolver(emailVerificationSchema),
    defaultValues: {
      email: initialEmail,
      verificationCode: '',
    },
  })

  const handleVerify = async (values: EmailVerificationFormData) => {
    try {
      setLoading(true)

      const response = await fetch('/api/v1/users/verify-email', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          email: values.email,
          verification_code: values.verificationCode,
        }),
      })

      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.detail || t('verify.verifyFailed'))
      }

      toast.success(t('verify.verifySuccess'))
      setTimeout(() => {
        navigate('/login')
      }, 1500)
    } catch (error: any) {
      toast.error(error.message)
    } finally {
      setLoading(false)
    }
  }

  const handleResendCode = async () => {
    const email = form.getValues('email')
    if (!email) {
      toast.error(t('verify.emailRequired'))
      return
    }

    try {
      setResendLoading(true)

      const response = await fetch('/api/v1/users/resend-verification-code', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          email: email,
          language: i18n.language,
        }),
      })

      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.detail || t('verify.resendFailed'))
      }

      setCountdown(60)
      toast.success(t('verify.resendSuccess'))
    } catch (error: any) {
      toast.error(error.message)
    } finally {
      setResendLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex bg-[#09090b] relative overflow-hidden">
      {/* Background glow effects */}
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute top-1/4 left-1/4 w-[500px] h-[500px] bg-indigo-500/8 rounded-full blur-3xl" />
        <div className="absolute bottom-1/4 right-1/3 w-[400px] h-[400px] bg-cyan-500/5 rounded-full blur-3xl" />
      </div>

      {/* Left side - Branding */}
      <div className="hidden lg:flex lg:w-1/2 p-12 flex-col justify-between relative">
        <div className="relative z-10">
          <div className="flex items-center gap-3 mb-12">
            <div className="h-12 w-12 bg-indigo-500/10 backdrop-blur-sm rounded-xl flex items-center justify-center ring-1 ring-indigo-500/20">
              <Shield className="h-7 w-7 text-indigo-400" />
            </div>
            <h1 className="text-2xl font-bold text-white">FangcunGuard</h1>
          </div>
          <h2 className="text-5xl font-bold bg-gradient-to-r from-white via-indigo-200 to-indigo-400 bg-clip-text text-transparent mb-6 leading-tight">
            {t('login.brandingTitle') || 'AI Safety Platform'}
          </h2>
          <p className="text-zinc-400 text-lg max-w-md leading-relaxed">
            {t('login.brandingSubtitle') || 'Enterprise-grade content moderation and security for AI applications'}
          </p>
        </div>
        <div className="relative z-10 text-sm text-zinc-600">
          {t('login.copyright')}
        </div>
      </div>

      {/* Right side - Verify Form */}
      <div className="flex-1 flex items-center justify-center p-8 relative">
        <div className="w-full max-w-md">
          <Card className="border-zinc-800 bg-zinc-900/50 backdrop-blur-xl">
            <CardHeader className="space-y-1 pb-6">
              <h1 className="text-2xl font-bold text-white">
                {t('login.title')}
              </h1>
              <p className="text-zinc-400 text-sm">
                {t('verify.title')}
              </p>
            </CardHeader>

            <CardContent>
              <Form {...form}>
                <form onSubmit={form.handleSubmit(handleVerify)} className="space-y-5">
                  <FormField
                    control={form.control}
                    name="email"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel className="text-zinc-300">{t('register.email')}</FormLabel>
                        <FormControl>
                          <div className="relative">
                            <Mail className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-zinc-500" />
                            <Input
                              type="email"
                              placeholder={t('verify.emailPlaceholder')}
                              className="pl-10 h-12 bg-zinc-800/50 border-zinc-700 text-white placeholder:text-zinc-500 focus:border-indigo-500 focus:ring-indigo-500/20"
                              autoComplete="email"
                              {...field}
                            />
                          </div>
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <FormField
                    control={form.control}
                    name="verificationCode"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel className="text-zinc-300">{t('register.verificationCode')}</FormLabel>
                        <FormControl>
                          <div className="relative">
                            <ShieldCheck className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-zinc-500" />
                            <Input
                              placeholder={t('verify.verificationCodePlaceholder')}
                              className="pl-10 h-12 text-center text-lg tracking-widest bg-zinc-800/50 border-zinc-700 text-white placeholder:text-zinc-500 focus:border-indigo-500 focus:ring-indigo-500/20"
                              maxLength={6}
                              {...field}
                            />
                          </div>
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <Button
                    type="submit"
                    className="w-full h-12 text-base font-medium mt-6 bg-indigo-600 hover:bg-indigo-500 text-white"
                    disabled={loading}
                  >
                    {loading ? t('verify.verifying') || 'Verifying...' : t('verify.verifyButton')}
                  </Button>

                  <div className="space-y-3 pt-2">
                    <div className="text-center text-sm">
                      <span className="text-zinc-500">{t('register.resendCodeQuestion')} </span>
                      <Button
                        type="button"
                        variant="link"
                        className="h-auto p-0 text-indigo-400 hover:text-indigo-300"
                        onClick={handleResendCode}
                        disabled={countdown > 0 || resendLoading}
                      >
                        {countdown > 0
                          ? t('verify.resendCodeCountdown', { count: countdown })
                          : t('verify.resendCode')}
                      </Button>
                    </div>

                    <div className="flex items-center justify-center gap-2 text-sm">
                      <Link to="/register" className="text-zinc-500 hover:text-zinc-300 hover:underline">
                        {t('register.backToRegister')}
                      </Link>
                      <span className="text-zinc-600">•</span>
                      <Link to="/login" className="text-zinc-500 hover:text-zinc-300 hover:underline">
                        {t('register.loginNow')}
                      </Link>
                    </div>
                  </div>
                </form>
              </Form>
            </CardContent>
          </Card>

          {/* Mobile Copyright */}
          <p className="text-xs text-zinc-600 text-center mt-6 lg:hidden">
            {t('login.copyright')}
          </p>
        </div>

        {/* Language Switcher - Bottom right corner */}
        <div className="absolute bottom-8 right-8">
          <div className="scale-75 opacity-60 hover:opacity-100 transition-opacity">
            <LanguageSwitcher />
          </div>
        </div>
      </div>
    </div>
  )
}

export default Verify
