import { AlertCircle, AlertTriangle, CheckCircle, Info, X } from 'lucide-react'
import { cn } from '@/utils/cn'

export type AlertVariant = 'info' | 'success' | 'warning' | 'error'

interface AlertProps {
  variant?: AlertVariant
  title?: string
  children: React.ReactNode
  className?: string
  onClose?: () => void
}

const config: Record<AlertVariant, {
  containerClass: string
  iconClass: string
  icon: typeof Info
}> = {
  info: {
    containerClass: 'bg-info/10 border-info/30 text-info',
    iconClass: 'text-info',
    icon: Info,
  },
  success: {
    containerClass: 'bg-success/10 border-success/30 text-success',
    iconClass: 'text-success',
    icon: CheckCircle,
  },
  warning: {
    containerClass: 'bg-warning/10 border-warning/30 text-warning',
    iconClass: 'text-warning',
    icon: AlertTriangle,
  },
  error: {
    containerClass: 'bg-danger/10 border-danger/30 text-danger',
    iconClass: 'text-danger',
    icon: AlertCircle,
  },
}

export function Alert({ variant = 'info', title, children, className, onClose }: AlertProps) {
  const { containerClass, iconClass, icon: Icon } = config[variant]

  return (
    <div
      role="alert"
      className={cn(
        'flex gap-3 p-4 rounded-lg border animate-in',
        containerClass,
        className
      )}
    >
      <Icon className={cn('w-5 h-5 shrink-0 mt-0.5', iconClass)} aria-hidden="true" />
      <div className="flex-1 min-w-0">
        {title && <p className="font-medium text-sm mb-0.5">{title}</p>}
        <p className="text-sm opacity-90">{children}</p>
      </div>
      {onClose && (
        <button
          onClick={onClose}
          className="shrink-0 opacity-70 hover:opacity-100 transition-opacity"
          aria-label="Dismiss alert"
        >
          <X className="w-4 h-4" />
        </button>
      )}
    </div>
  )
}
