'use client'

import { useState, useEffect, useSyncExternalStore } from 'react'
import { useRouter } from 'next/navigation'
import {
  Users, Loader2, AlertCircle, CheckCircle,
  ShieldCheck, ArrowRight, UserCheck, UserX,
  RefreshCw, ChevronDown, ChevronUp, Download, ArrowLeftRight, Layers,
} from 'lucide-react'
import { listProfiles, scrapeFollowers, scrapeFollowing, computeMutualFollow } from '@/lib/api'
import type { Profile, FollowerItem, MutualFollowAnalysis } from '@/types'
import { IGLogoFilled } from '@/components/ui/IGLogo'
import { scrapeStore, useScrapeTask } from '@/lib/scrapeStore'
import { ProfileDeepScrapePanel } from './ProfileDeepScrapePanel'

function useScrapeStatus() {
  return useSyncExternalStore(
    scrapeStore.subscribe,
    () => scrapeStore.isBusy(),
    () => false,
  )
}

function fmtNum(n: number | undefined): string {
  if (!n) return '0'
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M'
  if (n >= 1_000) return (n / 1_000).toFixed(1) + 'K'
  return n.toLocaleString('id-ID')
}

// ── Sub-komponen: Kartu Akun ──────────────────────────────────────────────
function AccountCard({
  item,
  badge,
  badgeColor,
}: {
  item: FollowerItem
  badge?: string
  badgeColor?: string
}) {
  return (
    <div className="glass rounded-xl px-3 py-2.5 flex items-center gap-3">
      <div className="w-9 h-9 rounded-full glass flex items-center justify-center shrink-0 text-xs font-bold text-white/40">
        {item.username.slice(0, 2).toUpperCase()}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-1.5 flex-wrap">
          <span className="font-semibold text-sm truncate">@{item.username}</span>
          {item.is_verified && <CheckCircle size={12} className="text-blue-400 shrink-0" />}
          {badge && (
            <span className={`text-[10px] px-1.5 py-0.5 rounded-full ${badgeColor ?? 'bg-white/10 text-white/50'}`}>
              {badge}
            </span>
          )}
        </div>
        {item.full_name && (
          <p className="text-xs text-white/40 truncate">{item.full_name}</p>
        )}
      </div>
      <a
        href={`https://instagram.com/${item.username}`}
        target="_blank"
        rel="noopener noreferrer"
        className="btn-glass text-[10px] px-2 py-1 shrink-0"
        onClick={e => e.stopPropagation()}
      >
        IG ↗
      </a>
    </div>
  )
}

// ── Sub-komponen: Tab panel hasil analisis ────────────────────────────────
type TabKey = 'mutuals' | 'not_following_back' | 'not_followed_back'

function MutualAnalysisPanel({ analysis }: { analysis: MutualFollowAnalysis }) {
  const [tab, setTab] = useState<TabKey>('mutuals')
  const [search, setSearch] = useState('')
  const [showAll, setShowAll] = useState(false)
  const PAGE = 30

  const lists: Record<TabKey, FollowerItem[]> = {
    mutuals: analysis.mutuals,
    not_following_back: analysis.not_following_back,
    not_followed_back: analysis.not_followed_back,
  }

  const filtered = lists[tab].filter(
    i =>
      !search ||
      i.username.toLowerCase().includes(search.toLowerCase()) ||
      i.full_name?.toLowerCase().includes(search.toLowerCase()),
  )

  const displayed = showAll ? filtered : filtered.slice(0, PAGE)

  const tabs: { key: TabKey; label: string; count: number; color: string; icon: React.ReactNode }[] = [
    {
      key: 'mutuals',
      label: 'Saling Follow',
      count: analysis.mutual_count,
      color: 'text-emerald-400',
      icon: <ArrowLeftRight size={13} />,
    },
    {
      key: 'not_following_back',
      label: 'Tidak Di-follow Balik',
      count: analysis.not_following_back.length,
      color: 'text-yellow-400',
      icon: <UserX size={13} />,
    },
    {
      key: 'not_followed_back',
      label: 'Tidak Follow Balik',
      count: analysis.not_followed_back.length,
      color: 'text-red-400',
      icon: <UserCheck size={13} />,
    },
  ]

  function downloadJSON() {
    const blob = new Blob([JSON.stringify(analysis, null, 2)], { type: 'application/json' })
    const url  = URL.createObjectURL(blob)
    const a    = document.createElement('a')
    a.href     = url
    a.download = `mutual_follow_${analysis.target_username}_${Date.now()}.json`
    a.click()
    URL.revokeObjectURL(url)
  }

  const badgeMap: Record<TabKey, { label: string; color: string }> = {
    mutuals:              { label: 'Saling Follow',        color: 'bg-emerald-500/20 text-emerald-300' },
    not_following_back:   { label: 'Tidak Di-follow Balik', color: 'bg-yellow-500/20 text-yellow-300' },
    not_followed_back:    { label: 'Tidak Follow Balik',    color: 'bg-red-500/20 text-red-300' },
  }

  return (
    <div className="glass-card p-5 mt-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
        <div>
          <h2 className="font-bold text-base">
            Analisis Follow — @{analysis.target_username}
          </h2>
          <p className="text-xs text-white/40 mt-0.5">
            {fmtNum(analysis.followers_count)} followers · {fmtNum(analysis.following_count)} following
            · dianalisis {new Date(analysis.scraped_at).toLocaleString('id-ID')}
          </p>
        </div>
        <button onClick={downloadJSON} className="btn-glass text-xs flex items-center gap-1.5">
          <Download size={13} /> Export JSON
        </button>
      </div>

      {/* Stats strip */}
      <div className="grid grid-cols-3 gap-3 mb-5">
        {tabs.map(t => (
          <div key={t.key} className="glass rounded-xl p-3 text-center">
            <p className={`text-xl font-bold ${t.color}`}>{fmtNum(t.count)}</p>
            <p className="text-[11px] text-white/40 mt-0.5">{t.label}</p>
          </div>
        ))}
      </div>

      {/* Tab bar */}
      <div className="flex gap-2 mb-4 overflow-x-auto pb-1">
        {tabs.map(t => (
          <button
            key={t.key}
            onClick={() => { setTab(t.key); setSearch(''); setShowAll(false) }}
            className={`btn-glass text-xs flex items-center gap-1.5 shrink-0 transition-all ${
              tab === t.key ? 'ring-1 ring-white/30 bg-white/10' : ''
            }`}
          >
            <span className={tab === t.key ? t.color : 'text-white/40'}>{t.icon}</span>
            {t.label}
            <span className={`font-bold ${tab === t.key ? t.color : 'text-white/30'}`}>
              {fmtNum(t.count)}
            </span>
          </button>
        ))}
      </div>

      {/* Search */}
      <input
        type="text"
        value={search}
        onChange={e => { setSearch(e.target.value); setShowAll(false) }}
        placeholder="Cari username..."
        className="input-glass text-sm mb-4"
      />

      {/* List */}
      {filtered.length === 0 ? (
        <p className="text-center text-white/30 text-sm py-8">Tidak ada data.</p>
      ) : (
        <>
          <div className="space-y-2">
            {displayed.map(item => (
              <AccountCard
                key={item.username}
                item={item}
                badge={badgeMap[tab].label}
                badgeColor={badgeMap[tab].color}
              />
            ))}
          </div>
          {filtered.length > PAGE && (
            <button
              onClick={() => setShowAll(v => !v)}
              className="btn-glass text-xs mt-3 w-full flex items-center justify-center gap-1.5"
            >
              {showAll ? <><ChevronUp size={13} /> Sembunyikan</> : <><ChevronDown size={13} /> Tampilkan semua ({filtered.length})</>}
            </button>
          )}
        </>
      )}
    </div>
  )
}

// ── Komponen scrape followers/following + analisis ────────────────────────
function FollowAnalysisSection({ username }: { username: string }) {
  const followKey = `profiles:follow:${username}`
  const [maxCount, setMaxCount] = useState(500)
  const [progress, setProgress] = useState('')

  // Hasil + status analisis persist lintas-navigasi via scrapeStore.
  const task      = useScrapeTask<MutualFollowAnalysis>(followKey)
  const isRunning  = task.status === 'running'
  const analysis   = task.status === 'success' ? task.data : null
  const error      = task.status === 'error' ? (task.error ?? '') : ''

  const globalBusy = useScrapeStatus()

  async function handleAnalyze() {
    if (scrapeStore.isBusy()) return

    setProgress(`Mengambil followers @${username}...`)
    // scrapeStore.run() menjaga proses + hasil tetap hidup walau pindah halaman.
    await scrapeStore.run<MutualFollowAnalysis>(
      followKey,
      'followers',
      `@${username}`,
      async () => {
        // Step 1: Followers
        setProgress(`Mengambil followers @${username}...`)
        const followersResp = await scrapeFollowers(username, maxCount)
        if (!followersResp.success) throw new Error(followersResp.message || 'Gagal ambil followers')
        const followers = followersResp.data?.items ?? []

        // Step 2: Following
        setProgress(`Mengambil following @${username}...`)
        const followingResp = await scrapeFollowing(username, maxCount)
        if (!followingResp.success) throw new Error(followingResp.message || 'Gagal ambil following')
        const following = followingResp.data?.items ?? []

        // Step 3: Compute
        return computeMutualFollow(username, followers, following)
      },
    )
    setProgress('')
  }

  return (
    <div className="glass-card p-6 mt-6">
      <h2 className="font-semibold mb-1 flex items-center gap-2 text-sm uppercase tracking-widest text-white/50">
        <ArrowLeftRight size={15} className="text-white/40" />
        Analisis Followers & Following
      </h2>
      <p className="text-xs text-white/30 mb-4">
        Scrape daftar followers dan following @{username}, lalu lihat siapa yang saling follow.
      </p>

      <div className="flex gap-3 items-end flex-wrap">
        <div>
          <label className="text-xs text-white/40 block mb-1">Max per list</label>
          <select
            value={maxCount}
            disabled={isRunning || globalBusy}
            onChange={e => setMaxCount(Number(e.target.value))}
            className="input-glass text-sm w-36 disabled:opacity-50"
          >
            {[100, 200, 500, 1000].map(n => (
              <option key={n} value={n}>{n} akun</option>
            ))}
          </select>
        </div>
        <button
          onClick={handleAnalyze}
          disabled={isRunning || globalBusy}
          className="btn-ig flex items-center gap-2 px-5 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isRunning
            ? <Loader2 size={15} className="animate-spin" />
            : <RefreshCw size={15} />}
          {isRunning ? 'Memproses...' : 'Mulai Analisis'}
        </button>
      </div>

      {isRunning && (
        <div className="mt-3 flex items-center gap-2 text-white/50 text-sm glass rounded-xl px-4 py-2.5">
          <Loader2 size={14} className="animate-spin text-indigo-400" />
          {progress || `Menganalisis followers & following @${username}...`}
        </div>
      )}

      {error && (
        <div className="mt-3 flex items-center gap-2 text-red-400 text-sm glass rounded-xl px-4 py-2.5">
          <AlertCircle size={14} /> {error}
        </div>
      )}

      {analysis && <MutualAnalysisPanel analysis={analysis} />}
    </div>
  )
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