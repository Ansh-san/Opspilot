/**
 * Knowledge Base API — all Axios calls for /api/v1/knowledge/*
 */

import { apiClient } from '@/api/client'
import type {
  KnowledgeDocument,
  KnowledgeDocumentListItem,
  SearchRequest,
  SearchResponse,
} from '@/types/knowledge'

export const knowledgeApi = {
  /** Upload a document (PDF, TXT, MD — max 10 MB) */
  upload: (file: File, onProgress?: (pct: number) => void) => {
    const form = new FormData()
    form.append('file', file)
    return apiClient.post<KnowledgeDocument>('/api/v1/knowledge/documents', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (e) => {
        if (onProgress && e.total) onProgress(Math.round((e.loaded / e.total) * 100))
      },
    })
  },

  /** List all documents for the current org */
  list: () => apiClient.get<KnowledgeDocumentListItem[]>('/api/v1/knowledge/documents'),

  /** Get a single document (includes chunks) */
  get: (id: string) => apiClient.get<KnowledgeDocument>(`/api/v1/knowledge/documents/${id}`),

  /** Delete a document */
  remove: (id: string) => apiClient.delete(`/api/v1/knowledge/documents/${id}`),

  /** Semantic search */
  search: (body: SearchRequest) =>
    apiClient.post<SearchResponse>('/api/v1/knowledge/search', body),
}
