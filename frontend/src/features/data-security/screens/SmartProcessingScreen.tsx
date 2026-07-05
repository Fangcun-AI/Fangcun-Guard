import { useEffect, useState } from 'react'
import { Info, Settings2 } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'

import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Switch } from '@/components/ui/switch'
import { useApplication } from '@/contexts/ApplicationContext'
import { useAuth } from '@/contexts/AuthContext'
import { dataLeakagePolicyApi } from '@/features/data-security/api'

type SettingKey = 'enable_format_detection' | 'enable_smart_segmentation'
type Settings = Record<SettingKey, boolean>
type ApplicationPolicy = Record<string, any> & {
  enable_format_detection_override: boolean | null
  enable_smart_segmentation_override: boolean | null
}

const defaults: Settings = { enable_format_detection: true, enable_smart_segmentation: true }
const settingKeys: SettingKey[] = ['enable_format_detection', 'enable_smart_segmentation']
const labels: Record<SettingKey, [string, string]> = {
  enable_format_detection: ['dataLeakagePolicy.enableFormatDetection', 'dataLeakagePolicy.enableFormatDetectionDesc'],
  enable_smart_segmentation: ['dataLeakagePolicy.enableSmartSegmentation', 'dataLeakagePolicy.enableSmartSegmentationDesc'],
}

const SmartProcessingScreen = () => {
  const { t } = useTranslation()
  const { currentApplicationId } = useApplication()
  const { onUserSwitch } = useAuth()
  const [loading, setLoading] = useState(false)
  const [policy, setPolicy] = useState<ApplicationPolicy | null>(null)
  const [settings, setSettings] = useState<Settings>(defaults)

  const load = async () => {
    if (!currentApplicationId) return
    setLoading(true)
    try {
      const data: ApplicationPolicy = await dataLeakagePolicyApi.getPolicy(currentApplicationId)
      setPolicy(data)
      setSettings({
        enable_format_detection: data.enable_format_detection_override ?? data.enable_format_detection ?? true,
        enable_smart_segmentation: data.enable_smart_segmentation_override ?? data.enable_smart_segmentation ?? true,
      })
    } catch (error) {
      console.error('Failed to fetch policy:', error)
      toast.error(t('dataLeakagePolicy.fetchPolicyFailed'))
    } finally {
      setLoading(false)
    }
  }
  useEffect(() => { void load() }, [currentApplicationId])
  useEffect(() => onUserSwitch(() => void load()), [onUserSwitch])

  const save = async () => {
    if (!currentApplicationId) {
      toast.error('No application selected')
      return
    }
    setLoading(true)
    try {
      await dataLeakagePolicyApi.updatePolicy(currentApplicationId, {
        ...settings,
        input_high_risk_action: policy?.input_high_risk_action_override,
        input_medium_risk_action: policy?.input_medium_risk_action_override,
        input_low_risk_action: policy?.input_low_risk_action_override,
        private_model_id: policy?.private_model_override,
        output_high_risk_anonymize: policy?.output_high_risk_anonymize_override,
        output_medium_risk_anonymize: policy?.output_medium_risk_anonymize_override,
        output_low_risk_anonymize: policy?.output_low_risk_anonymize_override,
      })
      toast.success(t('dataLeakagePolicy.savePolicySuccess'))
      void load()
    } catch (error: any) {
      console.error('Failed to save policy:', error)
      toast.error(error.response?.data?.error || error.response?.data?.detail || t('dataLeakagePolicy.savePolicyFailed'))
      setLoading(false)
    }
  }

  if (loading && !policy) {
    return <div className="flex h-64 items-center justify-center"><p>{t('dataLeakagePolicy.loading')}</p></div>
  }
  return (
    <div className="space-y-6">
      <Alert><Info className="h-4 w-4" /><AlertDescription>
        <p className="font-semibold">{t('dataSecurity.smartProcessingDescription')}</p>
        <p className="mt-1 text-sm">{t('dataSecurity.smartProcessingDescriptionDetail')}</p>
      </AlertDescription></Alert>
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2"><Settings2 className="h-5 w-5" />{t('dataSecurity.smartProcessingSettings')}</CardTitle>
          <CardDescription>{t('dataSecurity.smartProcessingSettingsDesc')}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {settingKeys.map((key) => (
            <div className="flex items-start justify-between rounded-lg border p-4" key={key}>
              <div className="flex-1 space-y-0.5">
                <p className="text-base font-medium">{t(labels[key][0])}</p>
                <p className="text-sm text-muted-foreground">{t(labels[key][1])}</p>
              </div>
              <Switch checked={settings[key]} onCheckedChange={(checked) => setSettings((state) => ({ ...state, [key]: checked }))} />
            </div>
          ))}
        </CardContent>
      </Card>
      <div className="flex justify-end"><Button disabled={loading} onClick={() => void save()}>
        {t(loading ? 'common.loading' : 'dataLeakagePolicy.savePolicy')}
      </Button></div>
    </div>
  )
}

export default SmartProcessingScreen
