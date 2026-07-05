import React from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import UserManagement from './UserManagementScreen'
import RateLimitManagement from './RateLimitManagementScreen'
import SubscriptionManagement from './SubscriptionManagementScreen'
import PackageMarketplace from './PackageMarketplaceScreen'

const AdminPanelScreen: React.FC = () => {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="users" replace />} />
      <Route path="/users" element={<UserManagement />} />
      <Route path="/rate-limits" element={<RateLimitManagement />} />
      <Route path="/subscriptions" element={<SubscriptionManagement />} />
      <Route path="/package-marketplace" element={<PackageMarketplace />} />
    </Routes>
  )
}

export default AdminPanelScreen
