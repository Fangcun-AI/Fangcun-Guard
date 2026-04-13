import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import {
  ShieldCheck,
  SearchCheck,
  Shield,
  Wrench,
  BarChart3,
  Link,
  Rocket,
  Activity,
  ScanSearch,
  Network,
  ChevronRight,
  Check,
  X,
  Loader2,
  AlertCircle,
} from 'lucide-react'
import { Card, CardContent } from '../../components/ui/card'
import { Button } from '../../components/ui/button'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../../components/ui/dialog'
import { pluginsApi } from '../../services/api'
import { cn } from '../../lib/utils'

// Map icon name strings to Lucide components
const iconMap: Record<string, React.ElementType> = {
  'shield-check': ShieldCheck,
  'search-check': SearchCheck,
  'shield': Shield,
  'wrench': Wrench,
  'bar-chart-3': BarChart3,
  'link': Link,
  'rocket': Rocket,
  'activity': Activity,
  'scan-search': ScanSearch,
  'network': Network,
}

// Category colors
const categoryConfig: Record<string, { bg: string; text: string; border: string; label_zh: string; label_en: string }> = {
  security: { bg: 'bg-indigo-900/30', text: 'text-indigo-400', border: 'border-indigo-800', label_zh: '安全防护', label_en: 'Security' },
  analysis: { bg: 'bg-purple-900/30', text: 'text-purple-400', border: 'border-purple-800', label_zh: '智能分析', label_en: 'Analysis' },
  integration: { bg: 'bg-green-900/30', text: 'text-green-400', border: 'border-green-800', label_zh: '系统集成', label_en: 'Integration' },
  utility: { bg: 'bg-orange-900/30', text: 'text-orange-400', border: 'border-orange-800', label_zh: '实用工具', label_en: 'Utility' },
}

// Deployment mode display
const deploymentModeConfig: Record<string, { label_zh: string; label_en: string; color: string }> = {
  white_box: { label_zh: '白盒模式', label_en: 'White Box', color: 'bg-sky-900/30 text-sky-400' },
  black_box: { label_zh: '黑盒模式', label_en: 'Black Box', color: 'bg-zinc-800/50 text-zinc-200' },
  both: { label_zh: '黑盒+白盒', label_en: 'Both Modes', color: 'bg-indigo-900/30 text-indigo-400' },
}

interface PluginData {
  name: string
  version: string
  description: string
  author: string
  plugin_type: string
  deployment_mode: string
  priority: number
  display_name: string
  display_name_en: string
  icon: string
  category: string
  tags: string[]
  documentation: string
  enabled: boolean
  hooks: {
    on_input_check: boolean
    on_output_check: boolean
    on_detection_check: boolean
    on_stream_complete: boolean
  } | null
}

// Built-in custom tool cards (not from backend API)
const CUSTOM_TOOLS: PluginData[] = [
  {
    name: 'deployment_agent',
    version: '1.0.0',
    description: 'AI-driven one-click deployment: auto-scan project, generate config, deploy FangcunGuard, and validate health',
    author: 'FangcunGuard',
    plugin_type: 'utility',
    deployment_mode: 'both',
    priority: 50,
    display_name: '智能部署 Agent',
    display_name_en: 'Deployment Agent',
    icon: 'rocket',
    category: 'integration',
    tags: ['deploy', 'agent', 'one-click', 'automation'],
    documentation: '',
    enabled: true,
    hooks: null,
    // custom field: external link (opens in new tab)
    _externalUrl: 'http://127.0.0.1:8888',
  } as PluginData & { _externalUrl?: string },
]

const ToolCenter: React.FC = () => {
  const { t, i18n } = useTranslation()
  const navigate = useNavigate()
  const isZh = i18n.language?.startsWith('zh')

  const [plugins, setPlugins] = useState<PluginData[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedPlugin, setSelectedPlugin] = useState<PluginData | null>(null)
  const [detailOpen, setDetailOpen] = useState(false)

  useEffect(() => {
    fetchPlugins()
  }, [])

  const fetchPlugins = async () => {
    try {
      setLoading(true)
      setError(null)
      const response = await pluginsApi.list()
      setPlugins([...CUSTOM_TOOLS, ...(response.plugins || [])])
    } catch (err: any) {
      setError(err.message || t('toolCenter.loadError'))
    } finally {
      setLoading(false)
    }
  }

  const openDetail = (plugin: PluginData & { _externalUrl?: string }) => {
    if (plugin._externalUrl) {
      window.open(plugin._externalUrl, '_blank')
      return
    }
    // Navigate to dedicated pages for scanners
    if (plugin.name === 'skill_scanner') {
      navigate('/tool-center/skill-scanner')
      return
    }
    if (plugin.name === 'mcp_scanner') {
      navigate('/tool-center/mcp-scanner')
      return
    }
    setSelectedPlugin(plugin)
    setDetailOpen(true)
  }

  const getIcon = (iconName: string) => {
    return iconMap[iconName] || Shield
  }

  const getDisplayName = (plugin: PluginData) => {
    return isZh ? plugin.display_name : plugin.display_name_en
  }

  const getCategoryLabel = (category: string) => {
    const config = categoryConfig[category]
    if (!config) return category
    return isZh ? config.label_zh : config.label_en
  }

  const getDeploymentLabel = (mode: string) => {
    const config = deploymentModeConfig[mode]
    if (!config) return mode
    return isZh ? config.label_zh : config.label_en
  }

  // Loading state
  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-zinc-400" />
      </div>
    )
  }

  // Error state
  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-64 gap-4">
        <AlertCircle className="h-12 w-12 text-red-400" />
        <p className="text-zinc-400">{error}</p>
        <Button onClick={fetchPlugins} variant="outline" size="sm">
          {t('common.refresh')}
        </Button>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold tracking-tight text-white">
          {t('toolCenter.title')}
        </h2>
        <p className="text-sm text-zinc-400 mt-1">
          {t('toolCenter.subtitle')}
        </p>
      </div>

      {/* Stats bar */}
      <div className="flex items-center gap-6 text-sm text-zinc-400">
        <span>
          {t('toolCenter.totalTools')}: <span className="font-semibold text-white">{plugins.length}</span>
        </span>
        <span>
          {t('toolCenter.enabledTools')}: <span className="font-semibold text-green-600">{plugins.filter(p => p.enabled).length}</span>
        </span>
      </div>

      {/* Plugin cards grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5">
        {plugins.map((plugin) => {
          const IconComponent = getIcon(plugin.icon)
          const catConfig = categoryConfig[plugin.category] || categoryConfig.utility
          const deployConfig = deploymentModeConfig[plugin.deployment_mode]

          return (
            <Card
              key={plugin.name}
              className="group hover:shadow-md transition-all duration-200 cursor-pointer border-zinc-800 hover:border-zinc-700 bg-zinc-900/50"
              onClick={() => openDetail(plugin as PluginData & { _externalUrl?: string })}
            >
              <CardContent className="p-5">
                {/* Top row: icon + name + status */}
                <div className="flex items-start gap-3.5">
                  <div className={cn(
                    'h-11 w-11 rounded-lg flex items-center justify-center flex-shrink-0',
                    catConfig.bg, catConfig.border, 'border'
                  )}>
                    <IconComponent className={cn('h-5.5 w-5.5', catConfig.text)} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <h3 className="font-semibold text-white truncate">
                        {getDisplayName(plugin)}
                      </h3>
                      <span className="text-xs text-zinc-400 flex-shrink-0">v{plugin.version}</span>
                    </div>
                    <p className="text-xs text-zinc-400 mt-0.5 line-clamp-2">
                      {plugin.description}
                    </p>
                  </div>
                </div>

                {/* Tags row */}
                <div className="flex flex-wrap gap-1.5 mt-3">
                  {/* Category badge */}
                  <span className={cn(
                    'px-2 py-0.5 text-xs rounded-full font-medium',
                    catConfig.bg, catConfig.text
                  )}>
                    {getCategoryLabel(plugin.category)}
                  </span>
                  {/* Deployment mode badge */}
                  {deployConfig && (
                    <span className={cn(
                      'px-2 py-0.5 text-xs rounded-full font-medium',
                      deployConfig.color
                    )}>
                      {getDeploymentLabel(plugin.deployment_mode)}
                    </span>
                  )}
                </div>

                {/* Hooks indicator */}
                {plugin.hooks && (
                  <div className="flex items-center gap-3 mt-3 pt-3 border-t border-zinc-800">
                    <span className="text-xs text-zinc-400">{t('toolCenter.hooks')}:</span>
                    <div className="flex gap-2">
                      {plugin.hooks.on_input_check && (
                        <span className="text-xs px-1.5 py-0.5 rounded bg-green-900/30 text-green-400 font-medium">INPUT</span>
                      )}
                      {plugin.hooks.on_output_check && (
                        <span className="text-xs px-1.5 py-0.5 rounded bg-indigo-900/30 text-indigo-400 font-medium">OUTPUT</span>
                      )}
                      {plugin.hooks.on_detection_check && (
                        <span className="text-xs px-1.5 py-0.5 rounded bg-purple-900/30 text-purple-400 font-medium">DETECT</span>
                      )}
                      {plugin.hooks.on_stream_complete && (
                        <span className="text-xs px-1.5 py-0.5 rounded bg-orange-900/30 text-orange-400 font-medium">STREAM</span>
                      )}
                    </div>
                  </div>
                )}

                {/* Footer: status + arrow */}
                <div className="flex items-center justify-between mt-3">
                  <div className="flex items-center gap-1.5">
                    {plugin.enabled ? (
                      <>
                        <span className="h-2 w-2 rounded-full bg-green-500" />
                        <span className="text-xs text-green-600 font-medium">{t('toolCenter.active')}</span>
                      </>
                    ) : (
                      <>
                        <span className="h-2 w-2 rounded-full bg-zinc-600" />
                        <span className="text-xs text-zinc-400">{t('toolCenter.inactive')}</span>
                      </>
                    )}
                  </div>
                  <ChevronRight className="h-4 w-4 text-zinc-600 group-hover:text-zinc-400 transition-colors" />
                </div>
              </CardContent>
            </Card>
          )
        })}
      </div>

      {/* Empty state */}
      {plugins.length === 0 && (
        <div className="flex flex-col items-center justify-center h-48 text-zinc-400">
          <Wrench className="h-12 w-12 mb-3" />
          <p>{t('toolCenter.noPlugins')}</p>
        </div>
      )}

      {/* Detail dialog */}
      <Dialog open={detailOpen} onOpenChange={setDetailOpen}>
        <DialogContent className="sm:max-w-[680px] max-h-[80vh] overflow-y-auto">
          {selectedPlugin && (
            <>
              <DialogHeader>
                <div className="flex items-center gap-3">
                  {(() => {
                    const IconComp = getIcon(selectedPlugin.icon)
                    const catConf = categoryConfig[selectedPlugin.category] || categoryConfig.utility
                    return (
                      <div className={cn(
                        'h-10 w-10 rounded-lg flex items-center justify-center',
                        catConf.bg, catConf.border, 'border'
                      )}>
                        <IconComp className={cn('h-5 w-5', catConf.text)} />
                      </div>
                    )
                  })()}
                  <div>
                    <DialogTitle className="text-lg">
                      {getDisplayName(selectedPlugin)}
                    </DialogTitle>
                    <p className="text-sm text-zinc-400 mt-0.5">v{selectedPlugin.version} · {selectedPlugin.author}</p>
                  </div>
                </div>
              </DialogHeader>

              <div className="space-y-5 mt-4">
                {/* Status & Mode */}
                <div className="flex flex-wrap gap-2">
                  <span className={cn(
                    'px-2.5 py-1 text-xs rounded-full font-medium',
                    selectedPlugin.enabled ? 'bg-green-900/30 text-green-400' : 'bg-zinc-800/50 text-zinc-400'
                  )}>
                    {selectedPlugin.enabled ? t('toolCenter.active') : t('toolCenter.inactive')}
                  </span>
                  <span className={cn(
                    'px-2.5 py-1 text-xs rounded-full font-medium',
                    (categoryConfig[selectedPlugin.category] || categoryConfig.utility).bg,
                    (categoryConfig[selectedPlugin.category] || categoryConfig.utility).text
                  )}>
                    {getCategoryLabel(selectedPlugin.category)}
                  </span>
                  {deploymentModeConfig[selectedPlugin.deployment_mode] && (
                    <span className={cn(
                      'px-2.5 py-1 text-xs rounded-full font-medium',
                      deploymentModeConfig[selectedPlugin.deployment_mode].color
                    )}>
                      {getDeploymentLabel(selectedPlugin.deployment_mode)}
                    </span>
                  )}
                </div>

                {/* Tags */}
                {selectedPlugin.tags.length > 0 && (
                  <div className="flex flex-wrap gap-1.5">
                    {selectedPlugin.tags.map((tag) => (
                      <span key={tag} className="px-2 py-0.5 text-xs rounded-md bg-zinc-800/50 text-zinc-400">
                        {tag}
                      </span>
                    ))}
                  </div>
                )}

                {/* Hooks table */}
                {selectedPlugin.hooks && (
                  <div>
                    <h4 className="text-sm font-semibold text-zinc-200 mb-2">{t('toolCenter.hookCapabilities')}</h4>
                    <div className="grid grid-cols-2 gap-2">
                      {[
                        { key: 'on_input_check', label: t('toolCenter.hookInput'), desc: t('toolCenter.hookInputDesc') },
                        { key: 'on_output_check', label: t('toolCenter.hookOutput'), desc: t('toolCenter.hookOutputDesc') },
                        { key: 'on_detection_check', label: t('toolCenter.hookDetection'), desc: t('toolCenter.hookDetectionDesc') },
                        { key: 'on_stream_complete', label: t('toolCenter.hookStream'), desc: t('toolCenter.hookStreamDesc') },
                      ].map((hook) => {
                        const active = (selectedPlugin.hooks as any)[hook.key]
                        return (
                          <div
                            key={hook.key}
                            className={cn(
                              'flex items-start gap-2 p-2.5 rounded-lg border',
                              active ? 'bg-green-900/20 border-green-800' : 'bg-zinc-800/50 border-zinc-800'
                            )}
                          >
                            {active ? (
                              <Check className="h-4 w-4 text-green-500 mt-0.5 flex-shrink-0" />
                            ) : (
                              <X className="h-4 w-4 text-zinc-600 mt-0.5 flex-shrink-0" />
                            )}
                            <div>
                              <p className={cn('text-xs font-medium', active ? 'text-green-400' : 'text-zinc-400')}>
                                {hook.label}
                              </p>
                              <p className="text-[11px] text-zinc-500 mt-0.5">{hook.desc}</p>
                            </div>
                          </div>
                        )
                      })}
                    </div>
                  </div>
                )}

                {/* Documentation */}
                {selectedPlugin.documentation && (
                  <div>
                    <h4 className="text-sm font-semibold text-zinc-200 mb-2">{t('toolCenter.documentation')}</h4>
                    <div className="prose prose-sm prose-invert max-w-none text-sm leading-relaxed whitespace-pre-wrap bg-zinc-800/50 rounded-lg p-4 border border-zinc-800">
                      {selectedPlugin.documentation}
                    </div>
                  </div>
                )}
              </div>
            </>
          )}
        </DialogContent>
      </Dialog>
    </div>
  )
}

export default ToolCenter
