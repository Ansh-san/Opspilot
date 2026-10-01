import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { useEffect, Component, type ReactNode, type ErrorInfo } from 'react'
import { useAuthStore } from '@/stores/authStore'
import { PageSpinner } from '@/components/ui/Spinner'
import Login from '@/pages/Login'
import Register from '@/pages/Register'
import Dashboard from '@/pages/Dashboard'
import NotFound from '@/pages/NotFound'
import TicketsPage from '@/pages/Tickets'
import TicketDetailPage from '@/pages/TicketDetail'
import KnowledgePage from '@/pages/Knowledge'
import AgentsPage from '@/pages/Agents'
import AuditPage from '@/pages/Audit'
import ApprovalsPage from '@/pages/Approvals'
import ObservabilityPage from '@/pages/Observability'
import EvaluationsPage from '@/pages/Evaluations'
import SettingsPage from '@/pages/Settings'


// ─── Error Boundary ────────────────────────────────────────────────────
interface EBState { hasError: boolean; message: string }
class ErrorBoundary extends Component<{ children: ReactNode }, EBState> {
  state: EBState = { hasError: false, message: '' }
  static getDerivedStateFromError(err: Error): EBState {
    return { hasError: true, message: err.message }
  }
  componentDidCatch(err: Error, info: ErrorInfo) {
    console.error('[ErrorBoundary]', err, info)
  }
  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen flex items-center justify-center bg-[#080C18] p-8">
          <div className="glass-card max-w-lg w-full p-8 space-y-4 border border-red-500/30">
            <div className="flex items-center gap-3">
              <span className="text-3xl">⚠️</span>
              <h1 className="text-xl font-bold text-red-400">Page Error</h1>
            </div>
            <p className="text-slate-300 text-sm">An unexpected error occurred in this page.</p>
            <p className="text-xs font-mono text-slate-500 bg-slate-900/50 rounded p-3">{this.state.message}</p>
            <button
              onClick={() => { this.setState({ hasError: false, message: '' }); window.location.href = '/dashboard' }}
              className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium rounded-lg transition-colors"
            >
              Go to Dashboard
            </button>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}

// ─── Route guards ────────────────────────────────────────────────────────────
function PrivateRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuthStore()
  if (isLoading) return <PageSpinner />
  if (!isAuthenticated) return <Navigate to="/login" replace />
  return <>{children}</>
}

function PublicRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuthStore()
  if (isAuthenticated) return <Navigate to="/dashboard" replace />
  return <>{children}</>
}

// ─── App ─────────────────────────────────────────────────────────────────────
export default function App() {
  const { isAuthenticated, loadUser, accessToken } = useAuthStore()

  // On mount — if we have a stored token, re-validate it by fetching /me
  useEffect(() => {
    if (accessToken && !isAuthenticated) {
      loadUser()
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <BrowserRouter future={{ v7_relativeSplatPath: true, v7_startTransition: true }}>
      <ErrorBoundary>
        <Routes>
          {/* ─── Public routes ────────────────────────────────────────── */}
          <Route
            path="/login"
            element={
              <PublicRoute>
                <Login />
              </PublicRoute>
            }
          />
          <Route
            path="/register"
            element={
              <PublicRoute>
                <Register />
              </PublicRoute>
            }
          />

          {/* ─── Protected routes ─────────────────────────────────────── */}
          <Route
            path="/dashboard"
            element={
              <PrivateRoute>
                <Dashboard />
              </PrivateRoute>
            }
          />
          <Route path="/tickets" element={<PrivateRoute><TicketsPage /></PrivateRoute>} />
          <Route path="/tickets/:id" element={<PrivateRoute><TicketDetailPage /></PrivateRoute>} />
          <Route path="/knowledge" element={<PrivateRoute><KnowledgePage /></PrivateRoute>} />
          <Route path="/approvals" element={<PrivateRoute><ApprovalsPage /></PrivateRoute>} />
          <Route path="/agents" element={<PrivateRoute><AgentsPage /></PrivateRoute>} />
          <Route path="/evaluations" element={<PrivateRoute><EvaluationsPage /></PrivateRoute>} />
          <Route path="/observability" element={<PrivateRoute><ObservabilityPage /></PrivateRoute>} />
          <Route path="/audit" element={<PrivateRoute><AuditPage /></PrivateRoute>} />
          <Route path="/settings" element={<PrivateRoute><SettingsPage /></PrivateRoute>} />

          {/* ─── Root redirect ────────────────────────────────────────── */}
          <Route path="/" element={<Navigate to="/dashboard" replace />} />

          {/* ─── 404 ──────────────────────────────────────────────────── */}
          <Route path="*" element={<NotFound />} />
        </Routes>
      </ErrorBoundary>
    </BrowserRouter>
  )
}
