import { useState } from 'react'
import { approvalsApi, type ApprovalRequestResponse } from '@/api/approvals'
import { useToast } from '@/components/ui/Toast'
import { getErrorMessage } from '@/api/client'

export function ApprovalModal({
  approval,
  onClose,
  onActionComplete,
}: {
  approval: ApprovalRequestResponse
  onClose: () => void
  onActionComplete: () => void
}) {
  const [rejectNote, setRejectNote] = useState('')
  const [actioning, setActioning] = useState(false)
  const { showToast } = useToast()

  const handleAction = async (action: 'approve' | 'reject') => {
    if (action === 'reject' && !rejectNote.trim()) {
      showToast('A note is required for rejection.', 'error')
      return
    }

    setActioning(true)
    try {
      if (action === 'approve') {
        const { data } = await approvalsApi.approve(approval.id, 'Approved from UI modal')
        if (data.success) {
          showToast('Tool executed successfully', 'success')
        } else {
          showToast(`Execution failed: ${data.error}`, 'error')
        }
      } else {
        await approvalsApi.reject(approval.id, rejectNote)
        showToast('Action rejected', 'success')
      }
      onActionComplete()
    } catch (e) {
      showToast(getErrorMessage(e), 'error')
    } finally {
      setActioning(false)
    }
  }

  const isPending = approval.status === 'pending'

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm">
      <div 
        className="glass-card w-full max-w-2xl max-h-[90vh] overflow-y-auto rounded-2xl border border-slate-700/50 shadow-2xl animate-in fade-in zoom-in-95 duration-200"
        onClick={e => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="approval-modal-title"
      >
        <div className="sticky top-0 bg-slate-900/80 backdrop-blur-md border-b border-slate-700/50 p-4 flex items-center justify-between z-10">
          <h2 id="approval-modal-title" className="text-lg font-semibold text-slate-100 flex items-center gap-2">
            🛡 Execution Approval
          </h2>
          <button 
            onClick={onClose}
            className="p-2 rounded-full hover:bg-slate-800 text-slate-400 transition-colors"
            aria-label="Close modal"
          >
            ✕
          </button>
        </div>

        <div className="p-6 space-y-6">
          <div className="space-y-4">
            <div>
              <p className="text-xs font-bold text-slate-500 uppercase tracking-wider">Policy Decision (The 'Why?')</p>
              <div className="mt-2 p-3 rounded-lg bg-slate-800/50 border border-slate-700/50">
                <p className="text-sm text-slate-300 leading-relaxed">{approval.reason}</p>
              </div>
            </div>

            <div>
              <p className="text-xs font-bold text-slate-500 uppercase tracking-wider">Proposed Action</p>
              <div className="mt-2 p-3 rounded-lg bg-slate-800/50 border border-slate-700/50">
                <p className="text-sm font-mono font-bold text-indigo-400">{approval.proposed_action}</p>
              </div>
            </div>

            <div>
              <p className="text-xs font-bold text-slate-500 uppercase tracking-wider">Arguments</p>
              <div className="mt-2 p-3 rounded-lg bg-slate-900/80 border border-slate-700/50 overflow-x-auto">
                <pre className="text-xs text-slate-300 font-mono">
                  {JSON.stringify(approval.action_args, null, 2)}
                </pre>
              </div>
            </div>
            
            {approval.evidence && approval.evidence.length > 0 && (
              <div>
                <p className="text-xs font-bold text-slate-500 uppercase tracking-wider">Evidence</p>
                <div className="mt-2 space-y-1.5 pl-1">
                  {approval.evidence.map((ev, i) => (
                    <div key={i} className="flex gap-2 text-sm text-slate-400">
                      <span className="text-indigo-400 flex-shrink-0">▸</span>
                      <span className="leading-relaxed">{ev}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>

        {isPending ? (
          <div className="sticky bottom-0 bg-slate-900/80 backdrop-blur-md border-t border-slate-700/50 p-6 space-y-4">
            <div>
              <label htmlFor="reject-note" className="text-xs font-medium text-slate-400 block mb-1">
                Rejection Note (required for rejection)
              </label>
              <input
                id="reject-note"
                type="text"
                value={rejectNote}
                onChange={e => setRejectNote(e.target.value)}
                placeholder="Why is this being rejected?"
                className="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-lg text-sm text-slate-200 focus:outline-none focus:border-indigo-500"
              />
            </div>
            <div className="flex gap-3">
              <button
                onClick={() => handleAction('approve')}
                disabled={actioning}
                className="flex-1 py-2.5 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white text-sm font-bold rounded-xl transition-all active:scale-[0.98]"
              >
                Approve & Execute
              </button>
              <button
                onClick={() => handleAction('reject')}
                disabled={actioning || !rejectNote.trim()}
                className="flex-1 py-2.5 bg-slate-700 hover:bg-slate-600 disabled:opacity-50 text-white text-sm font-bold rounded-xl transition-all active:scale-[0.98]"
              >
                Reject
              </button>
            </div>
          </div>
        ) : (
          <div className="sticky bottom-0 bg-slate-900/80 backdrop-blur-md border-t border-slate-700/50 p-6">
            <p className="text-sm text-slate-400 text-center">
              This approval has already been actioned ({approval.status}).
            </p>
            {approval.review_note && (
              <p className="text-xs text-slate-500 text-center mt-1 italic">
                Note: {approval.review_note}
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
