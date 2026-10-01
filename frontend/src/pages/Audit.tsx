import { useState, useEffect, useCallback } from 'react'
import { AppLayout } from '@/components/layout/AppLayout'
import { auditApi } from '@/api/audit'
import type { AuditLog } from '@/api/audit'
import { getErrorMessage } from '@/api/client'
import { useToast } from '@/components/ui/Toast'

const PAGE_SIZE = 15

export default function AuditPage() {
  const { showToast, ToastNode } = useToast()

  const [logs, setLogs] = useState<AuditLog[]>([])
  const [total, setTotal] = useState(0)
  const [totalPages, setTotalPages] = useState(1)
  const [page, setPage] = useState(1)
  const [isLoading, setIsLoading] = useState(true)

  const [eventTypeFilter, setEventTypeFilter] = useState('')
  const [resourceTypeFilter, setResourceTypeFilter] = useState('')

  const fetchLogs = useCallback(async () => {
    setIsLoading(true)
    try {
      const { data } = await auditApi.list({
        page,
        page_size: PAGE_SIZE,
        ...(eventTypeFilter && { event_type: eventTypeFilter }),
        ...(resourceTypeFilter && { resource_type: resourceTypeFilter }),
      })
      setLogs(data.items)
      setTotal(data.total)
      setTotalPages(data.total_pages)
    } catch (err) {
      showToast(getErrorMessage(err), 'error')
    } finally {
      setIsLoading(false)
    }
  }, [page, eventTypeFilter, resourceTypeFilter, showToast])

  useEffect(() => {
    fetchLogs()
  }, [fetchLogs])

  const formatDate = (iso: string) =>
    new Intl.DateTimeFormat('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    }).format(new Date(iso))

  return (
    <AppLayout title="Audit Log" subtitle="System security and activity audit trail">
      <div className="space-y-6">
        {ToastNode}
        
        {/* ── Header ────────────────────────────────────────────────────── */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-slate-100 flex items-center gap-2">
              <span className="text-indigo-400">🛡️</span> Audit Log
            </h1>
            <p className="text-sm text-slate-400 mt-1">
              {total} total events · Page {page} of {totalPages}
            </p>
          </div>
        </div>

      {/* ── Filter Bar ────────────────────────────────────────────────── */}
      <div className="glass-card p-4 flex flex-wrap items-center gap-3">
        <input
          type="text"
          value={eventTypeFilter}
          onChange={(e) => { setEventTypeFilter(e.target.value); setPage(1) }}
          placeholder="Filter by event (e.g. ticket.created)"
          className="bg-slate-800/60 border border-slate-700 rounded-lg px-4 py-2 text-slate-100 placeholder-slate-500 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/50 transition-all min-w-[250px]"
        />
        <input
          type="text"
          value={resourceTypeFilter}
          onChange={(e) => { setResourceTypeFilter(e.target.value); setPage(1) }}
          placeholder="Filter by resource type (e.g. ticket)"
          className="bg-slate-800/60 border border-slate-700 rounded-lg px-4 py-2 text-slate-100 placeholder-slate-500 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/50 transition-all min-w-[250px]"
        />
        {(eventTypeFilter || resourceTypeFilter) && (
          <button
            onClick={() => { setEventTypeFilter(''); setResourceTypeFilter(''); setPage(1) }}
            className="text-sm text-slate-400 hover:text-slate-100 transition-colors"
          >
            Clear filters
          </button>
        )}
      </div>

      {/* ── Table ─────────────────────────────────────────────────────── */}
      <div className="glass-card overflow-hidden">
        {isLoading ? (
          <div className="flex items-center justify-center py-24">
            <div className="flex flex-col items-center gap-3">
              <svg className="w-8 h-8 animate-spin text-indigo-500" viewBox="0 0 24 24" fill="none">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
              </svg>
              <span className="text-sm text-slate-400">Loading audit log…</span>
            </div>
          </div>
        ) : logs.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-24 gap-4">
            <div className="w-16 h-16 rounded-2xl bg-slate-800 flex items-center justify-center text-3xl">
              🛡️
            </div>
            <div className="text-center">
              <p className="text-slate-300 font-medium">No events found</p>
              <p className="text-slate-500 text-sm mt-1">Try adjusting your filters.</p>
            </div>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-slate-800/50 text-slate-400 text-left">
                <tr>
                  <th className="px-5 py-3.5 font-medium whitespace-nowrap border-b border-slate-700/50">Timestamp</th>
                  <th className="px-5 py-3.5 font-medium whitespace-nowrap border-b border-slate-700/50">Event Type</th>
                  <th className="px-5 py-3.5 font-medium whitespace-nowrap border-b border-slate-700/50">Actor</th>
                  <th className="px-5 py-3.5 font-medium whitespace-nowrap border-b border-slate-700/50">Resource Type</th>
                  <th className="px-5 py-3.5 font-medium whitespace-nowrap border-b border-slate-700/50">IP Address</th>
                  <th className="px-5 py-3.5 font-medium whitespace-nowrap border-b border-slate-700/50">Details</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-700/50">
                {logs.map((log) => (
                  <tr key={log.id} className="hover:bg-slate-800/30 transition-colors group align-top">
                    <td className="px-5 py-4 text-sm text-slate-300 whitespace-nowrap">
                      {formatDate(log.created_at)}
                    </td>
                    <td className="px-5 py-4 text-sm font-mono text-indigo-400">
                      {log.event_type}
                    </td>
                    <td className="px-5 py-4">
                      <span className="inline-block px-2 py-1 rounded bg-slate-800 border border-slate-700 text-[10px] font-bold text-slate-300 uppercase tracking-wider">
                        {log.actor_type}
                      </span>
                    </td>
                    <td className="px-5 py-4 text-sm text-slate-400">
                      {log.resource_type}
                    </td>
                    <td className="px-5 py-4 text-sm font-mono text-slate-500">
                      {log.ip_address ?? '—'}
                    </td>
                    <td className="px-5 py-4 text-xs text-slate-500 font-mono">
                      <pre className="whitespace-pre-wrap break-words max-w-sm bg-slate-900/50 p-2 rounded border border-slate-800">
                        {JSON.stringify(log.details, null, 2)}
                      </pre>
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
