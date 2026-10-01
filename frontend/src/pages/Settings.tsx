/**
 * SettingsPage — functional settings built from real backend data.
 *
 * Sections:
 *  1. Organization  — name, slug (from /auth/me)
 *  2. My Account    — current user name, email, role, status
 *  3. AI / System   — LLM provider, environment, mode
 *
 * No invented settings. Only data we can derive from the backend.
 */

import { useEffect, useState } from "react"
import { AppLayout } from "@/components/layout/AppLayout"
import { apiClient, getErrorMessage } from "@/api/client"
import { useAuthStore } from "@/stores/authStore"
import { useToast } from "@/components/ui/Toast"
import { Badge } from "@/components/ui/Badge"
import { Building2, User, Cpu, CheckCircle2, XCircle, RefreshCw, Copy, Check } from "lucide-react"

// ─── Types ────────────────────────────────────────────────────────────────────

interface SystemInfo {
  project_name: string
  version: string
  environment: string
  llm_provider: string
  embedding_model: string
  llm_model: string
  status: string
}

// ─── Sub-components ───────────────────────────────────────────────────────────

function SectionCard({ title, icon: Icon, children }: {
  title: string; icon: React.ElementType; children: React.ReactNode
}) {
  return (
    <div className="glass-card overflow-hidden">
      <div className="px-5 py-4 border-b border-slate-700/50 bg-slate-800/30 flex items-center gap-2.5">
        <Icon className="w-4 h-4 text-indigo-400" />
        <h2 className="text-sm font-semibold text-slate-200">{title}</h2>
      </div>
      <div className="p-5">{children}</div>
    </div>
  )
}

function Field({ label, value, mono = false }: { label: string; value: React.ReactNode; mono?: boolean }) {
  return (
    <div className="flex items-start justify-between gap-4 py-3 border-b border-slate-800/60 last:border-0">
      <span className="text-sm text-slate-500 shrink-0 w-40">{label}</span>
      <span className={`text-sm text-slate-200 text-right ${mono ? "font-mono" : ""}`}>{value}</span>
    </div>
  )
}

function CopyField({ label, value }: { label: string; value: string }) {
  const [copied, setCopied] = useState(false)
  const copy = () => {
    navigator.clipboard.writeText(value).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }
  return (
    <div className="flex items-start justify-between gap-4 py-3 border-b border-slate-800/60 last:border-0">
      <span className="text-sm text-slate-500 shrink-0 w-40">{label}</span>
      <div className="flex items-center gap-2">
        <span className="text-sm font-mono text-slate-200">{value}</span>
        <button onClick={copy} className="text-slate-500 hover:text-slate-300 transition-colors">
          {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
        </button>
      </div>
    </div>
  )
}

function ProviderBadge({ provider }: { provider: string }) {
  const configs: Record<string, { label: string; color: "success" | "warning" | "secondary" | "primary" }> = {
    mock:      { label: "Mock / Simulated", color: "warning" },
    openai:    { label: "OpenAI", color: "success" },
    anthropic: { label: "Anthropic", color: "primary" },
  }
  const cfg = configs[provider.toLowerCase()] ?? { label: provider, color: "secondary" as const }
  return <Badge variant={cfg.color}>{cfg.label}</Badge>
}

function EnvBadge({ env }: { env: string }) {
  const configs: Record<string, "success" | "warning" | "danger" | "secondary"> = {
    production: "success", staging: "warning", development: "secondary",
  }
  return <Badge variant={configs[env.toLowerCase()] ?? "secondary"}>{env.toUpperCase()}</Badge>
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function SettingsPage() {
  const { user } = useAuthStore()
  const { showToast, ToastNode } = useToast()
  const [sysInfo, setSysInfo] = useState<SystemInfo | null>(null)
  const [loading, setLoading] = useState(true)

  const load = async () => {
    setLoading(true)
    try {
      const { data } = await apiClient.get<SystemInfo>("/api/v1/health")
      setSysInfo(data)
    } catch (err) {
      showToast(getErrorMessage(err), "error")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  return (
    <AppLayout title="Settings" subtitle="Organization, account, and system configuration">
      <div className="space-y-6 max-w-2xl">
        {ToastNode}

        {/* ── Page Header ──────────────────────────────────────────────── */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-slate-100 flex items-center gap-2">
              <span className="text-indigo-400">⚙️</span> Settings
            </h1>
            <p className="text-sm text-slate-400 mt-1">Read-only view of your organization and system configuration</p>
          </div>
          <button onClick={load} disabled={loading} className={`p-2 rounded-lg hover:bg-slate-700 text-slate-500 hover:text-slate-300 transition-colors ${loading ? "animate-spin" : ""}`}>
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>

        {/* ── 1. Organization ──────────────────────────────────────────── */}
        <SectionCard title="Organization" icon={Building2}>
          {user ? (
            <>
              <Field label="Name" value={sysInfo?.project_name ?? "OpsPilot"} />
              <CopyField label="Org ID" value={user.org_id?.toString() ?? "—"} />
              <Field label="Version" value={<span className="font-mono text-xs bg-slate-800 px-2 py-0.5 rounded">{sysInfo?.version ?? "0.1.0"}</span>} />
              <Field label="Environment" value={sysInfo ? <EnvBadge env={sysInfo.environment} /> : "—"} />
            </>
          ) : (
            <p className="text-slate-500 text-sm py-2">Loading organization data…</p>
          )}
        </SectionCard>

        {/* ── 2. My Account ────────────────────────────────────────────── */}
        <SectionCard title="My Account" icon={User}>
          {user ? (
            <>
              <Field label="Name" value={user.full_name} />
              <Field label="Email" value={user.email} mono />
              <Field label="Role" value={
                <Badge variant={user.role === "admin" ? "primary" : "secondary"}>
                  {user.role?.toUpperCase()}
                </Badge>
              } />
              <Field label="Status" value={
                user.is_active ? (
                  <span className="flex items-center gap-1.5 text-emerald-400 text-xs font-medium">
                    <CheckCircle2 className="w-3.5 h-3.5" /> Active
                  </span>
                ) : (
                  <span className="flex items-center gap-1.5 text-red-400 text-xs font-medium">
                    <XCircle className="w-3.5 h-3.5" /> Inactive
                  </span>
                )
              } />
              <CopyField label="User ID" value={user.id?.toString() ?? "—"} />
              {user.last_login && (
                <Field
                  label="Last Login"
                  value={new Intl.DateTimeFormat("en-US", { dateStyle: "medium", timeStyle: "short" }).format(new Date(user.last_login))}
                />
              )}
              <Field
                label="Member Since"
                value={user.created_at ? new Intl.DateTimeFormat("en-US", { dateStyle: "medium" }).format(new Date(user.created_at)) : "—"}
              />
            </>
          ) : (
            <p className="text-slate-500 text-sm py-2">Loading account data…</p>
          )}
        </SectionCard>

        {/* ── 3. AI / System ───────────────────────────────────────────── */}
        <SectionCard title="AI & System" icon={Cpu}>
          {loading ? (
            <p className="text-slate-500 text-sm py-2">Loading system info…</p>
          ) : sysInfo ? (
            <>
              <Field label="LLM Provider" value={<ProviderBadge provider={sysInfo.llm_provider} />} />
              <Field label="LLM Model" value={<span className="font-mono text-xs">{sysInfo.llm_model || "N/A"}</span>} />
              <Field label="Embedding Model" value={<span className="font-mono text-xs">{sysInfo.embedding_model}</span>} />
              <Field label="API Status" value={
                sysInfo.status === "ok" ? (
                  <span className="flex items-center gap-1.5 text-emerald-400 text-xs font-medium">
                    <CheckCircle2 className="w-3.5 h-3.5" /> Healthy
                  </span>
                ) : (
                  <span className="flex items-center gap-1.5 text-red-400 text-xs font-medium">
                    <XCircle className="w-3.5 h-3.5" /> Degraded
                  </span>
                )
              } />
              {sysInfo.llm_provider === "mock" && (
                <div className="mt-4 flex items-start gap-2.5 px-3 py-2.5 rounded-lg bg-amber-500/10 border border-amber-500/20">
                  <span className="text-amber-400 text-lg shrink-0">⚠️</span>
                  <div>
                    <p className="text-xs font-semibold text-amber-300">Mock / Simulated Mode Active</p>
                    <p className="text-xs text-amber-300/70 mt-0.5">
                      Infrastructure tools are simulated for safety. The AI agent uses a deterministic mock LLM.
                      Set <code className="bg-slate-800 px-1 rounded font-mono">LLM_PROVIDER=openai</code> in your environment to enable real AI inference.
                    </p>
                  </div>
                </div>
              )}
            </>
          ) : (
            <div className="flex items-center gap-2 text-slate-500 text-sm py-2">
              <XCircle className="w-4 h-4 text-red-400" />
              Could not load system information
            </div>
          )}
        </SectionCard>
      </div>
    </AppLayout>
  )
}
