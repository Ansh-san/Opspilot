import { type ReactNode, useState } from 'react'
import { Sidebar } from './Sidebar'
import { Topbar } from './Topbar'

interface AppLayoutProps {
  children: ReactNode
  title?: string
  subtitle?: string
}

export function AppLayout({ children, title, subtitle }: AppLayoutProps) {
  const [isSidebarOpen, setIsSidebarOpen] = useState(false)

  return (
    <div className="flex min-h-screen bg-base">
      <Sidebar isOpen={isSidebarOpen} onClose={() => setIsSidebarOpen(false)} />
      <div className="flex flex-col flex-1 min-w-0">
        <Topbar 
          title={title} 
          subtitle={subtitle} 
          onOpenSidebar={() => setIsSidebarOpen(true)} 
        />
        <main className="flex-1 p-6 overflow-auto animate-in" role="main">
          {children}
        </main>
      </div>
    </div>
  )
}
