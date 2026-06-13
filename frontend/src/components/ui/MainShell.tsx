'use client'

import { useState, useEffect, type ReactNode } from 'react'
import { Menu, PanelLeftClose, PanelLeftOpen } from 'lucide-react'
import { clsx } from 'clsx'
import { IGLogoFilled } from '@/components/ui/IGLogo'
import { Sidebar } from '@/components/ui/Sidebar'

/**
 * Shell client untuk semua halaman /main.
 *  - Desktop (lg+): sidebar bisa disembunyikan penuh lewat tombol toggle
 *    yang menempel di tepi sidebar (geser ke tepi layar saat tersembunyi).
 *  - Mobile (<lg): sidebar jadi drawer (default tersembunyi) + backdrop,
 *    dibuka lewat tombol menu di top bar.
 */
export function MainShell({ children }: { children: ReactNode }) {
  const [collapsed, setCollapsed]   = useState(false)
  const [mobileOpen, setMobileOpen] = useState(false)

  // Ingat preferensi sembunyi/tampil antar sesi.
  useEffect(() => {
    try {
      if (localStorage.getItem('sidebar:collapsed') === '1') setCollapsed(true)
    } catch { /* ignore */ }
  }, [])

  const toggleCollapse = () =>
    setCollapsed(v => {
      const next = !v
      try { localStorage.setItem('sidebar:collapsed', next ? '1' : '0') } catch { /* ignore */ }
      return next
    })

  // Tutup drawer otomatis saat layar membesar ke desktop.
  useEffect(() => {
    const onResize = () => { if (window.innerWidth >= 1024) setMobileOpen(false) }
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [])

  return (
    <div className="min-h-screen">
      {/* Backdrop (mobile) */}
      <div
        className={clsx(
          'fixed inset-0 z-40 bg-black/60 backdrop-blur-sm lg:hidden transition-opacity duration-300',
          mobileOpen ? 'opacity-100' : 'opacity-0 pointer-events-none',
        )}
        onClick={() => setMobileOpen(false)}
        aria-hidden
      />

      <Sidebar
        collapsed={collapsed}
        mobileOpen={mobileOpen}
        onCloseMobile={() => setMobileOpen(false)}
      />

      {/* Tombol toggle sidebar — desktop. Menempel di tepi sidebar, geser ke
          tepi layar saat sidebar disembunyikan. */}
      <button
        onClick={toggleCollapse}
        aria-label={collapsed ? 'Tampilkan sidebar' : 'Sembunyikan sidebar'}
        title={collapsed ? 'Tampilkan sidebar' : 'Sembunyikan sidebar'}
        className={clsx(
          'hidden lg:flex items-center justify-center fixed top-6 z-60 h-9 w-9 rounded-xl',
          'glass border border-white/12 text-white/55 shadow-lg shadow-black/20',
          'hover:text-white hover:bg-white/10 hover:border-white/25 hover:scale-105',
          'transition-all duration-300 ease-in-out',
          collapsed ? 'left-4' : 'left-60',
        )}
      >
        {collapsed ? <PanelLeftOpen size={18} /> : <PanelLeftClose size={18} />}
      </button>

      <div
        className={clsx(
          'min-h-screen transition-[margin] duration-300 ease-in-out',
          collapsed ? 'lg:ml-0' : 'lg:ml-64',
        )}
      >
        {/* Top bar — hanya mobile */}
        <header className="lg:hidden sticky top-0 z-30 flex items-center gap-3 h-14 px-4 glass border-b border-white/[0.07]">
          <button
            onClick={() => setMobileOpen(true)}
            aria-label="Buka menu"
            className="p-1.5 -ml-1 rounded-lg text-white/70 hover:text-white hover:bg-white/10 transition-colors"
          >
            <Menu size={22} />
          </button>
          <div className="flex items-center gap-2">
            <IGLogoFilled size={26} />
            <span
              className="font-display font-800 text-base"
              style={{ fontFamily: 'var(--font-display)', fontWeight: 800 }}
            >
              <span className="ig-text">IG Scraper</span>
            </span>
          </div>
        </header>

        <main className="min-h-screen">{children}</main>
      </div>
    </div>
  )
}
