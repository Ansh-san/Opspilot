import { type ReactNode } from 'react'
import { cn } from '@/utils/cn'

interface CardProps {
  children: ReactNode
  className?: string
  hover?: boolean
  glow?: boolean
  onClick?: () => void
}

export function Card({ children, className, hover, glow, onClick }: CardProps) {
  return (
    <div
      className={cn(
        'glass-card p-6',
        hover && 'hover:border-base-divider hover:shadow-card-hover transition-all duration-200 cursor-pointer',
        glow && 'hover:shadow-glow transition-shadow duration-300',
        onClick && 'cursor-pointer',
        className
      )}
      onClick={onClick}
    >
      {children}
    </div>
  )
}

interface CardHeaderProps {
  title: string
  description?: string
  action?: ReactNode
  icon?: ReactNode
}

export function CardHeader({ title, description, action, icon }: CardHeaderProps) {
  return (
    <div className="flex items-start justify-between mb-4">
      <div className="flex items-center gap-3">
        {icon && (
          <div className="p-2 bg-primary-500/10 rounded-lg border border-primary-500/20">
            <span className="text-primary-400">{icon}</span>
          </div>
        )}
        <div>
          <h3 className="font-semibold text-slate-100">{title}</h3>
          {description && (
            <p className="text-xs text-slate-500 mt-0.5">{description}</p>
          )}
        </div>
      </div>
      {action && <div>{action}</div>}
    </div>
  )
}
