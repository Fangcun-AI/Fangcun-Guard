import React from 'react'

import { AdminPanelScreen } from '@/features/admin/screens'
import {
  ApplicationDiscoveryScreen,
  ApplicationManagementScreen,
} from '@/features/applications/screens'
import { AccessControlScreen } from '@/features/access-control/screens'
import { AccountScreen } from '@/features/account/screens'
import { SubscriptionScreen } from '@/features/billing/screens'
import { ConfigurationScreen } from '@/features/configuration/screens'
import {
  DashboardScreen,
  ReportsScreen,
} from '@/features/dashboard/screens'
import { DemoHubScreen } from '@/features/demo/screens'
import { DocumentationScreen } from '@/features/documentation/screens'
import { OnlineTestScreen } from '@/features/online-test/screens'
import { ResultsScreen } from '@/features/results/screens'
import {
  LLMProvidersScreen,
  ModelRoutesScreen,
  SecurityPolicyScreen,
} from '@/features/security-gateway/screens'
import {
  DeploymentAgentScreen,
  McpScannerScreen,
  SkillScannerScreen,
  ToolCenterScreen,
} from '@/features/tool-center/screens'

export interface WorkspaceRouteEntry {
  path: string
  element: React.ReactElement
}

const coreRoutes: WorkspaceRouteEntry[] = [
  { path: '/', element: <DashboardScreen /> },
  { path: '/dashboard', element: <DashboardScreen /> },
  { path: '/online-test', element: <OnlineTestScreen /> },
  { path: '/results', element: <ResultsScreen /> },
  { path: '/reports', element: <ReportsScreen /> },
]

const applicationRoutes: WorkspaceRouteEntry[] = [
  { path: '/applications', element: <ApplicationManagementScreen /> },
  { path: '/applications/list', element: <ApplicationManagementScreen /> },
  { path: '/applications/discovery', element: <ApplicationDiscoveryScreen /> },
]

const securityGatewayRoutes: WorkspaceRouteEntry[] = [
  { path: '/security-gateway/providers', element: <LLMProvidersScreen /> },
  { path: '/security-gateway/policy', element: <SecurityPolicyScreen /> },
  { path: '/security-gateway/model-routes', element: <ModelRoutesScreen /> },
  { path: '/config/*', element: <ConfigurationScreen /> },
  { path: '/access-control/*', element: <AccessControlScreen /> },
]

const toolCenterRoutes: WorkspaceRouteEntry[] = [
  { path: '/tool-center', element: <ToolCenterScreen /> },
  { path: '/tool-center/deployment-agent', element: <DeploymentAgentScreen /> },
  { path: '/tool-center/skill-scanner', element: <SkillScannerScreen /> },
  { path: '/tool-center/mcp-scanner', element: <McpScannerScreen /> },
]

const supportingRoutes: WorkspaceRouteEntry[] = [
  { path: '/admin/*', element: <AdminPanelScreen /> },
  { path: '/account', element: <AccountScreen /> },
  { path: '/documentation', element: <DocumentationScreen /> },
  { path: '/demo', element: <DemoHubScreen /> },
]

export function createWorkspaceRouteCatalog(includeSubscription: boolean): WorkspaceRouteEntry[] {
  const workspaceRoutes: WorkspaceRouteEntry[] = [
    ...coreRoutes,
    ...applicationRoutes,
    ...securityGatewayRoutes,
    ...toolCenterRoutes,
    ...supportingRoutes,
  ]

  if (includeSubscription) {
    const accountIndex = workspaceRoutes.findIndex((entry) => entry.path === '/account')
    const subscriptionRoute = { path: '/subscription', element: <SubscriptionScreen /> }

    if (accountIndex === -1) {
      workspaceRoutes.push(subscriptionRoute)
    } else {
      workspaceRoutes.splice(accountIndex + 1, 0, subscriptionRoute)
    }
  }

  return workspaceRoutes
}
