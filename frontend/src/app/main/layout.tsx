import type { ReactNode } from 'react'
import { Sidebar } from '@/components/ui/Sidebar'

export default function MainLayout({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <main className="flex-1 ml-64 min-h-screen">
        {children}
      </main>
    </div>
  )
}