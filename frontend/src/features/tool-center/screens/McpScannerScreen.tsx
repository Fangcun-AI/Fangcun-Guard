import React, { useState, useRef, useCallback, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import {
  ArrowLeft, Network, FolderSearch, Play, Loader2,
  AlertTriangle, ShieldAlert, ShieldCheck, ChevronDown, ChevronRight,
  Server, Info, CheckCircle2, Search, Cpu, Package
} from 'lucide-react'
import { Button } from '@/components/ui/button'

interface Finding {
  server_name?: string
  item_name?: string
  item_type?: string
  engine: string
  category: string
  severity: string
  title: string
  description: string
  evidence: string
  remediation: string
  confidence: number
  _idx?: number
}

interface ScanResult {
  request_id: string
  agents_scanned: number
  servers_extracted: number
  servers_by_agent: Record<string, { servers_count: number; server_names: string[] }>
  result: {
    findings: Finding[]
    servers_scanned: number
    servers_flagged: number
    max_severity: string
    scan_duration_ms: number
    engine_summary: Record<string, number>
  }
}

type ScanPhase = 'idle' | 'loading' | 'discovery' | 'scanning' | 'llm_analysis' | 'complete'

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

const McpScannerPage: React.FC = () => {
  const navigate = useNavigate()
  const { i18n } = useTranslation()
  const isZh = i18n.language?.startsWith('zh')

  const [directory, setDirectory] = useState('/mnt/scan_targets')
  const [phase, setPhase] = useState<ScanPhase>('idle')
  const [result, setResult] = useState<ScanResult | null>(null)
  const [error, setError] = useState('')

  // Real-time streaming state
  const [agents, setAgents] = useState<Array<{ name: string; servers_count: number; server_names: string[] }>>([])
  const [findings, setFindings] = useState<Finding[]>([])
  const [llmStatus, setLlmStatus] = useState('')
  const [llmAnalyzing, setLlmAnalyzing] = useState<{ server_name: string; agent: string } | null>(null)
  const [scanningAgent, setScanningAgent] = useState<{ name: string; index: number; total: number; servers_count: number } | null>(null)
  const [expandedAgents, setExpandedAgents] = useState<Set<string>>(new Set())
  const [flaggedAgents, setFlaggedAgents] = useState<Set<string>>(new Set())
  const [visibleAgentGroups, setVisibleAgentGroups] = useState(0)
  const [llmAnalyzingAgent, setLlmAnalyzingAgent] = useState<string | null>(null)
  const [displayedFindingsCount, setDisplayedFindingsCount] = useState(0)

  const abortRef = useRef<AbortController | null>(null)
  const pendingResultRef = useRef<{ result: ScanResult; serverAgentMap: Record<string, string> } | null>(null)
  const [pendingComplete, setPendingComplete] = useState(false)

  const handleScan = useCallback(async () => {
    if (!directory.trim()) return

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
    setPendingComplete(false)
    pendingResultRef.current = null

    try {
      const token = localStorage.getItem('auth_token')
      const response = await fetch('/api/v1/mcp-scanner/scan-directory', {
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
      let serverAgentMap: Record<string, string> = {}

      setPhase('discovery')

      let currentEvent = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })

        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (line.startsWith('event: ')) {
            currentEvent = line.slice(7).trim()
          } else if (line.startsWith('data: ') && currentEvent) {
            try {
              const data = JSON.parse(line.slice(6))
              handleSSEEvent(currentEvent, data, serverAgentMap)
            } catch {}
            currentEvent = ''
          }
        }
      }

      // Process remaining buffer
      if (buffer.trim()) {
        const lines = buffer.split('\n')
        for (const line of lines) {
          if (line.startsWith('event: ')) {
            currentEvent = line.slice(7).trim()
          } else if (line.startsWith('data: ') && currentEvent) {
            try {
              const data = JSON.parse(line.slice(6))
              handleSSEEvent(currentEvent, data, serverAgentMap)
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

  const handleSSEEvent = useCallback((event: string, data: any, serverAgentMap: Record<string, string>) => {
    switch (event) {
      case 'agent_discovered':
        setPhase('discovery')
        setAgents(prev => [...prev, {
          name: data.agent,
          servers_count: data.servers_count,
          server_names: data.server_names || [],
        }])
        for (const s of (data.server_names || [])) {
          serverAgentMap[s] = data.agent
        }
        break

      case 'discovery_complete':
        // Discovery includes extraction — move directly to scanning
        // (scanning phase events will follow immediately from backend)
        break

      case 'phase':
        if (data.phase === 'scanning') setPhase('scanning')
        if (data.phase === 'llm_analysis') {
          setPhase('llm_analysis')
          if (llmPhaseStartRef.current === 0) llmPhaseStartRef.current = Date.now()
        }
        if (data.message) setLlmStatus(data.message)
        break

      case 'scan_progress':
        setPhase('scanning')
        setScanningAgent({
          name: data.agent,
          index: data.agent_index,
          total: data.agents_total,
          servers_count: data.servers_count,
        })
        break

      case 'finding':
        setPhase(prev => prev === 'discovery' ? 'scanning' : prev)
        setFindings(prev => {
          const f = { ...(data as Finding), _idx: prev.length }
          const next = [...prev, f]
          return next.sort((a, b) => SEV_ORDER.indexOf(b.severity) - SEV_ORDER.indexOf(a.severity))
        })
        // Flag agents: handle cross-server findings like "server_a + server_b"
        const serverName = data.server_name || data.item_name || ''
        const serverParts = serverName.includes(' + ') ? serverName.split(' + ') : [serverName]
        const matchedAgents = new Set<string>()
        for (const part of serverParts) {
          const an = serverAgentMap[part.trim()]
          if (an) matchedAgents.add(an)
        }
        if (matchedAgents.size > 0) {
          setFlaggedAgents(prev => new Set([...prev, ...matchedAgents]))
        }
        break

      case 'agent_scan_done':
        break

      case 'static_complete':
        setScanningAgent(null)
        setLlmStatus(isZh ? '静态分析完成，启动 AI 深度分析...' : 'Static analysis done, starting AI analysis...')
        break

      case 'llm_progress':
        setPhase('llm_analysis')
        if (llmPhaseStartRef.current === 0) llmPhaseStartRef.current = Date.now()
        if (data.type === 'analyzing') {
          // No-op: spotlight driven by timer
        } else if (data.type === 'enriched') {
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
          // Don't clear llmAnalyzing — let cycling animation continue until it finishes
          setLlmStatus(isZh ? `AI 分析完成，已增强 ${data.enriched_count} 个发现` : `AI analysis done, enriched ${data.enriched_count} findings`)
        } else if (data.type === 'error') {
          // Don't clear llmAnalyzing — let cycling animation continue
          setLlmStatus(isZh ? `AI 分析中...` : `AI analyzing...`)
        }
        break

      case 'complete': {
        // Store result — don't transition yet, let the cycling animation finish first
        pendingResultRef.current = {
          result: data as ScanResult,
          serverAgentMap: { ...serverAgentMap },
        }
        setPendingComplete(true)
        break
      }

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

  // Progressive reveal
  const sortedAgentGroupKeys = React.useMemo(() => {
    if (!result || phase !== 'complete') return []
    const serverAgentMap: Record<string, string> = {}
    for (const [agent, info] of Object.entries(result.servers_by_agent)) {
      for (const s of info.server_names) serverAgentMap[s] = agent
    }
    const groups: Record<string, Finding[]> = {}
    for (const f of result.result.findings) {
      const sn = f.server_name || f.item_name || ''
      const parts = sn.includes(' + ') ? sn.split(' + ').map(p => p.trim()) : [sn]
      const matchedAgent = parts.map(p => serverAgentMap[p]).find(Boolean)
      const agent = matchedAgent || (isZh ? '跨服务器分析' : 'Cross-Server Analysis')
      if (!groups[agent]) groups[agent] = []
      groups[agent].push(f)
    }
    return Object.keys(groups).sort()
  }, [result, phase, isZh])

  useEffect(() => {
    if (phase !== 'complete' || sortedAgentGroupKeys.length === 0) return
    if (visibleAgentGroups >= sortedAgentGroupKeys.length) return
    const timer = setTimeout(() => { setVisibleAgentGroups(prev => prev + 1) }, 300)
    return () => clearTimeout(timer)
  }, [phase, visibleAgentGroups, sortedAgentGroupKeys.length])

  // Build flat list of agent→server pairs for spotlight
  const agentServerPairs = React.useMemo(() => {
    const pairs: Array<{ agent: string; server: string }> = []
    for (const a of agents) {
      for (const s of a.server_names) {
        pairs.push({ agent: a.name, server: s })
      }
    }
    return pairs
  }, [agents])

  // Timer-based spotlight cycling during LLM analysis
  const [llmAnalysisIdx, setLlmAnalysisIdx] = useState(0)

  useEffect(() => {
    if (phase !== 'llm_analysis' || agentServerPairs.length === 0) return
    const idx = llmAnalysisIdx % agentServerPairs.length
    const pair = agentServerPairs[idx]
    setLlmAnalyzing({ agent: pair.agent, server_name: pair.server })
    setLlmAnalyzingAgent(pair.agent)

    if (llmAnalysisIdx >= agentServerPairs.length) return
    // Dynamic speed: cycle through ALL servers in ~8 seconds total
    const stepMs = Math.max(50, Math.floor(8000 / agentServerPairs.length))
    const timer = setTimeout(() => { setLlmAnalysisIdx(prev => prev + 1) }, stepMs)
    return () => clearTimeout(timer)
  }, [phase, llmAnalysisIdx, agentServerPairs])

  // Transition to complete: wait for cycling to finish, then show results
  useEffect(() => {
    if (!pendingComplete || !pendingResultRef.current) return
    // If in LLM analysis phase, wait for cycling to reach the end
    if (phase === 'llm_analysis' && agentServerPairs.length > 0 && llmAnalysisIdx < agentServerPairs.length) return

    const { result: pr, serverAgentMap } = pendingResultRef.current
    // Brief pause at 76/76 before revealing results
    const timer = setTimeout(() => {
      setResult(pr)
      setPhase('complete')
      setVisibleAgentGroups(0)
      const agentsWithFindings = new Set<string>()
      for (const f of (pr.result?.findings || [])) {
        const sn = f.server_name || f.item_name || ''
        const parts = sn.includes(' + ') ? sn.split(' + ').map((p: string) => p.trim()) : [sn]
        for (const part of parts) {
          const an = serverAgentMap[part]
          if (an) agentsWithFindings.add(an)
        }
      }
      setExpandedAgents(agentsWithFindings)
      setFindings(pr.result.findings.sort(
        (a: Finding, b: Finding) => SEV_ORDER.indexOf(b.severity) - SEV_ORDER.indexOf(a.severity)
      ))
      pendingResultRef.current = null
      setPendingComplete(false)
    }, 800)
    return () => clearTimeout(timer)
  }, [pendingComplete, phase, llmAnalysisIdx, agentServerPairs.length])

  // Smooth counter
  useEffect(() => {
    if (displayedFindingsCount >= findings.length) return
    const timer = setTimeout(() => { setDisplayedFindingsCount(prev => prev + 1) }, 80)
    return () => clearTimeout(timer)
  }, [displayedFindingsCount, findings.length])

  // Group findings by agent (for complete phase)
  const findingsByAgent: Record<string, Finding[]> = {}
  if (result && phase === 'complete') {
    const serverAgentMap: Record<string, string> = {}
    for (const [agent, info] of Object.entries(result.servers_by_agent)) {
      for (const s of info.server_names) serverAgentMap[s] = agent
    }
    for (const f of result.result.findings) {
      const sn = f.server_name || f.item_name || ''
      // Handle cross-server findings like "server_a + server_b"
      const parts = sn.includes(' + ') ? sn.split(' + ').map(p => p.trim()) : [sn]
      const matchedAgent = parts.map(p => serverAgentMap[p]).find(Boolean)
      const agent = matchedAgent || (isZh ? '跨服务器分析' : 'Cross-Server Analysis')
      if (!findingsByAgent[agent]) findingsByAgent[agent] = []
      findingsByAgent[agent].push(f)
    }
  }

  const totalServers = result?.servers_extracted || agents.reduce((s, a) => s + a.servers_count, 0)

  // Phase indicator
  const phaseSteps = [
    { key: 'discovery', label: isZh ? '发现 Agent & 提取 MCP' : 'Discover & Extract', icon: <Search className="h-3.5 w-3.5" /> },
    { key: 'scanning', label: isZh ? '安全扫描' : 'Security Scan', icon: <ShieldAlert className="h-3.5 w-3.5" /> },
    { key: 'llm_analysis', label: isZh ? 'AI 深度分析' : 'AI Analysis', icon: <Cpu className="h-3.5 w-3.5" /> },
  ]
  const phaseKeys = ['discovery', 'scanning', 'llm_analysis', 'complete']
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
            <div className="h-8 w-8 rounded-lg bg-teal-50 border border-teal-200 flex items-center justify-center">
              <Network className="h-4 w-4 text-teal-600" />
            </div>
            <div>
              <h2 className="text-sm font-semibold text-white">
                {isZh ? 'MCP 服务器安全扫描' : 'MCP Server Scanner'}
              </h2>
              <p className="text-xs text-zinc-400">
                {isZh ? '扫描 Agent 项目中的 MCP 服务器配置，检测跨服务器攻击链' : 'Scan agent MCP configs for cross-server attack chains'}
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Scan Input */}
      <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-5 flex-shrink-0">
        <div className="flex items-center gap-2 mb-3">
          <FolderSearch className="h-5 w-5 text-teal-500" />
          <h3 className="font-medium text-zinc-200">
            {isZh ? '选择扫描目录' : 'Select Scan Directory'}
          </h3>
        </div>
        <p className="text-sm text-zinc-400 mb-4">
          {isZh
            ? '输入包含 AI Agent 项目的目录路径，系统将自动发现 MCP 服务器配置并进行安全扫描。'
            : 'Enter the path to a directory of AI agent projects.'}
        </p>
        <div className="flex gap-3">
          <input
            type="text"
            value={directory}
            onChange={e => setDirectory(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && !isScanning && handleScan()}
            placeholder={isZh ? '例如: /path/to/agent-projects' : 'e.g. /path/to/agent-projects'}
            className="flex-1 px-4 py-2.5 rounded-lg border border-zinc-800 bg-zinc-800/50 text-sm focus:outline-none focus:ring-2 focus:ring-teal-500/20 focus:border-teal-400 transition-all"
            disabled={isScanning}
          />
          <Button
            onClick={handleScan}
            disabled={isScanning || !directory.trim()}
            className="gap-2 bg-gradient-to-r from-teal-600 to-teal-500 hover:from-teal-700 hover:to-teal-600 text-white px-6"
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
                    <div className={`flex-1 h-0.5 rounded ${isDone ? 'bg-teal-400' : isActive ? 'bg-teal-200' : 'bg-zinc-800'} transition-colors duration-500`} />
                  )}
                  <div className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium transition-all duration-500 ${
                    isDone ? 'bg-green-50 text-green-700 border border-green-200' :
                    isActive ? 'bg-teal-50 text-teal-700 border border-teal-200 animate-pulse' :
                    'bg-zinc-800/50 text-zinc-400 border border-zinc-800'
                  }`}>
                    {isDone ? <CheckCircle2 className="h-3.5 w-3.5 text-green-500" /> : step.icon}
                    {step.label}
                  </div>
                </React.Fragment>
              )
            })}
          </div>

          <div className="mt-3 text-sm text-zinc-400">
            {phase === 'loading' && (
              <span className="flex items-center gap-2">
                <Loader2 className="h-3.5 w-3.5 animate-spin text-teal-500" />
                {isZh ? '连接中...' : 'Connecting...'}
              </span>
            )}
            {phase === 'discovery' && (
              <span className="flex items-center gap-2">
                <Loader2 className="h-3.5 w-3.5 animate-spin text-teal-500" />
                {isZh
                  ? `正在发现 Agent 并提取 MCP 配置... 已发现 ${agents.length} 个 Agent, ${totalServers} 个服务器`
                  : `Discovering agents & extracting MCP configs... ${agents.length} agents, ${totalServers} servers`}
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
                    → {isZh ? '正在扫描' : 'Scanning'} {scanningAgent.name} ({scanningAgent.servers_count} {isZh ? '个服务器' : 'servers'})
                  </div>
                )}
              </div>
            )}
            {phase === 'llm_analysis' && (
              <div className="space-y-1">
                <span className="flex items-center gap-2">
                  <Cpu className="h-3.5 w-3.5 animate-pulse text-teal-500" />
                  {isZh
                    ? `AI 深度分析中... 正在分析 ${Math.min(llmAnalysisIdx + 1, agentServerPairs.length)} / ${agentServerPairs.length} 个服务器`
                    : `AI deep analysis... analyzing ${Math.min(llmAnalysisIdx + 1, agentServerPairs.length)} / ${agentServerPairs.length} servers`}
                </span>
                <div className="ml-6 h-1.5 bg-zinc-800/50 rounded-full overflow-hidden w-48">
                  <div
                    className="h-full bg-gradient-to-r from-teal-500 to-teal-400 rounded-full transition-all duration-500"
                    style={{ width: `${agentServerPairs.length > 0 ? (Math.min(llmAnalysisIdx + 1, agentServerPairs.length) / agentServerPairs.length) * 100 : 0}%` }}
                  />
                </div>
              </div>
            )}
            {phase === 'complete' && result && (
              <span className="flex items-center gap-2 text-green-600">
                <CheckCircle2 className="h-3.5 w-3.5" />
                {isZh
                  ? `扫描完成: ${result.agents_scanned} 个 Agent 项目, ${Object.keys(result.servers_by_agent).length} 个含 MCP 配置, ${result.servers_extracted} 个 MCP 服务器, ${result.result.findings.length} 个安全问题 (${result.result.scan_duration_ms.toFixed(0)}ms)`
                  : `Complete: ${result.agents_scanned} agent projects, ${Object.keys(result.servers_by_agent).length} with MCP, ${result.servers_extracted} servers, ${result.result.findings.length} issues (${result.result.scan_duration_ms.toFixed(0)}ms)`}
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
              <Server className="h-4 w-4 text-teal-500" />
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
                      isBeingAnalyzed ? 'border-teal-400 bg-teal-50 shadow-sm shadow-teal-100 ring-1 ring-teal-300' :
                      isBeingScanned ? 'border-orange-400 bg-orange-50 shadow-sm shadow-orange-100 ring-1 ring-orange-300' :
                      isFlagged ? 'border-red-300 bg-red-50 shadow-sm shadow-red-100' :
                      'border-green-200 bg-green-50'
                    }`}
                    style={{ animation: `fadeSlideIn 0.3s ease-out` }}
                  >
                    <div className="font-medium text-sm text-zinc-200 truncate">
                      {isBeingAnalyzed && <Cpu className="inline h-3 w-3 text-teal-500 animate-pulse mr-1" />}
                      {isBeingScanned && <Search className="inline h-3 w-3 text-orange-500 animate-pulse mr-1" />}
                      {isFlagged && <ShieldAlert className="inline h-3 w-3 text-red-500 mr-1" />}
                      {agent.name}
                    </div>
                    <div className="text-xs text-zinc-400">
                      {agent.servers_count} {isZh ? '个服务器' : 'servers'}
                    </div>
                    {agent.server_names.length > 0 && (
                      <div className="mt-1.5 flex flex-wrap gap-1 max-h-16 overflow-hidden">
                        {agent.server_names.map(s => {
                          // Check if this specific server has findings
                          const serverHasFinding = findings.some(f => {
                            const sn = f.server_name || f.item_name || ''
                            const parts = sn.includes(' + ') ? sn.split(' + ').map(p => p.trim()) : [sn]
                            return parts.includes(s)
                          })
                          return (
                            <span key={s} className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-mono truncate max-w-[120px] ${
                              serverHasFinding ? 'bg-red-100 text-red-700' : 'bg-teal-100/60 text-teal-700'
                            }`}>
                              <Server className="h-2.5 w-2.5" />
                              {s}
                            </span>
                          )
                        })}
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          </div>
        </div>
      )}

      {/* AI Analysis Spotlight */}
      {phase === 'llm_analysis' && llmAnalyzing && (
        <div className="rounded-xl border-2 border-teal-300 bg-gradient-to-r from-teal-50 to-cyan-50 p-5 flex-shrink-0">
          <div className="flex items-center gap-3 mb-3">
            <div className="h-10 w-10 rounded-full bg-teal-100 border-2 border-teal-300 flex items-center justify-center animate-spin-slow">
              <Cpu className="h-5 w-5 text-teal-600" />
            </div>
            <div className="flex-1">
              <div className="text-sm font-semibold text-teal-800">
                {isZh ? 'AI 正在深度分析' : 'AI Deep Analysis'}
              </div>
              <div className="text-xs text-teal-500">
                {isZh
                  ? `正在分析 ${Math.min(llmAnalysisIdx + 1, agentServerPairs.length)} / ${agentServerPairs.length} 个服务器`
                  : `Analyzing ${Math.min(llmAnalysisIdx + 1, agentServerPairs.length)} / ${agentServerPairs.length} servers`}
              </div>
            </div>
          </div>
          <div className="flex items-center gap-3 p-3 rounded-lg bg-zinc-900/50/70 border border-teal-200" key={`${llmAnalyzing.agent}-${llmAnalyzing.server_name}`} style={{ animation: 'fadeSlideIn 0.3s ease-out' }}>
            <Server className="h-5 w-5 text-teal-500 flex-shrink-0" />
            <div className="flex-1 min-w-0">
              <div className="text-sm font-medium text-zinc-200">
                {llmAnalyzing.agent} <span className="text-zinc-400 font-normal mx-1">›</span> <span className="font-mono text-teal-700">{llmAnalyzing.server_name}</span>
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
              <div className="text-xs text-zinc-400 mb-1">{isZh ? 'MCP 服务器' : 'Servers'}</div>
              <div className="text-2xl font-bold text-zinc-200">{result.servers_extracted}</div>
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
                <ShieldAlert className="h-4 w-4 text-teal-500" />
                {isZh ? '详细扫描结果' : 'Detailed Results'}
                <span className="text-xs text-zinc-400 font-normal">
                  ({result.result.scan_duration_ms.toFixed(0)}ms)
                </span>
                {result.result.engine_summary.llm_semantic ? (
                  <span className="px-2 py-0.5 rounded-full bg-teal-100 text-teal-600 text-[10px] font-medium">
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
                            const serverName = f.server_name || f.item_name || ''
                            return (
                              <div key={idx} className={`rounded-lg border p-3 ${SEVERITY_CONFIG[f.severity]?.bg || 'bg-zinc-800/50'} ${SEVERITY_CONFIG[f.severity]?.border || 'border-zinc-800'}`}>
                                <div className="flex items-start gap-2">
                                  <SeverityBadge severity={f.severity} />
                                  <div className="flex-1 min-w-0">
                                    <div className="font-medium text-sm text-zinc-200">{f.title}</div>
                                    {serverName && (
                                      <div className="flex items-center gap-1 mt-1 text-xs text-zinc-400">
                                        <Server className="h-3 w-3" />
                                        <span className="font-mono">{serverName}</span>
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
                                        <span className="px-1.5 py-0.5 rounded bg-teal-100 text-teal-600 font-medium">
                                          <Cpu className="h-2.5 w-2.5 inline mr-0.5" />AI
                                        </span>
                                      )}
                                      {f.evidence && f.engine !== 'llm_semantic' && (
                                        <span className="px-1.5 py-0.5 rounded bg-teal-50 text-teal-500 font-medium">{isZh ? 'AI 增强' : 'AI Enhanced'}</span>
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
      `}</style>
    </div>
  )
}

export default McpScannerPage
