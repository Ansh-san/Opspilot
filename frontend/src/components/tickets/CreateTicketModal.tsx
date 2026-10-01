/**
 * CreateTicketModal — form modal for creating a new ticket.
 * On success, calls onCreated(ticket) so the parent can redirect.
 */

import { useState } from 'react'
import { ticketsApi } from '@/api/tickets'
import { getErrorMessage } from '@/api/client'
import type { Ticket, TicketCreate, TicketPriority, TicketSeverity } from '@/types/ticket'
import { useToast } from '@/components/ui/Toast'

interface Props {
  onClose: () => void
  onCreated: (ticket: Ticket) => void
}

const PRIORITIES: TicketPriority[] = ['low', 'medium', 'high', 'critical']
const SEVERITIES: TicketSeverity[] = ['s1', 's2', 's3', 's4']

const SEVERITY_LABELS: Record<TicketSeverity, string> = {
  s1: 'S1 — Critical Impact',
  s2: 'S2 — High Impact',
  s3: 'S3 — Medium Impact',
  s4: 'S4 — Low Impact',
}

export function CreateTicketModal({ onClose, onCreated }: Props) {
  const { showToast, ToastNode } = useToast()
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [form, setForm] = useState<TicketCreate>({
    title: '',
    description: '',
    priority: 'medium',
  })

  const handleChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>
  ) => {
    const { name, value } = e.target
    setForm((prev) => ({ ...prev, [name]: value || undefined }))
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (form.title.length < 3) {
      showToast('Title must be at least 3 characters.', 'warning')
      return
    }
    if (!form.description || form.description.length < 10) {
      showToast('Description must be at least 10 characters.', 'warning')
      return
    }
    setIsSubmitting(true)
    try {
      const { data: ticket } = await ticketsApi.create(form)
      onCreated(ticket)
    } catch (err) {
      showToast(getErrorMessage(err))
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <>
      {ToastNode}
      {/* Overlay */}
      <div
        className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm"
        onClick={onClose}
        aria-hidden
      />

      {/* Modal */}
      <div
        className="fixed inset-0 z-50 flex items-center justify-center p-4"
        role="dialog"
        aria-modal="true"
        aria-labelledby="modal-title"
      >
        <div className="glass-card w-full max-w-2xl max-h-[90vh] overflow-y-auto shadow-2xl">
          {/* Header */}
          <div className="flex items-center justify-between p-6 border-b border-slate-700/50">
            <div>
              <h2 id="modal-title" className="text-lg font-semibold text-slate-100">
                Create New Ticket
              </h2>
              <p className="text-sm text-slate-400 mt-0.5">
                Document an incident or service request
              </p>
            </div>
            <button
              onClick={onClose}
              className="p-2 rounded-lg text-slate-400 hover:text-slate-100 hover:bg-slate-700/50 transition-all"
              aria-label="Close modal"
            >
              <svg className="w-5 h-5" viewBox="0 0 20 20" fill="currentColor">
                <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
              </svg>
            </button>
          </div>

          {/* Form */}
          <form onSubmit={handleSubmit} className="p-6 space-y-5">
            {/* Title */}
            <div>
              <label htmlFor="title" className="block text-sm font-medium text-slate-300 mb-1.5">
                Title <span className="text-red-400">*</span>
              </label>
              <input
                id="title"
                name="title"
                type="text"
                value={form.title}
                onChange={handleChange}
                placeholder="Brief summary of the issue"
                required
                className="w-full bg-slate-800/60 border border-slate-700 rounded-lg px-4 py-2.5 text-slate-100 placeholder-slate-500 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/50 focus:border-indigo-500/50 transition-all"
              />
            </div>

            {/* Description */}
            <div>
              <label htmlFor="description" className="block text-sm font-medium text-slate-300 mb-1.5">
                Description <span className="text-red-400">*</span>
              </label>
              <textarea
                id="description"
                name="description"
                value={form.description}
                onChange={handleChange}
                rows={4}
                placeholder="Detailed description of the issue, steps to reproduce, and impact..."
                required
                className="w-full bg-slate-800/60 border border-slate-700 rounded-lg px-4 py-2.5 text-slate-100 placeholder-slate-500 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/50 focus:border-indigo-500/50 transition-all resize-none"
              />
            </div>

            {/* Row: Priority + Severity */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label htmlFor="priority" className="block text-sm font-medium text-slate-300 mb-1.5">
                  Priority <span className="text-red-400">*</span>
                </label>
                <select
                  id="priority"
                  name="priority"
                  value={form.priority}
                  onChange={handleChange}
                  className="w-full bg-slate-800/60 border border-slate-700 rounded-lg px-4 py-2.5 text-slate-100 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/50 focus:border-indigo-500/50 transition-all"
                >
                  {PRIORITIES.map((p) => (
                    <option key={p} value={p} className="bg-slate-900">
                      {p.charAt(0).toUpperCase() + p.slice(1)}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label htmlFor="severity" className="block text-sm font-medium text-slate-300 mb-1.5">
                  Severity
                </label>
                <select
                  id="severity"
                  name="severity"
                  value={form.severity ?? ''}
                  onChange={handleChange}
                  className="w-full bg-slate-800/60 border border-slate-700 rounded-lg px-4 py-2.5 text-slate-100 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/50 focus:border-indigo-500/50 transition-all"
                >
                  <option value="" className="bg-slate-900">None</option>
                  {SEVERITIES.map((s) => (
                    <option key={s} value={s} className="bg-slate-900">
                      {SEVERITY_LABELS[s]}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {/* Row: Category + Affected Service */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label htmlFor="category" className="block text-sm font-medium text-slate-300 mb-1.5">
                  Category
                </label>
                <input
                  id="category"
                  name="category"
                  type="text"
                  value={form.category ?? ''}
                  onChange={handleChange}
                  placeholder="e.g. Network, Auth, DB"
                  className="w-full bg-slate-800/60 border border-slate-700 rounded-lg px-4 py-2.5 text-slate-100 placeholder-slate-500 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/50 focus:border-indigo-500/50 transition-all"
                />
              </div>

              <div>
                <label htmlFor="affected_service" className="block text-sm font-medium text-slate-300 mb-1.5">
                  Affected Service
                </label>
                <input
                  id="affected_service"
                  name="affected_service"
                  type="text"
                  value={form.affected_service ?? ''}
                  onChange={handleChange}
                  placeholder="e.g. payment-api, auth-service"
                  className="w-full bg-slate-800/60 border border-slate-700 rounded-lg px-4 py-2.5 text-slate-100 placeholder-slate-500 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/50 focus:border-indigo-500/50 transition-all"
                />
              </div>
            </div>

            {/* Actions */}
            <div className="flex items-center justify-end gap-3 pt-2 border-t border-slate-700/50">
              <button
                type="button"
                onClick={onClose}
                disabled={isSubmitting}
                className="px-4 py-2 text-sm font-medium text-slate-400 hover:text-slate-100 bg-slate-700/50 hover:bg-slate-700 rounded-lg transition-all"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={isSubmitting}
                className="px-5 py-2 text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg transition-all flex items-center gap-2"
              >
                {isSubmitting ? (
                  <>
                    <svg className="w-4 h-4 animate-spin" viewBox="0 0 24 24" fill="none">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                    </svg>
                    Creating…
                  </>
                ) : (
                  'Create Ticket'
                )}
              </button>
            </div>
          </form>
        </div>
      </div>
    </>
  )
}
