import React from 'react'
import { Routes } from 'react-router-dom'

import Layout from '../components/Layout/Layout'
import ProtectedRoute from '../components/ProtectedRoute/ProtectedRoute'
import { createWorkspaceRouteCatalog } from './routeCatalog'
import { renderRouteCatalog } from './RouteRenderer'

interface AppShellProps {
  includeSubscription: boolean
}

function AppShell({ includeSubscription }: AppShellProps) {
  const workspaceRoutes = createWorkspaceRouteCatalog(includeSubscription)

  return (
    <ProtectedRoute>
      <Layout>
        <Routes>{renderRouteCatalog(workspaceRoutes)}</Routes>
      </Layout>
    </ProtectedRoute>
  )
}

export default AppShell
