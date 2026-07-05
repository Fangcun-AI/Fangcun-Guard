import React, { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Shield, Mail, Bot, Swords, ScanSearch, Network, ChevronRight } from 'lucide-react'
import JailbreakDemo from './JailbreakDemoScreen'
import AgentSafetyDemo from './AgentSafetyDemoScreen'
import EmailLeakDemo from './EmailLeakDemoScreen'
import SkillScannerDemo from './SkillScannerDemoScreen'
import McpScannerDemo from './McpScannerDemoScreen'

const TABS = [
  {
    key: 'jailbreak',
    icon: Swords,
    labelKey: 'demo.jailbreak.title',
    color: 'red',
    desc: '伪装续写 / 角色扮演绕过安全限制',
  },
  {
    key: 'agent',
    icon: Bot,
    labelKey: 'demo.agent.title',
    color: 'orange',
    desc: '上下文压缩导致安全指令丢失',
  },
  {
    key: 'email',
    icon: Mail,
    labelKey: 'demo.email.title',
    color: 'blue',
    desc: 'AI 写邮件泄露企业敏感信息',
  },
  {
    key: 'skill-scanner',
    icon: ScanSearch,
    labelKey: 'demo.skillScanner.title',
    color: 'purple',
    desc: '检测 Agent Skills 定义中的隐藏攻击',
  },
  {
    key: 'mcp-scanner',
    icon: Network,
    labelKey: 'demo.mcpScanner.title',
    color: 'teal',
    desc: 'MCP 服务器部署前安全审计',
  },
] as const

type TabKey = typeof TABS[number]['key']

const TAB_COLORS: Record<string, { active: string; icon: string; ring: string }> = {
  red: {
    active: 'border-red-500 bg-red-900/30 text-red-400',
    icon: 'bg-red-900/50 text-red-400',
    ring: 'ring-red-800',
  },
  orange: {
    active: 'border-orange-500 bg-orange-900/30 text-orange-400',
    icon: 'bg-orange-900/50 text-orange-400',
    ring: 'ring-orange-800',
  },
  blue: {
    active: 'border-indigo-500 bg-indigo-900/30 text-indigo-400',
    icon: 'bg-indigo-900/50 text-indigo-400',
    ring: 'ring-indigo-800',
  },
  purple: {
    active: 'border-purple-500 bg-purple-900/30 text-purple-400',
    icon: 'bg-purple-900/50 text-purple-400',
    ring: 'ring-purple-800',
  },
  teal: {
    active: 'border-teal-500 bg-teal-900/30 text-teal-400',
    icon: 'bg-teal-900/50 text-teal-400',
    ring: 'ring-teal-800',
  },
}

const DemoHubScreen: React.FC = () => {
  const { t } = useTranslation()
  const [activeTab, setActiveTab] = useState<TabKey>('jailbreak')

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="relative overflow-hidden rounded-xl bg-gradient-to-br from-zinc-900 via-zinc-800 to-zinc-900 px-6 py-6">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_right,_var(--tw-gradient-stops))] from-indigo-600/20 via-transparent to-transparent" />
        <div className="relative flex items-center gap-4">
          <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-white/10 backdrop-blur-sm ring-1 ring-white/20">
            <Shield className="h-6 w-6 text-indigo-400" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-white tracking-tight">{t('demo.pageTitle')}</h1>
            <p className="text-sm text-zinc-400 mt-0.5">{t('demo.pageDesc')}</p>
          </div>
        </div>
      </div>

      {/* Tab Cards */}
      <div className="grid grid-cols-5 gap-3">
        {TABS.map(({ key, icon: Icon, labelKey, color, desc }) => {
          const isActive = activeTab === key
          const colors = TAB_COLORS[color]
          return (
            <button
              key={key}
              onClick={() => setActiveTab(key)}
              className={`group relative flex items-start gap-3 rounded-lg border-2 px-4 py-3.5 text-left transition-all duration-200 cursor-pointer ${
                isActive
                  ? `${colors.active} border-current shadow-sm`
                  : 'border-zinc-800 bg-zinc-900/50 text-zinc-400 hover:border-zinc-700 hover:shadow-sm hover:-translate-y-0.5'
              }`}
            >
              <div className={`flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg transition-colors duration-200 ${
                isActive ? colors.icon : 'bg-zinc-800/50 text-zinc-400 group-hover:bg-zinc-800'
              }`}>
                <Icon className="h-4.5 w-4.5" />
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-1.5">
                  <span className="text-sm font-semibold">{t(labelKey)}</span>
                  <ChevronRight className={`h-3.5 w-3.5 transition-transform duration-200 ${
                    isActive ? 'translate-x-0.5 opacity-100' : 'opacity-0 group-hover:opacity-50'
                  }`} />
                </div>
                <p className={`text-xs mt-0.5 leading-relaxed ${isActive ? 'opacity-80' : 'text-zinc-400'}`}>
                  {desc}
                </p>
              </div>
            </button>
          )
        })}
      </div>

      {/* Tab Content */}
      <div>
        {activeTab === 'jailbreak' && <JailbreakDemo />}
        {activeTab === 'agent' && <AgentSafetyDemo />}
        {activeTab === 'email' && <EmailLeakDemo />}
        {activeTab === 'skill-scanner' && <SkillScannerDemo />}
        {activeTab === 'mcp-scanner' && <McpScannerDemo />}
      </div>
    </div>
  )
}

export default DemoHubScreen
