import React from 'react'
import { Route, Routes } from 'react-router-dom'

import { features } from './config'
import { ApplicationProvider } from './contexts/ApplicationContext'
import { LoginScreen } from './features/auth/screens'
import { useAppBootstrap } from './hooks/useAppBootstrap'
import AppShell from './navigation/AppShell'
import { renderRouteCatalog } from './navigation/RouteRenderer'
import { publicRouteCatalog } from './navigation/routeCatalog'

function App() {
  const { configLoaded } = useAppBootstrap()

  if (!configLoaded) {
    return null
  }

  return (
    <ApplicationProvider>
      <Routes>
        {renderRouteCatalog(publicRouteCatalog)}
        <Route path="/*" element={<AppShell includeSubscription={features.showSubscription()} />} />
        <Route path="/" element={<LoginScreen />} />
      </Routes>
    </ApplicationProvider>
  )
}

export default App
