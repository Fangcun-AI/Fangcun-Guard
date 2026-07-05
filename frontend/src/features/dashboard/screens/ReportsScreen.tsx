import React, { useCallback, useEffect, useState } from 'react'
import { format, subDays } from 'date-fns'
import ReactECharts from 'echarts-for-react'
import { Lock, Shield } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import type { DateRange } from 'react-day-picker'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { DateRangePicker } from '@/components/ui/date-range-picker'
import { useApplication } from '@/contexts/ApplicationContext'
import { dashboardApi } from '@/features/dashboard/api'
import type { DashboardStats } from '@/types'

type CategorySlice = { name: string; value: number }

const Reports: React.FC = () => {
  const { t } = useTranslation()
  const { currentApplicationId } = useApplication()
  const [stats, setStats] = useState<DashboardStats | null>(null)
  const [categories, setCategories] = useState<CategorySlice[]>([])
  const [error, setError] = useState<string>()
  const [loading, setLoading] = useState(true)
  const [dateRange, setDateRange] = useState<DateRange>({ from: subDays(new Date(), 30), to: new Date() })

  const fetchReport = useCallback(async () => {
    if (!dateRange.from || !dateRange.to) return
    setLoading(true)
    try {
      const [nextStats, distribution] = await Promise.all([
        dashboardApi.getStats(),
        dashboardApi.getCategoryDistribution({
          start_date: format(dateRange.from, 'yyyy-MM-dd'),
          end_date: format(dateRange.to, 'yyyy-MM-dd'),
        }),
      ])
      setStats(nextStats)
      setCategories(distribution.categories || [])
      setError(undefined)
    } catch (fetchError) {
      console.error('Error fetching report data:', fetchError)
      const message = t('reports.errorFetchingReports')
      setError(message)
      toast.error(message)
    } finally {
      setLoading(false)
    }
  }, [currentApplicationId, dateRange, t])

  useEffect(() => {
    void fetchReport()
  }, [fetchReport])

  if (loading) return <div className="flex items-center justify-center p-12"><div className="h-12 w-12 animate-spin rounded-full border-b-2 border-indigo-600" /></div>
  if (error) return (
    <div className="rounded-lg border border-red-800 bg-red-950/50 p-4">
      <div className="flex items-start gap-2">
        <div className="flex-1"><h3 className="font-semibold text-red-200">{t('reports.error')}</h3><p className="mt-1 text-sm text-red-400">{error}</p></div>
        <Button variant="link" onClick={() => void fetchReport()} className="text-indigo-400">{t('reports.retry')}</Button>
      </div>
    </div>
  )

  const periodTitle = dateRange.from && dateRange.to
    ? t('reports.riskTrendPeriod', { from: format(dateRange.from, 'MM-dd'), to: format(dateRange.to, 'MM-dd') })
    : ''
  const trend = stats?.daily_trends ?? []
  const chartOptions = {
    category: {
      title: { text: t('reports.categoryDistribution'), left: 'center' },
      tooltip: { trigger: 'item', formatter: '{a} <br/>{b}: {c} ({d}%)' },
      legend: { orient: 'vertical', left: 'left' },
      series: [{
        name: t('reports.riskCategory'),
        type: 'pie',
        radius: '50%',
        data: categories,
        emphasis: { itemStyle: { shadowBlur: 10, shadowOffsetX: 0, shadowColor: 'rgba(0, 0, 0, 0.5)' } },
      }],
    },
    trend: {
      title: { text: periodTitle, left: 'center' },
      tooltip: {
        trigger: 'axis',
        formatter: (params: Array<{ name: string; value: number }>) =>
          `${format(new Date(params[0].name), 'yyyy-MM-dd')}<br/>${t('reports.riskDetectionCount')}: ${params[0].value}`,
      },
      xAxis: { type: 'category', data: trend.map(({ date }) => format(new Date(date), 'MM/dd')) },
      yAxis: { type: 'value' },
      series: [{
        name: t('reports.riskDetectionCount'),
        type: 'line',
        data: trend.map(({ high_risk, medium_risk, low_risk }) => high_risk + medium_risk + low_risk),
        itemStyle: { color: '#ff4d4f' },
        smooth: true,
      }],
    },
  }
  const summaryCards = stats ? [
    [Shield, 'reports.securityRisksDetected', stats.security_risks, 'text-orange-600'],
    [Shield, 'reports.complianceRisksDetected', stats.compliance_risks, 'text-purple-600'],
    [Lock, 'reports.dataLeaksDetected', stats.data_leaks, 'text-pink-600'],
  ] as const : []

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-shrink-0 items-center justify-between">
        <h2 className="text-3xl font-bold tracking-tight">{t('reports.title')}</h2>
        <DateRangePicker value={dateRange} onChange={(range) => range?.from && range.to && setDateRange(range)} />
      </div>
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        {summaryCards.map(([Icon, label, value, color]) => (
          <Card key={label}>
            <CardHeader className="flex flex-row items-center justify-between pb-2"><CardTitle className="text-sm font-medium text-zinc-400">{t(label)}</CardTitle><Icon className="h-5 w-5 text-zinc-500" /></CardHeader>
            <CardContent><div className={`text-3xl font-bold ${color}`}>{value}<span className="ml-2 text-sm font-normal text-zinc-400">{t('reports.times')}</span></div></CardContent>
          </Card>
        ))}
      </div>
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader><CardTitle>{t('reports.categoryDistribution')}</CardTitle></CardHeader>
          <CardContent>{categories.length ? <ReactECharts option={chartOptions.category} style={{ height: 400 }} /> : <div className="flex h-[400px] items-center justify-center text-zinc-500">{t('reports.noRiskCategoryData')}</div>}</CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>{t('reports.riskTrend')}</CardTitle></CardHeader>
          <CardContent>{stats ? <ReactECharts option={chartOptions.trend} style={{ height: 400 }} /> : <div className="flex h-[400px] items-center justify-center text-zinc-500">{t('reports.noTrendData')}</div>}</CardContent>
        </Card>
      </div>
    </div>
  )
}

export default Reports
