import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { initSystemConfig } from '../config'

export function useAppBootstrap() {
  const { t, i18n } = useTranslation()
  const [configLoaded, setConfigLoaded] = useState(false)

  useEffect(() => {
    let active = true

    const loadConfig = async () => {
      await initSystemConfig()
      if (active) {
        setConfigLoaded(true)
      }
    }

    loadConfig()

    return () => {
      active = false
    }
  }, [])

  useEffect(() => {
    document.title = t('common.appName')
  }, [t, i18n.language])

  return { configLoaded }
}
