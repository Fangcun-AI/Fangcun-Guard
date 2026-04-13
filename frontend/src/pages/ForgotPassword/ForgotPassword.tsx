import React, { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Mail, CheckCircle2, Shield } from 'lucide-react'
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
import { Alert, AlertDescription } from '@/components/ui/alert'
import LanguageSwitcher from '../../components/LanguageSwitcher/LanguageSwitcher'
import api from '../../services/api'

import {
  forgotPasswordSchema,
  type ForgotPasswordFormData,
} from '@/lib/validators'

const ForgotPassword: React.FC = () => {
  const [loading, setLoading] = useState(false)
  const [emailSent, setEmailSent] = useState(false)
  const [submittedEmail, setSubmittedEmail] = useState('')
  const { t, i18n } = useTranslation()

  const form = useForm<ForgotPasswordFormData>({
    resolver: zodResolver(forgotPasswordSchema),
    defaultValues: {
      email: '',
    },
  })

  const handleSubmit = async (values: ForgotPasswordFormData) => {
    try {
      setLoading(true)
      const currentLanguage = i18n.language || localStorage.getItem('i18nextLng') || 'en'

      await api.post('/api/v1/auth/forgot-password', {
        email: values.email,
        language: currentLanguage,
      })

      setSubmittedEmail(values.email)
      setEmailSent(true)
    } catch (error: any) {
      console.error('Forgot password error:', error)
      toast.error(error.response?.data?.detail || t('forgotPassword.sendFailed'))
    } finally {
      setLoading(false)
    }
  }

  if (emailSent) {
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
              {t('forgotPassword.brandingTitle') || 'AI Safety Platform'}
            </h2>
            <p className="text-zinc-400 text-lg max-w-md leading-relaxed">
              {t('forgotPassword.brandingSubtitle') || 'The only production-ready open-source AI guardrails platform for enterprise AI applications.'}
            </p>
          </div>
          <div className="relative z-10 text-sm text-zinc-600">
            {t('forgotPassword.copyright')}
          </div>
        </div>

        {/* Right side - Success Message */}
        <div className="flex-1 flex items-center justify-center p-8 relative">
          <div className="w-full max-w-md">
            <Card className="border-zinc-800 bg-zinc-900/50 backdrop-blur-xl">
              <CardHeader className="space-y-1 pb-6">
                <h1 className="text-2xl font-bold text-white">
                  {t('forgotPassword.title')}
                </h1>
                <p className="text-zinc-400 text-sm">
                  {t('forgotPassword.emailSent')}
                </p>
              </CardHeader>

            <CardContent className="space-y-6">
              <Alert className="border-green-500/20 bg-green-500/10">
                <CheckCircle2 className="h-5 w-5 text-green-400" />
                <AlertDescription className="ml-2 text-green-300">
                  <p className="font-medium mb-2">{t('forgotPassword.emailSent')}</p>
                  <p className="text-sm">
                    {t('forgotPassword.emailSentDesc', { email: submittedEmail })}
                  </p>
                  <p className="text-sm mt-3">
                    {t('forgotPassword.checkSpam')}
                  </p>
                </AlertDescription>
              </Alert>

              <Link to="/login">
                <Button className="w-full h-12 text-base font-medium bg-indigo-600 hover:bg-indigo-500 text-white">
                  {t('forgotPassword.backToLogin')}
                </Button>
              </Link>
            </CardContent>

            </Card>

            {/* Mobile Copyright */}
            <p className="text-xs text-zinc-600 text-center mt-6 lg:hidden">
              {t('forgotPassword.copyright')}
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
            {t('forgotPassword.brandingTitle') || 'AI Safety Platform'}
          </h2>
          <p className="text-zinc-400 text-lg max-w-md leading-relaxed">
            {t('forgotPassword.brandingSubtitle') || 'The only production-ready open-source AI guardrails platform for enterprise AI applications.'}
          </p>
        </div>
        <div className="relative z-10 text-sm text-zinc-600">
          {t('forgotPassword.copyright')}
        </div>
      </div>

      {/* Right side - Form */}
      <div className="flex-1 flex items-center justify-center p-8 relative">
        <div className="w-full max-w-md">
          <Card className="border-zinc-800 bg-zinc-900/50 backdrop-blur-xl">
            <CardHeader className="space-y-1 pb-6">
              <h1 className="text-2xl font-bold text-white">
                {t('forgotPassword.title')}
              </h1>
              <p className="text-zinc-400 text-sm">
                {t('forgotPassword.subtitle')}
              </p>
            </CardHeader>

          <CardContent>
            <Form {...form}>
              <form onSubmit={form.handleSubmit(handleSubmit)} className="space-y-5">
                <FormField
                  control={form.control}
                  name="email"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel className="text-zinc-300">{t('forgotPassword.emailPlaceholder')}</FormLabel>
                      <FormControl>
                        <div className="relative">
                          <Mail className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-zinc-500" />
                          <Input
                            type="email"
                            placeholder={t('forgotPassword.emailPlaceholder')}
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

                <Button
                  type="submit"
                  className="w-full h-12 text-base font-medium mt-6 bg-indigo-600 hover:bg-indigo-500 text-white"
                  disabled={loading}
                >
                  {loading
                    ? t('forgotPassword.sending') || 'Sending...'
                    : t('forgotPassword.sendResetLink')}
                </Button>
              </form>
            </Form>
          </CardContent>

            <CardFooter className="flex-col pt-6">
              <div className="text-center text-sm">
                <Link to="/login" className="text-indigo-400 hover:text-indigo-300 font-medium hover:underline">
                  {t('forgotPassword.backToLogin')}
                </Link>
              </div>
            </CardFooter>
          </Card>

          {/* Mobile Copyright */}
          <p className="text-xs text-zinc-600 text-center mt-6 lg:hidden">
            {t('forgotPassword.copyright')}
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

export default ForgotPassword
