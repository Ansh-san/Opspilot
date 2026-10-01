import { Bell, Search, Menu } from 'lucide-react'
import { useAuthStore } from '@/stores/authStore'
import { Badge } from '@/components/ui/Badge'
import type { UserRole } from '@/types'

const roleLabels: Record<UserRole, { label: string; variant: 'primary' | 'secondary' | 'success' | 'warning' }> = {
  admin: { label: 'Admin', variant: 'danger' as never },
  manager: { label: 'Manager', variant: 'warning' },
  agent: { label: 'Agent', variant: 'primary' },
  viewer: { label: 'Viewer', variant: 'secondary' },
}

interface TopbarProps {
  title?: string
  subtitle?: string
  onOpenSidebar?: () => void
}

export function Topbar({ title, subtitle, onOpenSidebar }: TopbarProps) {
  const { user } = useAuthStore()
  const roleConfig = user ? roleLabels[user.role] : null

  return (
    <header className="flex items-center justify-between px-6 py-4 border-b border-base-border bg-base-surface/80 backdrop-blur-sm sticky top-0 z-10">
      {/* ─── Left: Mobile Menu & Page title ───────────────────────────── */}
      <div className="flex items-center gap-4">
        {/* Mobile Hamburger */}
        <button 
          onClick={onOpenSidebar}
          className="lg:hidden p-2 -ml-2 rounded-lg text-slate-400 hover:text-slate-100 hover:bg-base-elevated transition-colors"
          aria-label="Open sidebar"
        >
          <Menu className="w-5 h-5" />
        </button>

        <div>
          {title && (
            <h1 className="text-lg font-semibold text-slate-100">{title}</h1>
          )}
          {subtitle && (
            <p className="text-sm text-slate-500">{subtitle}</p>
          )}
        </div>
      </div>

      {/* ─── Right: Search + Notifications + User ─────────────────────── */}
      <div className="flex items-center gap-3">
        {/* Search */}
        <button
          className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-base-elevated border border-base-border
                     text-slate-500 hover:text-slate-300 hover:border-base-divider transition-all text-sm"
          aria-label="Search"
        >
          <Search className="w-4 h-4" />
          <span className="hidden sm:inline">Search…</span>
          <kbd className="hidden sm:inline ml-2 text-xs bg-base-surface px-1.5 py-0.5 rounded border border-base-border font-mono">
            ⌘K
          </kbd>
        </button>

        {/* Notifications */}
        <button
          className="relative p-2 rounded-lg hover:bg-base-elevated text-slate-400
                     hover:text-slate-100 transition-colors"
          aria-label="Notifications"
        >
          <Bell className="w-5 h-5" />
          <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-primary-500 rounded-full" aria-hidden="true" />
        </button>

        {/* User avatar */}
        <div className="flex items-center gap-2.5 pl-2 border-l border-base-border">
          <div className="w-8 h-8 rounded-full bg-gradient-to-br from-primary-500 to-secondary-500 flex items-center justify-center text-sm font-bold text-white">
            {user?.full_name?.[0]?.toUpperCase() ?? '?'}
          </div>
          <div className="hidden md:block">
            <p className="text-sm font-medium text-slate-200 leading-none">{user?.full_name}</p>
            {roleConfig && (
              <Badge variant={roleConfig.variant as never} className="mt-1 text-[10px] px-1.5 py-0">
                {roleConfig.label}
              </Badge>
            )}
          </div>
        </div>
      </div>
    </header>
  )
}
