import { NavLink, useLocation } from 'react-router-dom'
import {
  LayoutDashboard,
  Ticket,
  BookOpen,
  CheckCircle2,
  Bot,
  BarChart3,
  Activity,
  ScrollText,
  Settings,
  LogOut,
  Zap,
  ChevronRight,
} from 'lucide-react'
import { cn } from '@/utils/cn'
import { useAuthStore } from '@/stores/authStore'
import { Badge } from '@/components/ui/Badge'

interface NavItem {
  to: string
  label: string
  icon: typeof LayoutDashboard
  badge?: string
  badgeVariant?: 'primary' | 'warning' | 'danger'
  comingSoon?: boolean
}

const navItems: NavItem[] = [
  { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/tickets', label: 'Tickets', icon: Ticket },
  { to: '/knowledge', label: 'Knowledge', icon: BookOpen },
  { to: '/approvals', label: 'Approvals', icon: CheckCircle2 },
  { to: '/agents', label: 'AI Agents', icon: Bot },
  { to: '/evaluations', label: 'Evaluations', icon: BarChart3 },
  { to: '/observability', label: 'Observability', icon: Activity },
  { to: '/audit', label: 'Audit Log', icon: ScrollText },
]

const bottomItems: NavItem[] = [
  { to: '/settings', label: 'Settings', icon: Settings },
]

export function Sidebar({ isOpen, onClose }: { isOpen?: boolean; onClose?: () => void }) {
  const { user, logout } = useAuthStore()
  const location = useLocation()

  return (
    <>
      {/* Mobile Overlay */}
      {isOpen && (
        <div 
          className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm lg:hidden"
          onClick={onClose}
          aria-hidden="true"
        />
      )}

      {/* Sidebar Container */}
      <aside 
        className={cn(
          "fixed inset-y-0 left-0 z-50 flex flex-col w-64 bg-base-surface border-r border-base-border transform transition-transform duration-200 ease-in-out lg:relative lg:translate-x-0 lg:shrink-0",
          isOpen ? "translate-x-0" : "-translate-x-full"
        )}
      >
        {/* ─── Brand ──────────────────────────────────────────────────────── */}
      <div className="flex items-center gap-3 px-5 py-5 border-b border-base-border">
        <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-primary-500 to-secondary-500 flex items-center justify-center shadow-glow shrink-0">
          <Zap className="w-4 h-4 text-white" strokeWidth={2.5} />
        </div>
        <div>
          <span className="font-bold text-slate-100 tracking-tight">OpsPilot</span>
          <p className="text-[10px] text-slate-500 uppercase tracking-widest font-medium">
            Enterprise WorkOps
          </p>
        </div>
      </div>

      {/* ─── Org badge ──────────────────────────────────────────────────── */}
      <div className="px-4 py-3 border-b border-base-border">
        <div className="flex items-center gap-2 px-3 py-2 bg-base-elevated rounded-lg">
          <div className="w-5 h-5 rounded bg-primary-500/20 flex items-center justify-center text-[10px] font-bold text-primary-400">
            {user?.full_name?.[0]?.toUpperCase() ?? 'O'}
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-xs font-medium text-slate-300 truncate">
              {user?.full_name ?? 'Organization'}
            </p>
            <p className="text-[10px] text-slate-600 capitalize">{user?.role ?? 'role'}</p>
          </div>
        </div>
      </div>

      {/* ─── Navigation ─────────────────────────────────────────────────── */}
      <nav className="flex-1 px-3 py-4 space-y-0.5 overflow-y-auto" aria-label="Main navigation">
        {navItems.map((item) => (
          <SidebarNavItem key={item.to} item={item} currentPath={location.pathname} onClick={onClose} />
        ))}
      </nav>

      {/* ─── Bottom actions ─────────────────────────────────────────────── */}
      <div className="px-3 py-3 border-t border-base-border space-y-0.5">
        {bottomItems.map((item) => (
          <SidebarNavItem key={item.to} item={item} currentPath={location.pathname} onClick={onClose} />
        ))}
        <button
          onClick={logout}
          className="nav-item w-full text-left text-danger/80 hover:text-danger hover:bg-danger/10"
          aria-label="Log out"
        >
          <LogOut className="w-4 h-4 shrink-0" />
          <span>Log out</span>
        </button>
      </div>
    </aside>
    </>
  )
}

// ─── Nav Item ────────────────────────────────────────────────────────────────
function SidebarNavItem({
  item,
  currentPath,
  onClick
}: {
  item: NavItem
  currentPath: string
  onClick?: () => void
}) {
  const isActive = currentPath.startsWith(item.to)
  const Icon = item.icon

  return (
    <NavLink
      to={item.to}
      onClick={onClick}
      className={cn('nav-item', isActive && 'nav-item-active')}
      aria-current={isActive ? 'page' : undefined}
    >
      <Icon className="w-4 h-4 shrink-0" />
      <span className="flex-1">{item.label}</span>
      {item.badge && (
        <Badge variant={item.badgeVariant ?? 'primary'} className="text-[10px] px-1.5 py-0">
          {item.badge}
        </Badge>
      )}
      {isActive && (
        <ChevronRight className="w-3 h-3 opacity-50 shrink-0" />
      )}
    </NavLink>
  )
}
