'use client'

import { useState } from 'react'
import {
  Loader2, AlertCircle, CheckCircle,
  UserCheck, UserX, RefreshCw, ChevronDown, ChevronUp,
  Download, ArrowLeftRight,
} from 'lucide-react'
import { scrapeFollowers, scrapeFollowing, computeMutualFollow } from '@/lib/api'
import type { FollowerItem, MutualFollowAnalysis } from '@/types'
import { scrapeStore, useScrapeTask, useScrapeBusy } from '@/lib/scrapeStore'

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
export function FollowAnalysisSection({ username }: { username: string }) {
  const followKey = `profiles:follow:${username}`
  const [maxCount, setMaxCount] = useState(500)
  const [progress, setProgress] = useState('')

  // Hasil + status analisis persist lintas-navigasi via scrapeStore.
  const task      = useScrapeTask<MutualFollowAnalysis>(followKey)
  const isRunning  = task.status === 'running'
  const analysis   = task.status === 'success' ? task.data : null
  const error      = task.status === 'error' ? (task.error ?? '') : ''

  const globalBusy = useScrapeBusy()

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
