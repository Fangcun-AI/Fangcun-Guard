import React from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { ArrowLeft, Rocket, ExternalLink } from 'lucide-react'
import { Button } from '@/components/ui/button'

const DEPLOY_UI_URL = 'http://127.0.0.1:8888'

const DeploymentAgent: React.FC = () => {
  const navigate = useNavigate()
  const { i18n } = useTranslation()
  const isZh = i18n.language?.startsWith('zh')

  return (
    <div className="h-full flex flex-col gap-4">
      {/* Header bar */}
      <div className="flex items-center justify-between flex-shrink-0">
        <div className="flex items-center gap-3">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => navigate('/tool-center')}
            className="gap-1.5"
          >
            <ArrowLeft className="h-4 w-4" />
            {isZh ? '返回工具中心' : 'Back to Tool Center'}
          </Button>
          <div className="h-5 w-px bg-zinc-800" />
          <div className="flex items-center gap-2">
            <div className="h-8 w-8 rounded-lg bg-emerald-50 border border-emerald-200 flex items-center justify-center">
              <Rocket className="h-4 w-4 text-emerald-600" />
            </div>
            <div>
              <h2 className="text-sm font-semibold text-white">
                {isZh ? '智能部署 Agent' : 'Deployment Agent'}
              </h2>
              <p className="text-xs text-zinc-400">
                {isZh ? '一键部署 FangcunGuard 到目标应用' : 'One-click deploy FangcunGuard to target apps'}
              </p>
            </div>
          </div>
        </div>
        <Button
          variant="outline"
          size="sm"
          className="gap-1.5"
          onClick={() => window.open(DEPLOY_UI_URL, '_blank')}
        >
          <ExternalLink className="h-3.5 w-3.5" />
          {isZh ? '新窗口打开' : 'Open in new tab'}
        </Button>
      </div>

      {/* Iframe */}
      <div className="flex-1 rounded-lg border border-zinc-800 overflow-hidden bg-zinc-900/50 min-h-0">
        <iframe
          src={DEPLOY_UI_URL}
          title="Deployment Agent"
          className="w-full h-full border-0"
          allow="clipboard-read; clipboard-write"
        />
      </div>
    </div>
  )
}

export default DeploymentAgent
