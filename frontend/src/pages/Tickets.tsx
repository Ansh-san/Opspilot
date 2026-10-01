/**
 * TicketsPage — enterprise ticket management list with:
 * - KPI cards (Open, Investigating, Critical)
 * - Filter bar (status, priority, search)
 * - Paginated table with colored badges
 * - Create Ticket modal
 */

import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { ticketsApi } from '@/api/tickets'
import { getErrorMessage } from '@/api/client'
import type { Ticket, TicketStatus, TicketPriority } from '@/types/ticket'
import { StatusBadge, PriorityBadge, SeverityBadge } from '@/components/tickets/TicketBadges'
import { CreateTicketModal } from '@/components/tickets/CreateTicketModal'
import { useToast } from '@/components/ui/Toast'

import { AppLayout } from '@/components/layout/AppLayout'
import { Skeleton } from '@/components/ui/Skeleton'

const PAGE_SIZE = 15

// ─── KPI Card ────────────────────────────────────────────────────────────────
function KpiCard({
  label,
  value,
  icon,
  colorClass,
  loading,
}: {
  label: string
  value: number
  icon: string
  colorClass: string
  loading?: boolean
}) {
  if (loading) {
    return <Skeleton className="h-[104px] w-full rounded-2xl" />
  }
  return (
    <div className="glass-card p-5 flex items-center gap-4">
      <div className={`w-12 h-12 rounded-xl flex items-center justify-center text-xl ${colorClass}`}>
        {icon}
      </div>
      <div>
        <p className="text-2xl font-bold text-slate-100">{value}</p>
        <p className="text-sm text-slate-400">{label}</p>
      </div>
    </div>
  )
}

// ─── Filter Bar ───────────────────────────────────────────────────────────────
const STATUS_OPTIONS: { value: string; label: string }[] = [
  { value: '', label: 'All Statuses' },
  { value: 'open', label: 'Open' },
  { value: 'investigating', label: 'Investigating' },
  { value: 'waiting_approval', label: 'Waiting Approval' },
  { value: 'in_progress', label: 'In Progress' },
  { value: 'resolved', label: 'Resolved' },
  { value: 'closed', label: 'Closed' },
]

const PRIORITY_OPTIONS: { value: string; label: string }[] = [
  { value: '', label: 'All Priorities' },
  { value: 'critical', label: 'Critical' },
  { value: 'high', label: 'High' },
  { value: 'medium', label: 'Medium' },
  { value: 'low', label: 'Low' },
]

// ─── Main Page ────────────────────────────────────────────────────────────────
export default function TicketsPage() {
  const navigate = useNavigate()
  const { showToast, ToastNode } = useToast()

  const [tickets, setTickets] = useState<Ticket[]>([])
  const [total, setTotal] = useState(0)
  const [totalPages, setTotalPages] = useState(1)
  const [page, setPage] = useState(1)
  const [isLoading, setIsLoading] = useState(true)

  const [statusFilter, setStatusFilter] = useState<TicketStatus | ''>('')
  const [priorityFilter, setPriorityFilter] = useState<TicketPriority | ''>('')
  const [search, setSearch] = useState('')
  const [showModal, setShowModal] = useState(false)

  const fetchTickets = useCallback(async () => {
    setIsLoading(true)
    try {
      const { data } = await ticketsApi.list({
        skip: (page - 1) * PAGE_SIZE,
        limit: PAGE_SIZE,
        ...(statusFilter && { status: statusFilter }),
        ...(priorityFilter && { priority: priorityFilter }),
      })
      setTickets(data.items)
      setTotal(data.total)
      setTotalPages(data.total_pages)
    } catch (err) {
      const msg = getErrorMessage(err)
      if (msg.includes('403') || msg.toLowerCase().includes('forbidden')) {
        showToast('You don\'t have permission to view tickets.', 'error')
      } else {
        showToast(msg)
      }
    } finally {
      setIsLoading(false)
    }
  }, [page, statusFilter, priorityFilter, showToast])

  useEffect(() => {
    fetchTickets()
  }, [fetchTickets])

  // Client-side search filter (title/service)
  const displayed = search
    ? tickets.filter(
        (t) =>
          t.title.toLowerCase().includes(search.toLowerCase()) ||
          (t.affected_service ?? '').toLowerCase().includes(search.toLowerCase())
      )
    : tickets

  // KPI derived counts
  const openCount = tickets.filter((t) => t.status === 'open').length
  const investigatingCount = tickets.filter((t) => t.status === 'investigating').length
  const criticalCount = tickets.filter((t) => t.priority === 'critical').length

  const handleCreated = (ticket: Ticket) => {
    setShowModal(false)
    navigate(`/tickets/${ticket.id}`)
  }

  const formatDate = (iso: string) =>
    new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }).format(new Date(iso))

  return (
    <AppLayout title="Tickets" subtitle="Manage support and incidents">
      <div className="space-y-6 max-w-7xl">
        {ToastNode}
        {showModal && (
          <CreateTicketModal onClose={() => setShowModal(false)} onCreated={handleCreated} />
        )}

        {/* ── Header ────────────────────────────────────────────────────── */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-slate-100">Ticket Management</h1>
            <p className="text-sm text-slate-400 mt-0.5">
              {total} total tickets · Page {page} of {totalPages}
            </p>
          </div>
          <button
            id="create-ticket-btn"
            onClick={() => setShowModal(true)}
            className="flex items-center gap-2 px-4 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium rounded-xl transition-all shadow-lg shadow-indigo-500/20 focus-visible:ring-2 focus-visible:ring-indigo-400 focus:outline-none"
            aria-label="Create new ticket"
          >
            <svg className="w-4 h-4" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
              <path fillRule="evenodd" d="M10 3a1 1 0 011 1v5h5a1 1 0 110 2h-5v5a1 1 0 11-2 0v-5H4a1 1 0 110-2h5V4a1 1 0 011-1z" clipRule="evenodd" />
            </svg>
            New Ticket
          </button>
        </div>

        {/* ── KPI Cards ─────────────────────────────────────────────────── */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <KpiCard label="Open" value={openCount} icon="🔓" colorClass="bg-blue-500/10 text-blue-400" loading={isLoading} />
          <KpiCard label="Investigating" value={investigatingCount} icon="🔍" colorClass="bg-yellow-500/10 text-yellow-400" loading={isLoading} />
          <KpiCard label="Critical Priority" value={criticalCount} icon="🔴" colorClass="bg-red-500/10 text-red-400" loading={isLoading} />
        </div>

        {/* ── Filter Bar ────────────────────────────────────────────────── */}
        <div className="glass-card p-4 flex flex-wrap items-center gap-3">
          {/* Search */}
          <div className="relative flex-1 min-w-[200px]">
            <label htmlFor="ticket-search" className="sr-only">Search tickets</label>
            <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
              <path fillRule="evenodd" d="M8 4a4 4 0 100 8 4 4 0 000-8zM2 8a6 6 0 1110.89 3.476l4.817 4.817a1 1 0 01-1.414 1.414l-4.816-4.816A6 6 0 012 8z" clipRule="evenodd" />
            </svg>
            <input
              id="ticket-search"
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search tickets…"
              className="w-full bg-slate-800/60 border border-slate-700 rounded-lg pl-9 pr-4 py-2 text-slate-100 placeholder-slate-500 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/50 transition-all"
            />
          </div>

          {/* Status Filter */}
          <select
            id="status-filter"
            value={statusFilter}
            onChange={(e) => { setStatusFilter(e.target.value as TicketStatus | ''); setPage(1) }}
            className="bg-slate-800/60 border border-slate-700 rounded-lg px-3 py-2 text-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/50 transition-all"
            aria-label="Filter by status"
          >
            {STATUS_OPTIONS.map((o) => (
              <option key={o.value} value={o.value} className="bg-slate-900">
                {o.label}
              </option>
            ))}
          </select>

          {/* Priority Filter */}
          <select
            id="priority-filter"
            value={priorityFilter}
            onChange={(e) => { setPriorityFilter(e.target.value as TicketPriority | ''); setPage(1) }}
            className="bg-slate-800/60 border border-slate-700 rounded-lg px-3 py-2 text-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/50 transition-all"
            aria-label="Filter by priority"
          >
            {PRIORITY_OPTIONS.map((o) => (
              <option key={o.value} value={o.value} className="bg-slate-900">
                {o.label}
              </option>
            ))}
          </select>

          {(statusFilter || priorityFilter || search) && (
            <button
              onClick={() => { setStatusFilter(''); setPriorityFilter(''); setSearch(''); setPage(1) }}
              className="text-sm text-slate-400 hover:text-slate-100 transition-colors"
            >
              Clear filters
            </button>
          )}
        </div>

        {/* ── Table ─────────────────────────────────────────────────────── */}
        <div className="glass-card overflow-hidden">
          {isLoading ? (
            <div className="p-6 space-y-4">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-14 w-full" />
              ))}
            </div>
        ) : displayed.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-24 gap-4">
            <div className="w-16 h-16 rounded-2xl bg-slate-800 flex items-center justify-center text-3xl">
              🎫
            </div>
            <div className="text-center">
              <p className="text-slate-300 font-medium">No tickets found</p>
              <p className="text-slate-500 text-sm mt-1">
                {search || statusFilter || priorityFilter
                  ? 'Try adjusting your filters'
                  : 'Create your first ticket to get started'}
              </p>
            </div>
            {!search && !statusFilter && !priorityFilter && (
              <button
                onClick={() => setShowModal(true)}
                className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium rounded-lg transition-all"
              >
                Create Ticket
              </button>
            )}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-slate-700/50">
                  <th className="px-6 py-3.5 text-left text-xs font-semibold text-slate-400 uppercase tracking-wider">Title</th>
                  <th className="px-4 py-3.5 text-left text-xs font-semibold text-slate-400 uppercase tracking-wider">Status</th>
                  <th className="px-4 py-3.5 text-left text-xs font-semibold text-slate-400 uppercase tracking-wider">Priority</th>
                  <th className="px-4 py-3.5 text-left text-xs font-semibold text-slate-400 uppercase tracking-wider">Severity</th>
                  <th className="px-4 py-3.5 text-left text-xs font-semibold text-slate-400 uppercase tracking-wider">Service</th>
                  <th className="px-4 py-3.5 text-left text-xs font-semibold text-slate-400 uppercase tracking-wider">Created</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-700/30">
                {displayed.map((ticket) => (
                  <tr
                    key={ticket.id}
                    onClick={() => navigate(`/tickets/${ticket.id}`)}
                    className="hover:bg-slate-700/20 cursor-pointer transition-colors group"
                  >
                    <td className="px-6 py-4">
                      <div className="font-medium text-slate-200 group-hover:text-indigo-300 transition-colors line-clamp-1 max-w-xs">
                        {ticket.title}
                      </div>
                      {ticket.category && (
                        <div className="text-xs text-slate-500 mt-0.5">{ticket.category}</div>
                      )}
                    </td>
                    <td className="px-4 py-4">
                      <StatusBadge status={ticket.status} />
                    </td>
                    <td className="px-4 py-4">
                      <PriorityBadge priority={ticket.priority} />
                    </td>
                    <td className="px-4 py-4">
                      <SeverityBadge severity={ticket.severity} />
                    </td>
                    <td className="px-4 py-4 text-sm text-slate-400">
                      {ticket.affected_service ?? <span className="text-slate-600">—</span>}
                    </td>
                    <td className="px-4 py-4 text-sm text-slate-500">
                      {formatDate(ticket.created_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination */}
        {!isLoading && totalPages > 1 && (
          <div className="flex items-center justify-between px-6 py-4 border-t border-slate-700/50">
            <p className="text-sm text-slate-400">
              Showing {(page - 1) * PAGE_SIZE + 1}–{Math.min(page * PAGE_SIZE, total)} of {total}
            </p>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
                className="px-3 py-1.5 text-sm text-slate-400 hover:text-slate-100 bg-slate-700/50 hover:bg-slate-700 disabled:opacity-30 disabled:cursor-not-allowed rounded-lg transition-all"
              >
                ← Prev
              </button>
              <span className="text-sm text-slate-300 px-2">
                {page} / {totalPages}
              </span>
              <button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page === totalPages}
                className="px-3 py-1.5 text-sm text-slate-400 hover:text-slate-100 bg-slate-700/50 hover:bg-slate-700 disabled:opacity-30 disabled:cursor-not-allowed rounded-lg transition-all"
              >
                Next →
              </button>
            </div>
          </div>
        )}
      </div>
      </div>
    </AppLayout>
  )
}
