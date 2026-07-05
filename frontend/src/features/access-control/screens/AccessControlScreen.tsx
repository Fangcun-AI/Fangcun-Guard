import { useLocation } from 'react-router-dom'

import { resolveSection, SectionSurface } from '@/navigation/sectionResolver'
import { accessControlSections } from '@/features/access-control/accessControlSections'

const AccessControlScreen: React.FC = () => {
  const location = useLocation()
  const activeSection = resolveSection(location.pathname, accessControlSections, 'default-ban-policy')

  return (
    <SectionSurface section={activeSection} />
  )
}

export default AccessControlScreen
