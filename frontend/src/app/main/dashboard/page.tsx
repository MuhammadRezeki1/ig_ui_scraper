'use client'

import { useState, useEffect } from 'react'
import { Activity, TrendingUp, FileJson, Users, Zap, ArrowRight } from 'lucide-react'
import Link from 'next/link'
import { IGLogoFilled } from '@/components/ui/IGLogo'
import { StatCard } from '@/components/ui/StatCard'
import { getHealth, getSession, listOutputFiles } from '@/lib/api'
import type { HealthData, SessionInfo, OutputFile } from '@/types'

export default function DashboardPage() {
  const [health, setHealth] = useState<HealthData | null>(null)
  const [session, setSession] = useState<SessionInfo | null>(null)
  const [files, setFiles] = useState<OutputFile[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([
      getHealth().then(r => setHealth(r.data)).catch(() => {}),
      getSession().then(r => setSession(r.data)).catch(() => {}),
      listOutputFiles().then(r => setFiles(r.data.files)).catch(() => {}),
    ]).finally(() => setLoading(false))
  }, [])

  const totalComments = files.length * 47 // approx placeholder

  return (
    <div className="p-8 max-w-6xl">
      {/* Hero */}
      <div className="glass-strong rounded-3xl p-8 mb-8 relative overflow-hidden">
        <div className="absolute inset-0 opacity-10" style={{ background: 'var(--ig-grad)' }} />
        <div className="absolute -right-12 -top-12 w-64 h-64 rounded-full blur-3xl opacity-20"
          style={{ background: 'radial-gradient(circle, #E1306C, #833AB4)' }} />

        <div className="relative flex items-center justify-between">
          <div>
            <div className="flex items-center gap-3 mb-3">
              <IGLogoFilled size={48} />
              <div>
                <h1 className="text-3xl font-bold" style={{ fontFamily: 'var(--font-display)' }}>
                  <span className="ig-text">IG Scraper</span>
                </h1>
                <p className="text-white/50 text-sm">Instagram Analytics & Sentiment Dashboard</p>
              </div>
            </div>
            <p className="text-white/60 text-sm max-w-lg mt-4">
              Scrape komentar Instagram, analisis sentimen dengan IndoBERT, track engagement metrics — semuanya dalam satu dashboard.
            </p>
            <div className="flex gap-3 mt-6">
              <Link href="/main/scrapes" className="btn-ig flex items-center gap-2 text-sm">
                <Zap size={16} />
                Mulai Scrape
              </Link>
              <Link href="/main/files" className="btn-glass flex items-center gap-2 text-sm">
                <FileJson size={16} />
                Lihat Hasil
                <ArrowRight size={14} />
              </Link>
            </div>
          </div>

          <div className="hidden lg:block">
            <IGLogoFilled size={120} className="opacity-20" />
          </div>
        </div>
      </div>

      {/* Status Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <StatCard
          label="Engine Status"
          value={health?.api === 'running' ? 'Online' : 'Offline'}
          sub={health?.engine_dir?.split('\\').pop() || '—'}
          color={health?.api === 'running' ? 'green' : 'red'}
          icon={<Activity size={16} className={health?.api === 'running' ? 'text-emerald-400' : 'text-red-400'} />}
          loading={loading}
        />
        <StatCard
          label="Session"
          value={session?.has_session ? 'Aktif' : 'Belum Login'}
          sub={session?.user_id || '—'}
          color={session?.is_valid ? 'blue' : 'orange'}
          icon={<Users size={16} className="text-blue-400" />}
          loading={loading}
        />
        <StatCard
          label="Output Files"
          value={files.length}
          sub="file JSON tersimpan"
          color="purple"
          icon={<FileJson size={16} className="text-purple-400" />}
          loading={loading}
        />
        <StatCard
          label="Total Diproses"
          value={files.length > 0 ? `${files.length}` : '0'}
          sub="post discrape"
          color="pink"
          icon={<TrendingUp size={16} className="text-pink-400" />}
          loading={loading}
        />
      </div>

      {/* Quick Actions */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
        {[
          {
            href: '/main/scrapes',
            title: 'Scrape Post',
            desc: 'Ambil komentar & analisis sentimen dari URL Instagram',
            icon: '🔍',
            color: 'var(--ig-pink)',
          },
          {
            href: '/main/profiles',
            title: 'Track Profile',
            desc: 'Monitor followers, engagement rate, dan pertumbuhan akun',
            icon: '👤',
            color: 'var(--ig-purple)',
          },
          {
            href: '/main/analytics',
            title: 'Analytics',
            desc: 'Visualisasi data sentimen, hashtag, dan engagement metrics',
            icon: '📊',
            color: 'var(--ig-blue)',
          },
        ].map(item => (
          <Link
            key={item.href}
            href={item.href}
            className="glass-card p-6 group"
          >
            <div className="text-3xl mb-3">{item.icon}</div>
            <h3 className="font-semibold text-white mb-1.5" style={{ fontFamily: 'var(--font-display)' }}>
              {item.title}
            </h3>
            <p className="text-sm text-white/50 leading-relaxed">{item.desc}</p>
            <div
              className="flex items-center gap-1 mt-4 text-sm font-medium opacity-0 group-hover:opacity-100 transition-opacity"
              style={{ color: item.color }}
            >
              Buka <ArrowRight size={14} />
            </div>
          </Link>
        ))}
      </div>

      {/* Recent Files */}
      {files.length > 0 && (
        <div className="glass-card p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-semibold" style={{ fontFamily: 'var(--font-display)' }}>
              File Terbaru
            </h2>
            <Link href="/main/files" className="text-xs text-white/40 hover:text-white/70 transition-colors">
              Lihat semua →
            </Link>
          </div>
          <div className="space-y-2">
            {files.slice(0, 5).map(f => (
              <div key={f.name} className="flex items-center gap-3 py-2 border-b border-white/[0.04] last:border-0">
                <FileJson size={16} className="text-purple-400 flex-shrink-0" />
                <span className="text-sm text-white/70 flex-1 truncate font-mono text-xs">{f.name}</span>
                <span className="text-xs text-white/30">{(f.size / 1024).toFixed(1)} KB</span>
                <span className="text-xs text-white/30 hidden md:block">
                  {new Date(f.modified).toLocaleDateString('id-ID')}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}