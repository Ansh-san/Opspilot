import { useEffect, useState, useMemo } from "react"
import { AppLayout } from "@/components/layout/AppLayout"
import { evaluationsApi } from "@/api/evaluations"
import type { EvaluationRun, EvaluationResult } from "@/api/evaluations"
import { Badge } from "@/components/ui/Badge"
import { getErrorMessage } from "@/api/client"
import { useToast } from "@/components/ui/Toast"
import {
  FileCheck2, ChevronDown, ChevronRight,
  CheckCircle2, AlertTriangle, AlertCircle, Info,
  BarChart3, BookOpen, Target, Zap, RefreshCw,
} from "lucide-react"
import { Skeleton } from "@/components/ui/Skeleton"

function formatVal(val: number | null | undefined): string {
  if (val === null || val === undefined || Number.isNaN(val as number)) return "N/A"
  const n = val as number
  return n % 1 !== 0 ? n.toFixed(2) : n.toString()
}

function timeAgo(dateString: string) {
  const seconds = Math.floor((Date.now() - new Date(dateString).getTime()) / 1000)
  if (seconds < 60) return `${seconds}s ago`
  const mins = Math.floor(seconds / 60)
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  return `${Math.floor(hrs / 24)}d ago`
}

function metricVariant(status: string): "success" | "warning" | "danger" | "secondary" {
  switch (status.toUpperCase()) {
    case "GOOD": case "EXPECTED": case "PASS": return "success"
    case "WARNING": return "warning"
    case "CRITICAL": case "FAIL": return "danger"
    default: return "secondary"
  }
}

function StatusIcon({ status }: { status: string }) {
  switch (status.toUpperCase()) {
    case "GOOD": case "EXPECTED": case "PASS":
      return <CheckCircle2 className="w-4 h-4 text-emerald-500" />
    case "WARNING":
      return <AlertTriangle className="w-4 h-4 text-amber-500" />
    case "CRITICAL": case "FAIL":
      return <AlertCircle className="w-4 h-4 text-rose-500" />
    default:
      return <Info className="w-4 h-4 text-slate-500" />
  }
}

function KpiCard({ title, value, subtitle, icon: Icon, color, bgColor }: {
  title: string; value: string; subtitle: string
  icon: React.ElementType; color: string; bgColor: string
}) {
  return (
    <div className="glass-card p-5 flex items-start gap-4">
      <div className={`w-10 h-10 rounded-lg flex items-center justify-center shrink-0 ${bgColor}`}>
        <Icon className={`w-5 h-5 ${color}`} />
      </div>
      <div className="min-w-0">
        <p className="text-xs font-medium text-slate-500 uppercase tracking-wider">{title}</p>
        <p className="text-2xl font-bold text-slate-100 mt-0.5">{value}</p>
        <p className="text-xs text-slate-500 mt-0.5 truncate">{subtitle}</p>
      </div>
    </div>
  )
}

function EvaluationRow({ run }: { run: EvaluationRun }) {
  const [expanded, setExpanded] = useState(false)
  const metrics = run.evaluation_results || []
  const passCount = metrics.filter(m => ["GOOD","EXPECTED","PASS"].includes(m.status.toUpperCase())).length
  const failCount = metrics.filter(m => ["CRITICAL","FAIL"].includes(m.status.toUpperCase())).length
  const warnCount = metrics.filter(m => m.status.toUpperCase() === "WARNING").length

  return (
    <>
      <tr className="hover:bg-slate-800/30 transition-colors cursor-pointer group" onClick={() => setExpanded(!expanded)}>
        <td className="px-5 py-4">
          <div className="flex items-center gap-2">
            <button className="text-slate-600 group-hover:text-indigo-400 transition-colors">
              {expanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
            </button>
            <div className="font-mono text-xs text-indigo-400">{run.ai_run_id.split("-")[0]}</div>
          </div>
        </td>
        <td className="px-5 py-4 text-slate-400 font-mono text-xs">
          {run.ticket_id ? run.ticket_id.split("-")[0] : "—"}
        </td>
        <td className="px-5 py-4">
          <div className="flex items-center gap-1.5">
            {passCount > 0 && <span className="flex items-center gap-1 text-xs text-emerald-400"><CheckCircle2 className="w-3 h-3" /> {passCount}</span>}
            {warnCount > 0 && <span className="flex items-center gap-1 text-xs text-amber-400"><AlertTriangle className="w-3 h-3" /> {warnCount}</span>}
            {failCount > 0 && <span className="flex items-center gap-1 text-xs text-rose-400"><AlertCircle className="w-3 h-3" /> {failCount}</span>}
            {metrics.length === 0 && <span className="text-slate-600 text-xs">No metrics</span>}
          </div>
        </td>
        <td className="px-5 py-4">
          <Badge variant="secondary">{metrics.length} metric{metrics.length !== 1 ? "s" : ""}</Badge>
        </td>
        <td className="px-5 py-4 text-slate-500 text-xs whitespace-nowrap">{timeAgo(run.created_at)}</td>
      </tr>
      {expanded && (
        <tr>
          <td colSpan={5} className="p-0 border-b border-slate-700/50">
            <div className="bg-slate-900/50 px-14 py-6">
              <div className="flex items-start gap-2 mb-5 px-3 py-2.5 rounded-lg bg-indigo-500/10 border border-indigo-500/20">
                <Info className="w-4 h-4 text-indigo-400 mt-0.5 shrink-0" />
                <p className="text-xs text-indigo-300">
                  <strong className="font-semibold">Heuristic / Rule-Based Metrics</strong> — Scores computed deterministically via predefined rules, not LLM grading. They measure structural quality signals like evidence count, confidence thresholds, and response completeness.
                </p>
              </div>
              {metrics.length > 0 ? (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {metrics.map((m, idx) => (
                    <div key={idx} className="glass-card p-4 space-y-2">
                      <div className="flex justify-between items-start gap-2">
                        <span className="font-medium text-slate-200 text-sm leading-snug">{m.metric_name}</span>
                        <div className="flex items-center gap-1.5 shrink-0">
                          <span className="text-sm font-mono text-slate-400">{formatVal(m.score)}</span>
                          <StatusIcon status={m.status} />
                        </div>
                      </div>
                      <Badge variant={metricVariant(m.status)} className="text-[10px]">{m.status.toUpperCase()}</Badge>
                      <p className="text-xs text-slate-500 leading-relaxed">{m.explanation || "No explanation provided."}</p>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-slate-500 italic">No evaluation metrics recorded for this run.</p>
              )}
            </div>
          </td>
        </tr>
      )}
    </>
  )
}

export default function EvaluationsPage() {
  const { showToast, ToastNode } = useToast()
  const [runs, setRuns] = useState<EvaluationRun[]>([])
  const [loading, setLoading] = useState(true)

  const load = async () => {
    setLoading(true)
    try {
      const data = await evaluationsApi.listEvaluations()
      setRuns(Array.isArray(data.items) ? data.items : [])
    } catch (err) {
      showToast(getErrorMessage(err), "error")
    } finally {
      setLoading(false)
    }
  }
  useEffect(() => { load() }, [])

  const kpis = useMemo(() => {
    const safeRuns = Array.isArray(runs) ? runs : []
    const allMetrics: EvaluationResult[] = safeRuns.flatMap(r => r.evaluation_results || [])
    if (allMetrics.length === 0) return null
    const byName = (name: string) => allMetrics.filter(m => m.metric_name.toLowerCase().includes(name.toLowerCase()))
    const passRate = (metrics: EvaluationResult[]) => {
      if (metrics.length === 0) return null
      const passed = metrics.filter(m => ["GOOD","EXPECTED","PASS"].includes(m.status.toUpperCase())).length
      return Math.round((passed / metrics.length) * 100)
    }
    const avgScore = (metrics: EvaluationResult[]) => {
      const scored = metrics.filter(m => m.score !== null && m.score !== undefined)
      if (scored.length === 0) return null
      return (scored.reduce((s, m) => s + (m.score as number), 0) / scored.length).toFixed(2)
    }
    const retrieval = byName("retrieval").concat(byName("evidence"))
    const coverage = byName("coverage").concat(byName("groundedness"))
    const classification = byName("classification").concat(byName("category"))
    return {
      totalRuns: safeRuns.length,
      totalMetrics: allMetrics.length,
      overallPassRate: passRate(allMetrics),
      retrievalQuality: passRate(retrieval.length ? retrieval : allMetrics),
      evidenceCoverage: avgScore(coverage.length ? coverage : allMetrics),
      classificationAccuracy: passRate(classification.length ? classification : allMetrics),
    }
  }, [runs])

  return (
    <AppLayout title="Evaluations" subtitle="Rule-based AI quality metrics">
      <div className="space-y-6">
        {ToastNode}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-slate-100 flex items-center gap-2">
              <span className="text-indigo-400">📊</span> AI Evaluations
            </h1>
            <p className="text-sm text-slate-400 mt-1">
              {runs.length} total run{runs.length !== 1 ? "s" : ""} · <span className="text-amber-400 font-medium">Rule-Based / Heuristic Metrics</span>
            </p>
          </div>
          <button onClick={load} disabled={loading} className={`p-2 rounded-lg hover:bg-slate-700 text-slate-500 hover:text-slate-300 transition-colors ${loading ? "animate-spin" : ""}`}>
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>

        {kpis && (
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <KpiCard title="Eval Runs" value={kpis.totalRuns.toString()} subtitle={`${kpis.totalMetrics} total metrics`} icon={BarChart3} color="text-indigo-400" bgColor="bg-indigo-500/10" />
            <KpiCard title="Retrieval Quality" value={kpis.retrievalQuality !== null ? `${kpis.retrievalQuality}%` : "N/A"} subtitle="Evidence relevance pass rate" icon={BookOpen} color="text-emerald-400" bgColor="bg-emerald-500/10" />
            <KpiCard title="Evidence Coverage" value={kpis.evidenceCoverage !== null ? String(kpis.evidenceCoverage) : "N/A"} subtitle="Avg grounding score" icon={FileCheck2} color="text-blue-400" bgColor="bg-blue-500/10" />
            <KpiCard title="Overall Pass Rate" value={kpis.overallPassRate !== null ? `${kpis.overallPassRate}%` : "N/A"} subtitle="All heuristic checks" icon={Zap} color="text-amber-400" bgColor="bg-amber-500/10" />
          </div>
        )}

        <div className="glass-card overflow-hidden">
          <div className="px-5 py-4 border-b border-slate-700/50 flex items-center justify-between bg-slate-800/30">
            <h3 className="text-sm font-semibold text-slate-300 flex items-center gap-2">
              <FileCheck2 className="w-4 h-4 text-indigo-400" /> Evaluation History
            </h3>
            <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-amber-500/10 border border-amber-500/20">
              <span className="w-1.5 h-1.5 rounded-full bg-amber-400" />
              <span className="text-xs font-medium text-amber-300">Rule-Based Metrics</span>
            </div>
          </div>
          {loading ? (
            <div className="p-6 space-y-4">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-14 w-full" />
              ))}
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-slate-800/50 text-slate-400">
                  <tr>
                    <th className="px-5 py-3.5 font-medium text-left border-b border-slate-700/50">Run ID</th>
                    <th className="px-5 py-3.5 font-medium text-left border-b border-slate-700/50">Ticket</th>
                    <th className="px-5 py-3.5 font-medium text-left border-b border-slate-700/50">Results</th>
                    <th className="px-5 py-3.5 font-medium text-left border-b border-slate-700/50">Metrics</th>
                    <th className="px-5 py-3.5 font-medium text-left border-b border-slate-700/50">Time</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-700/50">
                  {runs.map(run => <EvaluationRow key={run.ai_run_id} run={run} />)}
                  {runs.length === 0 && (
                    <tr>
                      <td colSpan={5} className="py-24 text-center">
                        <div className="flex flex-col items-center gap-3">
                          <div className="w-16 h-16 rounded-2xl bg-slate-800 flex items-center justify-center text-3xl">📊</div>
                          <p className="text-slate-300 font-medium">No evaluations yet</p>
                          <p className="text-slate-500 text-sm">Evaluations run automatically after each AI agent investigation.</p>
                        </div>
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Classification Accuracy card (separate) */}
        {kpis && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <KpiCard
              title="Classification Accuracy"
              value={kpis.classificationAccuracy !== null ? `${kpis.classificationAccuracy}%` : "N/A"}
              subtitle="Category/priority accuracy"
              icon={Target}
              color="text-purple-400"
              bgColor="bg-purple-500/10"
            />
          </div>
        )}
      </div>
    </AppLayout>
  )
}
