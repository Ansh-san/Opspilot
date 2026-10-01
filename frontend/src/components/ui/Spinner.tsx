import { cn } from '@/utils/cn'

interface SpinnerProps {
  size?: 'sm' | 'md' | 'lg'
  className?: string
}

const sizeMap = {
  sm: 'w-4 h-4 border-[2px]',
  md: 'w-6 h-6 border-2',
  lg: 'w-8 h-8 border-[3px]',
}

export function Spinner({ size = 'md', className }: SpinnerProps) {
  return (
    <span
      role="status"
      aria-label="Loading"
      className={cn(
        'inline-block rounded-full border-primary-500/30 border-t-primary-500 animate-spin',
        sizeMap[size],
        className
      )}
    />
  )
}

/** Full-page loading overlay */
export function PageSpinner() {
  return (
    <div className="flex items-center justify-center min-h-screen bg-base">
      <div className="flex flex-col items-center gap-4">
        <Spinner size="lg" />
        <p className="text-sm text-slate-500 animate-pulse">Loading OpsPilot…</p>
      </div>
    </div>
  )
}
