import React from 'react'
import { Route } from 'react-router-dom'

import type { RouteCatalogEntry } from './routeCatalog'

export function renderRouteCatalog(entries: RouteCatalogEntry[]) {
  return entries.map((entry) => (
    <Route key={entry.path} path={entry.path} element={entry.element} />
  ))
}
