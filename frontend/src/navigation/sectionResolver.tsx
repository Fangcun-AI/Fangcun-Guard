import React from 'react'

export interface SectionEntry {
  id: string
  matches: (pathname: string) => boolean
  render: () => React.ReactElement
}

export function resolveSection(pathname: string, sections: SectionEntry[], fallbackId?: string) {
  const matched = sections.find((section) => section.matches(pathname))
  if (matched) {
    return matched
  }

  if (fallbackId) {
    const fallback = sections.find((section) => section.id === fallbackId)
    if (fallback) {
      return fallback
    }
  }

  return sections[0]
}

interface SectionSurfaceProps {
  section: SectionEntry
}

export function SectionSurface({ section }: SectionSurfaceProps) {
  return <div className="space-y-6">{section.render()}</div>
}
