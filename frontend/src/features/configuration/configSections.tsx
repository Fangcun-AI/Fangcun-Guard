import React from 'react'

import type { SectionEntry } from '@/navigation/sectionResolver'
import {
  AnswerManagementScreen,
  CustomScannersManagementScreen,
  KeywordListManagementScreen,
  OfficialScannersManagementScreen,
  SensitivityThresholdManagementScreen,
} from '@/features/configuration/screens'
import { DataSecurityScreen } from '@/features/data-security/screens'

export const configSections: SectionEntry[] = [
  {
    id: 'official-scanners',
    matches: (pathname) =>
      pathname === '/config' ||
      pathname === '/config/' ||
      pathname.includes('/official-scanners'),
    render: () => <OfficialScannersManagementScreen />,
  },
  {
    id: 'custom-scanners',
    matches: (pathname) => pathname.includes('/custom-scanners'),
    render: () => <CustomScannersManagementScreen />,
  },
  {
    id: 'sensitivity-thresholds',
    matches: (pathname) => pathname.includes('/sensitivity-thresholds'),
    render: () => <SensitivityThresholdManagementScreen />,
  },
  {
    id: 'data-security',
    matches: (pathname) => pathname.includes('/data-security'),
    render: () => <DataSecurityScreen />,
  },
  {
    id: 'keyword-list',
    matches: (pathname) =>
      pathname.includes('/keyword-list') ||
      pathname.includes('/blacklist') ||
      pathname.includes('/whitelist'),
    render: () => <KeywordListManagementScreen />,
  },
  {
    id: 'answers',
    matches: (pathname) =>
      pathname.includes('/answers') ||
      pathname.includes('/responses') ||
      pathname.includes('/response-templates') ||
      pathname.includes('/knowledge-bases'),
    render: () => <AnswerManagementScreen />,
  },
]
