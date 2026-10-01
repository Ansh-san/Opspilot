import { useState, useEffect, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { AppLayout } from '@/components/layout/AppLayout'
import { agentsApi } from '@/api/agents'
import { getErrorMessage } from '@/api/client'
import type { AIRunSummary } from '@/api/agents'
import { useToast } from '@/components/ui/Toast'
import { Badge } from '@/components/ui/Badge'

import { Skeleton } from '@/components/ui/Skeleton'

const PAGE_SIZE = 15

// ─── Helpers ──────────────────────────────────────────────────────────────────

const RISK_CONFIG: Record<string, { label: string; color: string; bg: string }> = {
  low:     { label: 'Low Risk',     color: 'text-emerald-400', bg: 'bg-emerald-500/10 border-emerald-500/25' },
  medium:  { label: 'Medium Risk',  color: 'text-amber-400',   bg: 'bg-amber-500/10 border-amber-500/25'   },
  high:    { label: 'High Risk',    color: 'text-red-400',     bg: 'bg-red-500/10 border-red-500/25'       },
  blocked: { label: 'Blocked',      color: 'text-rose-300',    bg: 'bg-rose-500/10 border-rose-500/25'     },
}

function RiskBadge({ level }: { level: string | null }) {
  if (!level) return <span className="text-slate-600">—</span>
  const cfg = RISK_CONFIG[level] ?? RISK_CONFIG.high
  return (
    <span className={`px-2.5 py-1 rounded-full text-[10px] font-semibold border ${cfg.bg} ${cfg.color} whitespace-nowrap`}>
      {cfg.label}
    </span>
  )
}

function ConfidenceBar({ value }: { value: number | null }) {
  if (value === null) return <span className="text-slate-600">—</span>
  const pct = Math.round(value * 100)
  const color = value >= 0.75 ? 'bg-emerald-500' : value >= 0.5 ? 'bg-amber-500' : 'bg-red-500'
  return (
    <div className="flex items-center gap-2">
      <div className="w-16 h-1.5 bg-slate-800 rounded-full overflow-hidden">
        <div className={`h-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs text-slate-400">{pct}%</span>
    </div>
  )
}

function getApprovalBadge(r: AIRunSummary) {
  if (r.risk_level === 'blocked') return <Badge variant="danger">BLOCKED</Badge>
  if (!r.approval_status) return <Badge variant="secondary">NO_ACTION</Badge>
  switch (r.approval_status.toLowerCase()) {
    case 'pending': return <Badge variant="warning">PENDING</Badge>
    case 'approved': return <Badge variant="success">APPROVED</Badge>
    case 'rejected': return <Badge variant="danger">REJECTED</Badge>
    default: return <Badge variant="secondary">{r.approval_status.toUpperCase()}</Badge>
  }
}

function getExecutionBadge(r: AIRunSummary) {
  if (!r.execution_result) return <span className="text-slate-600">—</span>
  switch (r.execution_result.toLowerCase()) {
    case 'success':
    case 'executed': return <Badge variant="success">EXECUTED</Badge>
    case 'failed': return <Badge variant="danger">FAILED</Badge>
    default: return <Badge variant="secondary">{r.execution_result.toUpperCase()}</Badge>
  }
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function AgentsPage() {
  const { showToast, ToastNode } = useToast()

  const [runs, setRuns] = useState<AIRunSummary[]>([])
  const [total, setTotal] = useState(0)
  const [totalPages, setTotalPages] = useState(1)
  const [page, setPage] = useState(1)
  const [isLoading, setIsLoading] = useState(true)

  const fetchRuns = useCallback(async () => {
    setIsLoading(true)
    try {
      const { data } = await agentsApi.listRuns({
        page,
        page_size: PAGE_SIZE,
      })
      setRuns(data.items)
      setTotal(data.total)
      setTotalPages(data.total_pages)
    } catch (err) {
      showToast(getErrorMessage(err), 'error')
    } finally {
      setIsLoading(false)
    }
  }, [page, showToast])

  useEffect(() => {
    fetchRuns()
  }, [fetchRuns])

  const formatDate = (iso: string) =>
    new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }).format(new Date(iso))

  return (
    <AppLayout title="Agents" subtitle="AI Agent Investigation History">
      <div className="space-y-6">
        {ToastNode}
        
        {/* ── Header ────────────────────────────────────────────────────── */}
        <div>
          <h1 className="text-2xl font-bold text-slate-100 flex items-center gap-2">
            <span className="text-indigo-400">🤖</span> AI Agent History
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            {total} total investigations · Page {page} of {totalPages}
          </p>
        </div>

      {/* ── Table ─────────────────────────────────────────────────────── */}
      <div className="glass-card overflow-hidden">
        {isLoading ? (
          <div className="p-6 space-y-4">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-14 w-full" />
            ))}
          </div>
        ) : runs.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-24 gap-4">
            <div className="w-16 h-16 rounded-2xl bg-slate-800 flex items-center justify-center text-3xl">
              🤖
            </div>
            <div className="text-center">
              <p className="text-slate-300 font-medium">No AI investigations yet</p>
              <p className="text-slate-500 text-sm mt-1">
                Trigger the AI agent from any ticket detail page.
              </p>
            </div>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-slate-800/50 text-slate-400">
                <tr>
                  <th className="px-5 py-3.5 font-medium whitespace-nowrap border-b border-slate-700/50">Run ID</th>
                  <th className="px-5 py-3.5 font-medium whitespace-nowrap border-b border-slate-700/50">Ticket</th>
                  <th className="px-5 py-3.5 font-medium whitespace-nowrap border-b border-slate-700/50">Confidence</th>
                  <th className="px-5 py-3.5 font-medium whitespace-nowrap border-b border-slate-700/50">Risk</th>
                  <th className="px-5 py-3.5 font-medium whitespace-nowrap border-b border-slate-700/50">Policy Result</th>
                  <th className="px-5 py-3.5 font-medium whitespace-nowrap border-b border-slate-700/50">Approval Status</th>
                  <th className="px-5 py-3.5 font-medium whitespace-nowrap border-b border-slate-700/50">Execution Result</th>
                  <th className="px-5 py-3.5 font-medium whitespace-nowrap border-b border-slate-700/50">Evaluation</th>
                  <th className="px-5 py-3.5 font-medium whitespace-nowrap border-b border-slate-700/50">Time</th>
                  <th className="px-5 py-3.5 font-medium whitespace-nowrap border-b border-slate-700/50"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-700/50">
                {runs.map((r) => (
                  <tr key={r.id} className="hover:bg-slate-800/30 transition-colors group">
                    <td className="px-5 py-4">
                      <div className="font-mono text-xs text-indigo-400">
                        {r.id.split('-')[0]}
                      </div>
                      {r.model_used && (
                        <div className="text-[10px] text-slate-500 mt-0.5">{r.model_used}</div>
                      )}
                    </td>
                    <td className="px-5 py-4">
                      {r.ticket_id ? (
                        <Link to={`/tickets/${r.ticket_id}`} className="font-mono text-xs text-slate-300 hover:text-indigo-400 transition-colors">
                          {r.ticket_id.split('-')[0]}
                        </Link>
                      ) : (
                        <span className="text-slate-600">—</span>
                      )}
                    </td>
                    <td className="px-5 py-4 min-w-[120px]">
                      <ConfidenceBar value={r.confidence} />
                    </td>
                    <td className="px-5 py-4">
                      <RiskBadge level={r.risk_level} />
                    </td>
                    <td className="px-5 py-4">
                      <span className="text-[10px] text-slate-400 font-mono bg-slate-800 px-2 py-1 rounded">
                        {r.decision || 'N/A'}
                      </span>
                    </td>
                    <td className="px-5 py-4 text-xs">
                      {getApprovalBadge(r)}
                    </td>
                    <td className="px-5 py-4 text-xs">
                      {getExecutionBadge(r)}
                    </td>
                    <td className="px-5 py-4 text-xs text-slate-400">
                      <Link to="/evaluations" className="text-indigo-400 hover:underline">View</Link>
                    </td>
                    <td className="px-5 py-4 text-xs text-slate-500 whitespace-nowrap">
                      {formatDate(r.created_at)}
                    </td>
                    <td className="px-5 py-4 text-right">
                      {r.ticket_id && (
                        <Link
                          to={`/tickets/${r.ticket_id}`}
                          className="opacity-0 group-hover:opacity-100 px-3 py-1.5 rounded-lg bg-indigo-500/10 text-indigo-400 text-xs font-medium hover:bg-indigo-500/20 transition-all"
                        >
                          Details
                        </Link>
                      )}
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
