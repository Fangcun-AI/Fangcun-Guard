import React, { useCallback, useEffect, useState } from 'react'
import { Check, Edit, Info } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import type { ColumnDef } from '@tanstack/react-table'

import { DataTable } from '@/components/data-table/DataTable'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { InputNumber } from '@/components/ui/input-number'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { useApplication } from '@/contexts/ApplicationContext'
import { useAuth } from '@/contexts/AuthContext'
import { sensitivityThresholdApi } from '@/features/configuration/api'

type LevelKey = 'high' | 'medium' | 'low'
type ThresholdConfig = {
  high_sensitivity_threshold: number
  medium_sensitivity_threshold: number
  low_sensitivity_threshold: number
  sensitivity_trigger_level: string
}
type SensitivityLevel = {
  key: LevelKey
  name: string
  threshold: number
  description: string
  target: string
}

const levels: Array<[LevelKey, string, string]> = [
  ['high', 'strictestDetection', 'highSensitivityTarget'],
  ['medium', 'balancedDetection', 'mediumSensitivityTarget'],
  ['low', 'loosestDetection', 'lowSensitivityTarget'],
]
const variants: Record<LevelKey, 'destructive' | 'default' | 'outline'> = {
  high: 'destructive',
  medium: 'default',
  low: 'outline',
}
const thresholdField = (level: LevelKey) => `${level}_sensitivity_threshold` as const

const SensitivityThresholdManagement: React.FC = () => {
  const { t } = useTranslation()
  const { currentApplicationId } = useApplication()
  const { onUserSwitch } = useAuth()
  const [config, setConfig] = useState<ThresholdConfig | null>(null)
  const [editing, setEditing] = useState<SensitivityLevel[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [dialogOpen, setDialogOpen] = useState(false)

  const loadConfig = useCallback(async () => {
    setLoading(true)
    try {
      setConfig(await sensitivityThresholdApi.get() as ThresholdConfig)
    } catch (error) {
      console.error('Failed to load sensitivity threshold config:', error)
      toast.error(t('sensitivity.fetchFailed'))
    } finally {
      setLoading(false)
    }
  }, [t])

  useEffect(() => {
    if (currentApplicationId) void loadConfig()
  }, [currentApplicationId, loadConfig])

  useEffect(() => onUserSwitch(loadConfig), [loadConfig, onUserSwitch])

  const describe = (value: ThresholdConfig): SensitivityLevel[] => levels.map(([key, description, target]) => ({
    key,
    name: t(`sensitivity.${key}`),
    threshold: value[thresholdField(key)],
    description: t(`sensitivity.${description}`),
    target: t(`sensitivity.${target}`),
  }))
  const openEditor = () => {
    if (!config) return
    setEditing(describe(config))
    setDialogOpen(true)
  }
  const saveThresholds = async () => {
    const values = Object.fromEntries(editing.map(({ key, threshold }) => [key, threshold])) as Record<LevelKey, number>
    const ordered = values.low > values.medium && values.medium > values.high
    if (!Object.values(values).every((value) => value >= 0 && value <= 1) || !ordered) {
      toast.error(t(ordered ? 'sensitivity.invalidThreshold' : 'sensitivity.thresholdOrder'))
      return
    }
    const next = {
      high_sensitivity_threshold: values.high,
      medium_sensitivity_threshold: values.medium,
      low_sensitivity_threshold: values.low,
      sensitivity_trigger_level: config?.sensitivity_trigger_level || 'medium',
    }
    await updateConfig(next, t('sensitivity.saveSuccess'), () => setDialogOpen(false))
  }
  const updateConfig = async (next: ThresholdConfig, message: string, afterSave?: () => void) => {
    setSaving(true)
    try {
      await sensitivityThresholdApi.update(next)
      setConfig(next)
      afterSave?.()
      toast.success(message)
    } catch (error) {
      console.error('Failed to update sensitivity threshold config:', error)
      toast.error(t('sensitivity.fetchFailed'))
    } finally {
      setSaving(false)
    }
  }
  const changeTrigger = (sensitivity_trigger_level: string) => {
    if (!config) return
    void updateConfig(
      { ...config, sensitivity_trigger_level },
      t('sensitivity.levelChangeSuccess', { level: t(`sensitivity.${sensitivity_trigger_level}`) }),
    )
  }

  const columns: ColumnDef<SensitivityLevel>[] = [
    { accessorKey: 'name', header: t('sensitivity.levelName'), cell: ({ row }) => <Badge variant={variants[row.original.key]}>{row.original.name}</Badge> },
    { accessorKey: 'threshold', header: t('sensitivity.threshold'), cell: ({ row }) => <code className="rounded bg-zinc-800/50 px-2 py-1 text-xs">{row.original.threshold.toFixed(2)}</code> },
    { accessorKey: 'description', header: t('common.description') },
    { accessorKey: 'target', header: t('sensitivity.targetScenario') },
  ]
  const editColumns: ColumnDef<SensitivityLevel>[] = [
    { accessorKey: 'name', header: t('sensitivity.sensitivityLevel'), cell: ({ row }) => <Badge variant={variants[row.original.key]}>{row.original.name}</Badge> },
    { accessorKey: 'threshold', header: t('sensitivity.probabilityThreshold'), cell: ({ row }) => (
      <InputNumber
        value={row.original.threshold}
        min={0}
        max={1}
        className="w-full"
        onChange={(threshold) => threshold !== undefined && setEditing(editing.map((level) => level.key === row.original.key ? { ...level, threshold } : level))}
      />
    ) },
  ]

  if (loading) return <div className="flex items-center justify-center p-12"><div className="mx-auto h-12 w-12 animate-spin rounded-full border-b-2 border-indigo-500" /></div>
  if (!config) return <div>{t('sensitivity.fetchFailed')}</div>

  const currentLevels = describe(config)
  const currentThreshold = config[thresholdField(config.sensitivity_trigger_level as LevelKey)]

  return (
    <div className="space-y-6">
      <Card>
        <CardContent className="space-y-6 pt-6">
          <div>
            <h3 className="flex items-center gap-2 text-lg font-semibold"><Info className="h-5 w-5" />{t('sensitivity.title')}</h3>
            <p className="mt-2 text-zinc-400">{t('sensitivity.description')}</p>
          </div>
          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-base">{t('sensitivity.currentSensitivityLevel')}</CardTitle>
              <Button onClick={openEditor} size="sm"><Edit className="mr-2 h-4 w-4" />{t('sensitivity.editThresholds')}</Button>
            </CardHeader>
            <CardContent><DataTable columns={columns} data={currentLevels} pagination={false} /></CardContent>
          </Card>
          <Card>
            <CardHeader><CardTitle className="text-base">{t('sensitivity.currentSensitivityLevel')}</CardTitle></CardHeader>
            <CardContent className="space-y-4">
              <div className="rounded-lg border border-indigo-800 bg-indigo-950/50 p-4">
                <p className="mb-2 text-sm font-medium text-indigo-200">{t('sensitivity.configurationExplanation')}</p>
                <div className="space-y-1 text-xs text-indigo-300">
                  {levels.map(([key]) => <p key={key}>• {t(`sensitivity.${key}SensitivityDesc`, { threshold: config[thresholdField(key)] })}</p>)}
                </div>
              </div>
              <div className="flex items-center gap-3">
                <span className="font-medium">{t('sensitivity.currentLevel')}：</span>
                <Select value={config.sensitivity_trigger_level} onValueChange={changeTrigger} disabled={saving}>
                  <SelectTrigger className="w-[200px]"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {levels.map(([key]) => <SelectItem key={key} value={key}><div className="flex items-center gap-2"><Badge variant={variants[key]}>{t(`sensitivity.${key}`)}</Badge><span>{t('sensitivity.sensitivityLabel')}</span></div></SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              <div className="mt-2 rounded border border-dashed border-zinc-700 bg-zinc-800/50 p-2">
                <p className="text-xs text-zinc-400">{t('sensitivity.currentDetectionRule', { threshold: currentThreshold })}</p>
              </div>
            </CardContent>
          </Card>
        </CardContent>
      </Card>
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="sm:max-w-[800px]">
          <DialogHeader><DialogTitle>{t('sensitivity.editThresholds')}</DialogTitle></DialogHeader>
          <div className="space-y-4">
            <div className="rounded-lg border border-yellow-800 bg-yellow-950/30 p-4">
              <p className="mb-2 text-sm font-medium text-yellow-200">{t('sensitivity.editInstructions')}</p>
              <div className="space-y-1 text-xs text-yellow-300"><p>• {t('sensitivity.editDescription1')}</p><p>• {t('sensitivity.editDescription2')}</p></div>
            </div>
            <DataTable columns={editColumns} data={editing} pagination={false} />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>{t('common.cancel')}</Button>
            <Button onClick={() => void saveThresholds()} disabled={saving}><Check className="mr-2 h-4 w-4" />{t('common.save')}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}

export default SensitivityThresholdManagement
