import { useEffect, useState } from 'react'
import {
  Ticket,
  CheckCircle,
  Bot,
  TrendingUp,
  AlertTriangle,
  ArrowUpRight,
  Activity,
  RefreshCw,
  Shield,
} from 'lucide-react'
import { AppLayout } from '@/components/layout/AppLayout'
import { Card } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { useAuthStore } from '@/stores/authStore'
import { apiClient } from '@/api/client'


import { Skeleton } from '@/components/ui/Skeleton'

const QUICK_LINKS = [
  { label: 'Create Ticket', icon: Ticket, to: '/tickets', description: 'Submit a new support ticket' },
  { label: 'Run AI Diagnosis', icon: Bot, to: '/agents', description: 'Trigger AI investigation' },
  { label: 'Review Approvals', icon: Shield, to: '/approvals', description: 'Pending human approvals' },
  { label: 'View Observability', icon: Activity, to: '/observability', description: 'System metrics & traces' },
]

export default function Dashboard() {
  const { user } = useAuthStore()
  
  const [ticketStats, setTicketStats] = useState({ open: '—', critical: '—' })
  const [aiMetrics, setAiMetrics] = useState({ totalRuns: '—', successRate: '—', avgLatency: '—', estimatedCost: '—' })
  const [pendingApprovals, setPendingApprovals] = useState('—')
  const [recentTickets, setRecentTickets] = useState<any[]>([])
  const [sysStatus, setSysStatus] = useState({ api: false, db: false, agent: false })
  const [loading, setLoading] = useState(true)

  const fetchData = async () => {
    setLoading(true)
    try {
      const [ticketsOpen, ticketsCritical, recent, approvals, obs, health] = await Promise.all([
        apiClient.get('/api/v1/tickets?status=open&limit=1').catch(() => ({ data: { total: 0 } })),
        apiClient.get('/api/v1/tickets?priority=critical&status=open&limit=1').catch(() => ({ data: { total: 0 } })),
        apiClient.get('/api/v1/tickets?limit=5').catch(() => ({ data: { items: [] } })),
        apiClient.get('/api/v1/approvals?status=pending').catch(() => ({ data: [] })),
        apiClient.get('/api/v1/observability/metrics').catch(() => ({ data: {} })),
        apiClient.get('/api/v1/health').catch(() => ({ data: { status: 'error' } }))
      ])

      setTicketStats({
        open: ticketsOpen.data.total?.toString() || '0',
        critical: ticketsCritical.data.total?.toString() || '0'
      })

      setRecentTickets(recent.data.items || [])
      setPendingApprovals(approvals.data.length?.toString() || '0')

      const obsData = obs.data
      setAiMetrics({
        totalRuns: obsData.total_runs?.toString() || '0',
        successRate: obsData.tool_success_rate != null ? Math.round(obsData.tool_success_rate * 100).toString() : 'N/A',
        avgLatency: obsData.avg_latency != null ? Math.round(obsData.avg_latency).toString() : 'N/A',
        estimatedCost: obsData.total_estimated_cost != null ? `$${obsData.total_estimated_cost.toFixed(2)}` : 'N/A'
      })

      setSysStatus({
        api: health.data.status === 'ok',
        db: health.data.status === 'ok',
        agent: health.data.status === 'ok',
      })
    } catch (err) {
      console.error("Dashboard data fetch failed", err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
  }, [])

  const greeting = (() => {
    const h = new Date().getHours()
    if (h < 12) return 'Good morning'
    if (h < 17) return 'Good afternoon'
    return 'Good evening'
  })()

  // Replace static data with live state
  const KPI_CARDS = [
    {
      label: 'Open Tickets',
      value: ticketStats.open,
      icon: Ticket,
      color: 'text-primary-400',
      bg: 'bg-primary-500/10 border-primary-500/20',
    },
    {
      label: 'Critical Tickets',
      value: ticketStats.critical,
      icon: AlertTriangle,
      color: 'text-danger',
      bg: 'bg-danger/10 border-danger/20',
    },
    {
      label: 'Pending Approvals',
      value: pendingApprovals,
      icon: Shield,
      color: 'text-warning',
      bg: 'bg-warning/10 border-warning/20',
    },
    {
      label: 'Total AI Runs',
      value: aiMetrics.totalRuns,
      icon: Bot,
      color: 'text-secondary-400',
      bg: 'bg-secondary-400/10 border-secondary-400/20',
    },
    {
      label: 'AI Success Rate',
      value: aiMetrics.successRate,
      unit: '%',
      icon: CheckCircle,
      color: 'text-success',
      bg: 'bg-success/10 border-success/20',
    },
    {
      label: 'Avg AI Latency',
      value: aiMetrics.avgLatency,
      unit: 'ms',
      icon: Activity,
      color: 'text-accent-400',
      bg: 'bg-accent-400/10 border-accent-400/20',
    },
    {
      label: 'Estimated Cost',
      value: aiMetrics.estimatedCost,
      icon: TrendingUp,
      color: 'text-indigo-400',
      bg: 'bg-indigo-400/10 border-indigo-400/20',
    },
  ]

  return (
    <AppLayout title="Dashboard" subtitle="Your operational overview">
      <div className="space-y-6 max-w-7xl">
        {/* ─── Welcome ──────────────────────────────────────────────────── */}
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-2xl font-bold text-slate-100">
              {greeting},{' '}
              <span className="gradient-text">{user?.full_name?.split(' ')[0]}</span> 👋
            </h2>
            <p className="text-slate-500 mt-1">
              Here's what's happening in your workspace today.
            </p>
          </div>
          <div className="flex items-center gap-2">
            {!loading && (
              <Badge variant={sysStatus.api ? "primary" : "danger"} dot>
                {sysStatus.api ? "System healthy" : "System degraded"}
              </Badge>
            )}
            <button 
              onClick={fetchData}
              disabled={loading}
              className={`p-2 rounded-lg hover:bg-base-elevated text-slate-500 hover:text-slate-300 transition-colors ${loading ? 'animate-spin' : ''}`}
              aria-label="Refresh data"
            >
              <RefreshCw className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* ─── Metrics ──────────────────────────────────────────────── */}
        <section aria-label="System Metrics">
          <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">
            System Metrics
          </h3>
          <div className="grid grid-cols-2 xl:grid-cols-4 gap-4">
            {loading ? (
              Array.from({ length: 7 }).map((_, i) => (
                <Skeleton key={i} className="h-32 w-full rounded-xl" />
              ))
            ) : (
              KPI_CARDS.map((card) => {
                const Icon = card.icon || Activity
                return (
                  <Card key={card.label} hover className="relative overflow-hidden">
                    <div className={`inline-flex p-2.5 rounded-lg border mb-3 ${card.bg}`}>
                      <Icon className={`w-5 h-5 ${card.color}`} aria-hidden="true" />
                    </div>
                    <div>
                      <p className="text-2xl font-bold text-slate-100">
                        {card.value}
                        {card.unit && <span className="text-sm text-slate-500 ml-1">{card.unit}</span>}
                      </p>
                      <p className="text-sm text-slate-500 mt-0.5">{card.label}</p>
                    </div>
                    <Badge variant="secondary" className="absolute top-4 right-4 text-[10px]">
                      Live
                    </Badge>
                  </Card>
                )
              })
            )}
          </div>
        </section>

        {/* ─── Recent Activity ────────────────────────────────────────────── */}
        <section aria-label="Recent Activity">
          <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">
            Recent Tickets
          </h3>
          <Card>
            {loading ? (
              <div className="space-y-4 py-2">
                <Skeleton className="h-12 w-full" />
                <Skeleton className="h-12 w-full" />
                <Skeleton className="h-12 w-full" />
              </div>
            ) : recentTickets.length > 0 ? (
              <div className="divide-y divide-slate-800/50">
                {recentTickets.map(ticket => (
                  <div key={ticket.id} className="py-4 flex items-center justify-between">
                    <div>
                      <p className="font-medium text-slate-200">{ticket.title}</p>
                      <p className="text-sm text-slate-500">Status: {ticket.status} · Priority: {ticket.priority}</p>
                    </div>
                    <Badge variant={ticket.status === 'open' ? 'warning' : 'secondary'}>
                      {ticket.status}
                    </Badge>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-6 text-slate-500">No recent tickets</div>
            )}
          </Card>
        </section>

        {/* ─── Quick actions ────────────────────────────────────────────── */}
        <section aria-label="Quick actions">
          <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">
            Quick Actions
          </h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
            {QUICK_LINKS.map((link) => {
              const Icon = link.icon
              return (
                <a
                  key={link.label}
                  href={link.to}
                  className="glass-card p-5 hover:border-base-divider hover:shadow-card transition-all duration-200 group block focus-visible:ring-2 focus-visible:ring-primary-500 focus:outline-none"
                >
                  <div className="flex items-start justify-between">
                    <div className="p-2 bg-base-elevated rounded-lg group-hover:bg-primary-500/10 group-hover:border-primary-500/20 border border-transparent transition-all">
                      <Icon className="w-5 h-5 text-slate-400 group-hover:text-primary-400 transition-colors" aria-hidden="true" />
                    </div>
                    <ArrowUpRight className="w-4 h-4 text-slate-600 group-hover:text-primary-400 transition-colors" />
                  </div>
                  <p className="font-semibold text-slate-200 mt-3 group-hover:text-slate-100 transition-colors">
                    {link.label}
                  </p>
                  <p className="text-xs text-slate-500 mt-1">{link.description}</p>
                </a>
              )
            })}
          </div>
        </section>

        {/* ─── System status ────────────────────────────────────────────── */}
        <section aria-label="System status">
          <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">
            System Status
          </h3>
          <Card>
            {loading ? (
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
                <Skeleton className="h-10 w-full" />
                <Skeleton className="h-10 w-full" />
                <Skeleton className="h-10 w-full" />
              </div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-6 divide-y sm:divide-y-0 sm:divide-x divide-base-border">
                {[
                  { label: 'API Backend', status: sysStatus.api ? 'Operational' : 'Degraded', ok: sysStatus.api },
                  { label: 'Database', status: sysStatus.db ? 'Operational' : 'Degraded', ok: sysStatus.db },
                  { label: 'AI Agent', status: sysStatus.agent ? 'Operational' : 'Degraded', ok: sysStatus.agent },
                ].map((s) => (
                  <div key={s.label} className="sm:px-6 first:pl-0 last:pr-0 py-2 sm:py-0">
                    <div className="flex items-center gap-2">
                      <span
                        className={`w-2 h-2 rounded-full ${s.ok ? 'bg-success animate-pulse-slow' : 'bg-danger'}`}
                        aria-hidden="true"
                      />
                      <span className="text-sm font-medium text-slate-300">{s.label}</span>
                    </div>
                    <p className="text-xs text-slate-500 mt-1 ml-4">{s.status}</p>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </section>
      </div>
    </AppLayout>
  )
}
