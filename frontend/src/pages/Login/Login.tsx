import React, { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { useAuth } from '../../contexts/AuthContext'
import { useNavigate, useLocation, Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Mail, Lock, Shield } from 'lucide-react'
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
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Alert, AlertDescription } from '@/components/ui/alert'
import LanguageSwitcher from '../../components/LanguageSwitcher/LanguageSwitcher'

import { loginSchema, type LoginFormData } from '@/lib/validators'

const Login: React.FC = () => {
  const [loading, setLoading] = useState(false)
  const [showVerificationAlert, setShowVerificationAlert] = useState(false)
  const [unverifiedEmail, setUnverifiedEmail] = useState('')
  const [showPasswordChangeModal, setShowPasswordChangeModal] = useState(false)
  const [passwordMessage, setPasswordMessage] = useState('')

  const { login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const { t } = useTranslation()

  const from = (location.state as any)?.from?.pathname || '/dashboard'

  const form = useForm<LoginFormData>({
    resolver: zodResolver(loginSchema),
    defaultValues: {
      email: '',
      password: '',
    },
  })

  const onSubmit = async (values: LoginFormData) => {
    try {
      setLoading(true)
      setShowVerificationAlert(false)

      const currentLanguage = localStorage.getItem('i18nextLng') || 'en'
      const loginResult = await login(values.email, values.password, currentLanguage)

      if (loginResult.requiresPasswordChange) {
        setPasswordMessage(
          loginResult.passwordMessage ||
            'Your password does not meet current security requirements. Please update it.'
        )
        setShowPasswordChangeModal(true)
      } else {
        toast.success(t('login.loginSuccess'))
        navigate(from, { replace: true })
      }
    } catch (error: any) {
      console.error('Login error:', error)
      const errorMessage = error.response?.data?.detail || t('login.loginFailed')

      if (error.response?.status === 403 && errorMessage.includes('not activated')) {
        setUnverifiedEmail(values.email)
        setShowVerificationAlert(true)
      } else {
        toast.error(errorMessage)
      }
    } finally {
      setLoading(false)
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
            {t('login.brandingSubtitle') || 'Enterprise-grade AI Guardrails and Lightweight AI Security Gateway, with support for user-defined scanners and custom model training.'}
          </p>

          <div className="mt-12 space-y-4">
            {['Content Safety', 'Data Leakage Prevention', 'Security Gateway', 'Agent Safety'].map((feature) => (
              <div key={feature} className="flex items-center gap-3 text-zinc-500">
                <div className="h-1.5 w-1.5 rounded-full bg-indigo-500" />
                <span className="text-sm">{feature}</span>
              </div>
            ))}
          </div>
        </div>
        <div className="relative z-10 text-sm text-zinc-600">
          {t('login.copyright')}
        </div>
      </div>

      {/* Right side - Login Form */}
      <div className="flex-1 flex items-center justify-center p-8 relative">
        <div className="w-full max-w-md">
          {/* Mobile logo */}
          <div className="flex items-center gap-3 mb-8 lg:hidden">
            <div className="h-10 w-10 bg-indigo-500/10 rounded-xl flex items-center justify-center ring-1 ring-indigo-500/20">
              <Shield className="h-6 w-6 text-indigo-400" />
            </div>
            <h1 className="text-xl font-bold text-white">FangcunGuard</h1>
          </div>

          <Card className="border-zinc-800 bg-zinc-900/50 backdrop-blur-xl">
            <CardHeader className="space-y-1 pb-6">
              <h1 className="text-2xl font-bold text-white">
                {t('login.title')}
              </h1>
              <p className="text-zinc-400 text-sm">
                {t('login.subtitle')}
              </p>
            </CardHeader>

            <CardContent>
              {showVerificationAlert && (
                <Alert variant="destructive" className="mb-6 bg-red-500/10 border-red-500/20">
                  <AlertDescription className="space-y-3">
                    <div>
                      <p className="font-medium mb-1">{t('login.accountNotActivated')}</p>
                      <p className="text-sm">
                        {t('login.accountNotActivatedDesc', { email: unverifiedEmail })}
                      </p>
                    </div>
                    <div className="flex items-center gap-3 text-sm">
                      <Button
                        variant="link"
                        size="sm"
                        className="h-auto p-0 text-red-400 underline"
                        onClick={() =>
                          navigate(`/verify?email=${encodeURIComponent(unverifiedEmail)}`)
                        }
                      >
                        {t('login.goToVerifyPage')}
                      </Button>
                      <span className="text-red-500/40">|</span>
                      <Button
                        variant="link"
                        size="sm"
                        className="h-auto p-0 text-red-400 underline"
                        onClick={() => setShowVerificationAlert(false)}
                      >
                        {t('login.closeReminder')}
                      </Button>
                    </div>
                  </AlertDescription>
                </Alert>
              )}

              <Form {...form}>
                <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-5">
                  <FormField
                    control={form.control}
                    name="email"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel className="text-zinc-300">{t('login.emailPlaceholder')}</FormLabel>
                        <FormControl>
                          <div className="relative">
                            <Mail className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-zinc-500" />
                            <Input
                              type="email"
                              placeholder={t('login.emailPlaceholder')}
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
                    name="password"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel className="text-zinc-300">{t('login.passwordPlaceholder')}</FormLabel>
                        <FormControl>
                          <div className="relative">
                            <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-zinc-500" />
                            <Input
                              type="password"
                              placeholder={t('login.passwordPlaceholder')}
                              className="pl-10 h-12 bg-zinc-800/50 border-zinc-700 text-white placeholder:text-zinc-500 focus:border-indigo-500 focus:ring-indigo-500/20"
                              autoComplete="current-password"
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
                    {loading ? t('login.loggingIn') || 'Logging in...' : t('login.loginButton')}
                  </Button>
                </form>
              </Form>
            </CardContent>

            <CardFooter className="flex-col space-y-3 pt-6">
              <div className="flex flex-col gap-2 text-sm text-center">
                <div>
                  <span className="text-zinc-500">{t('login.noAccount')} </span>
                  <Link to="/register" className="text-indigo-400 hover:text-indigo-300 font-medium hover:underline">
                    {t('login.registerNow')}
                  </Link>
                </div>
                <div>
                  <Link to="/verify" className="text-zinc-500 hover:text-zinc-300 hover:underline">
                    {t('login.verifyPage')}
                  </Link>
                  <span className="text-zinc-600 mx-2">•</span>
                  <Link to="/forgot-password" className="text-zinc-500 hover:text-zinc-300 hover:underline">
                    {t('login.forgotPassword')}
                  </Link>
                </div>
              </div>
            </CardFooter>
          </Card>

          <p className="text-xs text-zinc-600 text-center mt-6 lg:hidden">
            {t('login.copyright')}
          </p>
        </div>

        <div className="absolute bottom-8 right-8">
          <div className="scale-75 opacity-60 hover:opacity-100 transition-opacity">
            <LanguageSwitcher />
          </div>
        </div>
      </div>

      <Dialog open={showPasswordChangeModal} onOpenChange={setShowPasswordChangeModal}>
        <DialogContent className="bg-zinc-900 border-zinc-800">
          <DialogHeader>
            <DialogTitle className="text-white">{t('login.passwordChangeRequired')}</DialogTitle>
            <DialogDescription className="space-y-2 pt-2 text-zinc-400">
              <p>{passwordMessage}</p>
              <p>{t('login.passwordChangeDescription')}</p>
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="gap-2">
            <Button
              variant="outline"
              onClick={() => setShowPasswordChangeModal(false)}
              className="border-zinc-700 text-zinc-300 hover:bg-zinc-800"
            >
              {t('login.changeLater')}
            </Button>
            <Button
              onClick={() => {
                setShowPasswordChangeModal(false)
                navigate('/account?tab=password')
              }}
              className="bg-indigo-600 hover:bg-indigo-500 text-white"
            >
              {t('login.changeNow')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}

export default Login
