'use client'

import { useState, useEffect } from 'react'
import { FileJson, Eye, RefreshCw, Search, X, ChevronDown, ChevronUp, ExternalLink, CheckCircle, XCircle, Users } from 'lucide-react'
import { listOutputFiles, getOutputFile } from '@/lib/api'
import type { OutputFile } from '@/types'
import { SentimentChart } from '@/components/features/SentimentChart'
import { CommentList } from '@/components/features/CommentList'

// Tipe gabungan: file bisa berisi data POST, PROFILE, atau BATCH
type AnyResult = Record<string, any>

// Komponen reusable: daftar Top 5 komentar paling banyak like
function TopComments({ topLiked }: { topLiked?: any[] }) {
  if (!Array.isArray(topLiked) || topLiked.length === 0) return null
  return (
    <div className="glass-card p-5">
      <h4 className="text-xs font-medium text-white/50 uppercase tracking-widest mb-3">
        🔥 Top Komentar (Likes)
      </h4>
      <div className="space-y-2">
        {topLiked.slice(0, 5).map((c, i) => (
          <div key={i} className="flex gap-3 items-start py-2 border-b border-white/4 last:border-0">
            <span className="text-base font-bold text-white/20 w-6 shrink-0">#{i + 1}</span>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-white/80 mb-0.5">@{c.username}</p>
              <p className="text-sm text-white/50 line-clamp-2">{c.text}</p>
            </div>
            <p className="text-pink-400 font-bold text-sm shrink-0">❤ {(c.like_count || 0).toLocaleString('id-ID')}</p>
          </div>
        ))}
      </div>
    </div>
  )
}

export default function FilesPage() {
  const [files, setFiles] = useState<OutputFile[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [selected, setSelected] = useState<AnyResult | null>(null)
  const [selectedName, setSelectedName] = useState('')
  const [previewLoading, setPreviewLoading] = useState(false)
  const [showComments, setShowComments] = useState(false)
  // index post batch yang komentarnya sedang dibuka
  const [openBatchComment, setOpenBatchComment] = useState<number | null>(null)

  const load = () => {
    setLoading(true)
    listOutputFiles()
      .then(r => { if (r.success) setFiles(r.data.files) })
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  const filtered = files.filter(f => f.name.toLowerCase().includes(search.toLowerCase()))

  async function preview(filename: string) {
    setPreviewLoading(true)
    setSelected(null)
    setSelectedName(filename)
    setShowComments(false)
    setOpenBatchComment(null)
    try {
      const data = await getOutputFile(filename)
      // File profile dibungkus {profile:{...}, ...}. File batch punya results[].
      // File post langsung object. Normalisasi minimal: kalau ada wrapper profile, ratakan.
      const normalized = data?.profile && typeof data.profile === 'object' && !Array.isArray(data.results)
        ? { ...data.profile, ...data }
        : data
      setSelected(normalized)
    } catch { /* skip */ }
    finally { setPreviewLoading(false) }
  }

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  }

  // Deteksi jenis file
  const isBatch = (d: AnyResult) => d && Array.isArray(d.results)
  const isProfile = (d: AnyResult) =>
    d && !isBatch(d) && (d.followers !== undefined || d.posts_count !== undefined || d.method === 'web_profile_api')

  const displayUsername = (d: AnyResult) =>
    d?.username || d?.owner_username || d?.profile?.username || '—'

  const fmtNum = (n: any) =>
    typeof n === 'number' ? n.toLocaleString('id-ID') : (n ?? '—')

  return (
    <div className="p-8 max-w-7xl">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold" style={{ fontFamily: 'var(--font-display)' }}>Output Files</h1>
          <p className="text-sm text-white/40 mt-0.5">Semua hasil scraping tersimpan di sini</p>
        </div>
        <button onClick={load} disabled={loading} className="btn-glass flex items-center gap-2 text-sm">
          <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
          Refresh
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* File List */}
        <div>
          <div className="relative mb-4">
            <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-white/30" />
            <input
              type="text"
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="Cari file..."
              className="input-glass pl-9 text-sm"
            />
            {search && (
              <button onClick={() => setSearch('')} className="absolute right-3 top-1/2 -translate-y-1/2">
                <X size={14} className="text-white/30" />
              </button>
            )}
          </div>

          <div className="glass-card p-4">
            {loading ? (
              <div className="space-y-2">
                {[1,2,3,4,5].map(i => <div key={i} className="skeleton h-12 rounded-lg" />)}
              </div>
            ) : filtered.length === 0 ? (
              <div className="text-center py-12 text-white/30 text-sm">
                <FileJson size={40} className="mx-auto mb-3 opacity-20" />
                {files.length === 0 ? 'Belum ada file output.' : 'Tidak ada file yang cocok.'}
              </div>
            ) : (
              <div className="space-y-1.5 max-h-150 overflow-y-auto pr-1">
                {filtered.map(f => (
                  <button
                    key={f.name}
                    onClick={() => preview(f.name)}
                    className={`w-full text-left flex items-center gap-3 px-3 py-2.5 rounded-xl transition-all ${
                      selectedName === f.name
                        ? 'bg-white/10 border border-white/15'
                        : 'hover:bg-white/5 border border-transparent'
                    }`}
                  >
                    <FileJson size={16} className={
                      f.name.includes('batch') ? 'text-purple-400' :
                      f.name.includes('profile') ? 'text-blue-400' :
                      f.name.includes('post') ? 'text-pink-400' : 'text-white/40'
                    } />
                    <div className="flex-1 min-w-0">
                      <p className="text-xs font-mono text-white/80 truncate">{f.name}</p>
                      <p className="text-[10px] text-white/30 mt-0.5">
                        {formatSize(f.size)} · {new Date(f.modified).toLocaleString('id-ID')}
                      </p>
                    </div>
                    <Eye size={13} className="text-white/20 shrink-0" />
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Preview */}
        <div>
          {previewLoading && (
            <div className="glass-card p-12 text-center">
              <div className="animate-pulse text-white/30 text-sm">Memuat file...</div>
            </div>
          )}

          {/* ===== PREVIEW: BATCH ===== */}
          {selected && !previewLoading && isBatch(selected) && (
            <div className="space-y-4">
              <div className="glass-card p-5 flex items-center gap-6">
                <div>
                  <p className="text-2xl font-bold ig-text">
                    {selected.success ?? 0}/{selected.total ?? selected.results.length}
                  </p>
                  <p className="text-xs text-white/40">post berhasil</p>
                </div>
                <div className="flex items-center gap-2 text-sm text-emerald-400">
                  <CheckCircle size={16} /> {selected.success ?? 0} sukses
                </div>
                {(selected.failed ?? 0) > 0 && (
                  <div className="flex items-center gap-2 text-sm text-red-400">
                    <XCircle size={16} /> {selected.failed} gagal
                  </div>
                )}
              </div>

              {selected.results.map((item: AnyResult, idx: number) => {
                const d = item.data
                const ss = d?.sentiment_summary
                const isOpen = openBatchComment === idx

                if (!item.success || !d) {
                  return (
                    <div key={idx} className="glass-card p-4 border border-red-500/20">
                      <div className="flex items-center gap-2 text-red-400 text-sm">
                        <XCircle size={15} className="shrink-0" /> Gagal
                      </div>
                      <p className="text-xs text-white/40 mt-1 break-all">{item.url}</p>
                      {item.error && <p className="text-xs text-red-400/70 mt-1">{item.error}</p>}
                    </div>
                  )
                }

                return (
                  <div key={idx} className="glass-card p-5 space-y-3">
                    <div className="flex items-start justify-between">
                      <div className="min-w-0">
                        <h3 className="font-semibold">@{d.owner_username || 'unknown'}</h3>
                        <p className="text-xs text-white/40 mt-0.5">
                          {d.media_type} · {d.product_type || 'feed'} · {d.method || '—'}
                        </p>
                      </div>
                      {d.url && (
                        <a href={d.url} target="_blank" rel="noopener noreferrer"
                          className="btn-glass text-xs flex items-center gap-1.5 shrink-0">
                          <ExternalLink size={12} /> Buka
                        </a>
                      )}
                    </div>

                    <div className="grid grid-cols-3 gap-3">
                      {[
                        { l: 'Likes',    v: fmtNum(d.likes) },
                        { l: 'Komentar', v: fmtNum(d.comments_count) },
                        { l: 'Media',    v: d.media_type || '—' },
                      ].map(s => (
                        <div key={s.l} className="glass rounded-xl p-3 text-center">
                          <p className="text-base font-bold ig-text">{s.v}</p>
                          <p className="text-[11px] text-white/40">{s.l}</p>
                        </div>
                      ))}
                    </div>

                    {ss && ss.total_comments > 0 && <SentimentChart summary={ss} />}

                    {/* Top 5 komentar (likes) untuk post batch ini */}
                    {ss?.top_liked?.length > 0 && (
                      <div>
                        <h4 className="text-xs font-medium text-white/50 uppercase tracking-widest mb-2">
                          🔥 Top Komentar (Likes)
                        </h4>
                        <div className="space-y-2">
                          {ss.top_liked.slice(0, 5).map((c: any, i: number) => (
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
                          onClick={() => setOpenBatchComment(isOpen ? null : idx)}
                          className="w-full flex items-center justify-between text-sm font-medium"
                        >
                          <span>💬 Semua Komentar ({d.comments_count})</span>
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

          {/* ===== PREVIEW: PROFILE ===== */}
          {selected && !previewLoading && !isBatch(selected) && isProfile(selected) && (
            <div className="space-y-4">
              <div className="glass-card p-5">
                <div className="flex items-start gap-4 mb-4">
                  <div className="w-16 h-16 rounded-full overflow-hidden glass flex items-center justify-center shrink-0">
                    {selected.profile_pic_url ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img src={selected.profile_pic_url} alt={selected.username}
                        className="w-full h-full object-cover"
                        onError={(e) => { (e.target as HTMLImageElement).style.display = 'none' }} />
                    ) : (
                      <Users size={24} className="text-white/30" />
                    )}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <h3 className="font-bold text-lg truncate">@{displayUsername(selected)}</h3>
                      {selected.is_verified && <CheckCircle size={16} className="text-blue-400 shrink-0" />}
                    </div>
                    <p className="text-sm text-white/50 truncate">{selected.full_name || '—'}</p>
                    {selected.category && <p className="text-xs text-white/30 mt-0.5">{selected.category}</p>}
                  </div>
                </div>

                <div className="grid grid-cols-3 gap-3">
                  {[
                    { l: 'Followers', v: fmtNum(selected.followers) },
                    { l: 'Following', v: fmtNum(selected.following) },
                    { l: 'Posts',     v: fmtNum(selected.posts_count) },
                  ].map(s => (
                    <div key={s.l} className="glass rounded-xl p-3 text-center">
                      <p className="text-lg font-bold ig-text">{s.v}</p>
                      <p className="text-[11px] text-white/40">{s.l}</p>
                    </div>
                  ))}
                </div>

                {selected.scraped_at && (
                  <p className="text-[11px] text-white/30 mt-3">
                    Scraped: {new Date(selected.scraped_at).toLocaleString('id-ID')} · Method: {selected.method || '—'}
                  </p>
                )}
              </div>

              {selected.engagement_summary && (
                <div className="glass-card p-5">
                  <h4 className="text-xs font-medium text-white/50 uppercase tracking-widest mb-3">Engagement</h4>
                  {selected.engagement_summary.posts_analyzed > 0 ? (
                    <div className="grid grid-cols-2 gap-3 text-sm">
                      <div className="glass rounded-xl p-3">
                        <p className="text-white/40 text-xs">Engagement Rate</p>
                        <p className="font-bold text-emerald-400">{selected.engagement_summary.engagement_rate}%</p>
                      </div>
                      <div className="glass rounded-xl p-3">
                        <p className="text-white/40 text-xs">Post dianalisis</p>
                        <p className="font-bold">{selected.engagement_summary.posts_analyzed}</p>
                      </div>
                      <div className="glass rounded-xl p-3">
                        <p className="text-white/40 text-xs">Rata-rata Likes</p>
                        <p className="font-bold">{fmtNum(selected.engagement_summary.avg_likes)}</p>
                      </div>
                      <div className="glass rounded-xl p-3">
                        <p className="text-white/40 text-xs">Rata-rata Komentar</p>
                        <p className="font-bold">{fmtNum(selected.engagement_summary.avg_comments)}</p>
                      </div>
                    </div>
                  ) : (
                    <p className="text-sm text-white/40">
                      Belum ada post yang dianalisis (recent_posts kosong).
                    </p>
                  )}
                </div>
              )}
            </div>
          )}

          {/* ===== PREVIEW: POST ===== */}
          {selected && !previewLoading && !isBatch(selected) && !isProfile(selected) && (
            <div className="space-y-4">
              <div className="glass-card p-5">
                <div className="flex items-start justify-between mb-3">
                  <div>
                    <h3 className="font-semibold">@{displayUsername(selected)}</h3>
                    <p className="text-xs text-white/40 mt-0.5 font-mono">{selected.shortcode || '—'}</p>
                  </div>
                  {selected.url && (
                    <a href={selected.url} target="_blank" rel="noopener noreferrer"
                      className="btn-glass text-xs flex items-center gap-1.5">
                      <ExternalLink size={12} /> Buka
                    </a>
                  )}
                </div>

                <div className="grid grid-cols-3 gap-3 mb-3">
                  {[
                    { l: 'Likes',     v: fmtNum(selected.likes) },
                    { l: 'Komentar',  v: fmtNum(selected.comments_count) },
                    { l: 'Media',     v: selected.media_type || '—' },
                  ].map(s => (
                    <div key={s.l} className="glass rounded-xl p-3 text-center">
                      <p className="text-lg font-bold ig-text">{s.v}</p>
                      <p className="text-[11px] text-white/40">{s.l}</p>
                    </div>
                  ))}
                </div>

                {selected.scraped_at && (
                  <p className="text-[11px] text-white/30">
                    Scraped: {new Date(selected.scraped_at).toLocaleString('id-ID')} · Mode: {selected.sentiment_mode || '—'}
                  </p>
                )}
              </div>

              {selected.sentiment_summary && (
                <div className="glass-card p-5">
                  <h4 className="text-xs font-medium text-white/50 uppercase tracking-widest mb-3">Sentimen</h4>
                  <SentimentChart summary={selected.sentiment_summary} />
                </div>
              )}

              {/* Top 5 komentar (likes) untuk post tunggal */}
              <TopComments topLiked={selected.sentiment_summary?.top_liked} />

              {Array.isArray(selected.comments) && selected.comments.length > 0 && (
                <div className="glass-card p-5">
                  <button
                    onClick={() => setShowComments(v => !v)}
                    className="w-full flex items-center justify-between text-sm font-medium"
                  >
                    <span>💬 Semua Komentar ({selected.comments.length})</span>
                    {showComments ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                  </button>
                  {showComments && (
                    <div className="mt-4">
                      <CommentList comments={selected.comments} />
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {!selected && !previewLoading && (
            <div className="glass-card p-12 text-center text-white/20">
              <FileJson size={48} className="mx-auto mb-3 opacity-30" />
              <p className="text-sm">Pilih file untuk preview</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}