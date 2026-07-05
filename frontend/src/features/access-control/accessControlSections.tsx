import React from 'react'

import type { SectionEntry } from '@/navigation/sectionResolver'
import { BanPolicyScreen, FalsePositiveAppealScreen } from '@/features/access-control/screens'

export const accessControlSections: SectionEntry[] = [
  {
    id: 'ban-policy',
    matches: (pathname) => pathname.includes('/ban-policy'),
    render: () => <BanPolicyScreen />,
  },
  {
    id: 'false-positive-appeal',
    matches: (pathname) =>
      pathname.includes('/false-positive-appeal') || pathname.includes('/appeal'),
    render: () => <FalsePositiveAppealScreen />,
  },
  {
    id: 'default-ban-policy',
    matches: () => true,
    render: () => <BanPolicyScreen />,
  },
]
