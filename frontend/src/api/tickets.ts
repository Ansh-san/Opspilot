/**
 * Tickets API — all Axios calls for /api/v1/tickets/*
 */

import { apiClient } from '@/api/client'
import type {
  CommentCreate,
  Ticket,
  TicketComment,
  TicketCreate,
  TicketListResponse,
  TicketUpdate,
} from '@/types/ticket'

export interface TicketListParams {
  skip?: number
  limit?: number
  status?: string
  priority?: string
}

export const ticketsApi = {
  /** List tickets with pagination + optional filters */
  list: (params: TicketListParams = {}) =>
    apiClient.get<TicketListResponse>('/api/v1/tickets', { params }),

  /** Get a single ticket by ID */
  get: (id: string) =>
    apiClient.get<Ticket>(`/api/v1/tickets/${id}`),

  /** Create a new ticket */
  create: (data: TicketCreate) =>
    apiClient.post<Ticket>('/api/v1/tickets', data),

  /** Patch a ticket (partial update, status transitions) */
  update: (id: string, data: TicketUpdate) =>
    apiClient.patch<Ticket>(`/api/v1/tickets/${id}`, data),

  /** Delete a ticket */
  remove: (id: string) =>
    apiClient.delete(`/api/v1/tickets/${id}`),

  /** List comments on a ticket */
  listComments: (id: string) =>
    apiClient.get<TicketComment[]>(`/api/v1/tickets/${id}/comments`),

  /** Add a comment to a ticket */
  addComment: (id: string, data: CommentCreate) =>
    apiClient.post<TicketComment>(`/api/v1/tickets/${id}/comments`, data),
}
