import { Link } from 'react-router-dom'
import { Home, Zap } from 'lucide-react'
import { cn } from '@/utils/cn'

export default function NotFound() {
  return (
    <div className="min-h-screen bg-base flex items-center justify-center p-4">
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-1/3 left-1/2 -translate-x-1/2 w-[500px] h-[500px] bg-primary-500/5 rounded-full blur-3xl" />
      </div>

      <div className="text-center animate-slide-up">
        <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-br from-primary-500 to-secondary-500 shadow-glow mb-6">
          <Zap className="w-8 h-8 text-white" strokeWidth={2.5} />
        </div>
        <h1 className="text-8xl font-black text-slate-800 mb-2">404</h1>
        <h2 className="text-xl font-semibold text-slate-300 mb-2">Page not found</h2>
        <p className="text-slate-500 mb-8 max-w-sm mx-auto">
          The page you're looking for doesn't exist or has been moved.
        </p>
        <Link
          to="/dashboard"
          className={cn(
            'inline-flex items-center gap-2 px-5 py-2.5 rounded-lg font-medium text-sm',
            'bg-primary-500 hover:bg-primary-600 text-white shadow-glow',
            'transition-all duration-150'
          )}
        >
          <Home className="w-4 h-4" />
          Back to Dashboard
        </Link>
      </div>
    </div>
  )
}
