import { useState, useEffect, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { AppLayout } from '@/components/layout/AppLayout'
import { approvalsApi, type ApprovalRequestResponse } from '@/api/approvals'
import { useToast } from '@/components/ui/Toast'
import { ApprovalModal } from '@/components/approvals/ApprovalModal'

import { Skeleton } from '@/components/ui/Skeleton'

function StatusBadge({ status }: { status: string }) {
  const configs: Record<string, { bg: string; text: string }> = {
    pending: { bg: 'bg-amber-500/10 border-amber-500/30', text: 'text-amber-400' },
    approved: { bg: 'bg-emerald-500/10 border-emerald-500/30', text: 'text-emerald-400' },
    rejected: { bg: 'bg-rose-500/10 border-rose-500/30', text: 'text-rose-400' },
    executed: { bg: 'bg-indigo-500/10 border-indigo-500/30', text: 'text-indigo-400' },
    failed: { bg: 'bg-red-500/10 border-red-500/30', text: 'text-red-400' },
  }
  const conf = configs[status] || configs.pending
  return (
    <span className={`px-2.5 py-1 rounded-full text-[10px] font-bold uppercase border ${conf.bg} ${conf.text}`}>
      {status}
    </span>
  )
}

function RiskBadge({ risk }: { risk: string }) {
  const configs: Record<string, { bg: string; text: string }> = {
    low: { bg: 'bg-emerald-500/10 border-emerald-500/25', text: 'text-emerald-400' },
    medium: { bg: 'bg-amber-500/10 border-amber-500/25', text: 'text-amber-400' },
    high: { bg: 'bg-red-500/10 border-red-500/25', text: 'text-red-400' },
    blocked: { bg: 'bg-rose-500/10 border-rose-500/25', text: 'text-rose-300' },
  }
  const conf = configs[risk.toLowerCase()] || configs.high
  return (
    <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase border ${conf.bg} ${conf.text}`}>
      {risk}
    </span>
  )
}

export default function ApprovalsPage() {
  const [approvals, setApprovals] = useState<ApprovalRequestResponse[]>([])
  const [loading, setLoading] = useState(true)
  const [statusFilter, setStatusFilter] = useState<string>('pending')
  const [selectedApproval, setSelectedApproval] = useState<ApprovalRequestResponse | null>(null)
  const { showToast } = useToast()

  const fetchApprovals = useCallback(async () => {
    setLoading(true)
    try {
      const { data } = await approvalsApi.listApprovals(statusFilter === 'all' ? undefined : statusFilter)
      setApprovals(data)
    } catch (e) {
      showToast('Failed to load approvals', 'error')
    } finally {
      setLoading(false)
    }
  }, [statusFilter, showToast])

  useEffect(() => {
    fetchApprovals()
    // Poll every 10s to keep queue fresh
    const interval = setInterval(fetchApprovals, 10000)
    return () => clearInterval(interval)
  }, [fetchApprovals])

  return (
    <AppLayout title="Approvals Queue">
      <div className="max-w-6xl mx-auto space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-slate-100">Approvals</h1>
            <p className="text-sm text-slate-400 mt-1">Review and action AI-proposed tool executions.</p>
          </div>
          <div className="flex gap-2">
            {['pending', 'approved', 'executed', 'rejected', 'failed', 'all'].map((s) => (
              <button
                key={s}
                onClick={() => setStatusFilter(s)}
                className={`px-3 py-1.5 rounded-lg text-xs font-semibold capitalize transition-colors ${
                  statusFilter === s 
                    ? 'bg-indigo-600 text-white' 
                    : 'bg-slate-800 text-slate-400 hover:bg-slate-700'
                }`}
              >
                {s}
              </button>
            ))}
          </div>
        </div>

        <div className="glass-card overflow-hidden">
          {loading ? (
            <div className="p-6 space-y-4">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-14 w-full" />
              ))}
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm text-slate-300">
                <thead className="bg-slate-900/50 text-xs uppercase text-slate-500 border-b border-slate-700">
                  <tr>
                    <th className="px-4 py-3 font-semibold">Action</th>
                    <th className="px-4 py-3 font-semibold">Ticket</th>
                    <th className="px-4 py-3 font-semibold">Risk</th>
                    <th className="px-4 py-3 font-semibold">Confidence</th>
                    <th className="px-4 py-3 font-semibold">Status</th>
                    <th className="px-4 py-3 font-semibold">Requested At</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-700/50">
                  {approvals.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="px-4 py-8 text-center text-slate-500">
                        No approvals found matching the current filter.
                      </td>
                    </tr>
                  ) : (
                    approvals.map((ap) => (
                      <tr 
                        key={ap.id} 
                        onClick={() => setSelectedApproval(ap)}
                        className="hover:bg-slate-800/40 transition-colors cursor-pointer"
                      >
                        <td className="px-4 py-3">
                          <div className="font-mono text-xs text-slate-200">{ap.proposed_action}</div>
                          <div className="text-[10px] text-slate-500 truncate max-w-[250px]" title={ap.reason}>
                            {ap.reason}
                          </div>
                        </td>
                        <td className="px-4 py-3">
                          <Link 
                            to={`/tickets/${ap.ticket_id}`} 
                            onClick={(e) => e.stopPropagation()}
                            className="text-indigo-400 hover:text-indigo-300 text-xs font-mono"
                          >
                            {ap.ticket_id.split('-')[0]}...
                          </Link>
                        </td>
                        <td className="px-4 py-3">
                          <RiskBadge risk={ap.risk_level} />
                        </td>
                        <td className="px-4 py-3">
                          {ap.confidence != null ? `${Math.round(ap.confidence * 100)}%` : '—'}
                        </td>
                        <td className="px-4 py-3">
                          <StatusBadge status={ap.status} />
                        </td>
                        <td className="px-4 py-3 text-xs text-slate-500">
                          {new Date(ap.created_at).toLocaleString()}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      {selectedApproval && (
        <ApprovalModal 
          approval={selectedApproval} 
          onClose={() => setSelectedApproval(null)} 
          onActionComplete={() => {
            setSelectedApproval(null)
            fetchApprovals()
          }} 
        />
      )}
    </AppLayout>
  )
}
