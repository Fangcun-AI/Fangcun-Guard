import React, { useState, useEffect } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import {
  LayoutDashboard,
  FileSearch,
  BarChart3,
  Settings,
  User,
  LogOut,
  RefreshCw,
  TestTube,
  Book,
  Grid3x3,
  ChevronDown,
  Menu as MenuIcon,
  X,
  Shield,
  ShieldAlert,
  ChevronLeft,
  CreditCard,
  Users,
  Puzzle,
  Swords,
} from 'lucide-react'
import { useAuth } from '../../contexts/AuthContext'
import { adminApi, configApi } from '../../services/api'
import LanguageSwitcher from '../LanguageSwitcher/LanguageSwitcher'
import ApplicationSelector from '../ApplicationSelector'
import { features } from '../../config'
import { Button } from '../ui/button'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../ui/dialog'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select'
import { toast } from 'sonner'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '../ui/collapsible'
import { cn } from '../../lib/utils'

interface LayoutProps {
  children: React.ReactNode
}

const Layout: React.FC<LayoutProps> = ({ children }) => {
  const { t } = useTranslation()
  const [collapsed, setCollapsed] = useState(false)
  const [switchModalVisible, setSwitchModalVisible] = useState(false)
  const [users, setUsers] = useState<any[]>([])
  const [loading, setLoading] = useState(false)
  const [systemVersion, setSystemVersion] = useState<string>('')
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const [userMenuOpen, setUserMenuOpen] = useState(false)

  const navigate = useNavigate()
  const location = useLocation()
  const { user, logout, switchInfo, switchToUser, exitSwitch, refreshSwitchStatus } = useAuth()

  useEffect(() => {
    // If super admin, periodically check switch status
    if (user?.is_super_admin) {
      const interval = setInterval(() => {
        refreshSwitchStatus()
      }, 30000) // Check every 30 seconds
      return () => clearInterval(interval)
    }
  }, [user?.is_super_admin, refreshSwitchStatus])

  useEffect(() => {
    // Get system version information
    const fetchSystemVersion = async () => {
      try {
        const systemInfo = await configApi.getSystemInfo()
        console.log('System info:', systemInfo)
        // Backend returns 'version' field, not 'app_version'
        const version = (systemInfo as any).version || systemInfo.app_version
        if (version) {
          setSystemVersion(`v${version}`)
        } else {
          console.log('No version in system info')
        }
      } catch (error) {
        console.error('Failed to fetch system version:', error)
      }
    }

    fetchSystemVersion()
  }, [])

  const menuItems = [
    {
      key: '/dashboard',
      icon: LayoutDashboard,
      label: t('nav.dashboard'),
    },
    {
      key: '/online-test',
      icon: TestTube,
      label: t('nav.onlineTest'),
    },
    {
      key: '/results',
      icon: FileSearch,
      label: t('nav.results'),
    },
    {
      key: '/reports',
      icon: BarChart3,
      label: t('nav.reports'),
    },
    {
      key: '/applications',
      icon: Grid3x3,
      label: t('nav.applications'),
      children: [
        {
          key: '/applications/list',
          label: t('nav.applicationList'),
        },
        {
          key: '/applications/discovery',
          label: t('nav.applicationDiscovery'),
        },
      ],
    },
    {
      key: '/security-gateway',
      icon: Shield,
      label: t('nav.securityGateway'),
      children: [
        {
          key: '/security-gateway/providers',
          label: t('nav.llmProviders'),
        },
        {
          key: '/security-gateway/policy',
          label: t('nav.securityPolicy'),
        },
        {
          key: '/security-gateway/model-routes',
          label: t('nav.modelRoutes'),
        },
      ],
    },
    {
      key: '/config',
      icon: Settings,
      label: t('nav.config'),
      children: [
        {
          key: '/config/official-scanners',
          label: t('scannerPackages.officialScanners'),
        },
        {
          key: '/config/custom-scanners',
          label: t('customScanners.title'),
        },
        {
          key: '/config/data-security',
          label: t('config.dataSecurity'),
        },
        {
          key: '/config/keyword-list',
          label: t('config.keywordList'),
        },
        {
          key: '/config/answers',
          label: t('config.answers'),
        },
        {
          key: '/config/sensitivity-thresholds',
          label: t('config.sensitivity'),
        },
      ],
    },
    {
      key: '/access-control',
      icon: ShieldAlert,
      label: t('nav.accessControl'),
      children: [
        {
          key: '/access-control/ban-policy',
          label: t('nav.banPolicy'),
        },
        {
          key: '/access-control/false-positive-appeal',
          label: t('nav.falsePositiveAppeal'),
        },
      ],
    },
    {
      key: '/tool-center',
      icon: Puzzle,
      label: t('nav.toolCenter'),
    },
    // Subscription & Usage (for all users in SaaS mode)
    ...(features.showSubscription()
      ? [
          {
            key: '/subscription',
            icon: CreditCard,
            label: t('nav.subscription'),
          },
        ]
      : []),
    {
      key: '/demo',
      icon: Swords,
      label: t('nav.demo'),
    },
    {
      key: '/documentation',
      icon: Book,
      label: t('nav.documentation'),
    },
    // Admin menu - Only super admins can see (placed at bottom)
    ...(user?.is_super_admin
      ? [
          {
            key: '/admin',
            icon: Users,
            label: t('nav.admin'),
            children: [
              {
                key: '/admin/users',
                label: t('nav.tenantManagement'),
              },
              {
                key: '/admin/rate-limits',
                label: t('nav.rateLimiting'),
              },
              // Subscription management only in SaaS mode
              ...(features.showSubscription()
                ? [
                    {
                      key: '/admin/subscriptions',
                      label: t('nav.subscriptionManagement'),
                    },
                  ]
                : []),
              // Package marketplace only in SaaS mode
              ...(features.showMarketplace()
                ? [
                    {
                      key: '/admin/package-marketplace',
                      label: t('nav.packageMarketplace'),
                    },
                  ]
                : []),
            ],
          },
        ]
      : []),
  ]

  const handleMenuClick = (key: string) => {
    navigate(key)
    setMobileMenuOpen(false)
  }

  const getSelectedKeys = () => {
    const path = location.pathname
    if (path.startsWith('/config') || path.startsWith('/admin') || path.startsWith('/security-gateway') || path.startsWith('/access-control') || path.startsWith('/applications')) {
      return [path]
    }
    if (path === '/' || path === '/') {
      return ['/dashboard']
    }
    return [path.startsWith('/') ? path : '/platform' + path]
  }

  const getOpenKeys = () => {
    const path = location.pathname
    if (path.startsWith('/config')) {
      return ['/config']
    }
    if (path.startsWith('/access-control')) {
      return ['/access-control']
    }
    if (path.startsWith('/admin')) {
      return ['/admin']
    }
    if (path.startsWith('/applications')) {
      return ['/applications']
    }
    return []
  }

  const loadUsers = async () => {
    if (!user?.is_super_admin) return

    setLoading(true)
    try {
      const response = await adminApi.getUsers()
      setUsers(response.users || [])
    } catch (error) {
      console.error('Failed to load users:', error)
      toast.error(t('layout.loadUsersError'))
    } finally {
      setLoading(false)
    }
  }

  const handleSwitchUser = async (userId: string) => {
    try {
      await switchToUser(userId)
      setSwitchModalVisible(false)
      toast.success(t('layout.switchSuccess'))
      // Refresh current page
      window.location.reload()
    } catch (error) {
      console.error('Switch user failed:', error)
      toast.error(t('layout.switchError'))
    }
  }

  const handleExitSwitch = async () => {
    try {
      await exitSwitch()
      toast.success(t('layout.exitSwitchSuccess'))
      // Refresh current page
      window.location.reload()
    } catch (error) {
      console.error('Exit switch failed:', error)
      toast.error(t('layout.exitSwitchError'))
    }
  }

  const showSwitchModal = () => {
    setSwitchModalVisible(true)
    loadUsers()
  }

  const selectedKeys = getSelectedKeys()
  const openKeys = getOpenKeys()

  // User section at bottom of sidebar
  const UserSection = ({ isMobile = false }: { isMobile?: boolean }) => (
    <div className={cn("border-t", isMobile ? "border-zinc-800" : "border-zinc-800/50")}>
      {/* Tenant switch status */}
      {switchInfo.is_switched && !collapsed && (
        <div className={cn("px-3 py-2 border-b", isMobile ? "bg-orange-500/10 border-orange-500/20" : "bg-orange-500/10 border-orange-500/20")}>
          <p className={cn("text-xs mb-1", isMobile ? "text-orange-400" : "text-orange-400")}>{t('layout.switchedTo')}</p>
          <p className={cn("text-xs font-medium truncate", isMobile ? "text-orange-200" : "text-orange-200")}>{switchInfo.target_user?.email}</p>
          <Button variant="ghost" size="sm" onClick={handleExitSwitch} className={cn("w-full mt-2 h-7 text-xs", isMobile ? "text-orange-300 hover:text-orange-100 hover:bg-orange-500/20" : "text-orange-300 hover:text-orange-100 hover:bg-orange-500/20")}>
            <RefreshCw className="h-3 w-3 mr-1" />
            {t('layout.exitSwitch')}
          </Button>
        </div>
      )}

      {/* User info section */}
      <Collapsible open={userMenuOpen} onOpenChange={setUserMenuOpen}>
        <CollapsibleTrigger className="w-full">
          <div className={cn('flex items-center gap-3 px-3 py-3 transition-colors cursor-pointer', collapsed && 'justify-center', isMobile ? 'hover:bg-zinc-800' : 'hover:bg-white/5')}>
            <div className="h-9 w-9 rounded-full bg-indigo-600 flex items-center justify-center text-white flex-shrink-0">
              <User className="h-5 w-5" />
            </div>
            {!collapsed && (
              <div className="flex-1 min-w-0 text-left">
                <p className={cn("text-sm font-medium truncate", isMobile ? "text-zinc-100" : "text-zinc-100")}>{user?.email}</p>
                <div className="flex items-center gap-1 mt-0.5">
                  {user?.is_super_admin && <span className={cn("px-1.5 py-0.5 text-[10px] rounded border", isMobile ? "bg-red-500/20 text-red-300 border-red-500/30" : "bg-red-500/20 text-red-300 border-red-500/30")}>{t('layout.admin')}</span>}
                  {systemVersion && <span className={cn("px-1.5 py-0.5 text-[10px] rounded border", isMobile ? "bg-white/10 text-zinc-400 border-white/10" : "bg-white/10 text-zinc-400 border-white/10")}>{systemVersion}</span>}
                </div>
              </div>
            )}
            {!collapsed && <ChevronDown className={cn('h-4 w-4 transition-transform', isMobile ? 'text-zinc-500' : 'text-zinc-400', userMenuOpen && 'rotate-180')} />}
          </div>
        </CollapsibleTrigger>

        {!collapsed && (
          <CollapsibleContent>
            <div className={cn("border-t", isMobile ? "bg-zinc-900/50 border-zinc-800" : "bg-zinc-900/50 border-zinc-800/50")}>
              {/* Account */}
              <button onClick={() => navigate('/account')} className={cn("w-full px-4 py-2.5 text-left text-sm transition-colors flex items-center gap-2", isMobile ? "text-zinc-300 hover:text-white hover:bg-white/5" : "text-zinc-300 hover:text-white hover:bg-white/5")}>
                <User className="h-4 w-4" />
                {t('nav.account')}
              </button>

              {/* Super admin switch user */}
              {user?.is_super_admin && !switchInfo.is_switched && (
                <button onClick={showSwitchModal} className={cn("w-full px-4 py-2.5 text-left text-sm transition-colors flex items-center gap-2", isMobile ? "text-zinc-300 hover:text-white hover:bg-white/5" : "text-zinc-300 hover:text-white hover:bg-white/5")}>
                  <RefreshCw className="h-4 w-4" />
                  {t('layout.switchUser')}
                </button>
              )}

              <div className={cn("border-t", isMobile ? "border-zinc-800" : "border-zinc-800/50")} />

              {/* Language Switcher */}
              <div className="px-4 py-2.5">
                <LanguageSwitcher />
              </div>

              <div className={cn("border-t", isMobile ? "border-zinc-800" : "border-zinc-800/50")} />

              {/* Logout */}
              <button
                onClick={() => {
                  logout()
                  navigate('/login')
                }}
                className={cn("w-full px-4 py-2.5 text-left text-sm transition-colors flex items-center gap-2", isMobile ? "text-red-400 hover:text-red-300 hover:bg-red-500/10" : "text-red-400 hover:text-red-300 hover:bg-red-500/10")}
              >
                <LogOut className="h-4 w-4" />
                {t('nav.logout')}
              </button>
            </div>
          </CollapsibleContent>
        )}
      </Collapsible>
    </div>
  )

  return (
    <div className="flex h-screen bg-[#09090b] overflow-hidden">
      {/* Desktop Sidebar */}
      <aside className={cn('bg-zinc-950 border-r border-zinc-800/50 transition-all duration-300 flex flex-col', collapsed ? 'w-16' : 'w-64', 'hidden lg:flex')}>
        {/* Logo + Collapse Toggle */}
        <div className="h-16 flex items-center justify-between px-4 border-b border-zinc-800/50">
          <div
            className="flex items-center gap-2 cursor-pointer flex-1 min-w-0"
            onClick={() => {
              if (collapsed) {
                setCollapsed(false)
              } else {
                navigate('/dashboard')
              }
            }}
          >
            <div className="h-8 w-8 bg-indigo-500/10 rounded-lg flex items-center justify-center ring-1 ring-indigo-500/20 flex-shrink-0">
              <Shield className="h-5 w-5 text-indigo-400" />
            </div>
            {!collapsed && <span className="font-bold text-lg text-white truncate">FangcunGuard</span>}
          </div>
          {!collapsed && (
            <Button variant="ghost" size="sm" onClick={() => setCollapsed(true)} className="text-zinc-400 hover:text-white hover:bg-white/5 h-8 w-8 p-0 flex-shrink-0">
              <ChevronLeft className="h-4 w-4" />
            </Button>
          )}
        </div>

        {/* Menu */}
        <nav className="flex-1 overflow-y-auto py-4 px-2">
          {menuItems.map((item) => {
            if (item.children) {
              const isOpen = openKeys.includes(item.key)
              return (
                <Collapsible key={item.key} defaultOpen={isOpen}>
                  <CollapsibleTrigger className="w-full">
                    <div
                      className={cn(
                        'flex items-center gap-3 px-3 py-2.5 rounded-lg hover:bg-white/5 transition-colors cursor-pointer mb-1',
                        selectedKeys.some((k) => k.startsWith(item.key)) ? 'bg-indigo-500/10 text-indigo-400' : 'text-zinc-400'
                      )}
                    >
                      {item.icon && <item.icon className="h-5 w-5 flex-shrink-0" />}
                      {!collapsed && (
                        <>
                          <span className="flex-1 text-left text-sm font-medium">{item.label}</span>
                          <ChevronDown className="h-4 w-4" />
                        </>
                      )}
                    </div>
                  </CollapsibleTrigger>
                  {!collapsed && (
                    <CollapsibleContent>
                      <div className="ml-8 space-y-1 mb-1">
                        {item.children.map((child) => (
                          <div
                            key={child.key}
                            onClick={() => handleMenuClick(child.key)}
                            className={cn(
                              'px-3 py-2 rounded-lg hover:bg-white/5 transition-colors cursor-pointer text-sm',
                              selectedKeys.includes(child.key) ? 'bg-indigo-500/10 text-indigo-400 font-medium' : 'text-zinc-500 hover:text-zinc-300'
                            )}
                          >
                            {child.label}
                          </div>
                        ))}
                      </div>
                    </CollapsibleContent>
                  )}
                </Collapsible>
              )
            }

            const Icon = item.icon
            return (
              <div
                key={item.key}
                onClick={() => handleMenuClick(item.key)}
                className={cn(
                  'flex items-center gap-3 px-3 py-2.5 rounded-lg hover:bg-white/5 transition-colors cursor-pointer mb-1',
                  selectedKeys.includes(item.key) ? 'bg-indigo-500/10 text-indigo-400 font-medium' : 'text-zinc-400 hover:text-zinc-200'
                )}
              >
                {Icon && <Icon className="h-5 w-5 flex-shrink-0" />}
                {!collapsed && <span className="text-sm font-medium">{item.label}</span>}
              </div>
            )
          })}
        </nav>

        {/* User Section at Bottom */}
        <UserSection />
      </aside>

      {/* Mobile Sidebar */}
      {mobileMenuOpen && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <div className="fixed inset-0 bg-black/50" onClick={() => setMobileMenuOpen(false)} />
          <aside className="fixed left-0 top-0 bottom-0 w-64 bg-zinc-950 flex flex-col">
            <div className="h-16 flex items-center justify-between px-4 border-b border-zinc-800">
              <div className="flex items-center gap-2">
                <div className="h-8 w-8 bg-indigo-500/10 rounded-lg flex items-center justify-center ring-1 ring-indigo-500/20">
                  <Shield className="h-5 w-5 text-indigo-400" />
                </div>
                <span className="font-bold text-lg text-white">FangcunGuard</span>
              </div>
              <Button variant="ghost" size="sm" onClick={() => setMobileMenuOpen(false)} className="text-zinc-500 hover:text-white">
                <X className="h-5 w-5" />
              </Button>
            </div>
            <nav className="flex-1 overflow-y-auto py-4 px-2">
              {menuItems.map((item) => {
                if (item.children) {
                  const isOpen = openKeys.includes(item.key)
                  return (
                    <Collapsible key={item.key} defaultOpen={isOpen}>
                      <CollapsibleTrigger className="w-full">
                        <div
                          className={cn(
                            'flex items-center gap-3 px-3 py-2.5 rounded-md hover:bg-white/5 transition-colors cursor-pointer mb-1',
                            selectedKeys.some((k) => k.startsWith(item.key)) ? 'bg-indigo-500/10 text-indigo-400' : 'text-zinc-400'
                          )}
                        >
                          {item.icon && <item.icon className="h-5 w-5 flex-shrink-0" />}
                          <span className="flex-1 text-left text-sm font-medium">{item.label}</span>
                          <ChevronDown className="h-4 w-4" />
                        </div>
                      </CollapsibleTrigger>
                      <CollapsibleContent>
                        <div className="ml-8 space-y-1 mb-1">
                          {item.children.map((child) => (
                            <div
                              key={child.key}
                              onClick={() => handleMenuClick(child.key)}
                              className={cn(
                                'px-3 py-2 rounded-md hover:bg-white/5 transition-colors cursor-pointer text-sm',
                                selectedKeys.includes(child.key) ? 'bg-indigo-500/10 text-indigo-400 font-medium' : 'text-zinc-500 hover:text-zinc-300'
                              )}
                            >
                              {child.label}
                            </div>
                          ))}
                        </div>
                      </CollapsibleContent>
                    </Collapsible>
                  )
                }

                const Icon = item.icon
                return (
                  <div
                    key={item.key}
                    onClick={() => handleMenuClick(item.key)}
                    className={cn(
                      'flex items-center gap-3 px-3 py-2.5 rounded-md hover:bg-white/5 transition-colors cursor-pointer mb-1',
                      selectedKeys.includes(item.key) ? 'bg-indigo-500/10 text-indigo-400 font-medium' : 'text-zinc-400 hover:text-zinc-200'
                    )}
                  >
                    {Icon && <Icon className="h-5 w-5 flex-shrink-0" />}
                    <span className="text-sm font-medium">{item.label}</span>
                  </div>
                )
              })}
            </nav>
            <UserSection isMobile />
          </aside>
        </div>
      )}

      {/* Main Content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Header — Dark glass morphism */}
        <header className="h-16 bg-zinc-900/80 backdrop-blur-xl border-b border-zinc-800/60 flex items-center justify-between px-4 lg:px-6 flex-shrink-0">
          {/* Left side - Mobile menu & Title */}
          <div className="flex items-center gap-4">
            <Button variant="ghost" size="sm" className="lg:hidden text-zinc-400 hover:text-white" onClick={() => setMobileMenuOpen(true)}>
              <MenuIcon className="h-5 w-5" />
            </Button>
            <h1 className="text-lg font-bold text-white">{t('common.appName')}</h1>
          </div>

          {/* Right side - Actions */}
          <div className="flex items-center gap-2 lg:gap-3">
            {/* Application Selector */}
            <ApplicationSelector />
          </div>
        </header>

        {/* Content */}
        <main className="flex-1 overflow-hidden p-4 lg:p-6">
          <div className="bg-zinc-900/50 rounded-xl border border-zinc-800 p-6 h-full overflow-y-auto">
            {children}
          </div>
        </main>
      </div>

      {/* Tenant switch Dialog */}
      <Dialog open={switchModalVisible} onOpenChange={setSwitchModalVisible}>
        <DialogContent className="sm:max-w-[600px] bg-zinc-900 border-zinc-800">
          <DialogHeader>
            <DialogTitle className="text-white">{t('layout.switchTenant')}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <p className="text-sm text-zinc-400">{t('layout.selectTenantPrompt')}</p>
            <Select onValueChange={handleSwitchUser}>
              <SelectTrigger className="bg-zinc-800/50 border-zinc-700 text-white">
                <SelectValue placeholder={t('layout.selectTenantPlaceholder')} />
              </SelectTrigger>
              <SelectContent className="bg-zinc-900 border-zinc-800">
                {users.map((u) => (
                  <SelectItem key={u.id} value={u.id} className="text-zinc-300 focus:bg-zinc-800 focus:text-white">
                    <div className="flex items-center justify-between w-full">
                      <span>{u.email}</span>
                      <div className="flex gap-1">
                        {u.is_super_admin && <span className="px-2 py-0.5 text-xs rounded bg-red-500/20 text-red-300">{t('layout.admin')}</span>}
                        {u.is_verified ? (
                          <span className="px-2 py-0.5 text-xs rounded bg-green-500/20 text-green-300">{t('layout.verified')}</span>
                        ) : (
                          <span className="px-2 py-0.5 text-xs rounded bg-orange-500/20 text-orange-300">{t('layout.unverified')}</span>
                        )}
                      </div>
                    </div>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="text-xs text-zinc-500">{t('layout.switchNote')}</p>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}

export default Layout
