import { useEffect, useState, useMemo } from "react"
import { AppLayout } from "@/components/layout/AppLayout"
import { observabilityApi } from "@/api/observability"
import type { ObservabilityKPIs, AIRunTrace } from "@/api/observability"
import { Badge } from "@/components/ui/Badge"
import { getErrorMessage } from "@/api/client"
import { useToast } from "@/components/ui/Toast"
import {
  Activity, Clock, FileText, DollarSign, CheckCircle2, ShieldAlert,
  Shield, ShieldCheck, FileCheck2, Cpu, RefreshCw, DatabaseZap, AlertCircle,
} from "lucide-react"
import {
  XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip, ResponsiveContainer,
  LineChart, Line, AreaChart, Area,
} from "recharts"

// ─── Helpers ──────────────────────────────────────────────────────────────────

function fv(val: number | null | undefined, fmt?: (v: number) => string): string {
  if (val === null || val === undefined || Number.isNaN(val as number)) return "N/A"
  return fmt ? fmt(val as number) : String(val)
}

function formatTs(iso: string, showDate = false) {
  return new Intl.DateTimeFormat("en-US", {
    ...(showDate ? { month: "short", day: "numeric" } : {}),
    hour: "2-digit", minute: "2-digit",
  }).format(new Date(iso))
}

// ─── Metric Card ──────────────────────────────────────────────────────────────

function MetricCard({ title, value, subtitle, icon: Icon, colorClass }: {
  title: string; value: string | React.ReactNode; subtitle: string; icon: React.ElementType; colorClass: string
}) {
  return (
    <div className="glass-card p-5 flex items-start gap-4">
      <div className={`p-3 rounded-xl ${colorClass} shrink-0`}>
        <Icon className="w-5 h-5 text-white" />
      </div>
      <div>
        <p className="text-slate-400 text-xs font-medium uppercase tracking-wider">{title}</p>
        <h3 className="text-2xl font-bold text-slate-100 mt-1">{value}</h3>
        <p className="text-xs text-slate-500 mt-0.5">{subtitle}</p>
      </div>
    </div>
  )
}

// ─── Demo Banner ──────────────────────────────────────────────────────────────

function DemoBanner() {
  return (
    <div className="flex items-start gap-3 px-4 py-3 rounded-xl bg-amber-500/10 border border-amber-500/25">
      <DatabaseZap className="w-4 h-4 text-amber-400 mt-0.5 shrink-0" />
      <div>
        <p className="text-xs font-semibold text-amber-300 uppercase tracking-wide">DEMO / SYNTHETIC DATA</p>
        <p className="text-xs text-amber-300/70 mt-0.5">
          The time-series charts below reflect seeded synthetic data and are for demonstration purposes only.
          Real production metrics will accumulate as the AI agent processes live tickets.
        </p>
      </div>
    </div>
  )
}

// ─── Empty state ──────────────────────────────────────────────────────────────

function ChartEmptyState({ label }: { label: string }) {
  return (
    <div className="h-full flex flex-col items-center justify-center gap-3 text-center py-12">
      <div className="w-12 h-12 rounded-2xl bg-slate-800 flex items-center justify-center">
        <Activity className="w-5 h-5 text-slate-600" />
      </div>
      <div>
        <p className="text-slate-400 font-medium text-sm">No data yet</p>
        <p className="text-slate-600 text-xs mt-1">{label}</p>
      </div>
    </div>
  )
}

// ─── Custom Tooltip ───────────────────────────────────────────────────────────

function ChartTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-xs shadow-xl">
      <p className="text-slate-400 mb-1">{label}</p>
      {payload.map((p: any, i: number) => (
        <p key={i} style={{ color: p.color }}>{p.name}: <strong>{p.value}</strong></p>
      ))}
    </div>
  )
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function ObservabilityPage() {
  const { showToast, ToastNode } = useToast()
  const [kpis, setKpis] = useState<ObservabilityKPIs | null>(null)
  const [traces, setTraces] = useState<AIRunTrace[]>([])
  const [loading, setLoading] = useState(true)
  const [hasSyntheticData, setHasSyntheticData] = useState(false)

  const load = async () => {
    setLoading(true)
    try {
      const [kpiData, traceData] = await Promise.all([
        observabilityApi.getKPIs(),
        observabilityApi.getTraces(50, 0),
      ])
      const safeTraces = Array.isArray(traceData) ? traceData : []
      setKpis(kpiData)
      setTraces(safeTraces)
      // Detect synthetic data: if we have traces but 0 real runs from KPIs
      setHasSyntheticData(safeTraces.length > 0 && (kpiData.total_runs === 0 || kpiData.total_runs < safeTraces.length))
    } catch (err) {
      showToast(getErrorMessage(err), "error")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  // ── Build time series from traces ──────────────────────────────────────────
  const chartData = useMemo(() => {
    const safeTraces = Array.isArray(traces) ? traces : []
    return [...safeTraces].slice(0, 20).reverse().map(t => ({
      name: formatTs(t.created_at),
      latency: t.latency_ms ?? null,
      tokens: (t.input_tokens ?? 0) + (t.output_tokens ?? 0),
      cost: t.estimated_cost_usd ? parseFloat((t.estimated_cost_usd * 100).toFixed(4)) : null, // in cents for scale
      confidence: t.confidence ? Math.round(t.confidence * 100) : null,
    }))
  }, [traces])

  return (
    <AppLayout title="Observability & Telemetry" subtitle="Real-time AI agent monitoring">
      <div className="space-y-8 pb-12">
        {ToastNode}

        {/* ── Page Header ──────────────────────────────────────────────────── */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-slate-100 flex items-center gap-2">
              <span className="text-indigo-400">📡</span> Observability
            </h1>
            <p className="text-sm text-slate-400 mt-1">AI agent health, latency, cost, and safety signals</p>
          </div>
          <button onClick={load} disabled={loading} className={`p-2 rounded-lg hover:bg-slate-700 text-slate-500 hover:text-slate-300 transition-colors ${loading ? "animate-spin" : ""}`}>
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>

        {/* Demo Banner (shown when synthetic traces are present) */}
        {hasSyntheticData && <DemoBanner />}

        {loading ? (
          <div className="flex items-center justify-center py-32">
            <svg className="w-10 h-10 animate-spin text-indigo-500" viewBox="0 0 24 24" fill="none">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
            </svg>
          </div>
        ) : (
          <>
            {/* ── Overview KPIs ──────────────────────────────────────────── */}
            <section>
              <h2 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3 flex items-center gap-2">
                <Activity className="w-3.5 h-3.5" /> Overview
              </h2>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                <MetricCard title="Total AI Runs" value={kpis?.total_runs?.toString() ?? "0"} subtitle="Non-synthetic runs" icon={Cpu} colorClass="bg-indigo-600" />
                <MetricCard title="Success Rate" value={fv(kpis?.success_rate, v => `${(v * 100).toFixed(1)}%`)} subtitle={`${kpis?.total_runs ?? 0} total runs`} icon={CheckCircle2} colorClass="bg-emerald-600" />
                <MetricCard title="P95 Latency" value={fv(kpis?.p95_latency, v => `${Math.round(v)}ms`)} subtitle={`P50: ${fv(kpis?.p50_latency, v => `${Math.round(v)}ms`)}`} icon={Clock} colorClass="bg-blue-600" />
                <MetricCard title="Estimated Cost" value={fv(kpis?.total_cost, v => `$${v.toFixed(4)}`)} subtitle="Based on model pricing" icon={DollarSign} colorClass="bg-amber-600" />
              </div>
            </section>

            {/* ── Token & Cost ───────────────────────────────────────────── */}
            <section>
              <h2 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3 flex items-center gap-2">
                <FileText className="w-3.5 h-3.5" /> Token & Cost
              </h2>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <MetricCard title="Token Usage" value={fv(kpis?.total_tokens, v => v.toLocaleString())} subtitle="Total input + output tokens" icon={FileText} colorClass="bg-purple-600" />
                <MetricCard title="Tool Success Rate" value={fv(kpis?.tool_success_rate, v => `${(v * 100).toFixed(1)}%`)} subtitle="Tool execution pass rate" icon={FileCheck2} colorClass="bg-indigo-500" />
              </div>
            </section>

            {/* ── Safety ─────────────────────────────────────────────────── */}
            <section>
              <h2 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3 flex items-center gap-2">
                <Shield className="w-3.5 h-3.5" /> Safety & Interventions
              </h2>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <MetricCard title="Approval Rate" value={fv(kpis?.approval_rate, v => `${(v * 100).toFixed(1)}%`)} subtitle="Proposals approved" icon={ShieldCheck} colorClass="bg-emerald-600" />
                <MetricCard title="Rejection Rate" value={fv(kpis?.rejection_rate, v => `${(v * 100).toFixed(1)}%`)} subtitle="Proposals rejected" icon={ShieldAlert} colorClass="bg-rose-600" />
                <MetricCard title="Blocked Actions" value={fv(kpis?.blocked_count)} subtitle="High-risk blocks" icon={AlertCircle} colorClass="bg-orange-600" />
              </div>
            </section>

            {/* ── Time Series Charts ──────────────────────────────────────── */}
            <section className="space-y-4">
              <h2 className="text-xs font-semibold text-slate-500 uppercase tracking-wider flex items-center gap-2">
                <Activity className="w-3.5 h-3.5" /> Historical Trends
                {hasSyntheticData && (
                  <span className="ml-2 inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-amber-500/15 border border-amber-500/25 text-[10px] font-semibold text-amber-400 uppercase tracking-wide">
                    Demo Data
                  </span>
                )}
              </h2>

              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                {/* Latency Trend */}
                <div className="glass-card p-5">
                  <h3 className="text-sm font-semibold text-slate-300 mb-4 flex items-center gap-2">
                    <Clock className="w-4 h-4 text-blue-400" /> Agent Latency (ms)
                  </h3>
                  <div className="h-52">
                    {chartData.length > 0 ? (
                      <ResponsiveContainer width="100%" height="100%">
                        <AreaChart data={chartData}>
                          <defs>
                            <linearGradient id="latGrad" x1="0" y1="0" x2="0" y2="1">
                              <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
                              <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                            </linearGradient>
                          </defs>
                          <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                          <XAxis dataKey="name" stroke="#475569" tick={{ fontSize: 10 }} />
                          <YAxis stroke="#475569" tick={{ fontSize: 10 }} />
                          <RechartsTooltip content={<ChartTooltip />} />
                          <Area type="monotone" dataKey="latency" name="Latency (ms)" stroke="#3b82f6" strokeWidth={2} fill="url(#latGrad)" dot={false} connectNulls />
                        </AreaChart>
                      </ResponsiveContainer>
                    ) : <ChartEmptyState label="Run AI investigations to see latency trends" />}
                  </div>
                </div>

                {/* Token Usage Trend */}
                <div className="glass-card p-5">
                  <h3 className="text-sm font-semibold text-slate-300 mb-4 flex items-center gap-2">
                    <FileText className="w-4 h-4 text-purple-400" /> Token Usage per Run
                  </h3>
                  <div className="h-52">
                    {chartData.length > 0 ? (
                      <ResponsiveContainer width="100%" height="100%">
                        <AreaChart data={chartData}>
                          <defs>
                            <linearGradient id="tokGrad" x1="0" y1="0" x2="0" y2="1">
                              <stop offset="5%" stopColor="#a855f7" stopOpacity={0.3} />
                              <stop offset="95%" stopColor="#a855f7" stopOpacity={0} />
                            </linearGradient>
                          </defs>
                          <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                          <XAxis dataKey="name" stroke="#475569" tick={{ fontSize: 10 }} />
                          <YAxis stroke="#475569" tick={{ fontSize: 10 }} />
                          <RechartsTooltip content={<ChartTooltip />} />
                          <Area type="monotone" dataKey="tokens" name="Tokens" stroke="#a855f7" strokeWidth={2} fill="url(#tokGrad)" dot={false} connectNulls />
                        </AreaChart>
                      </ResponsiveContainer>
                    ) : <ChartEmptyState label="Run AI investigations to see token usage" />}
                  </div>
                </div>

                {/* Confidence Trend */}
                <div className="glass-card p-5">
                  <h3 className="text-sm font-semibold text-slate-300 mb-4 flex items-center gap-2">
                    <CheckCircle2 className="w-4 h-4 text-emerald-400" /> Agent Confidence (%)
                  </h3>
                  <div className="h-52">
                    {chartData.length > 0 ? (
                      <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={chartData}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                          <XAxis dataKey="name" stroke="#475569" tick={{ fontSize: 10 }} />
                          <YAxis stroke="#475569" tick={{ fontSize: 10 }} domain={[0, 100]} />
                          <RechartsTooltip content={<ChartTooltip />} />
                          <Line type="monotone" dataKey="confidence" name="Confidence %" stroke="#10b981" strokeWidth={2} dot={{ r: 2, fill: "#10b981" }} connectNulls />
                        </LineChart>
                      </ResponsiveContainer>
                    ) : <ChartEmptyState label="Run AI investigations to see confidence trends" />}
                  </div>
                </div>

                {/* Cost Trend */}
                <div className="glass-card p-5">
                  <h3 className="text-sm font-semibold text-slate-300 mb-4 flex items-center gap-2">
                    <DollarSign className="w-4 h-4 text-amber-400" /> Cost per Run (¢)
                  </h3>
                  <div className="h-52">
                    {chartData.length > 0 ? (
                      <ResponsiveContainer width="100%" height="100%">
                        <AreaChart data={chartData}>
                          <defs>
                            <linearGradient id="costGrad" x1="0" y1="0" x2="0" y2="1">
                              <stop offset="5%" stopColor="#f59e0b" stopOpacity={0.3} />
                              <stop offset="95%" stopColor="#f59e0b" stopOpacity={0} />
                            </linearGradient>
                          </defs>
                          <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                          <XAxis dataKey="name" stroke="#475569" tick={{ fontSize: 10 }} />
                          <YAxis stroke="#475569" tick={{ fontSize: 10 }} />
                          <RechartsTooltip content={<ChartTooltip />} />
                          <Area type="monotone" dataKey="cost" name="Cost (¢)" stroke="#f59e0b" strokeWidth={2} fill="url(#costGrad)" dot={false} connectNulls />
                        </AreaChart>
                      </ResponsiveContainer>
                    ) : <ChartEmptyState label="Run AI investigations to see cost trends" />}
                  </div>
                </div>
              </div>
            </section>

            {/* ── Recent AI Runs Table ──────────────────────────────────── */}
            <section className="glass-card overflow-hidden">
              <div className="px-5 py-4 border-b border-slate-700/50 bg-slate-800/30 flex items-center justify-between">
                <h3 className="text-sm font-semibold text-slate-300 flex items-center gap-2">
                  <Activity className="w-4 h-4 text-indigo-400" /> Recent AI Runs
                </h3>
                <span className="text-xs text-slate-500">{traces.length} traces</span>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead className="bg-slate-800/50 text-slate-400">
                    <tr>
                      <th className="px-5 py-3.5 font-medium text-left border-b border-slate-700/50">Run ID</th>
                      <th className="px-5 py-3.5 font-medium text-left border-b border-slate-700/50">Model</th>
                      <th className="px-5 py-3.5 font-medium text-left border-b border-slate-700/50">Risk</th>
                      <th className="px-5 py-3.5 font-medium text-left border-b border-slate-700/50">Confidence</th>
                      <th className="px-5 py-3.5 font-medium text-left border-b border-slate-700/50">Latency</th>
                      <th className="px-5 py-3.5 font-medium text-left border-b border-slate-700/50">Tokens</th>
                      <th className="px-5 py-3.5 font-medium text-left border-b border-slate-700/50">Cost</th>
                      <th className="px-5 py-3.5 font-medium text-left border-b border-slate-700/50">Time</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-700/50">
                    {traces.map(trace => (
                      <tr key={trace.id} className="hover:bg-slate-800/30 transition-colors">
                        <td className="px-5 py-4 font-mono text-xs text-indigo-400">{trace.id.split("-")[0]}</td>
                        <td className="px-5 py-4 text-slate-300 text-xs">{trace.model_used ?? "N/A"}</td>
                        <td className="px-5 py-4">
                          <Badge variant={trace.risk_level === "high" || trace.risk_level === "blocked" ? "danger" : trace.risk_level === "medium" ? "warning" : "secondary"}>
                            {trace.risk_level?.toUpperCase()}
                          </Badge>
                        </td>
                        <td className="px-5 py-4">
                          <div className="flex items-center gap-2">
                            <div className="w-16 h-1.5 bg-slate-800 rounded-full overflow-hidden">
                              <div
                                className={`h-full ${trace.confidence > 0.8 ? "bg-emerald-500" : trace.confidence > 0.5 ? "bg-amber-500" : "bg-red-500"}`}
                                style={{ width: `${Math.max(0, trace.confidence * 100)}%` }}
                              />
                            </div>
                            <span className="text-xs text-slate-400">{(trace.confidence * 100).toFixed(0)}%</span>
                          </div>
                        </td>
                        <td className="px-5 py-4 text-slate-300 text-xs">{fv(trace.latency_ms, v => `${v}ms`)}</td>
                        <td className="px-5 py-4 text-slate-400 text-xs">{fv((trace.input_tokens ?? 0) + (trace.output_tokens ?? 0))}</td>
                        <td className="px-5 py-4 text-slate-400 text-xs">{fv(trace.estimated_cost_usd, v => `$${v.toFixed(4)}`)}</td>
                        <td className="px-5 py-4 text-slate-500 text-xs whitespace-nowrap">{formatTs(trace.created_at)}</td>
                      </tr>
                    ))}
                    {traces.length === 0 && (
                      <tr>
                        <td colSpan={8} className="py-16 text-center">
                          <p className="text-slate-500">No AI runs found. Run the agent from a ticket to start collecting data.</p>
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </section>
          </>
        )}
      </div>
    </AppLayout>
  )
}
