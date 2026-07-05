import { useLocation } from 'react-router-dom'

import { resolveSection, SectionSurface } from '@/navigation/sectionResolver'
import { configSections } from '@/features/configuration/configSections'

const ConfigurationScreen: React.FC = () => {
  const location = useLocation()
  const activeSection = resolveSection(location.pathname, configSections, 'official-scanners')

  return (
    <SectionSurface section={activeSection} />
  )
}

export default ConfigurationScreen
