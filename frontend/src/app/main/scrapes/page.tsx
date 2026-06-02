'use client'

import { useState, useEffect, useSyncExternalStore } from 'react'
import { useRouter } from 'next/navigation'
import {
  Search, Link2, Loader2, AlertCircle, ChevronDown, ChevronUp,
  Plus, Trash2, CheckCircle, XCircle, Clock, MessageCircle,
} from 'lucide-react'
import { scrapePost, scrapePosts } from '@/lib/api'
import type { PostResult, Comment } from '@/types'
import { StatCard } from '@/components/ui/StatCard'
import { SentimentChart } from '@/components/features/SentimentChart'
import { CommentList } from '@/components/features/CommentList'
import { IGLogoFilled } from '@/components/ui/IGLogo'
import { scrapeStore } from '@/lib/scrapeStore'

type Mode = 'single' | 'batch'

interface BatchItem {
  url: string
  success: boolean
  data?: PostResult
  error?: string
}

function useScrapeStatus() {
  return useSyncExternalStore(
    scrapeStore.subscribe,
    () => scrapeStore.isBusy(),
    () => false,
  )
}

export default function ScrapePage() {
  const router = useRouter()

  const [mode, setMode] = useState<Mode>('single')
  const [url, setUrl] = useState('')
  const [batchUrls, setBatchUrls] = useState<string[]>(['', ''])
  const [maxComments, setMaxComments] = useState(100)

  // ── BARU: opsi replies ─────────────────────────────────────
  const [includeReplies, setIncludeReplies] = useState(true)
  const [maxRepliesPerComment, setMaxRepliesPerComment] = useState(20)

  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [warning, setWarning] = useState('')

  // Hasil single
  const [result, setResult] = useState<PostResult | null>(null)
  const [showComments, setShowComments] = useState(false)

  // Hasil batch
  const [batchResults, setBatchResults] = useState<BatchItem[] | null>(null)
  const [batchSummary, setBatchSummary] = useState<{ total: number; success: number; failed: number } | null>(null)
  const [openComments, setOpenComments] = useState<number | null>(null)

  const globalBusy = useScrapeStatus()

  useEffect(() => {
    if (scrapeStore.isBusy()) {
      const st = scrapeStore.get()
      setWarning(
        `Masih ada proses scraping berjalan (${st.kind === 'batch' ? 'batch' : 'single'}: ${st.label}). ` +
        `Tunggu sampai selesai. Hasil akan otomatis tersimpan dan bisa dilihat di Output Files.`
      )
    }
  }, [])

  async function handleScrape() {
    if (scrapeStore.isBusy()) {
      setWarning('Tunggu dulu — proses scraping sebelumnya belum selesai.')
      return
    }

    const target = mode === 'single' ? url.trim() : ''
    if (mode === 'single' && !target) { setError('Masukkan URL post/reel Instagram'); return }
    const validBatch = batchUrls.filter(u => u.trim())
    if (mode === 'batch' && validBatch.length === 0) { setError('Masukkan minimal 1 URL'); return }

    setError('')
    setWarning('')
    setResult(null)
    setBatchResults(null)
    setBatchSummary(null)
    setOpenComments(null)

    const label = mode === 'single' ? target : `${validBatch.length} URL`
    if (!scrapeStore.begin(mode, label)) {
      setWarning('Tunggu dulu — proses scraping sebelumnya belum selesai.')
      return
    }

    setLoading(true)

    const opts = {
      include_replies: includeReplies,
      max_replies_per_comment: maxRepliesPerComment,
    }

    try {
      if (mode === 'single') {
        const resp = await scrapePost(target, maxComments, opts)
        if (!resp.success) throw new Error(resp.message)
        setResult(resp.data)
        setShowComments(false)
      } else {
        const resp = await scrapePosts(validBatch, maxComments, 8, opts)
        if (!resp.success) throw new Error(resp.message)

        const data = resp.data as {
          total?: number
          success?: number
          failed?: number
          results?: BatchItem[]
        }
        setBatchResults(data.results || [])
        setBatchSummary({
          total: data.total ?? (data.results?.length || 0),
          success: data.success ?? (data.results?.filter(r => r.success).length || 0),
          failed: data.failed ?? (data.results?.filter(r => !r.success).length || 0),
        })
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Terjadi kesalahan')
    } finally {
      setLoading(false)
      scrapeStore.finish()
    }
  }

  const s = result?.sentiment_summary
  const disabled = loading || globalBusy

  // ── Hitung total reply dari semua komentar (kalau backend gak kirim total_replies) ─
  const totalRepliesFromComments = (comments?: Comment[]) =>
    (comments || []).reduce((acc, c) => acc + (c.replies?.length || 0), 0)

  return (
    <div className="p-8 max-w-5xl">
      {/* Header */}
      <div className="flex items-center gap-3 mb-8">
        <IGLogoFilled size={36} />
        <div>
          <h1 className="text-2xl font-bold" style={{ fontFamily: 'var(--font-display)' }}>
            Scrape Post
          </h1>
          <p className="text-sm text-white/40">Ambil komentar + balasan + analisis sentimen dari Instagram</p>
        </div>
      </div>

      {/* Banner peringatan: proses masih berjalan */}
      {globalBusy && !loading && (
        <div className="glass-card p-4 mb-6 flex items-start gap-3 border border-yellow-500/20">
          <Clock size={18} className="text-yellow-400 shrink-0 mt-0.5 animate-pulse" />
          <div className="flex-1">
            <p className="text-sm text-yellow-300 font-medium">Scraping masih berjalan</p>
            <p className="text-xs text-white/50 mt-0.5">
              Proses yang kamu mulai sebelumnya belum selesai. Tunggu sampai selesai sebelum memulai scrape baru.
              Hasil otomatis tersimpan — kamu bisa cek di Output Files.
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

      {/* Mode Toggle */}
      <div className="glass-card p-1 inline-flex mb-6 gap-1">
        {(['single', 'batch'] as Mode[]).map(m => (
          <button
            key={m}
            onClick={() => !disabled && setMode(m)}
            disabled={disabled}
            className={`px-5 py-2 rounded-xl text-sm font-medium transition-all ${
              mode === m ? 'bg-white/10 text-white' : 'text-white/40 hover:text-white/70'
            } ${disabled ? 'opacity-50 cursor-not-allowed' : ''}`}
          >
            {m === 'single' ? '🔗 Single URL' : '📋 Batch URLs'}
          </button>
        ))}
      </div>

      {/* Input Card */}
      <div className="glass-card p-6 mb-6">
        {mode === 'single' ? (
          <div className="mb-4">
            <label className="block text-xs text-white/50 mb-2 uppercase tracking-widest">URL Post / Reel</label>
            <div className="relative">
              <Link2 size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-white/30" />
              <input
                type="url"
                value={url}
                onChange={e => setUrl(e.target.value)}
                placeholder="https://www.instagram.com/p/xxxxxxx/"
                className="input-glass pl-10"
                disabled={disabled}
                onKeyDown={e => e.key === 'Enter' && handleScrape()}
              />
            </div>
          </div>
        ) : (
          <div className="mb-4">
            <label className="block text-xs text-white/50 mb-2 uppercase tracking-widest">Daftar URL</label>
            <div className="space-y-2">
              {batchUrls.map((u, i) => (
                <div key={i} className="flex gap-2">
                  <div className="relative flex-1">
                    <Link2 size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-white/30" />
                    <input
                      type="url"
                      value={u}
                      disabled={disabled}
                      onChange={e => {
                        const copy = [...batchUrls]
                        copy[i] = e.target.value
                        setBatchUrls(copy)
                      }}
                      placeholder={`URL #${i + 1}`}
                      className="input-glass pl-9 text-sm"
                    />
                  </div>
                  {batchUrls.length > 1 && (
                    <button
                      onClick={() => !disabled && setBatchUrls(batchUrls.filter((_, idx) => idx !== i))}
                      disabled={disabled}
                      className="glass rounded-xl p-2.5 text-white/40 hover:text-red-400 transition-colors disabled:opacity-50"
                    >
                      <Trash2 size={14} />
                    </button>
                  )}
                </div>
              ))}
              <button
                onClick={() => !disabled && setBatchUrls([...batchUrls, ''])}
                disabled={disabled}
                className="btn-glass flex items-center gap-2 text-sm w-full justify-center disabled:opacity-50"
              >
                <Plus size={14} /> Tambah URL
              </button>
            </div>
          </div>
        )}

        {/* Max Comments + Replies Options */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
          {/* Max Comments */}
          <div>
            <label className="block text-xs text-white/50 mb-2 uppercase tracking-widest">
              Max Komentar: <span className="text-white/80 normal-case">{maxComments}</span>
            </label>
            <input
              type="range"
              min={10}
              max={100}
              step={10}
              value={maxComments}
              disabled={disabled}
              onChange={e => setMaxComments(Number(e.target.value))}
              className="w-full accent-pink-500 h-1.5"
            />
            <div className="flex justify-between text-[10px] text-white/20 mt-1">
              <span>10</span><span>50</span><span>100</span>
            </div>
          </div>

          {/* Max Replies per Comment */}
          <div>
            <label className="block text-xs text-white/50 mb-2 uppercase tracking-widest">
              Max Balasan / komentar: <span className="text-white/80 normal-case">{maxRepliesPerComment}</span>
            </label>
            <input
              type="range"
              min={0}
              max={50}
              step={5}
              value={maxRepliesPerComment}
              disabled={disabled || !includeReplies}
              onChange={e => setMaxRepliesPerComment(Number(e.target.value))}
              className="w-full accent-purple-500 h-1.5 disabled:opacity-30"
            />
            <div className="flex justify-between text-[10px] text-white/20 mt-1">
              <span>0</span><span>25</span><span>50</span>
            </div>
          </div>
        </div>

        {/* Toggle Include Replies + Button */}
        <div className="flex items-center gap-4">
          <label
            className={`flex items-center gap-2 cursor-pointer select-none ${disabled ? 'opacity-50 cursor-not-allowed' : ''}`}
          >
            <div className="relative">
              <input
                type="checkbox"
                checked={includeReplies}
                onChange={e => setIncludeReplies(e.target.checked)}
                disabled={disabled}
                className="sr-only peer"
              />
              <div className="w-10 h-5 rounded-full bg-white/10 peer-checked:bg-pink-500/60 transition-colors" />
              <div className="absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform peer-checked:translate-x-5" />
            </div>
            <MessageCircle size={14} className="text-white/40" />
            <span className="text-xs text-white/70">Sertakan balasan komentar</span>
          </label>

          <div className="flex-1" />

          <button
            onClick={handleScrape}
            disabled={disabled}
            className="btn-ig flex items-center gap-2 px-6 py-3 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {disabled ? <Loader2 size={16} className="animate-spin" /> : <Search size={16} />}
            {loading ? 'Memproses...' : globalBusy ? 'Menunggu...' : 'Scrape'}
          </button>
        </div>

        {warning && (
          <div className="mt-4 flex items-center gap-2 text-yellow-300 text-sm glass rounded-xl px-4 py-3">
            <Clock size={16} className="shrink-0" />
            {warning}
          </div>
        )}

        {error && (
          <div className="mt-4 flex items-center gap-2 text-red-400 text-sm glass rounded-xl px-4 py-3">
            <AlertCircle size={16} className="shrink-0" />
            {error}
          </div>
        )}
      </div>

      {/* Loading State */}
      {loading && (
        <div className="glass-card p-12 text-center mb-6">
          <div className="relative w-16 h-16 mx-auto mb-4">
            <IGLogoFilled size={64} className="opacity-30" />
            <div className="absolute inset-0 animate-spin-slow">
              <div className="w-full h-full rounded-full border-2 border-transparent border-t-pink-500" />
            </div>
          </div>
          <p className="text-white/60 text-sm">Sedang scraping Instagram...</p>
          <p className="text-white/30 text-xs mt-1">
            {includeReplies
              ? 'Mengambil komentar + balasan, bisa makan waktu 1-3 menit'
              : mode === 'batch'
                ? 'Batch bisa makan waktu beberapa menit'
                : 'Bisa memakan waktu 30-60 detik'}
          </p>
          <p className="text-white/30 text-xs mt-1">Jangan pindah halaman agar hasil langsung tampil di sini.</p>
          <div className="flex justify-center gap-3 mt-4">
            {['Buka browser', 'Ambil komentar', ...(includeReplies ? ['Ambil balasan'] : []), 'Analisis sentimen'].map((step, i) => (
              <div key={i} className="flex items-center gap-1 text-xs text-white/30">
                <div className="w-1.5 h-1.5 rounded-full bg-pink-500 animate-pulse" style={{ animationDelay: `${i * 0.3}s` }} />
                {step}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ============ HASIL SINGLE ============ */}
      {result && s && (
        <div className="space-y-6">
          {/* Post Info */}
          <div className="glass-card p-6">
            <div className="flex items-start justify-between mb-4">
              <div>
                <h2 className="font-semibold text-lg" style={{ fontFamily: 'var(--font-display)' }}>
                  @{result.owner_username || 'unknown'}
                </h2>
                <p className="text-xs text-white/40 mt-0.5">
                  {result.media_type} · {result.product_type || 'feed'} · {result.method}
                </p>
              </div>
              <a
                href={result.url}
                target="_blank"
                rel="noopener noreferrer"
                className="btn-glass text-xs flex items-center gap-1.5"
              >
                <Link2 size={12} /> Buka Post
              </a>
            </div>
            {result.caption && (
              <p className="text-sm text-white/50 leading-relaxed line-clamp-3 mb-4 border-l-2 border-white/10 pl-3">
                {result.caption}
              </p>
            )}
          </div>

          {/* Engagement Stats */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <StatCard label="Likes"        value={result.likes}        color="pink"   />
            <StatCard label="Komentar"     value={result.comments_count} color="purple" />
            {(result.replies_count ?? totalRepliesFromComments(result.comments)) > 0 && (
              <StatCard
                label="Balasan"
                value={result.replies_count ?? totalRepliesFromComments(result.comments)}
                color="blue"
              />
            )}
            {result.video_views > 0 && <StatCard label="Video Views" value={result.video_views} color="blue" />}
            {result.saves_count > 0  && <StatCard label="Saves"       value={result.saves_count}  color="orange" />}
            {result.shares_count > 0 && <StatCard label="Shares"      value={result.shares_count} color="yellow" />}
          </div>

          {/* Sentiment Summary */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="glass-card p-6">
              <h3 className="font-semibold mb-4 text-sm uppercase tracking-widest text-white/50">
                Distribusi Sentimen (Parent)
              </h3>
              <SentimentChart summary={s} />
            </div>

            <div className="glass-card p-6">
              <h3 className="font-semibold mb-4 text-sm uppercase tracking-widest text-white/50">Detail Sentimen</h3>
              <div className="space-y-3">
                {[
                  { label: '😊 Positif',    count: s.positive_count,    pct: s.positive_percentage,   color: '#22c55e' },
                  { label: '😞 Negatif',    count: s.negative_count,    pct: s.negative_percentage,   color: '#f87171' },
                  { label: '😐 Netral',     count: s.neutral_count,     pct: s.neutral_percentage,    color: '#94a3b8' },
                  { label: '😂 Humor',      count: s.humor_count,       pct: s.humor_percentage,      color: '#818cf8' },
                  { label: '⚠️ Toxic',      count: s.toxic_count,       pct: s.toxic_percentage,      color: '#fde047' },
                  { label: '🚨 Hate Speech',count: s.hate_speech_count, pct: s.hate_percentage,       color: '#ef4444' },
                ].map(item => (
                  <div key={item.label}>
                    <div className="flex justify-between text-sm mb-1">
                      <span className="text-white/70">{item.label}</span>
                      <span className="text-white/50">{item.count} ({item.pct}%)</span>
                    </div>
                    <div className="progress-bar">
                      <div className="progress-fill" style={{ width: `${item.pct}%`, background: item.color }} />
                    </div>
                  </div>
                ))}
              </div>
              {s.sarcasm_count > 0 && (
                <p className="text-xs text-white/40 mt-4">
                  🎭 Sarkasme: {s.sarcasm_count} ({s.sarcasm_percentage}%) &nbsp;
                  🙏 Doa/Wellwish: {s.wellwish_count} ({s.wellwish_percentage}%)
                </p>
              )}
            </div>
          </div>

          {/* Replies Sentiment (kalau ada) */}
          {s.replies_sentiment_breakdown && (s.total_replies ?? 0) > 0 && (
            <div className="glass-card p-6">
              <h3 className="font-semibold mb-4 text-sm uppercase tracking-widest text-white/50">
                💬 Distribusi Sentimen (Balasan) — total {s.total_replies}
              </h3>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                {[
                  { label: '😊 Positif',     k: 'positive_percentage',     v: s.replies_sentiment_breakdown.positive_count, color: 'text-emerald-400' },
                  { label: '😞 Negatif',     k: 'negative_percentage',     v: s.replies_sentiment_breakdown.negative_count, color: 'text-rose-400' },
                  { label: '😐 Netral',      k: 'neutral_percentage',      v: s.replies_sentiment_breakdown.neutral_count,  color: 'text-white/60' },
                  { label: '😂 Humor',       k: 'humor_percentage',        v: s.replies_sentiment_breakdown.humor_count,    color: 'text-indigo-400' },
                  { label: '⚠️ Toxic',       k: 'toxic_percentage',        v: s.replies_sentiment_breakdown.toxic_count,    color: 'text-yellow-400' },
                  { label: '🚨 Hate',        k: 'hate_percentage',         v: s.replies_sentiment_breakdown.hate_speech_count, color: 'text-red-400' },
                ].map((item) => (
                  <div key={item.label} className="glass rounded-xl p-3 text-center">
                    <p className={`text-base font-bold ${item.color}`}>
                      {(s.replies_sentiment_breakdown as unknown as Record<string, number>)[item.k]}%
                    </p>
                    <p className="text-[11px] text-white/40 mt-0.5">{item.label} ({item.v})</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Top Commented */}
          {s.top_liked?.length > 0 && (
            <div className="glass-card p-6">
              <h3 className="font-semibold mb-4 text-sm uppercase tracking-widest text-white/50">🔥 Top Komentar (Likes)</h3>
              <div className="space-y-3">
                {s.top_liked.slice(0, 5).map((c, i) => (
                  <div key={i} className="flex gap-3 items-start py-2 border-b border-white/4 last:border-0">
                    <span className="text-lg font-bold text-white/20 w-6 shrink-0">#{i + 1}</span>
                    <div className="flex-1">
                      <p className="text-sm font-medium text-white/80 mb-0.5">@{c.username}</p>
                      <p className="text-sm text-white/50">{c.text}</p>
                    </div>
                    <div className="text-right shrink-0">
                      <p className="text-pink-400 font-bold text-sm">❤ {c.like_count}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Comments Toggle */}
          <div className="glass-card p-6">
            <button
              onClick={() => setShowComments(v => !v)}
              className="w-full flex items-center justify-between font-semibold text-sm"
            >
              <span>
                💬 Semua Komentar ({result.comments_count})
                {(result.replies_count ?? 0) > 0 && (
                  <span className="text-white/40 font-normal ml-1">
                    + {result.replies_count} balasan
                  </span>
                )}
              </span>
              {showComments ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
            </button>
            {showComments && (
              <div className="mt-4">
                <CommentList comments={result.comments} />
              </div>
            )}
          </div>
        </div>
      )}

      {/* ============ HASIL BATCH ============ */}
      {batchResults && batchSummary && (
        <div className="space-y-5">
          <div className="glass-card p-5 flex items-center gap-6">
            <div>
              <p className="text-2xl font-bold ig-text">{batchSummary.success}/{batchSummary.total}</p>
              <p className="text-xs text-white/40">post berhasil</p>
            </div>
            <div className="flex items-center gap-2 text-sm text-emerald-400">
              <CheckCircle size={16} /> {batchSummary.success} sukses
            </div>
            {batchSummary.failed > 0 && (
              <div className="flex items-center gap-2 text-sm text-red-400">
                <XCircle size={16} /> {batchSummary.failed} gagal
              </div>
            )}
          </div>

          {batchResults.map((item, idx) => {
            const d = item.data
            const ss = d?.sentiment_summary
            const isOpen = openComments === idx

            if (!item.success || !d) {
              return (
                <div key={idx} className="glass-card p-5 border border-red-500/20">
                  <div className="flex items-center gap-2 text-red-400 text-sm">
                    <XCircle size={16} className="shrink-0" />
                    <span className="font-medium">Gagal</span>
                  </div>
                  <p className="text-xs text-white/40 mt-1 break-all">{item.url}</p>
                  {item.error && <p className="text-xs text-red-400/70 mt-1">{item.error}</p>}
                </div>
              )
            }

            const replyTotal = d.replies_count ?? totalRepliesFromComments(d.comments)

            return (
              <div key={idx} className="glass-card p-5 space-y-4">
                <div className="flex items-start justify-between">
                  <div className="min-w-0">
                    <h3 className="font-semibold">@{d.owner_username || 'unknown'}</h3>
                    <p className="text-xs text-white/40 mt-0.5">
                      {d.media_type} · {d.product_type || 'feed'} · {d.method || '—'}
                    </p>
                  </div>
                  <a href={d.url} target="_blank" rel="noopener noreferrer"
                    className="btn-glass text-xs flex items-center gap-1.5 shrink-0">
                    <Link2 size={12} /> Buka
                  </a>
                </div>

                {d.caption && (
                  <p className="text-sm text-white/50 leading-relaxed line-clamp-2 border-l-2 border-white/10 pl-3">
                    {d.caption}
                  </p>
                )}

                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  <div className="glass rounded-xl p-3 text-center">
                    <p className="text-lg font-bold ig-text">{(d.likes || 0).toLocaleString('id-ID')}</p>
                    <p className="text-[11px] text-white/40">Likes</p>
                  </div>
                  <div className="glass rounded-xl p-3 text-center">
                    <p className="text-lg font-bold ig-text">{(d.comments_count || 0).toLocaleString('id-ID')}</p>
                    <p className="text-[11px] text-white/40">Komentar</p>
                  </div>
                  {replyTotal > 0 && (
                    <div className="glass rounded-xl p-3 text-center">
                      <p className="text-lg font-bold text-blue-400">{replyTotal.toLocaleString('id-ID')}</p>
                      <p className="text-[11px] text-white/40">Balasan</p>
                    </div>
                  )}
                  {ss && (
                    <div className="glass rounded-xl p-3 text-center">
                      <p className="text-lg font-bold text-emerald-400">{ss.positive_percentage}%</p>
                      <p className="text-[11px] text-white/40">Positif</p>
                    </div>
                  )}
                </div>

                {ss && ss.total_comments > 0 && (
                  <div>
                    <h4 className="text-xs font-medium text-white/50 uppercase tracking-widest mb-2">Sentimen</h4>
                    <SentimentChart summary={ss} />
                  </div>
                )}

                {ss && Array.isArray(ss.top_liked) && ss.top_liked.length > 0 && (
                  <div>
                    <h4 className="text-xs font-medium text-white/50 uppercase tracking-widest mb-2">🔥 Top Komentar (Likes)</h4>
                    <div className="space-y-2">
                      {ss.top_liked.slice(0, 5).map((c, i) => (
                        <div key={i} className="flex gap-3 items-start py-1.5 border-b border-white/4 last:border-0">
                          <span className="text-sm font-bold text-white/20 w-5 shrink-0">#{i + 1}</span>
                          <div className="flex-1 min-w-0">
                            <p className="text-xs font-medium text-white/80">@{c.username}</p>
                            <p className="text-xs text-white/50 line-clamp-2">{c.text}</p>
                          </div>
                          <p className="text-pink-400 font-bold text-xs shrink-0">❤ {(c.like_count || 0).toLocaleString('id-ID')}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {Array.isArray(d.comments) && d.comments.length > 0 && (
                  <div>
                    <button
                      onClick={() => setOpenComments(isOpen ? null : idx)}
                      className="w-full flex items-center justify-between text-sm font-medium"
                    >
                      <span>
                        💬 Semua Komentar ({d.comments_count})
                        {replyTotal > 0 && (
                          <span className="text-white/40 font-normal ml-1">
                            + {replyTotal} balasan
                          </span>
                        )}
                      </span>
                      {isOpen ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                    </button>
                    {isOpen && (
                      <div className="mt-3">
                        <CommentList comments={d.comments} />
                      </div>
                    )}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}