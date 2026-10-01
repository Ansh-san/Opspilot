/**
 * KnowledgePage — Phase 3 Knowledge Base UI
 *
 * Features:
 *  • Drag-and-drop file upload zone with progress bar
 *  • Document table (Title, Type, Status, Chunks, Date)
 *  • Semantic Search panel with elegant result cards
 */

import { useState, useEffect, useCallback, useRef } from 'react'
import { AppLayout } from '@/components/layout/AppLayout'
import { knowledgeApi } from '@/api/knowledge'
import { getErrorMessage } from '@/api/client'
import { useToast } from '@/components/ui/Toast'
import type { KnowledgeDocumentListItem, SearchHit } from '@/types/knowledge'
import { AlertTriangle, X } from 'lucide-react'
import { Skeleton } from '@/components/ui/Skeleton'

// ─── Constants ────────────────────────────────────────────────────────────────
const ALLOWED_TYPES = ['.pdf', '.txt', '.md']
const MAX_MB = 10

// ─── Status badge ─────────────────────────────────────────────────────────────
function StatusBadge({ status }: { status: string }) {
  const map: Record<string, string> = {
    ready: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30',
    processing: 'bg-amber-500/15 text-amber-400 border-amber-500/30',
    pending: 'bg-slate-500/15 text-slate-400 border-slate-500/30',
    failed: 'bg-red-500/15 text-red-400 border-red-500/30',
  }
  const pulse = status === 'processing'
  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium border ${map[status] ?? map.pending}`}
    >
      {pulse && (
        <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse" />
      )}
      {status.charAt(0).toUpperCase() + status.slice(1)}
    </span>
  )
}

// ─── Type badge ───────────────────────────────────────────────────────────────
function TypeBadge({ type }: { type: string }) {
  const map: Record<string, string> = {
    pdf: 'bg-red-500/15 text-red-400',
    txt: 'bg-blue-500/15 text-blue-400',
    markdown: 'bg-purple-500/15 text-purple-400',
  }
  const labels: Record<string, string> = { pdf: 'PDF', txt: 'TXT', markdown: 'MD' }
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-mono font-medium ${map[type] ?? 'bg-slate-500/15 text-slate-400'}`}>
      {labels[type] ?? type.toUpperCase()}
    </span>
  )
}

// ─── Delete Confirm Modal ─────────────────────────────────────────────────────
function DeleteConfirmModal({
  doc,
  onConfirm,
  onCancel,
  isDeleting,
}: {
  doc: KnowledgeDocumentListItem
  onConfirm: () => void
  onCancel: () => void
  isDeleting: boolean
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onCancel} />
      <div className="relative glass-card w-full max-w-md p-6 space-y-5 shadow-2xl border border-red-500/20">
        <button onClick={onCancel} className="absolute top-4 right-4 text-slate-500 hover:text-slate-300 transition-colors">
          <X className="w-4 h-4" />
        </button>
        <div className="flex items-start gap-4">
          <div className="w-10 h-10 rounded-xl bg-red-500/15 flex items-center justify-center shrink-0">
            <AlertTriangle className="w-5 h-5 text-red-400" />
          </div>
          <div>
            <h3 className="text-slate-100 font-semibold">Delete Document?</h3>
            <p className="text-sm text-slate-400 mt-1">
              You are about to permanently delete{" "}
              <span className="text-slate-200 font-medium">"{doc.title}"</span>.
            </p>
          </div>
        </div>
        <div className="bg-red-500/8 border border-red-500/20 rounded-lg px-4 py-3 space-y-1.5">
          <p className="text-xs font-semibold text-red-400 uppercase tracking-wide">Consequences</p>
          <ul className="text-xs text-slate-400 space-y-1 list-disc list-inside">
            <li>The document and all <strong className="text-slate-300">{doc.chunk_count} embedding chunks</strong> will be permanently deleted</li>
            <li>Future AI agent investigations will no longer retrieve content from this document</li>
            <li>This action cannot be undone</li>
          </ul>
        </div>
        <div className="flex gap-3 justify-end">
          <button
            onClick={onCancel}
            disabled={isDeleting}
            className="px-4 py-2 text-sm text-slate-400 hover:text-slate-100 bg-slate-700/50 hover:bg-slate-700 rounded-lg transition-all disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            disabled={isDeleting}
            className="px-4 py-2 text-sm font-semibold text-white bg-red-600 hover:bg-red-500 rounded-lg transition-all disabled:opacity-50"
          >
            {isDeleting ? "Deleting…" : "Delete Document"}
          </button>
        </div>
      </div>
    </div>
  )
}

// ─── Similarity score bar ─────────────────────────────────────────────────────
function ScoreBar({ score }: { score: number }) {
  const pct = Math.max(0, Math.min(100, score * 100))
  const color = pct > 75 ? '#10b981' : pct > 45 ? '#f59e0b' : '#6366f1'
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 bg-slate-700 rounded-full overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{ width: `${pct}%`, background: color }}
        />
      </div>
      <span className="text-xs font-mono text-slate-400 w-10 text-right">
        {(score * 100).toFixed(1)}%
      </span>
    </div>
  )
}

// ─── Upload Zone ──────────────────────────────────────────────────────────────
function UploadZone({
  onUploaded,
}: {
  onUploaded: () => void
}) {
  const { showToast } = useToast()
  const [dragging, setDragging] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [progress, setProgress] = useState(0)
  const [fileName, setFileName] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)

  const handleFile = useCallback(
    async (file: File) => {
      const ext = '.' + file.name.split('.').pop()?.toLowerCase()
      if (!ALLOWED_TYPES.includes(ext)) {
        showToast(`Unsupported file type: ${ext}. Use PDF, TXT, or MD.`, 'error')
        return
      }
      if (file.size > MAX_MB * 1024 * 1024) {
        showToast(`File exceeds ${MAX_MB} MB limit.`, 'error')
        return
      }
      setFileName(file.name)
      setUploading(true)
      setProgress(0)
      try {
        await knowledgeApi.upload(file, setProgress)
        showToast(`"${file.name}" uploaded and processed.`, 'success')
        onUploaded()
      } catch (err) {
        showToast(getErrorMessage(err), 'error')
      } finally {
        setUploading(false)
        setFileName('')
        setProgress(0)
      }
    },
    [onUploaded, showToast]
  )

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault()
      setDragging(false)
      const file = e.dataTransfer.files[0]
      if (file) handleFile(file)
    },
    [handleFile]
  )

  return (
    <div
      onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
      onDragLeave={() => setDragging(false)}
      onDrop={onDrop}
      onClick={() => !uploading && inputRef.current?.click()}
      className={`
        relative border-2 border-dashed rounded-xl p-8 text-center cursor-pointer
        transition-all duration-200 select-none
        ${dragging
          ? 'border-indigo-400 bg-indigo-500/10 scale-[1.01]'
          : 'border-slate-600 hover:border-indigo-500/60 hover:bg-indigo-500/5'
        }
        ${uploading ? 'pointer-events-none opacity-90' : ''}
      `}
    >
      <input
        ref={inputRef}
        type="file"
        accept=".pdf,.txt,.md"
        className="hidden"
        onChange={(e) => { const f = e.target.files?.[0]; if (f) handleFile(f) }}
      />

      {uploading ? (
        <div className="space-y-3">
          <div className="text-2xl">⏳</div>
          <p className="text-sm text-slate-300 font-medium">Uploading {fileName}…</p>
          <div className="w-full max-w-xs mx-auto bg-slate-700 rounded-full h-2 overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-indigo-500 to-purple-500 rounded-full transition-all duration-300"
              style={{ width: `${progress}%` }}
            />
          </div>
          <p className="text-xs text-slate-500">{progress}% — extracting & embedding…</p>
        </div>
      ) : (
        <div className="space-y-2">
          <div className="text-4xl mb-3">{dragging ? '📂' : '📁'}</div>
          <p className="text-slate-200 font-semibold">
            {dragging ? 'Drop to upload' : 'Drag & drop a file here'}
          </p>
          <p className="text-sm text-slate-500">or click to browse</p>
          <p className="text-xs text-slate-600 mt-2">PDF · TXT · MD — max {MAX_MB} MB</p>
        </div>
      )}
    </div>
  )
}

function DocumentTable({
  docs, loading, onDelete,
}: {
  docs: KnowledgeDocumentListItem[]
  loading: boolean
  onDelete: (id: string) => void
}) {
  const { showToast } = useToast()
  const [pendingDelete, setPendingDelete] = useState<KnowledgeDocumentListItem | null>(null)
  const [deleting, setDeleting] = useState(false)

  const handleDelete = async () => {
    if (!pendingDelete) return
    setDeleting(true)
    try {
      await knowledgeApi.remove(pendingDelete.id)
      showToast(`"${pendingDelete.title}" deleted.`, "success")
      onDelete(pendingDelete.id)
      setPendingDelete(null)
    } catch (err) {
      showToast(getErrorMessage(err), "error")
    } finally {
      setDeleting(false)
    }
  }

  if (loading) {
    return (
      <div className="glass-card p-6 space-y-4">
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton key={i} className="h-14 w-full" />
        ))}
      </div>
    )
  }

  if (docs.length === 0) {
    return (
      <div className="glass-card p-10 text-center">
        <div className="text-4xl mb-3">🗄️</div>
        <p className="text-slate-400 font-medium">No documents yet</p>
        <p className="text-sm text-slate-600 mt-1">Upload a PDF, TXT, or MD file above to get started.</p>
      </div>
    )
  }

  return (
    <>
      {pendingDelete && (
        <DeleteConfirmModal
          doc={pendingDelete}
          onConfirm={handleDelete}
          onCancel={() => setPendingDelete(null)}
          isDeleting={deleting}
        />
      )}
      <div className="glass-card overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-700/60">
              <th className="px-5 py-3.5 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">Title</th>
              <th className="px-5 py-3.5 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">Type</th>
              <th className="px-5 py-3.5 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">Status</th>
              <th className="px-5 py-3.5 text-center text-xs font-semibold text-slate-500 uppercase tracking-wider">Chunks</th>
              <th className="px-5 py-3.5 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">Date</th>
              <th className="px-5 py-3.5" />
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60">
            {docs.map((doc) => (
              <tr key={doc.id} className="hover:bg-slate-800/30 transition-colors group">
                <td className="px-5 py-4 max-w-xs">
                  <p className="font-medium text-slate-100 truncate" title={doc.title}>{doc.title}</p>
                </td>
                <td className="px-5 py-4"><TypeBadge type={doc.source_type} /></td>
                <td className="px-5 py-4"><StatusBadge status={doc.status} /></td>
                <td className="px-5 py-4 text-center">
                  <span className="font-mono text-slate-300 text-xs bg-slate-800 px-2 py-0.5 rounded">{doc.chunk_count}</span>
                </td>
                <td className="px-5 py-4 text-slate-500 text-xs">
                  {new Date(doc.created_at).toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric" })}
                </td>
                <td className="px-5 py-4 text-right">
                  <button
                    onClick={() => setPendingDelete(doc)}
                    className="opacity-0 group-hover:opacity-100 text-slate-500 hover:text-red-400 transition-all text-xs px-2 py-1 rounded hover:bg-red-500/10"
                  >
                    🗑 Delete
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  )
}

// ─── Search Result Card ───────────────────────────────────────────────────────
function SearchResultCard({ hit, index }: { hit: SearchHit; index: number }) {
  return (
    <div
      className="glass-card p-5 space-y-3 hover:border-indigo-500/30 transition-colors"
      style={{ animationDelay: `${index * 60}ms` }}
    >
      {/* Header */}
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-indigo-300 truncate" title={hit.document_title}>
            📄 {hit.document_title}
          </p>
          {(hit.page || hit.section) && (
            <p className="text-xs text-slate-500 mt-0.5">
              {hit.page ? `Page ${hit.page}` : ''}
              {hit.page && hit.section ? ' · ' : ''}
              {hit.section ?? ''}
            </p>
          )}
        </div>
        <span className="shrink-0 text-xs font-mono bg-indigo-500/15 text-indigo-300 px-2 py-0.5 rounded">
          #{index + 1}
        </span>
      </div>

      {/* Similarity score */}
      <ScoreBar score={hit.similarity_score} />

      {/* Passage */}
      <p className="text-sm text-slate-300 leading-relaxed line-clamp-4 border-l-2 border-indigo-500/40 pl-3">
        {hit.content}
      </p>
    </div>
  )
}

// ─── Search Panel ─────────────────────────────────────────────────────────────
function SearchPanel() {
  const { showToast } = useToast()
  const [query, setQuery] = useState('')
  const [topK, setTopK] = useState(5)
  const [results, setResults] = useState<SearchHit[]>([])
  const [searched, setSearched] = useState(false)
  const [loading, setLoading] = useState(false)

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!query.trim()) return
    setLoading(true)
    try {
      const { data } = await knowledgeApi.search({ query: query.trim(), top_k: topK })
      setResults(data.results)
      setSearched(true)
    } catch (err) {
      showToast(getErrorMessage(err), 'error')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-5">
      {/* Search form */}
      <form onSubmit={handleSearch} className="flex gap-3">
        <div className="relative flex-1">
          <span className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-500 text-lg">🔍</span>
          <input
            id="knowledge-search-input"
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="e.g. How do I restart the payment service?"
            className="
              w-full pl-10 pr-4 py-3 bg-slate-800/60 border border-slate-700
              rounded-xl text-sm text-slate-100 placeholder-slate-500
              focus:outline-none focus:ring-2 focus:ring-indigo-500/60 focus:border-indigo-500/60
              transition-all
            "
          />
        </div>
        <select
          value={topK}
          onChange={(e) => setTopK(Number(e.target.value))}
          className="bg-slate-800/60 border border-slate-700 rounded-xl text-sm text-slate-300 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-500/60"
        >
          {[3, 5, 8, 10].map((n) => (
            <option key={n} value={n}>Top {n}</option>
          ))}
        </select>
        <button
          type="submit"
          disabled={loading || !query.trim()}
          className="
            px-5 py-3 bg-gradient-to-r from-indigo-600 to-purple-600
            hover:from-indigo-500 hover:to-purple-500
            text-white text-sm font-semibold rounded-xl
            disabled:opacity-50 disabled:cursor-not-allowed
            transition-all duration-150 whitespace-nowrap
          "
        >
          {loading ? 'Searching…' : 'Search'}
        </button>
      </form>

      {/* Results */}
      {loading && (
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="glass-card p-5 animate-pulse space-y-3">
              <div className="h-4 bg-slate-700 rounded w-1/2" />
              <div className="h-2 bg-slate-700 rounded w-full" />
              <div className="h-16 bg-slate-700/60 rounded" />
            </div>
          ))}
        </div>
      )}

      {!loading && searched && results.length === 0 && (
        <div className="glass-card p-8 text-center">
          <div className="text-3xl mb-2">🔎</div>
          <p className="text-slate-400 font-medium">No results found</p>
          <p className="text-xs text-slate-600 mt-1">Try a different query or upload more documents.</p>
        </div>
      )}

      {!loading && results.length > 0 && (
        <div className="space-y-3">
          <p className="text-xs text-slate-500 font-medium uppercase tracking-wider">
            {results.length} result{results.length !== 1 ? 's' : ''} — ranked by cosine similarity
          </p>
          {results.map((hit, i) => (
            <SearchResultCard key={hit.chunk_id} hit={hit} index={i} />
          ))}
        </div>
      )}
    </div>
  )
}

// ─── Page ─────────────────────────────────────────────────────────────────────
export default function KnowledgePage() {
  const [docs, setDocs] = useState<KnowledgeDocumentListItem[]>([])
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState<'documents' | 'search'>('documents')

  const fetchDocs = useCallback(async () => {
    setLoading(true)
    try {
      const { data } = await knowledgeApi.list()
      setDocs(data)
    } catch {
      /* toast handled globally */
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchDocs() }, [fetchDocs])

  const ready = docs.filter((d) => d.status === 'ready').length
  const processing = docs.filter((d) => d.status === 'processing').length
  const totalChunks = docs.reduce((s, d) => s + d.chunk_count, 0)

  return (
    <AppLayout title="Knowledge Base" subtitle="Upload documents and search them semantically with AI embeddings.">
      <div className="space-y-6">
        {/* KPI row */}
        <div className="grid grid-cols-3 gap-4">
          <div className="glass-card p-4 flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-emerald-500/15 flex items-center justify-center text-lg">✅</div>
            <div>
              <p className="text-xl font-bold text-slate-100">{ready}</p>
              <p className="text-xs text-slate-500">Ready</p>
            </div>
          </div>
          <div className="glass-card p-4 flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-amber-500/15 flex items-center justify-center text-lg">⚙️</div>
            <div>
              <p className="text-xl font-bold text-slate-100">{processing}</p>
              <p className="text-xs text-slate-500">Processing</p>
            </div>
          </div>
          <div className="glass-card p-4 flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-indigo-500/15 flex items-center justify-center text-lg">🧩</div>
            <div>
              <p className="text-xl font-bold text-slate-100">{totalChunks.toLocaleString()}</p>
              <p className="text-xs text-slate-500">Total Chunks</p>
            </div>
          </div>
        </div>

        {/* Upload zone */}
        <section>
          <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-3">Upload Document</h2>
          <UploadZone onUploaded={fetchDocs} />
        </section>

        {/* Tabs */}
        <div className="flex gap-1 bg-slate-800/40 rounded-xl p-1 w-fit">
          {(['documents', 'search'] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`
                px-5 py-2 rounded-lg text-sm font-medium transition-all
                ${activeTab === tab
                  ? 'bg-indigo-600 text-white shadow'
                  : 'text-slate-400 hover:text-slate-200'
                }
              `}
            >
              {tab === 'documents' ? '📋 Documents' : '🔍 Semantic Search'}
            </button>
          ))}
        </div>

        {/* Tab content */}
        {activeTab === 'documents' ? (
          <DocumentTable
            docs={docs}
            loading={loading}
            onDelete={(id) => setDocs((prev) => prev.filter((d) => d.id !== id))}
          />
        ) : (
          <SearchPanel />
        )}
      </div>
    </AppLayout>
  )
}

