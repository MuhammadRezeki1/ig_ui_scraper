'use client'

import { useState, useEffect, useSyncExternalStore } from 'react'
import { useRouter } from 'next/navigation'
import { Users, Search, Loader2, AlertCircle, Eye, CheckCircle, Clock, ShieldCheck } from 'lucide-react'
import { listProfiles, scrapeProfile } from '@/lib/api'
import type { Profile } from '@/types'
import { IGLogoFilled } from '@/components/ui/IGLogo'
import { scrapeStore } from '@/lib/scrapeStore'

function useScrapeStatus() {
  return useSyncExternalStore(
    scrapeStore.subscribe,
    () => scrapeStore.isBusy(),
    () => false,
  )
}

export default function ProfilesPage() {
  const router = useRouter()

  const [profiles, setProfiles] = useState<Profile[]>([])
  const [loading, setLoading] = useState(true)
  const [scrapeUsername, setScrapeUsername] = useState('')
  const [scraping, setScraping] = useState(false)
  const [scrapeResult, setScrapeResult] = useState<Profile | null>(null)
  const [error, setError] = useState('')
  const [warning, setWarning] = useState('')

  const globalBusy = useScrapeStatus()

  useEffect(() => {
    listProfiles()
      .then(r => { if (r.success) setProfiles(r.data.users) })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    if (scrapeStore.isBusy()) {
      const st = scrapeStore.get()
      setWarning(
        `Masih ada proses scraping berjalan (${st.kind === 'batch' ? 'batch' : st.kind}: ${st.label}). ` +
        `Tunggu sampai selesai sebelum memulai scrape baru.`
      )
    }
  }, [])

  async function handleScrape() {
    if (scrapeStore.isBusy()) {
      setWarning('Tunggu dulu — proses scraping sebelumnya belum selesai.')
      return
    }

    const u = scrapeUsername.trim().replace('@', '')
    if (!u) { setError('Masukkan username'); return }

    setError('')
    setWarning('')
    setScrapeResult(null)

    if (!scrapeStore.begin('profile', `@${u}`)) {
      setWarning('Tunggu dulu — proses scraping sebelumnya belum selesai.')
      return
    }

    setScraping(true)
    try {
      const resp = await scrapeProfile(u)
      if (!resp.success) throw new Error(resp.message)

      const prof = resp.data?.profile ?? resp.data
      if (!prof || !prof.username) {
        throw new Error('Data profile kosong / format tidak dikenali')
      }
      setScrapeResult(prof as Profile)

      listProfiles().then(r => { if (r.success) setProfiles(r.data.users) })
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Gagal scrape profile')
    } finally {
      setScraping(false)
      scrapeStore.finish()
    }
  }

  const disabled = scraping || globalBusy

  return (
    <div className="p-8 max-w-5xl">
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

      {/* Banner: scraping lain masih berjalan */}
      {globalBusy && !scraping && (
        <div className="glass-card p-4 mb-6 flex items-start gap-3 border border-yellow-500/20">
          <Clock size={18} className="text-yellow-400 shrink-0 mt-0.5 animate-pulse" />
          <div className="flex-1">
            <p className="text-sm text-yellow-300 font-medium">Scraping masih berjalan</p>
            <p className="text-xs text-white/50 mt-0.5">
              Proses scraping yang dimulai sebelumnya belum selesai. Tunggu sampai selesai sebelum memulai scrape baru.
              Hasil otomatis tersimpan — bisa dilihat di Output Files.
            </p>
            <button
              onClick={() => router.push('/main/files')}
              className="btn-glass text-xs mt-2"
            >
              Lihat Output Files
            </button>
          </div>
        </div>
      )}

      {/* Scrape Input */}
      <div className="glass-card p-6 mb-6">
        <h2 className="font-semibold mb-4 text-sm uppercase tracking-widest text-white/50">Scrape Profile Baru</h2>
        <div className="flex gap-3">
          <div className="relative flex-1">
            <input
              type="text"
              value={scrapeUsername}
              disabled={disabled}
              onChange={e => setScrapeUsername(e.target.value)}
              placeholder="paste url/link disini"
              className="input-glass pl-8 disabled:opacity-50"
              onKeyDown={e => e.key === 'Enter' && handleScrape()}
            />
          </div>
          <button onClick={handleScrape} disabled={disabled} className="btn-ig flex items-center gap-2 px-5 disabled:opacity-50 disabled:cursor-not-allowed">
            {disabled ? <Loader2 size={16} className="animate-spin" /> : <Search size={16} />}
            {scraping ? 'Memproses...' : globalBusy ? 'Menunggu...' : 'Scrape'}
          </button>
        </div>

        {warning && (
          <div className="mt-3 flex items-center gap-2 text-yellow-300 text-sm glass rounded-xl px-4 py-2.5">
            <Clock size={14} /> {warning}
          </div>
        )}
        {error && (
          <div className="mt-3 flex items-center gap-2 text-red-400 text-sm glass rounded-xl px-4 py-2.5">
            <AlertCircle size={14} /> {error}
          </div>
        )}

        {/* Scrape Result */}
        {scrapeResult && (
          <div className="mt-4 glass rounded-2xl p-5">
            <div className="flex items-start gap-4">
              <div className="w-16 h-16 rounded-full overflow-hidden glass flex items-center justify-center text-2xl shrink-0">
                {scrapeResult.profile_pic_url ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={scrapeResult.profile_pic_url} alt={scrapeResult.username}
                    className="w-full h-full object-cover"
                    onError={(e) => { (e.target as HTMLImageElement).style.display = 'none' }} />
                ) : (
                  <Users size={24} className="text-white/30" />
                )}
              </div>
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-1">
                  <h3 className="font-bold text-lg">@{scrapeResult.username}</h3>
                  {scrapeResult.is_verified && <CheckCircle size={18} className="text-blue-400" />}
                </div>
                <p className="text-white/60 text-sm mb-3">{scrapeResult.full_name}</p>
                <div className="grid grid-cols-3 gap-3">
                  {[
                    { label: 'Followers', value: scrapeResult.followers?.toLocaleString('id-ID') || '—' },
                    { label: 'Following', value: scrapeResult.following?.toLocaleString('id-ID') || '—' },
                    { label: 'Posts',     value: scrapeResult.posts_count?.toLocaleString('id-ID') || '—' },
                  ].map(s => (
                    <div key={s.label} className="glass rounded-xl p-3 text-center">
                      <p className="text-lg font-bold ig-text">{s.value}</p>
                      <p className="text-xs text-white/40">{s.label}</p>
                    </div>
                  ))}
                </div>
                {scrapeResult.engagement_summary && (
                  <div className="mt-3 flex items-center gap-4 text-xs text-white/50">
                    <span>📊 {scrapeResult.engagement_summary.posts_analyzed} post dianalisis</span>
                    <span className="text-emerald-400 font-semibold">
                      {scrapeResult.engagement_summary.engagement_rate}% engagement
                    </span>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Tracked Profiles */}
      <div className="glass-card p-6">
        <h2 className="font-semibold mb-4 flex items-center gap-2" style={{ fontFamily: 'var(--font-display)' }}>
          <Users size={18} className="text-white/50" />
          Tracked Profiles
          {!loading && <span className="text-white/30 font-normal text-sm">({profiles.length})</span>}
        </h2>

        {loading ? (
          <div className="space-y-3">
            {[1,2,3].map(i => <div key={i} className="skeleton h-16 rounded-xl" />)}
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
              <div key={p.username} className="glass rounded-xl px-4 py-3.5 flex items-center gap-4 hover:bg-white/[0.07] transition-colors">
                <div className="w-10 h-10 rounded-full glass flex items-center justify-center shrink-0">
                  <Users size={16} className="text-white/40" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-sm">@{p.username}</span>
                    {p.is_verified && <CheckCircle size={14} className="text-blue-400" />}
                  </div>
                  <p className="text-xs text-white/40 truncate">{p.full_name || p.category || ''}</p>
                </div>
                <div className="hidden md:flex items-center gap-6 text-xs">
                  <div className="text-center">
                    <p className="font-bold text-white/80">{(p.followers || 0).toLocaleString('id-ID')}</p>
                    <p className="text-white/30">followers</p>
                  </div>
                  <div className="text-center">
                    <p className="font-bold text-white/80">{(p.posts_count || 0).toLocaleString('id-ID')}</p>
                    <p className="text-white/30">posts</p>
                  </div>
                  {p.engagement_summary && (
                    <div className="text-center">
                      <p className="font-bold text-emerald-400">{p.engagement_summary.engagement_rate}%</p>
                      <p className="text-white/30">engagement</p>
                    </div>
                  )}
                </div>
                <button className="btn-glass text-xs flex items-center gap-1.5 shrink-0">
                  <Eye size={12} /> Detail
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}