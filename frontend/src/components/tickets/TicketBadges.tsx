/**
 * TicketBadges — colored badge components for Status, Priority, Severity.
 * Used across the List and Detail pages.
 */

import type { TicketPriority, TicketSeverity, TicketStatus } from '@/types/ticket'

// ─── Status ──────────────────────────────────────────────────────────────────
const STATUS_CONFIG: Record<TicketStatus, { label: string; className: string }> = {
  open:             { label: 'Open',             className: 'bg-blue-500/15 text-blue-400 border-blue-500/30' },
  investigating:    { label: 'Investigating',    className: 'bg-yellow-500/15 text-yellow-400 border-yellow-500/30' },
  waiting_approval: { label: 'Waiting Approval', className: 'bg-orange-500/15 text-orange-400 border-orange-500/30' },
  in_progress:      { label: 'In Progress',      className: 'bg-indigo-500/15 text-indigo-400 border-indigo-500/30' },
  resolved:         { label: 'Resolved',         className: 'bg-green-500/15 text-green-400 border-green-500/30' },
  closed:           { label: 'Closed',           className: 'bg-slate-500/15 text-slate-400 border-slate-500/30' },
}

// ─── Priority ─────────────────────────────────────────────────────────────────
const PRIORITY_CONFIG: Record<TicketPriority, { label: string; className: string; dot: string }> = {
  low:      { label: 'Low',      dot: 'bg-slate-400',  className: 'bg-slate-500/10 text-slate-400 border-slate-500/20' },
  medium:   { label: 'Medium',   dot: 'bg-blue-400',   className: 'bg-blue-500/10 text-blue-400 border-blue-500/20' },
  high:     { label: 'High',     dot: 'bg-amber-400',  className: 'bg-amber-500/10 text-amber-400 border-amber-500/20' },
  critical: { label: 'Critical', dot: 'bg-red-400',    className: 'bg-red-500/10 text-red-400 border-red-500/20' },
}

// ─── Severity ─────────────────────────────────────────────────────────────────
const SEVERITY_CONFIG: Record<TicketSeverity, { label: string; className: string }> = {
  s1: { label: 'S1 — Critical', className: 'bg-red-500/15 text-red-400 border-red-500/30' },
  s2: { label: 'S2 — High',     className: 'bg-orange-500/15 text-orange-400 border-orange-500/30' },
  s3: { label: 'S3 — Medium',   className: 'bg-yellow-500/15 text-yellow-400 border-yellow-500/30' },
  s4: { label: 'S4 — Low',      className: 'bg-slate-500/15 text-slate-400 border-slate-500/30' },
}

function BaseBadge({ label, className }: { label: string; className: string }) {
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border ${className}`}>
      {label}
    </span>
  )
}

export function StatusBadge({ status }: { status: TicketStatus }) {
  const cfg = STATUS_CONFIG[status] ?? { label: status, className: 'bg-slate-500/15 text-slate-400 border-slate-500/30' }
  return <BaseBadge label={cfg.label} className={cfg.className} />
}

export function PriorityBadge({ priority }: { priority: TicketPriority }) {
  const cfg = PRIORITY_CONFIG[priority] ?? { label: priority, className: 'bg-slate-500/15 text-slate-400 border-slate-500/30', dot: 'bg-slate-400' }
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium border ${cfg.className}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${cfg.dot}`} />
      {cfg.label}
    </span>
  )
}

export function SeverityBadge({ severity }: { severity: TicketSeverity | null }) {
  if (!severity) return <span className="text-slate-600 text-xs">—</span>
  const cfg = SEVERITY_CONFIG[severity]
  return <BaseBadge label={cfg.label} className={cfg.className} />
}
