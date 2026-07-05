import React from 'react'

import LanguageSwitcher from '@/components/LanguageSwitcher/LanguageSwitcher'
import { Shield } from 'lucide-react'

interface AuthSplitLayoutProps {
  brandTitle: string
  brandSubtitle: string
  copyright: string
  children: React.ReactNode
  features?: string[]
  mobileBrandName?: string
}

const defaultFeatures = [
  'Content Safety',
  'Data Leakage Prevention',
  'Guard Router',
  'Agent Runtime Firewall',
]

const AuthSplitLayout: React.FC<AuthSplitLayoutProps> = ({
  brandTitle,
  brandSubtitle,
  copyright,
  children,
  features = defaultFeatures,
  mobileBrandName = 'FangcunGuard',
}) => {
  return (
    <div className="min-h-screen flex bg-[#09090b] relative overflow-hidden">
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute top-1/4 left-1/4 w-[500px] h-[500px] bg-indigo-500/8 rounded-full blur-3xl" />
        <div className="absolute bottom-1/4 right-1/3 w-[400px] h-[400px] bg-cyan-500/5 rounded-full blur-3xl" />
      </div>

      <div className="hidden lg:flex lg:w-1/2 p-12 flex-col justify-between relative">
        <div className="relative z-10">
          <div className="flex items-center gap-3 mb-12">
            <div className="h-12 w-12 bg-indigo-500/10 backdrop-blur-sm rounded-xl flex items-center justify-center ring-1 ring-indigo-500/20">
              <Shield className="h-7 w-7 text-indigo-400" />
            </div>
            <h1 className="text-2xl font-bold text-white">{mobileBrandName}</h1>
          </div>
          <h2 className="text-5xl font-bold bg-gradient-to-r from-white via-indigo-200 to-indigo-400 bg-clip-text text-transparent mb-6 leading-tight">
            {brandTitle}
          </h2>
          <p className="text-zinc-400 text-lg max-w-md leading-relaxed">{brandSubtitle}</p>

          {features.length > 0 && (
            <div className="mt-12 space-y-4">
              {features.map((feature) => (
                <div key={feature} className="flex items-center gap-3 text-zinc-500">
                  <div className="h-1.5 w-1.5 rounded-full bg-indigo-500" />
                  <span className="text-sm">{feature}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="relative z-10 text-sm text-zinc-600">{copyright}</div>
      </div>

      <div className="flex-1 flex items-center justify-center p-8 relative">
        <div className="w-full max-w-md">
          <div className="flex items-center gap-3 mb-8 lg:hidden">
            <div className="h-10 w-10 bg-indigo-500/10 rounded-xl flex items-center justify-center ring-1 ring-indigo-500/20">
              <Shield className="h-6 w-6 text-indigo-400" />
            </div>
            <h1 className="text-xl font-bold text-white">{mobileBrandName}</h1>
          </div>

          {children}

          <p className="text-xs text-zinc-600 text-center mt-6 lg:hidden">{copyright}</p>
        </div>

        <div className="absolute bottom-8 right-8">
          <div className="scale-75 opacity-60 hover:opacity-100 transition-opacity">
            <LanguageSwitcher />
          </div>
        </div>
      </div>
    </div>
  )
}

export default AuthSplitLayout
