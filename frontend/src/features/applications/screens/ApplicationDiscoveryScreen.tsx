import React, { useCallback, useEffect, useState } from 'react'
import { ArrowRight, Copy, ExternalLink, Eye, EyeOff, Info, RefreshCw, RotateCcw, Settings } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import { toast } from 'sonner'

import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { applicationsApi, type ApplicationRecord } from '@/features/applications/api'
import { authService } from '@/services/auth'
import { copyToClipboard } from '@/utils/clipboard'

const integrationGuide = 'https://github.com/fangcunguard/fangcunguard/blob/main/docs/THIRD_PARTY_GATEWAY_INTEGRATION.md'

const ApplicationDiscovery: React.FC = () => {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [apiKey, setApiKey] = useState('')
  const [recentApps, setRecentApps] = useState<ApplicationRecord[]>([])
  const [loading, setLoading] = useState(true)
  const [regenerating, setRegenerating] = useState(false)
  const [revealKey, setRevealKey] = useState(false)
  const [newKeyIssued, setNewKeyIssued] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [user, apps] = await Promise.all([authService.getCurrentUser(), applicationsApi.list()])
      setApiKey(user.api_key || '')
      setRecentApps(
        apps
          .filter(({ source }) => source === 'auto_discovery')
          .sort((left, right) => Date.parse(right.created_at) - Date.parse(left.created_at))
          .slice(0, 5),
      )
    } catch (error) {
      console.error('Failed to fetch application discovery data:', error)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const copyKey = async () => {
    try {
      await copyToClipboard(apiKey)
      toast.success(t('common.copied'))
    } catch (error) {
      console.error('Failed to copy API key:', error)
      toast.error(t('common.copyFailed'))
    }
  }
  const regenerate = async () => {
    setRegenerating(true)
    try {
      setApiKey((await authService.regenerateApiKey()).api_key)
      setNewKeyIssued(true)
      toast.success(t('common.apiKeyRegenerated'))
    } catch (error) {
      console.error('Failed to regenerate API key:', error)
      toast.error(t('common.apiKeyRegenerateFailed'))
    } finally {
      setRegenerating(false)
    }
  }
  const maskedKey = apiKey ? `${apiKey.slice(0, 12)}${'*'.repeat(20)}${apiKey.slice(-8)}` : ''

  return (
    <div className="space-y-6">
      <div><h1 className="text-2xl font-bold text-white">{t('applicationManagement.discovery.title')}</h1><p className="mt-1 text-zinc-400">{t('applicationManagement.discovery.description')}</p></div>
      <Alert className="border-indigo-800 bg-indigo-950/50"><Info className="h-5 w-5 text-indigo-400" /><AlertDescription className="text-indigo-300">{t('applicationManagement.discovery.overview')}</AlertDescription></Alert>
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <div><CardTitle className="flex items-center gap-2"><Settings className="h-5 w-5" />{t('applicationManagement.discovery.tenantApiKey')}</CardTitle><CardDescription>{t('applicationManagement.discovery.tenantApiKeyDesc')}</CardDescription></div>
          {apiKey && <Button variant="outline" size="sm" onClick={() => void regenerate()} disabled={regenerating} className="border-red-800 text-red-500 hover:bg-red-950/50 hover:text-red-400"><RotateCcw className={`mr-2 h-4 w-4 ${regenerating ? 'animate-spin' : ''}`} />{t('applicationManagement.discovery.regenerateApiKey')}</Button>}
        </CardHeader>
        <CardContent>
          {newKeyIssued && <Alert className="mb-4 border-green-800 bg-green-950/30"><AlertDescription className="text-green-300">{t('applicationManagement.discovery.newApiKeyWarning')}</AlertDescription></Alert>}
          <div className="flex items-center gap-2 rounded-md bg-zinc-800/50 p-3 font-mono text-sm">
            <code className="flex-1 break-all">{revealKey ? apiKey : maskedKey || t('common.loading')}</code>
            <Button variant="ghost" size="sm" onClick={() => setRevealKey(!revealKey)} disabled={!apiKey} title={t(revealKey ? 'common.hide' : 'common.show')}>{revealKey ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}</Button>
            <Button variant="ghost" size="sm" onClick={() => void copyKey()} disabled={!apiKey}><Copy className="h-4 w-4" /></Button>
          </div>
        </CardContent>
      </Card>
      {recentApps.length > 0 && <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <div><CardTitle>{t('applicationManagement.discovery.recentDiscovered')}</CardTitle><CardDescription>{t('applicationManagement.discovery.recentDiscoveredDesc')}</CardDescription></div>
          <Button variant="ghost" size="sm" onClick={() => void load()} disabled={loading}><RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} /></Button>
        </CardHeader>
        <CardContent className="space-y-2">
          {recentApps.map((app) => <div key={app.id} className="flex items-center justify-between rounded-md bg-zinc-800/50 p-3">
            <div className="flex items-center gap-3"><Badge variant="secondary" className="bg-indigo-900/50 text-indigo-300">{t('applicationManagement.sourceAutoDiscovery')}</Badge><span className="font-medium">{app.name}</span>{app.external_id && <span className="text-xs text-zinc-500">({app.external_id})</span>}</div>
            <span className="text-xs text-zinc-500">{new Date(app.created_at).toLocaleDateString()}</span>
          </div>)}
        </CardContent>
      </Card>}
      <div className="flex gap-4">
        <Button variant="outline" onClick={() => navigate('/applications/list')}>{t('applicationManagement.discovery.viewAllApps')}<ArrowRight className="ml-2 h-4 w-4" /></Button>
        <Button variant="link" className="text-indigo-400" onClick={() => window.open(integrationGuide, '_blank')}><ExternalLink className="mr-2 h-4 w-4" />{t('applicationManagement.discovery.viewDocs')}</Button>
      </div>
    </div>
  )
}

export default ApplicationDiscovery
