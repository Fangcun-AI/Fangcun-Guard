import { useEffect, useState } from 'react'
import { BookOpen, Edit2, FileText, Info, X } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Label } from '@/components/ui/label'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Textarea } from '@/components/ui/textarea'
import { fixedAnswerTemplatesApi } from '@/features/configuration/api'
import { KnowledgeBaseManagementScreen } from '@/features/knowledge-base/screens'

type Language = 'en' | 'zh'
type TemplateKind = 'security_risk' | 'data_leakage'
type TemplateKey = `${TemplateKind}_template`
type Templates = Record<TemplateKey, Record<Language, string>>

const dismissedKey = 'answerManagement.fixedAnswerInfoDismissed'
const defaults: Templates = {
  security_risk_template: {
    en: 'Request blocked by FangcunGuard due to possible violation of policy related to {scanner_name}.',
    zh: '请求已被FangcunGuard拦截，原因：可能违反了与{scanner_name}有关的策略要求。',
  },
  data_leakage_template: {
    en: 'Request blocked by FangcunGuard due to possible sensitive data ({entity_type_names}).',
    zh: '请求已被FangcunGuard拦截，原因：可能包含敏感数据（{entity_type_names}）。',
  },
}
const kinds: TemplateKind[] = ['security_risk', 'data_leakage']
const keyOf = (kind: TemplateKind): TemplateKey => `${kind}_template`

const AnswerManagementScreen = () => {
  const { t, i18n } = useTranslation()
  const language: Language = i18n.language === 'zh' ? 'zh' : 'en'
  const [tab, setTab] = useState('fixed-answer')
  const [dismissed, setDismissed] = useState(() => localStorage.getItem(dismissedKey) === 'true')
  const [templates, setTemplates] = useState<Templates>(defaults)
  const [editing, setEditing] = useState<TemplateKind | null>(null)
  const [value, setValue] = useState('')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  const load = async () => {
    setLoading(true)
    try {
      const data = await fixedAnswerTemplatesApi.get()
      if (data) {
        setTemplates({
          security_risk_template: data.security_risk_template || defaults.security_risk_template,
          data_leakage_template: data.data_leakage_template || defaults.data_leakage_template,
        })
      }
    } catch (error) {
      console.error('Failed to load templates:', error)
    } finally {
      setLoading(false)
    }
  }
  useEffect(() => { void load() }, [])

  const edit = (kind: TemplateKind) => {
    setEditing(kind)
    setValue(templates[keyOf(kind)][language])
  }
  const save = async () => {
    if (!editing) return
    const key = keyOf(editing)
    const updated = { ...templates[key], [language]: value }
    setSaving(true)
    try {
      await fixedAnswerTemplatesApi.update({ [key]: updated })
      setTemplates((state) => ({ ...state, [key]: updated }))
      setEditing(null)
      toast.success(t('common.updateSuccess'))
    } catch (error) {
      console.error('Failed to save template:', error)
      toast.error(t('common.saveFailed'))
    } finally {
      setSaving(false)
    }
  }
  const dismiss = () => {
    localStorage.setItem(dismissedKey, 'true')
    setDismissed(true)
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-lg">{t('answer.title')}</CardTitle>
          <CardDescription className="text-sm">{t('answer.description')}</CardDescription>
        </CardHeader>
        <CardContent>
          <Tabs className="w-full" value={tab} onValueChange={setTab}>
            <TabsList className="mb-6 grid w-full grid-cols-2">
              <TabsTrigger className="flex items-center gap-2" value="fixed-answer"><FileText className="h-4 w-4" />{t('answer.fixedAnswer')}</TabsTrigger>
              <TabsTrigger className="flex items-center gap-2" value="proxy-answer"><BookOpen className="h-4 w-4" />{t('answer.proxyAnswer')}</TabsTrigger>
            </TabsList>
            <TabsContent className="mt-0 space-y-4" value="fixed-answer">
              {!dismissed && <div className="relative rounded-lg border bg-card p-4">
                <button className="absolute right-2 top-2 rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground" onClick={dismiss} title={t('common.close')}><X className="h-4 w-4" /></button>
                <div className="flex items-start gap-3 pr-6"><Info className="mt-0.5 h-5 w-5 flex-shrink-0 text-indigo-400" /><div>
                  <h4 className="mb-2 text-sm font-medium">{t('answer.fixedAnswerTitle')}</h4>
                  <p className="text-sm text-muted-foreground">{t('answer.fixedAnswerDesc')}</p>
                </div></div>
              </div>}
              {kinds.map((kind) => <div className="rounded-lg border p-4" key={kind}>
                <div className="mb-2 flex items-center justify-between">
                  <h5 className="text-sm font-medium">{t(`answer.${kind === 'security_risk' ? 'securityRisk' : 'dataLeakage'}Template`)}</h5>
                  <Button disabled={loading} onClick={() => edit(kind)} size="sm" variant="ghost"><Edit2 className="mr-1 h-4 w-4" />{t('common.edit')}</Button>
                </div>
                <div className="rounded bg-muted p-3 font-mono text-sm">{templates[keyOf(kind)][language]}</div>
                <p className="mt-2 text-xs text-muted-foreground">{t(`answer.${kind === 'security_risk' ? 'securityRisk' : 'dataLeakage'}TemplateDesc`)}</p>
              </div>)}
            </TabsContent>
            <TabsContent className="mt-0" value="proxy-answer">
              <div className="mb-4 rounded-lg border bg-card p-4"><div className="flex items-start gap-3">
                <Info className="mt-0.5 h-5 w-5 flex-shrink-0 text-indigo-400" /><div>
                  <h4 className="mb-2 text-sm font-medium">{t('answer.proxyAnswerTitle')}</h4>
                  <p className="text-sm text-muted-foreground">{t('answer.proxyAnswerDesc')}</p>
                  <p className="mt-3 rounded-md bg-indigo-500/10 p-3 text-sm text-indigo-400"><strong>{t('answer.proxyAnswerNote')}:</strong> {t('answer.proxyAnswerNoteDesc')}</p>
                </div>
              </div></div>
              <KnowledgeBaseManagementScreen />
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>
      <Dialog open={editing !== null} onOpenChange={(open) => !open && setEditing(null)}>
        <DialogContent className="max-w-lg">
          <DialogHeader><DialogTitle>{t(`answer.edit${editing === 'security_risk' ? 'SecurityRisk' : 'DataLeakage'}Template`)}</DialogTitle></DialogHeader>
          <div className="space-y-4">
            <div><Label>{t('answer.templateContent')}</Label><Textarea className="mt-2 font-mono" onChange={(event) => setValue(event.target.value)} rows={4} value={value} /></div>
            <p className="text-xs text-muted-foreground">{t(`answer.${editing === 'security_risk' ? 'securityRisk' : 'dataLeakage'}TemplateDesc`)}</p>
            <p className="text-xs text-muted-foreground">{t('answer.editLanguageHint', { language: language === 'zh' ? '中文' : 'English' })}</p>
          </div>
          <DialogFooter>
            <Button onClick={() => setEditing(null)} variant="outline">{t('common.cancel')}</Button>
            <Button disabled={saving} onClick={() => void save()}>{t(saving ? 'common.saving' : 'common.save')}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}

export default AnswerManagementScreen
