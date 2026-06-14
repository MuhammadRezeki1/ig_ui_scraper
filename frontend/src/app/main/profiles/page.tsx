'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import {
  Users, CheckCircle, ShieldCheck, ArrowRight, ArrowLeftRight, Layers,
} from 'lucide-react'
import { listProfiles } from '@/lib/api'
import type { Profile } from '@/types'
import { IGLogoFilled } from '@/components/ui/IGLogo'
import { ProfileDeepScrapePanel } from './ProfileDeepScrapePanel'
import { FollowAnalysisSection } from './FollowAnalysisSection'

function fmtNum(n: number | undefined): string {
  if (!n) return '0'
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M'
  if (n >= 1_000) return (n / 1_000).toFixed(1) + 'K'
  return n.toLocaleString('id-ID')
}

// ════════════════════════════════════════════════════════════════════════════
// MAIN PAGE
// ════════════════════════════════════════════════════════════════════════════

export default function ProfilesPage() {
  const router = useRouter()

  const [profiles, setProfiles] = useState<Profile[]>([])
  const [loading,  setLoading]  = useState(true)

  /** Username yang sedang ditampilkan panel analisis follow-nya */
  const [analysisTarget, setAnalysisTarget] = useState<string | null>(null)
  /** Username yang sedang ditampilkan panel deep scrape-nya */
  const [deepTarget, setDeepTarget] = useState<string | null>(null)

  useEffect(() => {
    listProfiles()
      .then(r => { if (r.success) setProfiles(r.data.users) })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  return (
    <div className="p-8 max-w-5xl">
      {/* ── Header ── */}
      <div className="flex items-center gap-3 mb-6">
        <IGLogoFilled size={36} />
        <div className="flex-1">
          <h1 className="text-2xl font-bold" style={{ fontFamily: 'var(--font-display)' }}>Profiles</h1>
          <p className="text-sm text-white/40">Track & analisis akun Instagram</p>
        </div>
        <button
          onClick={() => router.push('/main/verified-following')}
          className="btn-glass text-xs flex items-center gap-1.5"
        >
          <ShieldCheck size={14} className="text-blue-400" />
          Verified Following
        </button>
      </div>

      {/* ── Scrape Profil + Postingan (deep, satu langkah) ── */}
      <div className="glass-card p-6 mb-6">
        <ProfileDeepScrapePanel />
      </div>

      {/* ── Tracked Profiles ── */}
      <div className="glass-card p-6">
        <h2 className="font-semibold mb-4 flex items-center gap-2" style={{ fontFamily: 'var(--font-display)' }}>
          <Users size={18} className="text-white/50" />
          Tracked Profiles
          {!loading && <span className="text-white/30 font-normal text-sm">({profiles.length})</span>}
        </h2>

        {loading ? (
          <div className="space-y-3">
            {[1, 2, 3].map(i => <div key={i} className="skeleton h-16 rounded-xl" />)}
          </div>
        ) : profiles.length === 0 ? (
          <div className="text-center py-12 text-white/30 text-sm">
            <Users size={40} className="mx-auto mb-3 opacity-20" />
            <p>Belum ada profile yang di-track.</p>
            <p className="text-xs mt-1">Scrape profile di atas untuk memulai.</p>
          </div>
        ) : (
          <div className="space-y-3">
            {profiles.map(p => (
              <div key={p.username}>
                {/* Baris akun */}
                <div className="glass rounded-xl px-4 py-3.5 flex items-center gap-4 hover:bg-white/[0.07] transition-colors">
                  <div
                    className="w-10 h-10 rounded-full glass flex items-center justify-center shrink-0 cursor-pointer"
                    onClick={() => router.push(`/main/profiles/${p.username}`)}
                  >
                    <Users size={16} className="text-white/40" />
                  </div>
                  <div
                    className="flex-1 min-w-0 cursor-pointer"
                    onClick={() => router.push(`/main/profiles/${p.username}`)}
                  >
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-sm">@{p.username}</span>
                      {p.is_verified && <CheckCircle size={14} className="text-blue-400" />}
                    </div>
                    <p className="text-xs text-white/40 truncate">
                      {p.full_name || (p as Profile & { category?: string }).category || ''}
                    </p>
                  </div>
                  <div className="hidden md:flex items-center gap-6 text-xs">
                    <div className="text-center">
                      <p className="font-bold text-white/80">{fmtNum(p.followers)}</p>
                      <p className="text-white/30">followers</p>
                    </div>
                    <div className="text-center">
                      <p className="font-bold text-white/80">{fmtNum(p.posts_count)}</p>
                      <p className="text-white/30">posts</p>
                    </div>
                    {p.engagement_summary && (
                      <div className="text-center">
                        <p className="font-bold text-emerald-400">{p.engagement_summary.engagement_rate}%</p>
                        <p className="text-white/30">engagement</p>
                      </div>
                    )}
                  </div>
                  <div className="flex gap-2 shrink-0">
                    {/* Tombol analisis follow */}
                    <button
                      title="Analisis Followers & Following"
                      onClick={() =>
                        setAnalysisTarget(analysisTarget === p.username ? null : p.username)
                      }
                      className={`btn-glass text-xs flex items-center gap-1 px-2.5 py-1.5 transition-all ${
                        analysisTarget === p.username ? 'ring-1 ring-indigo-400/50 text-indigo-300' : ''
                      }`}
                    >
                      <ArrowLeftRight size={12} />
                      <span className="hidden sm:inline">Follow</span>
                    </button>
                    {/* Tombol deep scrape */}
                    <button
                      title="Deep Scrape (komentar, balasan & likers tiap post)"
                      onClick={() =>
                        setDeepTarget(deepTarget === p.username ? null : p.username)
                      }
                      className={`btn-glass text-xs flex items-center gap-1 px-2.5 py-1.5 transition-all ${
                        deepTarget === p.username ? 'ring-1 ring-pink-400/50 text-pink-300' : ''
                      }`}
                    >
                      <Layers size={12} />
                      <span className="hidden sm:inline">Deep</span>
                    </button>
                    {/* Tombol detail */}
                    <button
                      onClick={() => router.push(`/main/profiles/${p.username}`)}
                      className="btn-glass text-xs flex items-center gap-1.5"
                    >
                      Detail <ArrowRight size={12} />
                    </button>
                  </div>
                </div>

                {/* Panel analisis follow (expand di bawah baris) */}
                {analysisTarget === p.username && (
                  <div className="mt-2 ml-2 border-l-2 border-indigo-500/30 pl-4">
                    <FollowAnalysisSection username={p.username} />
                  </div>
                )}

                {/* Panel deep scrape (expand di bawah baris) */}
                {deepTarget === p.username && (
                  <div className="mt-2 ml-2 border-l-2 border-pink-500/30 pl-4">
                    <ProfileDeepScrapePanel initialUsername={p.username} locked />
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}