import { useState, useEffect, useRef, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ticketsApi } from '@/api/tickets'
import { agentsApi } from '@/api/agents'
import { getErrorMessage } from '@/api/client'
import type { Ticket, TicketComment } from '@/types/ticket'
import type { AgentRunResult } from '@/api/agents'
import { approvalsApi, type ApprovalRequestResponse } from '@/api/approvals'
import { apiClient } from '@/api/client'
import { ApprovalModal } from '@/components/approvals/ApprovalModal'
import { StatusBadge, PriorityBadge, SeverityBadge } from '@/components/tickets/TicketBadges'
import { useToast } from '@/components/ui/Toast'

// ─── Helpers ──────────────────────────────────────────────────────────────────

const RISK_CONFIG: Record<string, { label: string; color: string; bg: string }> = {
  low:     { label: 'Low Risk',     color: 'text-emerald-400', bg: 'bg-emerald-500/10 border-emerald-500/25' },
  medium:  { label: 'Medium Risk',  color: 'text-amber-400',   bg: 'bg-amber-500/10 border-amber-500/25'   },
  high:    { label: 'High Risk',    color: 'text-red-400',     bg: 'bg-red-500/10 border-red-500/25'       },
  blocked: { label: 'Blocked',      color: 'text-rose-300',    bg: 'bg-rose-500/10 border-rose-500/25'     },
}

const CONFIDENCE_COLOR = (v: number) =>
  v >= 0.75 ? '#34d399' : v >= 0.5 ? '#fbbf24' : '#f87171'

function ConfidenceRing({ value }: { value: number }) {
  const pct = Math.round(value * 100)
  const r = 26, circ = 2 * Math.PI * r
  const dash = circ * value
  const color = CONFIDENCE_COLOR(value)
  return (
    <div className="relative w-16 h-16 flex-shrink-0">
      <svg className="w-16 h-16 -rotate-90" viewBox="0 0 64 64">
        <circle cx="32" cy="32" r={r} fill="none" stroke="#1e293b" strokeWidth="5" />
        <circle
          cx="32" cy="32" r={r} fill="none" stroke={color} strokeWidth="5"
          strokeDasharray={`${dash} ${circ}`}
          strokeLinecap="round"
          style={{ transition: 'stroke-dasharray 0.8s ease' }}
        />
      </svg>
      <div className="absolute inset-0 flex items-center justify-center">
        <span className="text-xs font-bold" style={{ color }}>{pct}%</span>
      </div>
    </div>
  )
}

function RiskBadge({ level }: { level: string }) {
  const cfg = RISK_CONFIG[level] ?? RISK_CONFIG.high
  return (
    <span className={`px-2.5 py-1 rounded-full text-xs font-semibold border ${cfg.bg} ${cfg.color}`}>
      {cfg.label}
    </span>
  )
}

function SectionHeader({ icon, title }: { icon: string; title: string }) {
  return (
    <div className="flex items-center gap-2 mb-3">
      <span className="text-base">{icon}</span>
      <h4 className="text-xs font-semibold text-slate-300 uppercase tracking-wider">{title}</h4>
    </div>
  )
}

function EvidenceCard({
  title, score, page, section, content,
}: {
  title: string; score: number; page: number | null; section: string | null; content: string
}) {
  const [expanded, setExpanded] = useState(false)
  const pct = Math.round(score * 100)
  const scoreColor = score >= 0.7 ? 'text-emerald-400' : score >= 0.5 ? 'text-amber-400' : 'text-slate-400'
  return (
    <div className="rounded-xl border border-slate-700/60 bg-slate-800/40 overflow-hidden">
      <button
        onClick={() => setExpanded(e => !e)}
        className="w-full flex items-start gap-3 p-3.5 text-left hover:bg-slate-700/20 transition-colors"
      >
        {/* Score gauge */}
        <div className="flex-shrink-0 mt-0.5">
          <div className={`text-xs font-bold tabular-nums ${scoreColor}`}>{pct}%</div>
          <div className="text-[10px] text-slate-600">match</div>
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-xs font-semibold text-slate-200 truncate">{title}</p>
          <div className="flex items-center gap-2 mt-0.5">
            {page != null && (
              <span className="text-[10px] text-slate-500">p.{page}</span>
            )}
            {section && (
              <span className="text-[10px] text-slate-500 truncate">{section}</span>
            )}
          </div>
        </div>
        <svg
          className={`w-4 h-4 text-slate-500 flex-shrink-0 transition-transform ${expanded ? 'rotate-180' : ''}`}
          viewBox="0 0 20 20" fill="currentColor"
        >
          <path fillRule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" clipRule="evenodd" />
        </svg>
      </button>
      {expanded && (
        <div className="px-3.5 pb-3.5 border-t border-slate-700/40">
          <p className="text-xs text-slate-400 leading-relaxed mt-2.5 font-mono whitespace-pre-wrap line-clamp-6">
            &ldquo;{content.slice(0, 600)}{content.length > 600 ? '…' : ''}&rdquo;
          </p>
        </div>
      )}
    </div>
  )
}

// ─── Approval Section ─────────────────────────────────────────────────────────
function ApprovalSection({ approvalId }: { approvalId: string }) {
  const [approval, setApproval] = useState<ApprovalRequestResponse | null>(null)
  const [modalOpen, setModalOpen] = useState(false)

  const fetchApproval = useCallback(async () => {
    try {
      const { data } = await approvalsApi.getApproval(approvalId)
      setApproval(data)
    } catch (e) {
      console.error(e)
    }
  }, [approvalId])

  useEffect(() => {
    fetchApproval()
    // Poll if pending
    const interval = setInterval(() => {
      if (!approval || approval.status === 'pending') {
        fetchApproval()
      }
    }, 5000)
    return () => clearInterval(interval)
  }, [fetchApproval, approval?.status])

  if (!approval) return null

  const isPending = approval.status === 'pending'
  const isExecuted = approval.status === 'executed' || approval.status === 'approved'

  return (
    <div className="space-y-2 mt-4">
      <SectionHeader icon="🛡" title="Execution Approval" />
      <div className={`p-4 rounded-xl border ${isPending ? 'bg-amber-500/10 border-amber-500/30' : 'bg-slate-800/50 border-slate-700/40'}`}>
        <div className="flex flex-col gap-3">
          <div className="flex justify-between items-start">
            <div>
              <p className="text-xs text-slate-400 uppercase tracking-wide">Proposed Action</p>
              <div className="flex items-center gap-2 mt-1">
                <p className="text-sm font-bold text-slate-200 font-mono">{approval.proposed_action}</p>
                {isExecuted && (
                  <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase bg-indigo-500/20 text-indigo-400 border border-indigo-500/30 shadow-[0_0_10px_rgba(99,102,241,0.2)]">
                    [SIMULATED]
                  </span>
                )}
              </div>
            </div>
            
            <div className="text-right">
              <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase border ${
                approval.status === 'approved' ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30' :
                approval.status === 'rejected' ? 'bg-rose-500/20 text-rose-400 border-rose-500/30' :
                approval.status === 'executed' ? 'bg-indigo-500/20 text-indigo-400 border-indigo-500/30' :
                approval.status === 'failed' ? 'bg-red-500/20 text-red-400 border-red-500/30' :
                'bg-amber-500/20 text-amber-400 border-amber-500/30'
              }`}>
                {approval.status}
              </span>
            </div>
          </div>
          
          <div className="flex items-center gap-3 mt-2">
            <button
              onClick={() => setModalOpen(true)}
              className="text-xs font-semibold text-indigo-400 hover:text-indigo-300 bg-indigo-500/10 hover:bg-indigo-500/20 px-3 py-1.5 rounded-lg transition-colors border border-indigo-500/20"
            >
              {isPending ? 'Review Approval Required' : 'View Details'}
            </button>
          </div>
        </div>
      </div>
      {modalOpen && (
        <ApprovalModal 
          approval={approval} 
          onClose={() => setModalOpen(false)} 
          onActionComplete={() => {
            setModalOpen(false)
            fetchApproval()
          }} 
        />
      )}
    </div>
  )
}

// ─── Main AI Panel ────────────────────────────────────────────────────────────
function AiInvestigationPanel({
  ticket,
  onRunComplete,
}: {
  ticket: Ticket
  onRunComplete: (result: AgentRunResult) => void
}) {
  const [isRunning, setIsRunning] = useState(false)
  const [result, setResult] = useState<AgentRunResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [evaluations, setEvaluations] = useState<any[]>([])
  const { showToast } = useToast()

  const handleRun = useCallback(async () => {
    setIsRunning(true)
    setError(null)
    setEvaluations([])
    try {
      const { data } = await agentsApi.runOnTicket(ticket.id)
      setResult(data)
      onRunComplete(data)
      showToast('AI investigation complete', 'success')
      
      // Fetch evaluations for this new run
      try {
        const evalData = await apiClient.get(`/evaluations/${data.ai_run_id}`)
        setEvaluations(evalData.data?.evaluation_results || [])
      } catch (e) {
        // silently fail evaluation fetch
      }
    } catch (err) {
      const msg = getErrorMessage(err)
      setError(msg)
      showToast(msg, 'error')
    } finally {
      setIsRunning(false)
    }
  }, [ticket.id, onRunComplete, showToast])

  // (Feature intentionally omitted: pre-loading evals for past runs since ticket schema doesn't expose ai_run_id)

  // Evidence from agent_trace (retrieved_documents stored in trace)
  const evidenceDocs: Array<{
    document_title: string; similarity_score: number; page: number | null;
    section: string | null; content: string
  }> = (() => {
    if (!result) return []
    // Pull from agent_trace.retrieved_documents if present
    const trace = result as unknown as { agent_trace?: { retrieved_documents?: unknown[] } }
    return (trace.agent_trace?.retrieved_documents as typeof evidenceDocs) ?? []
  })()

  return (
    <div className="glass-card p-6 space-y-5 relative overflow-hidden">
      {/* Decorative glow */}
      <div className="absolute top-0 right-0 w-48 h-48 bg-indigo-500/5 rounded-full -translate-y-1/2 translate-x-1/2 blur-3xl pointer-events-none" />

      {/* Header */}
      <div className="flex items-center gap-2.5">
        <div className="w-8 h-8 rounded-lg bg-indigo-500/10 flex items-center justify-center text-indigo-400 text-sm">
          🤖
        </div>
        <div className="flex-1 min-w-0">
          <h3 className="text-sm font-semibold text-slate-200">AI Investigation</h3>
          <p className="text-xs text-slate-500">Powered by OpsPilot Agent</p>
        </div>
        {result && (
          <span className="px-2 py-0.5 text-[10px] font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 rounded-full">
            Complete
          </span>
        )}
      </div>

      {/* Run button — idle state */}
      {!result && !isRunning && (
        <div className="rounded-xl border border-dashed border-slate-700 p-5 text-center space-y-4">
          <div className="w-12 h-12 rounded-full bg-indigo-500/10 flex items-center justify-center text-2xl mx-auto">
            🔍
          </div>
          <div>
            <p className="text-sm font-medium text-slate-300">Ready to Investigate</p>
            <p className="text-xs text-slate-500 mt-1 leading-relaxed max-w-[200px] mx-auto">
              Run the AI agent to classify, diagnose, and recommend a fix for this ticket.
            </p>
          </div>
          {error && (
            <p className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">
              {error}
            </p>
          )}
          <button
            id="run-ai-agent-btn"
            onClick={handleRun}
            className="w-full py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-semibold transition-all active:scale-[0.98] flex items-center justify-center gap-2"
          >
            <svg className="w-4 h-4" viewBox="0 0 20 20" fill="currentColor">
              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM9.555 7.168A1 1 0 008 8v4a1 1 0 001.555.832l3-2a1 1 0 000-1.664l-3-2z" clipRule="evenodd" />
            </svg>
            Run AI Investigation
          </button>
        </div>
      )}

      {/* Loading state */}
      {isRunning && (
        <div className="rounded-xl border border-indigo-500/20 bg-indigo-500/5 p-6 text-center space-y-4">
          <div className="flex items-center justify-center gap-3">
            <svg className="w-6 h-6 animate-spin text-indigo-400" viewBox="0 0 24 24" fill="none">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
            </svg>
            <span className="text-sm font-medium text-indigo-300">Analysing ticket…</span>
          </div>
          <div className="space-y-1.5">
            {['Classifying ticket', 'Retrieving knowledge', 'Generating diagnosis', 'Building recommendation'].map((step, i) => (
              <div key={step} className="flex items-center gap-2 text-xs text-slate-500">
                <div className="w-1.5 h-1.5 rounded-full bg-indigo-500/40 animate-pulse" style={{ animationDelay: `${i * 200}ms` }} />
                {step}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Results */}
      {result && !isRunning && (
        <div className="space-y-4">

          {/* Confidence + Risk summary bar */}
          <div className="flex items-center gap-4 p-4 rounded-xl bg-slate-800/50 border border-slate-700/50">
            <ConfidenceRing value={result.confidence ?? 0} />
            <div className="flex-1 space-y-1.5">
              <div className="flex items-center gap-2 flex-wrap">
                {result.risk_level && <RiskBadge level={result.risk_level} />}
                {result.requires_approval && (
                  <span className="px-2.5 py-1 rounded-full text-xs font-semibold border bg-amber-500/10 border-amber-500/25 text-amber-400">
                    ⚠ Approval Required
                  </span>
                )}
                {result.insufficient_evidence && (
                  <span className="px-2.5 py-1 rounded-full text-xs font-semibold border bg-slate-500/10 border-slate-500/25 text-slate-400">
                    Low Evidence
                  </span>
                )}
              </div>
              {result.latency_ms != null && (
                <p className="text-[10px] text-slate-600">
                  Completed in {result.latency_ms}ms · {result.model_used ?? 'mock'} LLM
                </p>
              )}
            </div>
          </div>

          {/* Evaluations Summary */}
          {evaluations.length > 0 && (
            <div className="p-3 rounded-xl bg-slate-800/30 border border-slate-700/30 flex items-center justify-between">
              <div className="flex items-center gap-4">
                <span className="text-xs font-semibold text-slate-400 uppercase">Evaluations:</span>
                <div className="flex gap-3">
                  {evaluations.slice(0, 3).map((e, idx) => (
                    <span key={idx} className="text-xs">
                      <span className="text-slate-300">{e.metric_name}: </span>
                      <span className={`font-semibold ${
                        e.status === 'GOOD' || e.status === 'PASS' || e.status === 'EXPECTED' ? 'text-emerald-400' :
                        e.status === 'WARNING' ? 'text-amber-400' : 'text-rose-400'
                      }`}>
                        {e.status}
                      </span>
                    </span>
                  ))}
                </div>
              </div>
              <a href="/evaluations" className="text-xs text-indigo-400 hover:text-indigo-300 transition-colors">
                View All →
              </a>
            </div>
          )}

          {/* Approval Section */}
          {result.approval_id && (
            <ApprovalSection 
              approvalId={result.approval_id}
            />
          )}

          {/* Classification */}
          {result.classification && (
            <div className="space-y-2">
              <SectionHeader icon="🏷" title="Classification" />
              <div className="grid grid-cols-2 gap-2">
                {[
                  { label: 'Category', value: result.classification.category },
                  { label: 'Priority',  value: result.classification.priority },
                  { label: 'Severity',  value: result.classification.severity?.toUpperCase() },
                ].map(({ label, value }) => (
                  <div key={label} className="p-2.5 rounded-lg bg-slate-800/60 border border-slate-700/40">
                    <p className="text-[10px] text-slate-500 uppercase tracking-wide">{label}</p>
                    <p className="text-xs font-semibold text-slate-200 mt-0.5 capitalize">{value}</p>
                  </div>
                ))}
                <div className="p-2.5 rounded-lg bg-slate-800/60 border border-slate-700/40">
                  <p className="text-[10px] text-slate-500 uppercase tracking-wide">Confidence</p>
                  <p className="text-xs font-semibold text-slate-200 mt-0.5">
                    {Math.round((result.classification.confidence ?? 0) * 100)}%
                  </p>
                </div>
              </div>
              {result.classification.reasoning && (
                <p className="text-xs text-slate-500 leading-relaxed italic px-1">
                  {result.classification.reasoning}
                </p>
              )}
            </div>
          )}

          {/* Diagnosis */}
          {result.diagnosis && (
            <div className="space-y-2">
              <SectionHeader icon="🔬" title="Diagnosis" />
              <div className="p-3.5 rounded-xl bg-slate-800/50 border border-slate-700/40 space-y-3">
                <div>
                  <p className="text-[10px] text-slate-500 uppercase tracking-wide mb-1">Root Cause</p>
                  <p className="text-xs text-slate-200 leading-relaxed">{result.diagnosis.root_cause}</p>
                </div>
                {result.diagnosis.affected_components.length > 0 && (
                  <div>
                    <p className="text-[10px] text-slate-500 uppercase tracking-wide mb-1">Affected Components</p>
                    <div className="flex flex-wrap gap-1.5">
                      {result.diagnosis.affected_components.map((c) => (
                        <span key={c} className="px-2 py-0.5 rounded-md text-[10px] font-mono bg-slate-700/60 text-slate-300 border border-slate-700/60">
                          {c}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
                <div>
                  <p className="text-[10px] text-slate-500 uppercase tracking-wide mb-1">Impact</p>
                  <p className="text-xs text-slate-400 leading-relaxed">{result.diagnosis.impact_summary}</p>
                </div>
              </div>
              {/* Evidence bullets */}
              {result.diagnosis.evidence.length > 0 && (
                <div className="space-y-1.5 pl-1">
                  {result.diagnosis.evidence.map((ev, i) => (
                    <div key={i} className="flex gap-2 text-xs text-slate-500">
                      <span className="text-indigo-400 flex-shrink-0">▸</span>
                      <span className="leading-relaxed">{ev}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Recommendation */}
          {result.recommendation && (
            <div className="space-y-2">
              <SectionHeader icon="🛠" title="Recommendation" />
              <div className="p-3.5 rounded-xl bg-slate-800/50 border border-slate-700/40 space-y-3">
                <p className="text-xs font-semibold text-slate-200">{result.recommendation.action}</p>
                <div className="space-y-1.5">
                  {result.recommendation.steps.map((step, i) => (
                    <div key={i} className="flex gap-2.5 text-xs text-slate-400">
                      <span className="flex-shrink-0 w-5 h-5 rounded-full bg-indigo-500/15 text-indigo-400 flex items-center justify-center text-[10px] font-bold">
                        {i + 1}
                      </span>
                      <span className="leading-relaxed pt-0.5">{step}</span>
                    </div>
                  ))}
                </div>
                <div className="flex items-center justify-between pt-1 border-t border-slate-700/40 text-xs text-slate-500">
                  <span>⏱ {result.recommendation.estimated_resolution_time}</span>
                </div>
              </div>
            </div>
          )}

          {/* Retrieved evidence cards */}
          {evidenceDocs.length > 0 && (
            <div className="space-y-2">
              <SectionHeader icon="📚" title={`Knowledge Sources (${evidenceDocs.length})`} />
              <div className="space-y-2">
                {evidenceDocs.map((doc, i) => (
                  <EvidenceCard
                    key={i}
                    title={doc.document_title}
                    score={doc.similarity_score}
                    page={doc.page}
                    section={doc.section}
                    content={doc.content}
                  />
                ))}
              </div>
            </div>
          )}

          {/* Errors */}
          {result.errors.length > 0 && (
            <div className="p-3 rounded-lg bg-red-500/5 border border-red-500/20 space-y-1">
              <p className="text-[10px] font-semibold text-red-400 uppercase tracking-wide">Agent Warnings</p>
              {result.errors.map((e, i) => (
                <p key={i} className="text-xs text-red-400/80">{e}</p>
              ))}
            </div>
          )}

          {/* Re-run */}
          <button
            onClick={() => { setResult(null); setError(null) }}
            className="w-full py-2 rounded-lg border border-slate-700 hover:border-indigo-500/50 text-xs text-slate-500 hover:text-indigo-400 transition-all"
          >
            ↺ Re-run Investigation
          </button>
        </div>
      )}
    </div>
  )
}

// ─── Comment Thread ────────────────────────────────────────────────────────────
function CommentThread({
  ticketId,
  initialComments,
  onError,
}: {
  ticketId: string
  initialComments: TicketComment[]
  onError: (msg: string) => void
}) {
  const [comments, setComments] = useState<TicketComment[]>(initialComments)
  const [body, setBody] = useState('')
  const [isSending, setIsSending] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  const handleSend = async () => {
    if (!body.trim()) return
    setIsSending(true)
    try {
      const { data: comment } = await ticketsApi.addComment(ticketId, { body: body.trim() })
      setComments((prev) => [...prev, comment])
      setBody('')
      setTimeout(() => bottomRef.current?.scrollIntoView({ behavior: 'smooth' }), 50)
    } catch (err) {
      onError(getErrorMessage(err))
    } finally {
      setIsSending(false)
    }
  }

  const formatTime = (iso: string) =>
    new Intl.DateTimeFormat('en-US', {
      month: 'short', day: 'numeric',
      hour: '2-digit', minute: '2-digit',
    }).format(new Date(iso))

  return (
    <div className="glass-card p-6 space-y-5">
      <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2">
        <span className="w-1.5 h-1.5 rounded-full bg-indigo-400 inline-block" />
        Comments ({comments.length})
      </h3>

      {/* Thread */}
      <div className="space-y-4 max-h-96 overflow-y-auto pr-1">
        {comments.length === 0 ? (
          <p className="text-sm text-slate-500 text-center py-6">
            No comments yet. Be the first to add context.
          </p>
        ) : (
          comments.map((c) => (
            <div
              key={c.id}
              className={`flex gap-3 ${c.is_ai_generated ? 'items-start' : 'items-start'}`}
            >
              {/* Avatar */}
              <div
                className={`w-7 h-7 rounded-full flex-shrink-0 flex items-center justify-center text-xs font-bold ${
                  c.is_ai_generated
                    ? 'bg-indigo-500/20 text-indigo-400 border border-indigo-500/30'
                    : 'bg-slate-700 text-slate-300'
                }`}
              >
                {c.is_ai_generated ? '🤖' : 'U'}
              </div>

              {/* Bubble */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-xs font-medium text-slate-300">
                    {c.is_ai_generated ? 'OpsPilot AI' : 'User'}
                  </span>
                  {c.is_ai_generated && (
                    <span className="px-1.5 py-0.5 text-[10px] font-medium bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 rounded">
                      AI
                    </span>
                  )}
                  <span className="text-xs text-slate-600">{formatTime(c.created_at)}</span>
                </div>
                <div
                  className={`p-3 rounded-xl text-sm text-slate-300 leading-relaxed ${
                    c.is_ai_generated
                      ? 'bg-indigo-500/5 border border-indigo-500/15'
                      : 'bg-slate-700/40'
                  }`}
                >
                  {c.body}
                </div>
              </div>
            </div>
          ))
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="border-t border-slate-700/50 pt-4 space-y-3">
        <textarea
          value={body}
          onChange={(e) => setBody(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) handleSend()
          }}
          placeholder="Add a comment… (Ctrl+Enter to send)"
          rows={3}
          className="w-full bg-slate-800/60 border border-slate-700 rounded-xl px-4 py-3 text-slate-100 placeholder-slate-500 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/50 transition-all resize-none"
        />
        <div className="flex justify-end">
          <button
            onClick={handleSend}
            disabled={!body.trim() || isSending}
            className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 disabled:cursor-not-allowed text-white text-sm font-medium rounded-lg transition-all flex items-center gap-2"
          >
            {isSending ? (
              <svg className="w-4 h-4 animate-spin" viewBox="0 0 24 24" fill="none">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
              </svg>
            ) : (
              <svg className="w-4 h-4" viewBox="0 0 20 20" fill="currentColor">
                <path d="M10.894 2.553a1 1 0 00-1.788 0l-7 14a1 1 0 001.169 1.409l5-1.429A1 1 0 009 15.571V11a1 1 0 112 0v4.571a1 1 0 00.725.962l5 1.428a1 1 0 001.17-1.408l-7-14z" />
              </svg>
            )}
            {isSending ? 'Sending…' : 'Send'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ─── Metadata Row ─────────────────────────────────────────────────────────────
function MetaRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-start justify-between py-2.5 border-b border-slate-700/30 last:border-0">
      <span className="text-xs font-medium text-slate-500 uppercase tracking-wide w-28 flex-shrink-0 pt-0.5">
        {label}
      </span>
      <div className="text-sm text-slate-300 flex-1 text-right">{children}</div>
    </div>
  )
}

// ─── Main Page ─────────────────────────────────────────────────────────────────
export default function TicketDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { showToast, ToastNode } = useToast()

  const [ticket, setTicket] = useState<Ticket | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    if (!id) return
    setIsLoading(true)
    ticketsApi
      .get(id)
      .then(({ data }) => setTicket(data))
      .catch((err) => {
        const msg = getErrorMessage(err)
        if (msg.includes('404') || msg.toLowerCase().includes('not found')) {
          showToast('Ticket not found.', 'error')
          setTimeout(() => navigate('/tickets'), 2000)
        } else if (msg.includes('403') || msg.toLowerCase().includes('forbidden')) {
          showToast('You don\'t have permission to view this ticket.', 'error')
          setTimeout(() => navigate('/tickets'), 2000)
        } else {
          showToast(msg)
        }
      })
      .finally(() => setIsLoading(false))
  }, [id, navigate, showToast])

  const formatDate = (iso: string) =>
    new Intl.DateTimeFormat('en-US', {
      weekday: 'short', month: 'short', day: 'numeric',
      hour: '2-digit', minute: '2-digit',
    }).format(new Date(iso))

  if (isLoading) {
    return (
      <div className="min-h-screen bg-[#080C18] flex items-center justify-center">
        {ToastNode}
        <div className="flex flex-col items-center gap-3">
          <svg className="w-8 h-8 animate-spin text-indigo-500" viewBox="0 0 24 24" fill="none">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
          </svg>
          <span className="text-sm text-slate-400">Loading ticket…</span>
        </div>
      </div>
    )
  }

  if (!ticket) {
    return (
      <div className="min-h-screen bg-[#080C18] flex items-center justify-center">
        {ToastNode}
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-[#080C18] p-6 space-y-5">
      {ToastNode}

      {/* ── Breadcrumb / Header ──────────────────────────────────────── */}
      <div className="flex items-center gap-3">
        <button
          onClick={() => navigate('/tickets')}
          className="flex items-center gap-1.5 text-sm text-slate-400 hover:text-slate-100 transition-colors"
        >
          <svg className="w-4 h-4" viewBox="0 0 20 20" fill="currentColor">
            <path fillRule="evenodd" d="M12.707 5.293a1 1 0 010 1.414L9.414 10l3.293 3.293a1 1 0 01-1.414 1.414l-4-4a1 1 0 010-1.414l4-4a1 1 0 011.414 0z" clipRule="evenodd" />
          </svg>
          Tickets
        </button>
        <span className="text-slate-700">/</span>
        <span className="text-sm text-slate-300 truncate max-w-xs">{ticket.title}</span>
      </div>

      {/* ── Title + Badges ───────────────────────────────────────────── */}
      <div className="glass-card p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="flex-1 min-w-0">
            <h1 className="text-xl font-bold text-slate-100 leading-snug">{ticket.title}</h1>
            <div className="flex flex-wrap items-center gap-2 mt-3">
              <StatusBadge status={ticket.status} />
              <PriorityBadge priority={ticket.priority} />
              <SeverityBadge severity={ticket.severity} />
              {ticket.category && (
                <span className="px-2.5 py-0.5 rounded-full text-xs bg-slate-700/50 text-slate-400 border border-slate-700">
                  {ticket.category}
                </span>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* ── Two-column layout ────────────────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        {/* LEFT — description + comments */}
        <div className="lg:col-span-2 space-y-5">
          {/* Description */}
          <div className="glass-card p-6 space-y-3">
            <h2 className="text-sm font-semibold text-slate-200 flex items-center gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-slate-500 inline-block" />
              Description
            </h2>
            <p className="text-sm text-slate-300 leading-relaxed whitespace-pre-wrap">
              {ticket.description}
            </p>
          </div>

          {/* Comment Thread */}
          <CommentThread
            ticketId={ticket.id}
            initialComments={ticket.comments}
            onError={(msg) => showToast(msg)}
          />
        </div>

        {/* RIGHT — metadata + AI panel */}
        <div className="space-y-5">
          {/* Metadata */}
          <div className="glass-card p-6">
            <h2 className="text-sm font-semibold text-slate-200 mb-3">Details</h2>
            <div>
              <MetaRow label="Status"><StatusBadge status={ticket.status} /></MetaRow>
              <MetaRow label="Priority"><PriorityBadge priority={ticket.priority} /></MetaRow>
              <MetaRow label="Severity"><SeverityBadge severity={ticket.severity} /></MetaRow>
              <MetaRow label="Service">
                {ticket.affected_service ?? <span className="text-slate-600">—</span>}
              </MetaRow>
              <MetaRow label="Created">
                <span className="text-slate-400">{formatDate(ticket.created_at)}</span>
              </MetaRow>
              <MetaRow label="Updated">
                <span className="text-slate-400">{formatDate(ticket.updated_at)}</span>
              </MetaRow>
            </div>
          </div>

          {/* AI Panel */}
          <AiInvestigationPanel
            ticket={ticket}
            onRunComplete={(runResult) => {
              // Reflect the updated confidence in the ticket header immediately
              setTicket((prev) =>
                prev
                  ? { ...prev, ai_confidence: runResult.confidence ?? prev.ai_confidence }
                  : prev
              )
            }}
          />
        </div>
      </div>
    </div>
  )
}
