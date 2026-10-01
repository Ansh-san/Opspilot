/**
 * Toast — lightweight toast notification for errors, warnings, success.
 * Usage: <Toast message="..." type="error" onClose={() => ...} />
 */

import { useEffect } from 'react'

interface ToastProps {
  message: string
  type?: 'error' | 'warning' | 'success' | 'info'
  onClose: () => void
  duration?: number
}

const TOAST_STYLES = {
  error:   'bg-red-500/10 border-red-500/30 text-red-400',
  warning: 'bg-amber-500/10 border-amber-500/30 text-amber-400',
  success: 'bg-green-500/10 border-green-500/30 text-green-400',
  info:    'bg-blue-500/10 border-blue-500/30 text-blue-400',
}

const TOAST_ICONS = {
  error:   '✕',
  warning: '⚠',
  success: '✓',
  info:    'ℹ',
}

export function Toast({ message, type = 'error', onClose, duration = 5000 }: ToastProps) {
  useEffect(() => {
    const timer = setTimeout(onClose, duration)
    return () => clearTimeout(timer)
  }, [onClose, duration])

  return (
    <div className={`fixed top-4 right-4 z-50 flex items-start gap-3 px-4 py-3 rounded-xl border backdrop-blur-sm shadow-xl max-w-sm animate-in ${TOAST_STYLES[type]}`}>
      <span className="text-sm font-bold mt-0.5">{TOAST_ICONS[type]}</span>
      <p className="text-sm flex-1">{message}</p>
      <button
        onClick={onClose}
        className="text-current opacity-60 hover:opacity-100 transition-opacity text-sm leading-none"
        aria-label="Dismiss"
      >
        ✕
      </button>
    </div>
  )
}

/** Hook to manage a single toast message */
import { useState, useCallback } from 'react'

export function useToast() {
  const [toast, setToast] = useState<{ message: string; type: ToastProps['type'] } | null>(null)

  const showToast = useCallback((message: string, type: ToastProps['type'] = 'error') => {
    setToast({ message, type })
  }, [])

  const hideToast = useCallback(() => setToast(null), [])

  const ToastNode = toast ? (
    <Toast message={toast.message} type={toast.type} onClose={hideToast} />
  ) : null

  return { showToast, ToastNode }
}
