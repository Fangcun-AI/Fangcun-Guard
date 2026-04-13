import React, { useState, useEffect } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { useNavigate, useSearchParams, Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Lock, CheckCircle2, XCircle } from 'lucide-react'
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
  resetPasswordSchema,
  type ResetPasswordFormData,
} from '@/lib/validators'

const ResetPassword: React.FC = () => {
  const [loading, setLoading] = useState(false)
  const [verifyingToken, setVerifyingToken] = useState(true)
  const [tokenValid, setTokenValid] = useState(false)
  const [resetSuccess, setResetSuccess] = useState(false)
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const { t } = useTranslation()
  const token = searchParams.get('token')

  useEffect(() => {
    const verifyToken = async () => {
      if (!token) {
        setTokenValid(false)
        setVerifyingToken(false)
        return
      }

      try {
        await api.post('/api/v1/auth/verify-reset-token', null, {
          params: { token },
        })
        setTokenValid(true)
      } catch (error: any) {
        console.error('Token verification error:', error)
        setTokenValid(false)
        toast.error(t('resetPassword.tokenInvalid'))
      } finally {
        setVerifyingToken(false)
      }
    }

    verifyToken()
  }, [token, t])

  const form = useForm<ResetPasswordFormData>({
    resolver: zodResolver(resetPasswordSchema),
    defaultValues: {
      password: '',
      confirmPassword: '',
    },
  })

  const handleSubmit = async (values: ResetPasswordFormData) => {
    if (!token) {
      toast.error(t('resetPassword.tokenInvalid'))
      return
    }

    try {
      setLoading(true)
      await api.post('/api/v1/auth/reset-password', {
        token,
        new_password: values.password,
      })

      setResetSuccess(true)
      toast.success(t('resetPassword.resetSuccess'))

      // Redirect to login after 3 seconds
      setTimeout(() => {
        navigate('/login')
      }, 3000)
    } catch (error: any) {
      console.error('Reset password error:', error)
      toast.error(error.response?.data?.detail || t('resetPassword.resetFailed'))
    } finally {
      setLoading(false)
    }
  }

  if (verifyingToken) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#09090b] p-5">
        <div className="w-full max-w-md">
          <Card className="border-zinc-800 bg-zinc-900/50 backdrop-blur-xl">
            <CardContent className="flex flex-col items-center justify-center py-16">
              <div className="h-12 w-12 animate-spin rounded-full border-4 border-primary border-t-transparent"></div>
              <p className="mt-4 text-zinc-500">{t('common.loading')}</p>
            </CardContent>
          </Card>
        </div>
      </div>
    )
  }

  if (!tokenValid) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#09090b] p-5">
        <div className="w-full max-w-md">
          <Card className="border-zinc-800 bg-zinc-900/50 backdrop-blur-xl relative">
            {/* Language Switcher */}
            <div className="absolute top-4 right-4 z-10">
              <LanguageSwitcher />
            </div>

            <CardHeader className="text-center space-y-2 pb-6">
              <h1 className="text-3xl font-bold text-white">
                {t('resetPassword.title')}
              </h1>
            </CardHeader>

            <CardContent className="space-y-6">
              <Alert variant="destructive">
                <XCircle className="h-5 w-5" />
                <AlertDescription className="ml-2">
                  <p className="font-medium mb-1">{t('resetPassword.tokenInvalid')}</p>
                  <p className="text-sm">{t('resetPassword.tokenExpired')}</p>
                </AlertDescription>
              </Alert>

              <div className="space-y-3">
                <Link to="/forgot-password">
                  <Button className="w-full h-12 text-base font-medium bg-indigo-600 hover:bg-indigo-500 text-white">
                    {t('forgotPassword.sendResetLink')}
                  </Button>
                </Link>
                <div className="text-center">
                  <Link to="/login" className="text-sm text-indigo-400 hover:text-indigo-300 hover:underline">
                    {t('resetPassword.backToLogin')}
                  </Link>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    )
  }

  if (resetSuccess) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#09090b] p-5">
        <div className="w-full max-w-md">
          <Card className="border-zinc-800 bg-zinc-900/50 backdrop-blur-xl relative">
            {/* Language Switcher */}
            <div className="absolute top-4 right-4 z-10">
              <LanguageSwitcher />
            </div>

            <CardHeader className="text-center space-y-2 pb-6">
              <h1 className="text-3xl font-bold text-white">
                {t('resetPassword.title')}
              </h1>
              <p className="text-zinc-400 text-base">
                {t('resetPassword.resetSuccess')}
              </p>
            </CardHeader>

            <CardContent className="space-y-6">
              <Alert className="border-green-500/20 bg-green-500/10">
                <CheckCircle2 className="h-5 w-5 text-green-400" />
                <AlertDescription className="ml-2 text-green-300">
                  <p className="font-medium mb-1">{t('resetPassword.resetSuccess')}</p>
                  <p className="text-sm">{t('resetPassword.resetSuccessDesc')}</p>
                </AlertDescription>
              </Alert>

              <Link to="/login">
                <Button className="w-full h-12 text-base font-medium bg-indigo-600 hover:bg-indigo-500 text-white">
                  {t('resetPassword.backToLogin')}
                </Button>
              </Link>
            </CardContent>

            <CardFooter className="flex-col">
              <p className="text-xs text-zinc-500 text-center">
                {t('resetPassword.copyright')}
              </p>
            </CardFooter>
          </Card>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-[#09090b] p-5">
      <div className="w-full max-w-md">
        <Card className="border-zinc-800 bg-zinc-900/50 backdrop-blur-xl relative">
          {/* Language Switcher */}
          <div className="absolute top-4 right-4 z-10">
            <LanguageSwitcher />
          </div>

          <CardHeader className="text-center space-y-2 pb-8">
            <h1 className="text-3xl font-bold text-white">
              {t('resetPassword.title')}
            </h1>
            <p className="text-zinc-400 text-base">
              {t('resetPassword.subtitle')}
            </p>
          </CardHeader>

          <CardContent>
            <Form {...form}>
              <form onSubmit={form.handleSubmit(handleSubmit)} className="space-y-5">
                <FormField
                  control={form.control}
                  name="password"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel className="text-zinc-300">{t('resetPassword.newPasswordPlaceholder')}</FormLabel>
                      <FormControl>
                        <div className="relative">
                          <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-zinc-500" />
                          <Input
                            type="password"
                            placeholder={t('resetPassword.newPasswordPlaceholder')}
                            className="pl-10 h-12 bg-zinc-800/50 border-zinc-700 text-white placeholder:text-zinc-500 focus:border-indigo-500 focus:ring-indigo-500/20"
                            autoComplete="new-password"
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
                  name="confirmPassword"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel className="text-zinc-300">{t('resetPassword.confirmPasswordPlaceholder')}</FormLabel>
                      <FormControl>
                        <div className="relative">
                          <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-zinc-500" />
                          <Input
                            type="password"
                            placeholder={t('resetPassword.confirmPasswordPlaceholder')}
                            className="pl-10 h-12 bg-zinc-800/50 border-zinc-700 text-white placeholder:text-zinc-500 focus:border-indigo-500 focus:ring-indigo-500/20"
                            autoComplete="new-password"
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
                    ? t('resetPassword.resetting') || 'Resetting...'
                    : t('resetPassword.resetButton')}
                </Button>
              </form>
            </Form>
          </CardContent>

          <CardFooter className="flex-col space-y-4">
            <div className="text-center text-sm text-zinc-500">
              <Link to="/login" className="text-indigo-400 hover:text-indigo-300 hover:underline font-medium">
                {t('resetPassword.backToLogin')}
              </Link>
            </div>
            <p className="text-xs text-zinc-500 text-center">
              {t('resetPassword.copyright')}
            </p>
          </CardFooter>
        </Card>
      </div>
    </div>
  )
}

export default ResetPassword
