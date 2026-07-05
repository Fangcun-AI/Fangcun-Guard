import React from 'react'

import { authRouteCatalog } from '../features/auth/authRouteCatalog'
export { createWorkspaceRouteCatalog } from '../features/workspace/workspaceRouteCatalog'

export interface RouteCatalogEntry {
  path: string
  element: React.ReactElement
}

export const publicRouteCatalog: RouteCatalogEntry[] = authRouteCatalog
