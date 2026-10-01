import { Construction } from 'lucide-react'
import { AppLayout } from '@/components/layout/AppLayout'
import { Badge } from '@/components/ui/Badge'

function ComingSoon({ title, description, phase }: { title: string; description: string; phase: number }) {
  return (
    <AppLayout title={title}>
      <div className="flex flex-col items-center justify-center min-h-[60vh] text-center">
        <div className="p-4 bg-base-elevated rounded-2xl border border-base-border mb-6">
          <Construction className="w-10 h-10 text-primary-400" />
        </div>
        <Badge variant="secondary" className="mb-4">Phase {phase}</Badge>
        <h2 className="text-xl font-semibold text-slate-200 mb-2">{title}</h2>
        <p className="text-slate-500 max-w-md">{description}</p>
      </div>
    </AppLayout>
  )
}

export function Tickets() {
  return <ComingSoon title="Tickets" description="Ticket management, status tracking, and AI-powered diagnosis. Coming in Phase 2." phase={2} />
}

export function Knowledge() {
  return <ComingSoon title="Knowledge Base" description="Document upload, RAG pipeline, and semantic search. Coming in Phase 3." phase={3} />
}


export function Settings() {
  return (
    <AppLayout title="Settings">
      <div className="flex flex-col items-center justify-center min-h-[60vh] text-center space-y-6">
        <div className="p-6 bg-slate-800/50 rounded-2xl border border-slate-700/50">
          <Construction className="w-12 h-12 text-slate-400 mb-4 mx-auto" />
          <h2 className="text-xl font-semibold text-slate-200 mb-2">Organization Settings</h2>
          <p className="text-slate-400 max-w-sm mb-6">
            Organization settings, RBAC user management, and integrations are managed by your administrator.
          </p>
          <button 
            className="px-6 py-2 bg-indigo-500 hover:bg-indigo-600 text-white font-medium rounded-lg shadow shadow-indigo-500/20 transition-all"
            onClick={() => alert("Contacting administrator...")}
          >
            Contact Administrator
          </button>
        </div>
      </div>
    </AppLayout>
  )
}
