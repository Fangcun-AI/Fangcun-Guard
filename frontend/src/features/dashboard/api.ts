import api, { responseBody as body } from '@/core/api/client'
import type { DashboardStats } from '@/types'

export const dashboardApi = {
  getStats: (): Promise<DashboardStats> => body(api.get('/api/v1/dashboard/stats')),
  getCategoryDistribution: (params?: { start_date?: string; end_date?: string }):
    Promise<{ categories: { name: string; value: number }[] }> =>
    body(api.get('/api/v1/dashboard/category-distribution', { params })),
}
