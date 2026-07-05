import React, { useState, useRef, useCallback, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import {
  ArrowLeft, ScanSearch, FolderSearch, Play, Loader2,
  AlertTriangle, ShieldAlert, ShieldCheck, ChevronDown, ChevronRight,
  FileCode2, Package, Info, CheckCircle2, Search, Cpu
} from 'lucide-react'
import { Button } from '@/components/ui/button'

interface Finding {
  tool_name?: string
  item_name?: string
  engine: string
  category: string
  severity: string
  title: string
  description: string
  evidence: string
  remediation: string
  confidence: number
  _idx?: number  // original backend index for enrichment matching
}

interface ScanResult {
  request_id: string
  agents_scanned: number
  tools_extracted: number
  tools_by_agent: Record<string, { tools_count: number; tool_names: string[] }>
  result: {
    findings: Finding[]
    tools_scanned: number
    tools_flagged: number
    max_severity: string
    scan_duration_ms: number
    engine_summary: Record<string, number>
  }
}

type ScanPhase = 'idle' | 'loading' | 'discovery' | 'extraction' | 'scanning' | 'llm_analysis' | 'complete'

const SEVERITY_CONFIG: Record<string, { color: string; bg: string; border: string; icon: React.ReactNode }> = {
  critical: { color: 'text-red-700', bg: 'bg-red-50', border: 'border-red-200', icon: <ShieldAlert className="h-4 w-4 text-red-600" /> },
  high: { color: 'text-orange-700', bg: 'bg-orange-50', border: 'border-orange-200', icon: <AlertTriangle className="h-4 w-4 text-orange-500" /> },
  medium: { color: 'text-yellow-700', bg: 'bg-yellow-50', border: 'border-yellow-200', icon: <AlertTriangle className="h-4 w-4 text-yellow-500" /> },
  low: { color: 'text-zinc-400', bg: 'bg-zinc-800/50', border: 'border-zinc-800', icon: <Info className="h-4 w-4 text-zinc-400" /> },
  info: { color: 'text-indigo-400', bg: 'bg-indigo-900/30', border: 'border-indigo-800', icon: <Info className="h-4 w-4 text-indigo-400" /> },
}

const SEV_ORDER = ['info', 'low', 'medium', 'high', 'critical']

const SeverityBadge: React.FC<{ severity: string }> = ({ severity }) => {
  const config = SEVERITY_CONFIG[severity] || SEVERITY_CONFIG.info
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold ${config.bg} ${config.color} ${config.border} border`}>
      {config.icon}
      {severity.toUpperCase()}
    </span>
  )
}

const sleep = (ms: number) => new Promise(r => setTimeout(r, ms))

const SkillScannerPage: React.FC = () => {
  const navigate = useNavigate()
  const { i18n } = useTranslation()
  const isZh = i18n.language?.startsWith('zh')

  const [directory, setDirectory] = useState('/mnt/scan_targets')
  const [phase, setPhase] = useState<ScanPhase>('idle')
  const [result, setResult] = useState<ScanResult | null>(null)
  const [error, setError] = useState('')

  // Real-time streaming state
  const [agents, setAgents] = useState<Array<{ name: string; tools_count: number; tool_names: string[] }>>([])
  const [findings, setFindings] = useState<Finding[]>([])
  const [llmStatus, setLlmStatus] = useState('')
  const [llmAnalyzing, setLlmAnalyzing] = useState<{ tool_name: string; agent: string; title: string; severity: string } | null>(null)
  const [scanningAgent, setScanningAgent] = useState<{ name: string; index: number; total: number; tools_count: number } | null>(null)
  const [expandedAgents, setExpandedAgents] = useState<Set<string>>(new Set())
  const [flaggedAgents, setFlaggedAgents] = useState<Set<string>>(new Set())
  const [visibleAgentGroups, setVisibleAgentGroups] = useState(0)
  const [llmAnalyzingAgent, setLlmAnalyzingAgent] = useState<string | null>(null)
  const [displayedFindingsCount, setDisplayedFindingsCount] = useState(0)

  const abortRef = useRef<AbortController | null>(null)

  const handleScan = useCallback(async () => {
    if (!directory.trim()) return

    // Abort previous scan
    if (abortRef.current) abortRef.current.abort()
    const controller = new AbortController()
    abortRef.current = controller

    setPhase('loading')
    setError('')
    setResult(null)
    setAgents([])
    setFindings([])
    setLlmStatus('')
    setLlmAnalyzing(null)
    setLlmAnalysisIdx(0)
    setScanningAgent(null)
    setExpandedAgents(new Set())
    setFlaggedAgents(new Set())
    setVisibleAgentGroups(0)
    setDisplayedFindingsCount(0)
    setLlmAnalyzingAgent(null)

    try {
      const token = localStorage.getItem('auth_token')
      const response = await fetch('/api/v1/skill-scanner/scan-directory', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ directory: directory.trim() }),
        signal: controller.signal,
      })

      if (!response.ok) {
        const err = await response.json().catch(() => ({ detail: 'Request failed' }))
        throw new Error(err.detail || `HTTP ${response.status}`)
      }

      const reader = response.body?.getReader()
      if (!reader) throw new Error('No stream')

      const decoder = new TextDecoder()
      let buffer = ''
      let toolAgentMap: Record<string, string> = {}

      setPhase('discovery')

      // currentEvent must persist across chunks (event: and data: may arrive in different chunks)
      let currentEvent = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })

        // Parse SSE lines
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (line.startsWith('event: ')) {
            currentEvent = line.slice(7).trim()
          } else if (line.startsWith('data: ') && currentEvent) {
            try {
              const data = JSON.parse(line.slice(6))
              handleSSEEvent(currentEvent, data, toolAgentMap)
            } catch {}
            currentEvent = ''
          }
        }
      }

      // Process any remaining data in buffer after stream ends
      if (buffer.trim()) {
        const lines = buffer.split('\n')
        for (const line of lines) {
          if (line.startsWith('event: ')) {
            currentEvent = line.slice(7).trim()
          } else if (line.startsWith('data: ') && currentEvent) {
            try {
              const data = JSON.parse(line.slice(6))
              handleSSEEvent(currentEvent, data, toolAgentMap)
            } catch {}
            currentEvent = ''
          }
        }
      }
    } catch (e: any) {
      if (e.name === 'AbortError') return
      setError(e.message || 'Scan failed')
      setPhase('idle')
    }
  }, [directory])

  const handleSSEEvent = useCallback((event: string, data: any, toolAgentMap: Record<string, string>) => {
    switch (event) {
      case 'agent_discovered':
        setPhase('discovery')
        setAgents(prev => [...prev, {
          name: data.agent,
          tools_count: data.tools_count,
          tool_names: data.tool_names || [],
        }])
        // Build tool→agent map
        for (const t of (data.tool_names || [])) {
          toolAgentMap[t] = data.agent
        }
        break

      case 'discovery_complete':
        setPhase('extraction')
        // Brief pause then move to scanning
        setTimeout(() => setPhase('scanning'), 800)
        break

      case 'phase':
        if (data.phase === 'scanning') setPhase('scanning')
        if (data.phase === 'llm_analysis') setPhase('llm_analysis')
        if (data.message) setLlmStatus(data.message)
        break

      case 'scan_progress':
        setPhase('scanning')
        setScanningAgent({
          name: data.agent,
          index: data.agent_index,
          total: data.agents_total,
          tools_count: data.tools_count,
        })
        break

      case 'finding':
        setPhase(prev => prev === 'discovery' || prev === 'extraction' ? 'scanning' : prev)
        setFindings(prev => {
          const f = { ...(data as Finding), _idx: prev.length }
          const next = [...prev, f]
          return next.sort((a, b) => SEV_ORDER.indexOf(b.severity) - SEV_ORDER.indexOf(a.severity))
        })
        // Flag the agent
        const toolName = data.tool_name || ''
        const agentName = toolAgentMap[toolName]
        if (agentName) {
          setFlaggedAgents(prev => new Set([...prev, agentName]))
        }
        break

      case 'agent_scan_done':
        // Agent finished scanning with findings
        break

      case 'static_complete':
        setScanningAgent(null)
        setLlmStatus(isZh ? '静态分析完成，启动 AI 深度分析...' : 'Static analysis done, starting AI analysis...')
        break

      case 'llm_progress':
        setPhase('llm_analysis')
        if (data.type === 'analyzing') {
          // No-op: spotlight is now driven by agentToolPairs timer
        } else if (data.type === 'enriched') {
          // Update the finding matching this backend index (_idx)
          setFindings(prev => {
            const targetIdx = data.index
            return prev.map(f => {
              if (f._idx === targetIdx) {
                return {
                  ...f,
                  ...(data.description ? { description: data.description } : {}),
                  ...(data.evidence ? { evidence: data.evidence } : {}),
                  ...(data.remediation ? { remediation: data.remediation } : {}),
                }
              }
              return f
            })
          })
        } else if (data.type === 'llm_done') {
          setLlmAnalyzing(null)
          setLlmAnalyzingAgent(null)
          setLlmStatus(isZh ? `AI 分析完成，已增强 ${data.enriched_count} 个发现` : `AI analysis done, enriched ${data.enriched_count} findings`)
        } else if (data.type === 'error') {
          setLlmAnalyzing(null)
          setLlmAnalyzingAgent(null)
          setLlmStatus(isZh ? `AI 分析跳过: ${data.message}` : `AI analysis skipped: ${data.message}`)
        }
        break

      case 'complete':
        setResult(data as ScanResult)
        setPhase('complete')
        setVisibleAgentGroups(0)  // Start progressive reveal from 0
        // Auto-expand agents with findings
        const agentsWithFindings = new Set<string>()
        for (const f of (data.result?.findings || [])) {
          const tn = f.tool_name || f.item_name || ''
          const an = toolAgentMap[tn]
          if (an) agentsWithFindings.add(an)
        }
        setExpandedAgents(agentsWithFindings)
        // Update findings with final data
        setFindings((data as ScanResult).result.findings.sort(
          (a: Finding, b: Finding) => SEV_ORDER.indexOf(b.severity) - SEV_ORDER.indexOf(a.severity)
        ))
        break

      case 'error':
        setError(data.message || 'Scan error')
        setPhase('idle')
        break
    }
  }, [isZh])

  const toggleAgent = (agent: string) => {
    setExpandedAgents(prev => {
      const next = new Set(prev)
      if (next.has(agent)) next.delete(agent)
      else next.add(agent)
      return next
    })
  }

  // Progressive reveal: show agent groups one by one in complete phase
  const sortedAgentGroupKeys = React.useMemo(() => {
    if (!result || phase !== 'complete') return []
    const toolAgentMap: Record<string, string> = {}
    for (const [agent, info] of Object.entries(result.tools_by_agent)) {
      for (const t of info.tool_names) toolAgentMap[t] = agent
    }
    const groups: Record<string, Finding[]> = {}
    for (const f of result.result.findings) {
      const toolName = f.tool_name || f.item_name || ''
      const agent = toolAgentMap[toolName] || (isZh ? '跨工具组合分析' : 'Cross-Tool Analysis')
      if (!groups[agent]) groups[agent] = []
      groups[agent].push(f)
    }
    return Object.keys(groups).sort()
  }, [result, phase, isZh])

  useEffect(() => {
    if (phase !== 'complete' || sortedAgentGroupKeys.length === 0) return
    if (visibleAgentGroups >= sortedAgentGroupKeys.length) return

    const timer = setTimeout(() => {
      setVisibleAgentGroups(prev => prev + 1)
    }, 300)
    return () => clearTimeout(timer)
  }, [phase, visibleAgentGroups, sortedAgentGroupKeys.length])

  // Build a flat list of agent→tool pairs for spotlight cycling
  const agentToolPairs = React.useMemo(() => {
    const pairs: Array<{ agent: string; tool: string }> = []
    for (const a of agents) {
      for (const t of a.tool_names) {
        pairs.push({ agent: a.name, tool: t })
      }
    }
    return pairs
  }, [agents])

  // Timer-based spotlight cycling during LLM analysis
  const [llmAnalysisIdx, setLlmAnalysisIdx] = useState(0)

  useEffect(() => {
    if (phase !== 'llm_analysis' || agentToolPairs.length === 0) return
    const idx = llmAnalysisIdx % agentToolPairs.length
    const pair = agentToolPairs[idx]
    setLlmAnalyzing({
      agent: pair.agent,
      tool_name: pair.tool,
      title: '',
      severity: '',
    })
    setLlmAnalyzingAgent(pair.agent)

    // Stop cycling once we've gone through all pairs
    if (llmAnalysisIdx >= agentToolPairs.length) return
    const timer = setTimeout(() => {
      setLlmAnalysisIdx(prev => prev + 1)
    }, 1500)
    return () => clearTimeout(timer)
  }, [phase, llmAnalysisIdx, agentToolPairs])

  // Smooth counter: animate displayedFindingsCount toward actual findings.length
  useEffect(() => {
    if (displayedFindingsCount >= findings.length) return
    const timer = setTimeout(() => {
      setDisplayedFindingsCount(prev => prev + 1)
    }, 80)
    return () => clearTimeout(timer)
  }, [displayedFindingsCount, findings.length])

  // Group findings by agent (for complete phase)
  const findingsByAgent: Record<string, Finding[]> = {}
  if (result && phase === 'complete') {
    const toolAgentMap: Record<string, string> = {}
    for (const [agent, info] of Object.entries(result.tools_by_agent)) {
      for (const t of info.tool_names) toolAgentMap[t] = agent
    }
    for (const f of result.result.findings) {
      const toolName = f.tool_name || f.item_name || ''
      const agent = toolAgentMap[toolName] || (isZh ? '跨工具组合分析' : 'Cross-Tool Analysis')
      if (!findingsByAgent[agent]) findingsByAgent[agent] = []
      findingsByAgent[agent].push(f)
    }
  }

  // Derived values
  const agentEntries = result
    ? Object.entries(result.tools_by_agent).sort(([, a], [, b]) => b.tools_count - a.tools_count)
    : agents.map(a => [a.name, { tools_count: a.tools_count, tool_names: a.tool_names }] as const)

  const totalTools = result?.tools_extracted || agents.reduce((s, a) => s + a.tools_count, 0)

  // Phase indicator
  const phaseSteps = [
    { key: 'discovery', label: isZh ? '发现 Agent' : 'Discovery', icon: <Search className="h-3.5 w-3.5" /> },
    { key: 'extraction', label: isZh ? '提取工具' : 'Extraction', icon: <FileCode2 className="h-3.5 w-3.5" /> },
    { key: 'scanning', label: isZh ? '安全扫描' : 'Scanning', icon: <ShieldAlert className="h-3.5 w-3.5" /> },
    { key: 'llm_analysis', label: isZh ? 'AI 分析' : 'AI Analysis', icon: <Cpu className="h-3.5 w-3.5" /> },
  ]
  const phaseKeys = ['discovery', 'extraction', 'scanning', 'llm_analysis', 'complete']
  const activePhaseIdx = phaseKeys.indexOf(phase)

  const isScanning = phase !== 'idle' && phase !== 'complete'

  return (
    <div className="h-full flex flex-col gap-4 overflow-auto">
      {/* Header */}
      <div className="flex items-center justify-between flex-shrink-0">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="sm" onClick={() => { abortRef.current?.abort(); navigate('/tool-center') }} className="gap-1.5">
            <ArrowLeft className="h-4 w-4" />
            {isZh ? '返回工具中心' : 'Back to Tool Center'}
          </Button>
          <div className="h-5 w-px bg-zinc-800" />
          <div className="flex items-center gap-2">
            <div className="h-8 w-8 rounded-lg bg-purple-50 border border-purple-200 flex items-center justify-center">
              <ScanSearch className="h-4 w-4 text-purple-600" />
            </div>
            <div>
              <h2 className="text-sm font-semibold text-white">
                {isZh ? 'Agent Skills 安全扫描' : 'Agent Skills Scanner'}
              </h2>
              <p className="text-xs text-zinc-400">
                {isZh ? '扫描 Agent 项目中的工具定义，检测安全隐患' : 'Scan agent projects for tool definition security issues'}
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Scan Input */}
      <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-5 flex-shrink-0">
        <div className="flex items-center gap-2 mb-3">
          <FolderSearch className="h-5 w-5 text-purple-500" />
          <h3 className="font-medium text-zinc-200">
            {isZh ? '选择扫描目录' : 'Select Scan Directory'}
          </h3>
        </div>
        <p className="text-sm text-zinc-400 mb-4">
          {isZh
            ? '输入包含 AI Agent 项目的目录路径，系统将自动识别并提取工具定义进行安全扫描。'
            : 'Enter the path to a directory containing AI agent projects.'}
        </p>
        <div className="flex gap-3">
          <input
            type="text"
            value={directory}
            onChange={e => setDirectory(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && !isScanning && handleScan()}
            placeholder={isZh ? '例如: /path/to/agent-projects' : 'e.g. /path/to/agent-projects'}
            className="flex-1 px-4 py-2.5 rounded-lg border border-zinc-800 bg-zinc-800/50 text-sm focus:outline-none focus:ring-2 focus:ring-purple-500/20 focus:border-purple-400 transition-all"
            disabled={isScanning}
          />
          <Button
            onClick={handleScan}
            disabled={isScanning || !directory.trim()}
            className="gap-2 bg-gradient-to-r from-purple-600 to-purple-500 hover:from-purple-700 hover:to-purple-600 text-white px-6"
          >
            {isScanning ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                {isZh ? '扫描中...' : 'Scanning...'}
              </>
            ) : (
              <>
                <Play className="h-4 w-4" />
                {isZh ? '开始扫描' : 'Start Scan'}
              </>
            )}
          </Button>
        </div>
        {error && (
          <div className="mt-3 p-3 rounded-lg bg-red-50 border border-red-200 text-sm text-red-700">{error}</div>
        )}
      </div>

      {/* Phase Progress Bar */}
      {activePhaseIdx >= 0 && (
        <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-4 flex-shrink-0">
          <div className="flex items-center gap-2">
            {phaseSteps.map((step, idx) => {
              const isActive = idx === activePhaseIdx
              const isDone = idx < activePhaseIdx
              return (
                <React.Fragment key={step.key}>
                  {idx > 0 && (
                    <div className={`flex-1 h-0.5 rounded ${isDone ? 'bg-purple-400' : isActive ? 'bg-purple-200' : 'bg-zinc-800'} transition-colors duration-500`} />
                  )}
                  <div className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium transition-all duration-500 ${
                    isDone ? 'bg-green-50 text-green-700 border border-green-200' :
                    isActive ? 'bg-purple-50 text-purple-700 border border-purple-200 animate-pulse' :
                    'bg-zinc-800/50 text-zinc-400 border border-zinc-800'
                  }`}>
                    {isDone ? <CheckCircle2 className="h-3.5 w-3.5 text-green-500" /> : step.icon}
                    {step.label}
                  </div>
                </React.Fragment>
              )
            })}
          </div>

          {/* Live counter */}
          <div className="mt-3 text-sm text-zinc-400">
            {phase === 'loading' && (
              <span className="flex items-center gap-2">
                <Loader2 className="h-3.5 w-3.5 animate-spin text-purple-500" />
                {isZh ? '连接中...' : 'Connecting...'}
              </span>
            )}
            {phase === 'discovery' && (
              <span className="flex items-center gap-2">
                <Loader2 className="h-3.5 w-3.5 animate-spin text-purple-500" />
                {isZh
                  ? `正在发现 Agent 项目... 已发现 ${agents.length} 个`
                  : `Discovering agents... found ${agents.length}`}
              </span>
            )}
            {phase === 'extraction' && (
              <span className="flex items-center gap-2">
                <Loader2 className="h-3.5 w-3.5 animate-spin text-purple-500" />
                {isZh
                  ? `正在提取工具定义... ${totalTools} 个工具`
                  : `Extracting tool definitions... ${totalTools} tools`}
              </span>
            )}
            {phase === 'scanning' && (
              <div className="space-y-1">
                <span className="flex items-center gap-2">
                  <ShieldAlert className="h-3.5 w-3.5 animate-pulse text-orange-500" />
                  {isZh
                    ? `静态安全扫描中... ${scanningAgent ? `(${scanningAgent.index + 1}/${scanningAgent.total})` : ''} 已发现 ${displayedFindingsCount} 个问题`
                    : `Static security scan... ${scanningAgent ? `(${scanningAgent.index + 1}/${scanningAgent.total})` : ''} ${displayedFindingsCount} issues found`}
                </span>
                {scanningAgent && (
                  <div className="ml-6 text-xs text-orange-600 font-mono animate-pulse">
                    → {isZh ? '正在扫描' : 'Scanning'} {scanningAgent.name} ({scanningAgent.tools_count} {isZh ? '个工具' : 'tools'})
                  </div>
                )}
              </div>
            )}
            {phase === 'llm_analysis' && (
              <div className="space-y-1">
                <span className="flex items-center gap-2">
                  <Cpu className="h-3.5 w-3.5 animate-pulse text-purple-500" />
                  {isZh
                    ? `AI 深度分析中... 正在分析 ${Math.min(llmAnalysisIdx + 1, agentToolPairs.length)} / ${agentToolPairs.length} 个技能`
                    : `AI deep analysis... analyzing ${Math.min(llmAnalysisIdx + 1, agentToolPairs.length)} / ${agentToolPairs.length} skills`}
                </span>
                {/* Progress bar */}
                <div className="ml-6 h-1.5 bg-zinc-800/50 rounded-full overflow-hidden w-48">
                  <div
                    className="h-full bg-gradient-to-r from-purple-500 to-purple-400 rounded-full transition-all duration-500"
                    style={{ width: `${agentToolPairs.length > 0 ? (Math.min(llmAnalysisIdx + 1, agentToolPairs.length) / agentToolPairs.length) * 100 : 0}%` }}
                  />
                </div>
              </div>
            )}
            {phase === 'complete' && result && (
              <span className="flex items-center gap-2 text-green-600">
                <CheckCircle2 className="h-3.5 w-3.5" />
                {isZh
                  ? `扫描完成: ${result.agents_scanned} 个 Agent, ${result.tools_extracted} 个工具, ${result.result.findings.length} 个安全问题 (${result.result.scan_duration_ms.toFixed(0)}ms)`
                  : `Complete: ${result.agents_scanned} agents, ${result.tools_extracted} tools, ${result.result.findings.length} issues (${result.result.scan_duration_ms.toFixed(0)}ms)`}
              </span>
            )}
          </div>
        </div>
      )}

      {/* Agent Cards Grid */}
      {agents.length > 0 && (
        <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 flex-shrink-0">
          <div className="p-4 border-b border-zinc-800">
            <h3 className="font-medium text-zinc-200 flex items-center gap-2">
              <Package className="h-4 w-4 text-purple-500" />
              {isZh ? 'Agent 项目' : 'Agent Projects'}
              <span className="text-xs text-zinc-400 font-normal ml-1">{agents.length}</span>
            </h3>
          </div>
          <div className="p-4">
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-2">
              {agents.map((agent) => {
                const isFlagged = flaggedAgents.has(agent.name)
                const isBeingAnalyzed = llmAnalyzing?.agent === agent.name
                const isBeingScanned = scanningAgent?.name === agent.name
                return (
                  <div
                    key={agent.name}
                    className={`rounded-lg border px-3 py-2 transition-all duration-300 ${
                      isBeingAnalyzed ? 'border-purple-400 bg-purple-50 shadow-sm shadow-purple-100 ring-1 ring-purple-300' :
                      isBeingScanned ? 'border-orange-400 bg-orange-50 shadow-sm shadow-orange-100 ring-1 ring-orange-300' :
                      isFlagged ? 'border-red-300 bg-red-50 shadow-sm shadow-red-100' :
                      'border-green-200 bg-green-50'
                    }`}
                    style={{ animation: `fadeSlideIn 0.3s ease-out` }}
                  >
                    <div className="font-medium text-sm text-zinc-200 truncate">
                      {isBeingAnalyzed && <Cpu className="inline h-3 w-3 text-purple-500 animate-pulse mr-1" />}
                      {isBeingScanned && <Search className="inline h-3 w-3 text-orange-500 animate-pulse mr-1" />}
                      {agent.name}
                    </div>
                    <div className="text-xs text-zinc-400">
                      {agent.tools_count} {isZh ? '个工具' : 'tools'}
                      {isFlagged && <ShieldAlert className="inline h-3 w-3 text-red-500 ml-1" />}
                    </div>
                    <div className="mt-1.5 flex flex-wrap gap-1 max-h-16 overflow-hidden">
                      {agent.tool_names.map(t => (
                        <span key={t} className="inline-block px-1.5 py-0.5 rounded text-[10px] bg-purple-100/60 text-purple-700 font-mono truncate max-w-[120px]">
                          {t}
                        </span>
                      ))}
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        </div>
      )}

      {/* AI Analysis Spotlight */}
      {phase === 'llm_analysis' && llmAnalyzing && (
        <div className="rounded-xl border-2 border-purple-300 bg-gradient-to-r from-purple-50 to-indigo-50 p-5 flex-shrink-0">
          <div className="flex items-center gap-3 mb-3">
            <div className="h-10 w-10 rounded-full bg-purple-100 border-2 border-purple-300 flex items-center justify-center animate-spin-slow">
              <Cpu className="h-5 w-5 text-purple-600" />
            </div>
            <div className="flex-1">
              <div className="text-sm font-semibold text-purple-800">
                {isZh ? 'AI 正在深度分析' : 'AI Deep Analysis'}
              </div>
              <div className="text-xs text-purple-500">
                {isZh
                  ? `正在分析 ${Math.min(llmAnalysisIdx + 1, agentToolPairs.length)} / ${agentToolPairs.length} 个技能`
                  : `Analyzing ${Math.min(llmAnalysisIdx + 1, agentToolPairs.length)} / ${agentToolPairs.length} skills`}
              </div>
            </div>
          </div>
          <div className="flex items-center gap-3 p-3 rounded-lg bg-zinc-900/50/70 border border-purple-200" key={`${llmAnalyzing.agent}-${llmAnalyzing.tool_name}`} style={{ animation: 'fadeSlideIn 0.3s ease-out' }}>
            <Package className="h-5 w-5 text-purple-500 flex-shrink-0" />
            <div className="flex-1 min-w-0">
              <div className="text-sm font-medium text-zinc-200">
                {llmAnalyzing.agent} <span className="text-zinc-400 font-normal mx-1">›</span> <span className="font-mono text-purple-700">{llmAnalyzing.tool_name}</span>
              </div>
            </div>
          </div>
        </div>
      )}


      {/* Complete: Full grouped results */}
      {phase === 'complete' && result && (
        <>
          {/* Stats */}
          <div className="grid grid-cols-4 gap-3 flex-shrink-0">
            <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-4">
              <div className="text-xs text-zinc-400 mb-1">{isZh ? 'Agent 项目' : 'Agents'}</div>
              <div className="text-2xl font-bold text-zinc-200">{result.agents_scanned}</div>
            </div>
            <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-4">
              <div className="text-xs text-zinc-400 mb-1">{isZh ? '工具定义' : 'Tools'}</div>
              <div className="text-2xl font-bold text-zinc-200">{result.tools_extracted}</div>
            </div>
            <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-4">
              <div className="text-xs text-zinc-400 mb-1">{isZh ? '安全问题' : 'Issues'}</div>
              <div className={`text-2xl font-bold ${result.result.findings.length > 0 ? 'text-red-600' : 'text-green-600'}`}>
                {result.result.findings.length}
              </div>
            </div>
            <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-4">
              <div className="text-xs text-zinc-400 mb-1">{isZh ? '最高严重度' : 'Max Severity'}</div>
              <div className="mt-1"><SeverityBadge severity={result.result.max_severity} /></div>
            </div>
          </div>

          {/* Findings grouped by agent */}
          <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 flex-shrink-0">
            <div className="p-4 border-b border-zinc-800">
              <h3 className="font-medium text-zinc-200 flex items-center gap-2">
                <ShieldAlert className="h-4 w-4 text-purple-500" />
                {isZh ? '详细扫描结果' : 'Detailed Results'}
                <span className="text-xs text-zinc-400 font-normal">
                  ({result.result.scan_duration_ms.toFixed(0)}ms)
                </span>
                {result.result.engine_summary.llm_semantic ? (
                  <span className="px-2 py-0.5 rounded-full bg-purple-100 text-purple-600 text-[10px] font-medium">
                    <Cpu className="h-2.5 w-2.5 inline mr-0.5" />
                    {isZh ? 'AI 增强' : 'AI Enhanced'}
                  </span>
                ) : null}
              </h3>
            </div>

            {result.result.findings.length === 0 ? (
              <div className="p-8 text-center">
                <ShieldCheck className="h-12 w-12 text-green-400 mx-auto mb-3" />
                <p className="text-sm text-zinc-400">{isZh ? '未发现安全问题' : 'No security issues found'}</p>
              </div>
            ) : (
              <div className="divide-y divide-zinc-800">
                {Object.entries(findingsByAgent).sort(([a], [b]) => a.localeCompare(b))
                  .filter((_, idx) => idx < visibleAgentGroups)
                  .map(([agent, agentFindings]) => {
                  const isExpanded = expandedAgents.has(agent)
                  const maxSev = agentFindings.reduce((max, f) =>
                    SEV_ORDER.indexOf(f.severity) > SEV_ORDER.indexOf(max) ? f.severity : max
                  , 'info')

                  return (
                    <div key={agent} style={{ animation: 'fadeSlideIn 0.4s ease-out' }}>
                      <button
                        onClick={() => toggleAgent(agent)}
                        className="w-full flex items-center gap-3 px-4 py-3 hover:bg-zinc-800/50 transition-colors text-left"
                      >
                        {isExpanded ? <ChevronDown className="h-4 w-4 text-zinc-400" /> : <ChevronRight className="h-4 w-4 text-zinc-400" />}
                        <Package className="h-4 w-4 text-zinc-400" />
                        <span className="font-medium text-sm text-zinc-200 flex-1">{agent}</span>
                        <span className="text-xs text-zinc-400 mr-2">
                          {agentFindings.length} {isZh ? '个问题' : 'issues'}
                        </span>
                        <SeverityBadge severity={maxSev} />
                      </button>

                      {isExpanded && (
                        <div className="px-4 pb-3 space-y-2">
                          {agentFindings.map((f, idx) => {
                            const toolName = f.tool_name || f.item_name || ''
                            return (
                              <div key={idx} className={`rounded-lg border p-3 ${SEVERITY_CONFIG[f.severity]?.bg || 'bg-zinc-800/50'} ${SEVERITY_CONFIG[f.severity]?.border || 'border-zinc-800'}`}>
                                <div className="flex items-start gap-2">
                                  <SeverityBadge severity={f.severity} />
                                  <div className="flex-1 min-w-0">
                                    <div className="font-medium text-sm text-zinc-200">{f.title}</div>
                                    {toolName && (
                                      <div className="flex items-center gap-1 mt-1 text-xs text-zinc-400">
                                        <FileCode2 className="h-3 w-3" />
                                        <span className="font-mono">{toolName}</span>
                                      </div>
                                    )}
                                    {f.description && (
                                      <p className="mt-1.5 text-xs text-zinc-400 leading-relaxed">{f.description.slice(0, 500)}</p>
                                    )}
                                    {f.evidence && (
                                      <div className="mt-1.5 px-2 py-1.5 rounded bg-red-100/50 text-xs font-mono text-red-700 break-all leading-relaxed">{f.evidence.slice(0, 300)}</div>
                                    )}
                                    {f.remediation && (
                                      <div className="mt-1.5 text-xs text-emerald-700 bg-emerald-50/50 px-2 py-1.5 rounded">
                                        <span className="font-medium">{isZh ? '🛡 修复建议：' : '🛡 Remediation: '}</span>
                                        {f.remediation.slice(0, 300)}
                                      </div>
                                    )}
                                    <div className="mt-1.5 flex items-center gap-2 text-[10px] text-zinc-400">
                                      {f.engine === 'llm_semantic' && (
                                        <span className="px-1.5 py-0.5 rounded bg-purple-100 text-purple-600 font-medium">
                                          <Cpu className="h-2.5 w-2.5 inline mr-0.5" />AI
                                        </span>
                                      )}
                                      {f.evidence && f.engine !== 'llm_semantic' && (
                                        <span className="px-1.5 py-0.5 rounded bg-purple-50 text-purple-500 font-medium">{isZh ? 'AI 增强' : 'AI Enhanced'}</span>
                                      )}
                                      <span>{isZh ? '引擎' : 'Engine'}: {f.engine} | {isZh ? '类别' : 'Category'}: {f.category}</span>
                                    </div>
                                  </div>
                                </div>
                              </div>
                            )
                          })}
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        </>
      )}

      {/* CSS Animation */}
      <style>{`
        @keyframes fadeSlideIn {
          from { opacity: 0; transform: translateY(8px); }
          to { opacity: 1; transform: translateY(0); }
        }
        @keyframes spin-slow {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
        .animate-spin-slow {
          animation: spin-slow 3s linear infinite;
        }
        .animate-pulse-slow {
          animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
        }
      `}</style>
    </div>
  )
}

export default SkillScannerPage
