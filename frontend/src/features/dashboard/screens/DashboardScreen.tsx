import React, { useCallback, useEffect, useState } from 'react'
import ReactECharts from 'echarts-for-react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import {
  AlertCircle,
  AlertTriangle,
  CheckCircle,
  FileCheck,
  Lock,
  Shield,
  TrendingUp,
} from 'lucide-react'

import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { useApplication } from '@/contexts/ApplicationContext'
import { dashboardApi } from '@/features/dashboard/api'
import type { DashboardStats } from '@/types'

const riskLevels = [
  ['high_risk', 'dashboard.highRisk', '#ff4d4f'],
  ['medium_risk', 'dashboard.mediumRisk', '#faad14'],
  ['low_risk', 'dashboard.lowRisk', '#fadb14'],
  ['no_risk', 'dashboard.noRisk', '#52c41a'],
] as const

const Dashboard: React.FC = () => {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const { currentApplicationId } = useApplication()
  const [stats, setStats] = useState<DashboardStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchStats = useCallback(async () => {
    setLoading(true)
    try {
      setStats(await dashboardApi.getStats())
      setError(null)
    } catch (err) {
      console.error('Error fetching stats:', err)
      setError(t('dashboard.errorFetchingStats'))
    } finally {
      setLoading(false)
    }
  }, [currentApplicationId, t])

  useEffect(() => {
    void fetchStats()
  }, [fetchStats])

  if (loading) {
    return (
      <div className="flex min-h-[400px] items-center justify-center">
        <div className="h-12 w-12 animate-spin rounded-full border-4 border-primary border-t-transparent" />
      </div>
    )
  }

  if (error) {
    return (
      <Alert variant="destructive">
        <AlertCircle className="h-5 w-5" />
        <AlertDescription className="ml-2 flex items-center justify-between">
          <div>
            <p className="font-medium">{t('dashboard.error')}</p>
            <p className="mt-1 text-sm">{error}</p>
          </div>
          <Button variant="outline" size="sm" onClick={fetchStats}>
            {t('dashboard.retry')}
          </Button>
        </AlertDescription>
      </Alert>
    )
  }

  if (!stats) return null

  const openResults = (state?: Record<string, string | string[]>) => {
    navigate('/results', state ? { state } : undefined)
  }
  const totalRisks = stats.high_risk_count + stats.medium_risk_count + stats.low_risk_count
  const cards = [
    [FileCheck, 'dashboard.totalRequests', stats.total_requests, 'text-indigo-600', () => openResults()],
    [Shield, 'dashboard.securityRisks', stats.security_risks, 'text-orange-500', () => openResults({ security_risk_level: 'any_risk' })],
    [Shield, 'dashboard.complianceRisks', stats.compliance_risks, 'text-purple-600', () => openResults({ compliance_risk_level: 'any_risk' })],
    [Lock, 'dashboard.dataLeaks', stats.data_leaks, 'text-pink-600', () => openResults({ data_risk_level: 'any_risk' })],
    [AlertTriangle, 'dashboard.totalRisks', totalRisks, 'text-orange-600', () => openResults({ risk_level: 'any_risk' })],
    [CheckCircle, 'dashboard.safePassed', stats.safe_count, 'text-green-600', () => openResults({ risk_level: ['no_risk'] })],
  ] as const
  const pieData = riskLevels.map(([level, label, color]) => ({
    value: stats.risk_distribution[level] || 0,
    name: t(label),
    itemStyle: { color },
  }))
  const trendSeries = [
    ['dashboard.totalDetections', 'total', '#1890ff'],
    ['dashboard.highRisk', 'high_risk', '#ff4d4f'],
    ['dashboard.mediumRisk', 'medium_risk', '#faad14'],
  ] as const
  const chartOptions = {
    distribution: {
      title: { text: t('dashboard.riskDistribution'), left: 'center' },
      tooltip: { trigger: 'item', formatter: '{a} <br/>{b}: {c} ({d}%)' },
      legend: { orient: 'vertical', left: 'left' },
      series: [{
        name: t('dashboard.riskLevel'),
        type: 'pie',
        radius: '50%',
        data: pieData,
        emphasis: { itemStyle: { shadowBlur: 10, shadowOffsetX: 0, shadowColor: 'rgba(0, 0, 0, 0.5)' } },
      }],
    },
    trends: {
      title: { text: t('dashboard.dailyTrends'), left: 'center' },
      tooltip: { trigger: 'axis' },
      legend: { data: trendSeries.map(([label]) => t(label)), bottom: 0 },
      xAxis: { type: 'category', data: stats.daily_trends.map(({ date }) => date) },
      yAxis: { type: 'value' },
      series: trendSeries.map(([label, field, color]) => ({
        name: t(label),
        type: 'line',
        data: stats.daily_trends.map((entry) => entry[field]),
        itemStyle: { color },
      })),
    },
  }

  const renderCard = ([Icon, label, value, color, onClick]: typeof cards[number], showUnit = true) => (
    <Card className="cursor-pointer transition-shadow" onClick={onClick}>
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="text-sm font-medium text-zinc-400">{t(label)}</CardTitle>
        <Icon className="h-5 w-5 text-zinc-500" />
      </CardHeader>
      <CardContent>
        <div className={`text-3xl font-bold ${color}`}>
          {value}
          {showUnit && <span className="ml-2 text-sm font-normal text-zinc-400">{t('dashboard.times')}</span>}
        </div>
      </CardContent>
    </Card>
  )

  return (
    <div className="space-y-6">
      <h2 className="text-3xl font-bold tracking-tight">{t('dashboard.title')}</h2>
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
        {cards.slice(0, 4).map((card, index) => (
          <React.Fragment key={card[1]}>{renderCard(card, index !== 0)}</React.Fragment>
        ))}
      </div>
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        {cards.slice(4).map((card) => <React.Fragment key={card[1]}>{renderCard(card)}</React.Fragment>)}
        <Card className="transition-shadow">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-zinc-400">{t('dashboard.blockRate')}</CardTitle>
            <TrendingUp className="h-5 w-5 text-zinc-500" />
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold text-indigo-600">
              {stats.total_requests > 0 ? ((totalRisks / stats.total_requests) * 100).toFixed(1) : 0}
              <span className="text-xl font-normal text-zinc-400">%</span>
            </div>
          </CardContent>
        </Card>
      </div>
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card>
          <CardContent className="p-6">
            <ReactECharts
              option={chartOptions.distribution}
              style={{ height: 400 }}
              onEvents={{
                click: ({ name }: { name: string }) => {
                  const risk = riskLevels.find(([, label]) => t(label) === name)
                  if (risk) openResults({ risk_level: [risk[0]] })
                },
              }}
            />
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-6">
            <ReactECharts option={chartOptions.trends} style={{ height: 400 }} />
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

export default Dashboard
