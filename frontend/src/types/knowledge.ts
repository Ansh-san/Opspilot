/** TypeScript types for the Knowledge Base (Phase 3). */

export type DocumentSourceType = 'pdf' | 'txt' | 'markdown'
export type DocumentStatus = 'pending' | 'processing' | 'ready' | 'failed'

export interface KnowledgeChunk {
  id: string
  chunk_index: number
  content: string
  chunk_metadata: {
    document_id: string
    chunk_index: number
    page: number | null
    section: string | null
    source_title: string
  }
}

export interface KnowledgeDocumentListItem {
  id: string
  org_id: string
  title: string
  source_type: DocumentSourceType
  status: DocumentStatus
  chunk_count: number
  uploaded_by: string
  created_at: string
}

export interface KnowledgeDocument extends KnowledgeDocumentListItem {
  source_path: string | null
  chunks: KnowledgeChunk[]
}

// ─── Search ──────────────────────────────────────────────────────────────────

export interface SearchRequest {
  query: string
  top_k?: number
}

export interface SearchHit {
  chunk_id: string
  document_id: string
  document_title: string
  content: string
  similarity_score: number
  page: number | null
  section: string | null
  source_title: string | null
}

export interface SearchResponse {
  query: string
  top_k: number
  results: SearchHit[]
}
