import { useEffect, useState } from 'react'
import { AlertTriangle, Lock, Save, Shield } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { useApplication } from '@/contexts/ApplicationContext'
import { useAuth } from '@/contexts/AuthContext'
import { gatewayPolicyApi } from '@/features/data-security/api'

type Level = 'high' | 'medium' | 'low'
type Action = 'block' | 'replace' | 'pass' | 'anonymize' | 'anonymize_restore' | 'switch_private_model'
type Group = 'general_input' | 'general_output' | 'input' | 'output'
type PolicyField = `${Group}_${Level}_risk_action`
type FormState = Record<PolicyField, Action> & { private_model_id: string | null }
type PrivateModel = {
  id: string
  config_name: string
  provider?: string
  is_default_private_model: boolean
}
type GatewayPolicy = Record<string, any> & {
  private_model_override: string | null
  available_private_models: PrivateModel[]
}

const levels: Level[] = ['high', 'medium', 'low']
const colors: Record<Level, string> = {
  high: 'border-red-200 bg-red-100 text-red-800',
  medium: 'border-yellow-200 bg-yellow-100 text-yellow-800',
  low: 'border-green-200 bg-green-100 text-green-800',
}
const defaults: FormState = {
  general_input_high_risk_action: 'block',
  general_input_medium_risk_action: 'replace',
  general_input_low_risk_action: 'pass',
  general_output_high_risk_action: 'block',
  general_output_medium_risk_action: 'replace',
  general_output_low_risk_action: 'pass',
  input_high_risk_action: 'block',
  input_medium_risk_action: 'anonymize',
  input_low_risk_action: 'pass',
  output_high_risk_action: 'block',
  output_medium_risk_action: 'anonymize',
  output_low_risk_action: 'pass',
  private_model_id: null,
}
const policyFields = Object.keys(defaults).filter((field) => field !== 'private_model_id') as PolicyField[]
const actionKeys: Record<Action, string> = {
  block: 'gateway.actionBlock',
  replace: 'gateway.actionReplace',
  pass: 'gateway.actionPass',
  anonymize: 'gateway.actionAnonymize',
  anonymize_restore: 'gateway.actionAnonymizeRestore',
  switch_private_model: 'gateway.actionSwitchPrivate',
}

const SecurityPolicyScreen = () => {
  const { t } = useTranslation()
  const { onUserSwitch } = useAuth()
  const { currentApplicationId } = useApplication()
  const [policy, setPolicy] = useState<GatewayPolicy | null>(null)
  const [form, setForm] = useState<FormState>(defaults)
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [tab, setTab] = useState<'general' | 'data-leakage'>('general')

  const load = async () => {
    if (!currentApplicationId) return
    setLoading(true)
    try {
      const data: GatewayPolicy = await gatewayPolicyApi.getPolicy(currentApplicationId)
      const next = { ...defaults }
      policyFields.forEach((field) => {
        next[field] = data[`${field}_override`] || data[field] || defaults[field]
      })
      next.private_model_id = data.private_model_override
      setPolicy(data)
      setForm(next)
    } catch (error) {
      console.error('Failed to fetch policy:', error)
      toast.error(t('gateway.fetchPolicyFailed'))
    } finally {
      setLoading(false)
    }
  }
  useEffect(() => { void load() }, [currentApplicationId])
  useEffect(() => onUserSwitch(() => void load()), [onUserSwitch])

  const save = async () => {
    if (!currentApplicationId) return
    setSaving(true)
    try {
      await gatewayPolicyApi.updatePolicy(currentApplicationId, form)
      toast.success(t('gateway.policySaved'))
      void load()
    } catch (error) {
      console.error('Failed to save policy:', error)
      toast.error(t('gateway.savePolicyFailed'))
    } finally {
      setSaving(false)
    }
  }
  const actions = (values: Action[]) => values.map((value) => ({ value, label: t(actionKeys[value]) }))
  const generalActions = actions(['block', 'replace', 'pass'])
  const inputActions = actions(['block', 'switch_private_model', 'anonymize', 'anonymize_restore', 'pass'])
  const outputActions = actions(['block', 'anonymize', 'pass'])
  const hasPrivateModels = Boolean(policy?.available_private_models?.length)

  const PolicyGroup = ({ group, title, description, choices }: {
    group: Group
    title: string
    description: string
    choices: Array<{ value: Action; label: string }>
  }) => (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">{title}</CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-1">
        {levels.map((level) => {
          const field = `${group}_${level}_risk_action` as PolicyField
          return (
            <div className="flex items-center justify-between border-b py-3 last:border-b-0" key={field}>
              <Badge className={colors[level]} variant="outline">{t(`gateway.${level}Risk`)}</Badge>
              <Select value={form[field]} onValueChange={(value) => setForm((state) => ({ ...state, [field]: value as Action }))}>
                <SelectTrigger className="w-[200px]"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {choices.map((choice) => (
                    <SelectItem
                      disabled={choice.value === 'switch_private_model' && !hasPrivateModels}
                      key={choice.value}
                      value={choice.value}
                    >
                      {choice.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )
        })}
      </CardContent>
    </Card>
  )

  if (loading) {
    return <Card><CardHeader><Skeleton className="h-6 w-48" /><Skeleton className="mt-2 h-4 w-96" /></CardHeader><CardContent><Skeleton className="h-64 w-full" /></CardContent></Card>
  }
  if (!currentApplicationId) {
    return <Card><CardContent className="py-8 text-center text-muted-foreground">{t('gateway.selectApplicationFirst')}</CardContent></Card>
  }
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0">
        <div className="flex items-center gap-2">
          <Shield className="h-5 w-5" />
          <div><CardTitle>{t('gateway.securityPolicyTitle')}</CardTitle><CardDescription>{t('gateway.securityPolicyDescription')}</CardDescription></div>
        </div>
        <Button disabled={saving} onClick={() => void save()}><Save className="mr-1 h-4 w-4" />{t(saving ? 'common.saving' : 'common.save')}</Button>
      </CardHeader>
      <CardContent>
        <Tabs className="w-full" value={tab} onValueChange={(value) => setTab(value as typeof tab)}>
          <TabsList className="grid w-full grid-cols-2">
            <TabsTrigger className="flex items-center gap-2" value="general"><AlertTriangle className="h-4 w-4" />{t('gateway.generalRiskPolicy')}</TabsTrigger>
            <TabsTrigger className="flex items-center gap-2" value="data-leakage"><Lock className="h-4 w-4" />{t('gateway.dataLeakagePolicy')}</TabsTrigger>
          </TabsList>
          <TabsContent className="mt-4 space-y-4" value="general">
            <PolicyGroup group="general_input" title={t('gateway.generalInputPolicyTitle')} description={t('gateway.generalInputPolicyDesc')} choices={generalActions} />
            <PolicyGroup group="general_output" title={t('gateway.generalOutputPolicyTitle')} description={t('gateway.generalOutputPolicyDesc')} choices={generalActions} />
          </TabsContent>
          <TabsContent className="mt-4 space-y-4" value="data-leakage">
            {!hasPrivateModels && <div className="rounded-lg border border-orange-200 bg-orange-50 p-4 text-sm text-orange-800">{t('gateway.noPrivateModelsWarning')}</div>}
            <Card>
              <CardHeader><CardTitle className="text-base">{t('gateway.privateModelSelection')}</CardTitle><CardDescription>{t('gateway.privateModelSelectionDesc')}</CardDescription></CardHeader>
              <CardContent>
                <Select disabled={!hasPrivateModels} value={form.private_model_id || 'default'} onValueChange={(value) => setForm((state) => ({ ...state, private_model_id: value === 'default' ? null : value }))}>
                  <SelectTrigger><SelectValue placeholder={t('gateway.selectPrivateModel')} /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="default">{t('gateway.useDefaultPrivateModel')}</SelectItem>
                    {policy?.available_private_models?.map((model) => <SelectItem key={model.id} value={model.id}>{model.config_name}{model.is_default_private_model && ` [${t('gateway.defaultBadge')}]`}{model.provider && ` (${model.provider})`}</SelectItem>)}
                  </SelectContent>
                </Select>
              </CardContent>
            </Card>
            <PolicyGroup group="input" title={t('gateway.inputPolicy')} description={t('gateway.inputPolicyDesc')} choices={inputActions} />
            <PolicyGroup group="output" title={t('gateway.outputPolicy')} description={t('gateway.outputPolicyDesc')} choices={outputActions} />
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  )
}

export default SecurityPolicyScreen
