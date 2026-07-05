import React, { useCallback, useEffect, useState } from 'react'
import { Edit, RefreshCw, RotateCw } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import type { ColumnDef } from '@tanstack/react-table'

import { DataTable } from '@/components/data-table/DataTable'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Progress } from '@/components/ui/progress'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { billingService } from '@/services/billing'
import type { SubscriptionListItem } from '@/types/billing'
import { confirmDialog } from '@/utils/confirm-dialog'

type Plan = SubscriptionListItem['subscription_type']
type PlanFilter = Plan | 'all'

const SubscriptionManagement: React.FC = () => {
  const { t } = useTranslation()
  const [subscriptions, setSubscriptions] = useState<SubscriptionListItem[]>([])
  const [loading, setLoading] = useState(false)
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)
  const [search, setSearch] = useState('')
  const [filter, setFilter] = useState<PlanFilter>('all')
  const [edit, setEdit] = useState<{ record: SubscriptionListItem; plan: Plan }>()

  const errorText = (error: unknown, fallback: string) =>
    error instanceof Error ? error.message : fallback
  const fetchSubscriptions = useCallback(async () => {
    setLoading(true)
    try {
      const result = await billingService.listAllSubscriptions({
        skip: (page - 1) * pageSize,
        limit: pageSize,
        search: search || undefined,
        subscription_type: filter === 'all' ? undefined : filter,
        sort_by: 'current_month_usage',
        sort_order: 'desc',
      })
      setSubscriptions(result.data)
      setTotal(result.total)
    } catch (error) {
      toast.error(errorText(error, t('admin.subscriptions.fetchFailed')))
    } finally {
      setLoading(false)
    }
  }, [filter, page, pageSize, search, t])

  useEffect(() => {
    void fetchSubscriptions()
  }, [fetchSubscriptions])

  const updatePlan = async () => {
    if (!edit) return
    try {
      await billingService.updateSubscription(edit.record.tenant_id, { subscription_type: edit.plan })
      setEdit(undefined)
      toast.success(t('admin.subscriptions.updateSuccess'))
      void fetchSubscriptions()
    } catch (error) {
      toast.error(errorText(error, t('admin.subscriptions.updateFailed')))
    }
  }
  const resetQuota = async (tenantId: string) => {
    if (!await confirmDialog({ title: t('admin.subscriptions.resetConfirm'), description: t('admin.subscriptions.resetWarning') })) return
    try {
      await billingService.resetTenantQuota(tenantId)
      toast.success(t('admin.subscriptions.resetSuccess'))
      void fetchSubscriptions()
    } catch (error) {
      toast.error(errorText(error, t('admin.subscriptions.resetFailed')))
    }
  }
  const resetFilters = () => {
    setSearch('')
    setFilter('all')
    setPage(1)
  }

  const columns: ColumnDef<SubscriptionListItem>[] = [
    { accessorKey: 'email', header: t('admin.subscriptions.email'), size: 250 },
    { accessorKey: 'subscription_type', header: t('admin.subscriptions.plan'), size: 150, cell: ({ row }) => <Badge variant={row.original.subscription_type === 'subscribed' ? 'default' : 'outline'}>{row.original.plan_name}</Badge> },
    { id: 'usage', header: t('admin.subscriptions.usage'), size: 300, cell: ({ row }) => {
      const record = row.original
      return <div className="space-y-2"><div className="text-sm">{record.current_month_usage.toLocaleString()} / {record.monthly_quota.toLocaleString()} ({record.usage_percentage.toFixed(1)}%)</div><Progress value={Math.min(record.usage_percentage, 100)} className={`h-2 ${record.usage_percentage >= 90 ? '[&>div]:bg-red-500' : '[&>div]:bg-indigo-500'}`} /></div>
    } },
    { accessorKey: 'usage_reset_at', header: t('admin.subscriptions.resetDate'), size: 150, cell: ({ row }) => <span className="text-sm">{new Date(row.original.usage_reset_at).toLocaleDateString()}</span> },
    { id: 'actions', header: t('common.actions'), size: 180, cell: ({ row }) => (
      <div className="flex gap-2">
        <Button variant="outline" size="sm" onClick={() => setEdit({ record: row.original, plan: row.original.subscription_type })}><Edit className="mr-2 h-4 w-4" />{t('common.edit')}</Button>
        <Button variant="outline" size="sm" className="text-red-600 hover:text-red-700" onClick={() => void resetQuota(row.original.tenant_id)}><RotateCw className="mr-2 h-4 w-4" />{t('admin.subscriptions.reset')}</Button>
      </div>
    ) },
  ]

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle>{t('admin.subscriptions.title')}</CardTitle>
          <Button variant="outline" onClick={() => void fetchSubscriptions()} disabled={loading}><RefreshCw className={`mr-2 h-4 w-4 ${loading ? 'animate-spin' : ''}`} />{t('common.refresh')}</Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex gap-4">
          <Input placeholder={t('admin.subscriptions.searchPlaceholder')} value={search} onChange={(event) => { setSearch(event.target.value); setPage(1) }} className="max-w-xs" />
          <Select value={filter} onValueChange={(value) => { setFilter(value as PlanFilter); setPage(1) }}>
            <SelectTrigger className="w-[200px]"><SelectValue placeholder={t('admin.subscriptions.filterByType')} /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">{t('common.all')}</SelectItem>
              <SelectItem value="free">{t('admin.subscriptions.freePlan')}</SelectItem>
              <SelectItem value="subscribed">{t('admin.subscriptions.subscribedPlan')}</SelectItem>
            </SelectContent>
          </Select>
          {(search || filter !== 'all') && <Button variant="outline" onClick={resetFilters}>{t('common.reset')}</Button>}
        </div>
        <DataTable
          columns={columns}
          data={subscriptions}
          loading={loading}
          pageCount={Math.max(1, Math.ceil(total / pageSize))}
          currentPage={page}
          pageSize={pageSize}
          onPageChange={setPage}
          onPageSizeChange={(size) => { setPageSize(size); setPage(1) }}
        />
      </CardContent>
      <Dialog open={Boolean(edit)} onOpenChange={(open) => !open && setEdit(undefined)}>
        <DialogContent className="sm:max-w-[500px]">
          <DialogHeader><DialogTitle>{t('admin.subscriptions.editSubscription')}</DialogTitle></DialogHeader>
          {edit && <div className="space-y-4">
            <div><span className="font-semibold">{t('admin.subscriptions.tenant')}:</span> {edit.record.email}</div>
            <div><span className="font-semibold">{t('admin.subscriptions.currentPlan')}:</span> <Badge variant={edit.record.subscription_type === 'subscribed' ? 'default' : 'outline'}>{edit.record.plan_name}</Badge></div>
            <div className="space-y-2">
              <label className="font-semibold">{t('admin.subscriptions.newPlan')}:</label>
              <Select value={edit.plan} onValueChange={(plan) => setEdit({ ...edit, plan: plan as Plan })}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="free">{t('admin.subscriptions.freePlan')} (10,000 {t('account.calls')}/month)</SelectItem>
                  <SelectItem value="subscribed">{t('admin.subscriptions.subscribedPlan')} (1,000,000 {t('account.calls')}/month)</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>}
          <DialogFooter><Button variant="outline" onClick={() => setEdit(undefined)}>{t('common.cancel')}</Button><Button onClick={() => void updatePlan()}>{t('common.confirm')}</Button></DialogFooter>
        </DialogContent>
      </Dialog>
    </Card>
  )
}

export default SubscriptionManagement
