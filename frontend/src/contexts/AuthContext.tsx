import React, { ReactNode, createContext, useCallback, useContext, useEffect, useState } from 'react'
import { adminApi } from '../services/api'
import { UserInfo, authService } from '../services/auth'

interface SwitchInfo {
  is_switched: boolean
  admin_user?: { id: string; email: string }
  target_user?: { id: string; email: string; api_key: string }
}
interface AuthContextType {
  user: UserInfo | null
  isAuthenticated: boolean
  isLoading: boolean
  switchInfo: SwitchInfo
  login: (email: string, password: string, language?: string) => Promise<{ requiresPasswordChange?: boolean; passwordMessage?: string }>
  logout: () => Promise<void>
  switchToUser: (userId: string) => Promise<void>
  exitSwitch: () => Promise<void>
  refreshSwitchStatus: () => Promise<void>
  refreshUserInfo: () => Promise<void>
  onUserSwitch: (callback: () => void) => () => void
}
const AuthContext = createContext<AuthContextType | undefined>(undefined)
const emptySwitch = (): SwitchInfo => ({ is_switched: false })

export const AuthProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<UserInfo | null>(null)
  const [isAuthenticated, setAuthenticated] = useState(false)
  const [isLoading, setLoading] = useState(true)
  const [switchInfo, setSwitchInfo] = useState<SwitchInfo>(emptySwitch())
  const [listeners, setListeners] = useState(new Set<() => void>())

  const applyLanguage = async (current: UserInfo) => {
    if (!current.language) return
    localStorage.setItem('i18nextLng', current.language)
    await (await import('../i18n')).default.changeLanguage(current.language)
  }
  const clearIdentity = () => {
    setUser(null)
    setAuthenticated(false)
    setSwitchInfo(emptySwitch())
  }
  const refreshSwitchStatus = async () => {
    try { setSwitchInfo(await adminApi.getCurrentSwitch()) } catch { setSwitchInfo(emptySwitch()) }
  }
  const refreshUserInfo = async () => {
    if (!authService.isAuthenticated()) return
    try {
      const current = await authService.getCurrentUser()
      setUser(current)
      await applyLanguage(current)
    } catch (error) {
      console.error('Failed to refresh user info:', error)
    }
  }
  const checkSession = async () => {
    try {
      if (!authService.isAuthenticated()) return clearIdentity()
      const current = await authService.getCurrentUser()
      setUser(current)
      setAuthenticated(true)
      await applyLanguage(current)
      await refreshSwitchStatus()
    } catch {
      authService.clearToken()
      clearIdentity()
    } finally {
      setLoading(false)
    }
  }
  useEffect(() => { void checkSession() }, [])

  const login = async (email: string, password: string, language?: string) => {
    const response = await authService.login({ email, password, language })
    authService.setToken(response.access_token)
    const current = await authService.getCurrentUser()
    setUser(current)
    setAuthenticated(true)
    await applyLanguage(current)
    await refreshSwitchStatus()
    return { requiresPasswordChange: response.requires_password_change, passwordMessage: response.password_message }
  }
  const logout = async () => {
    await authService.logout()
    localStorage.removeItem('switch_session_token')
    clearIdentity()
  }
  const notifySwitch = () => listeners.forEach(listener => listener())
  const switchToUser = async (userId: string) => {
    const currentApp = localStorage.getItem('current_application_id')
    if (currentApp) localStorage.setItem('admin_saved_application_id', currentApp)
    const response = await adminApi.switchToUser(userId)
    localStorage.setItem('switch_session_token', response.switch_session_token)
    await refreshSwitchStatus()
    notifySwitch()
  }
  const exitSwitch = async () => {
    await adminApi.exitSwitch()
    localStorage.removeItem('switch_session_token')
    const savedApp = localStorage.getItem('admin_saved_application_id')
    if (savedApp) {
      localStorage.setItem('current_application_id', savedApp)
      localStorage.removeItem('admin_saved_application_id')
    }
    await refreshSwitchStatus()
    notifySwitch()
  }
  const onUserSwitch = useCallback((callback: () => void) => {
    setListeners(previous => new Set(previous).add(callback))
    return () => setListeners(previous => {
      const next = new Set(previous)
      next.delete(callback)
      return next
    })
  }, [])
  return <AuthContext.Provider value={{
    user, isAuthenticated, isLoading, switchInfo, login, logout, switchToUser,
    exitSwitch, refreshSwitchStatus, refreshUserInfo, onUserSwitch
  }}>{children}</AuthContext.Provider>
}

export const useAuth = () => {
  const value = useContext(AuthContext)
  if (!value) throw new Error('useAuth must be used within an AuthProvider')
  return value
}
