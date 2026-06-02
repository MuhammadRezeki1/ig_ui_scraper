'use client'

import { useState } from 'react'
import { Heart, MessageCircle, AlertTriangle, Smile, Meh, Frown, Laugh, Shield } from 'lucide-react'
import type { Comment } from '@/types'
import { clsx } from 'clsx'

interface CommentListProps {
  comments: Comment[]
}

type FilterCategory = 'ALL' | 'POSITIVE' | 'NEGATIVE' | 'NEUTRAL' | 'HATE_SPEECH' | 'TOXIC' | 'HUMOR'

const CATEGORY_CONFIG: Record<string, { label: string; icon: React.ComponentType<{ size?: number }>; badgeClass: string }> = {
  POSITIVE:    { label: 'Positif',      icon: Smile,         badgeClass: 'badge-positive' },
  NEGATIVE:    { label: 'Negatif',      icon: Frown,         badgeClass: 'badge-negative' },
  NEUTRAL:     { label: 'Netral',       icon: Meh,           badgeClass: 'badge-neutral' },
  HATE_SPEECH: { label: 'Hate Speech',  icon: Shield,        badgeClass: 'badge-hate' },
  TOXIC:       { label: 'Toxic',        icon: AlertTriangle, badgeClass: 'badge-toxic' },
  HUMOR:       { label: 'Humor',        icon: Laugh,         badgeClass: 'badge-humor' },
}

const FILTERS: FilterCategory[] = ['ALL', 'POSITIVE', 'NEGATIVE', 'NEUTRAL', 'HATE_SPEECH', 'TOXIC', 'HUMOR']

export function CommentList({ comments }: CommentListProps) {
  const [filter, setFilter] = useState<FilterCategory>('ALL')
  const [page, setPage] = useState(1)
  const PER_PAGE = 20

  const filtered = filter === 'ALL' ? comments : comments.filter(c => c.category === filter)
  const total = filtered.length
  const paginated = filtered.slice(0, page * PER_PAGE)
  const hasMore = paginated.length < total

  return (
    <div>
      {/* Filter tabs */}
      <div className="flex gap-2 flex-wrap mb-4">
        {FILTERS.map(f => {
          const count = f === 'ALL' ? comments.length : comments.filter(c => c.category === f).length
          return (
            <button
              key={f}
              onClick={() => { setFilter(f); setPage(1) }}
              className={clsx(
                'px-3 py-1.5 rounded-lg text-xs font-medium transition-all duration-200',
                filter === f
                  ? 'bg-white/10 text-white border border-white/20'
                  : 'text-white/40 hover:text-white/70 border border-transparent'
              )}
            >
              {f === 'ALL' ? 'Semua' : CATEGORY_CONFIG[f]?.label || f}
              <span className="ml-1.5 opacity-60">({count})</span>
            </button>
          )
        })}
      </div>

      {/* List */}
      <div className="space-y-2">
        {paginated.map((c, i) => {
          const cfg = CATEGORY_CONFIG[c.category]
          const Icon = cfg?.icon || Meh
          return (
            <div
              key={c.comment_id || i}
              className="glass rounded-xl px-4 py-3 flex gap-3 items-start hover:bg-white/[0.07] transition-colors"
            >
              {/* Number */}
              <span className="text-[11px] text-white/20 font-mono w-6 flex-shrink-0 mt-0.5 text-right">
                {c.number}
              </span>

              {/* Content */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-sm font-semibold text-white/80">@{c.username}</span>
                  {cfg && (
                    <span className={`badge ${cfg.badgeClass}`}>
                      <Icon size={10} />
                      {cfg.label}
                    </span>
                  )}
                  {c.is_sarcasm && <span className="badge badge-neutral">🎭 Sarkas</span>}
                  {c.is_wellwish && <span className="badge badge-positive">🙏 Doa</span>}
                </div>
                <p className="text-sm text-white/60 leading-relaxed">{c.text}</p>
                {(c.hate_words?.length > 0 || c.toxic_words?.length > 0) && (
                  <div className="flex gap-1 flex-wrap mt-1.5">
                    {[...c.hate_words, ...c.toxic_words].map((w, wi) => (
                      <span key={wi} className="text-[10px] px-1.5 py-0.5 rounded bg-red-500/15 text-red-300 border border-red-500/20">
                        {w}
                      </span>
                    ))}
                  </div>
                )}
                {c.positive_words?.length > 0 && (
                  <div className="flex gap-1 flex-wrap mt-1.5">
                    {c.positive_words.map((w, wi) => (
                      <span key={wi} className="text-[10px] px-1.5 py-0.5 rounded bg-green-500/15 text-green-300 border border-green-500/20">
                        {w}
                      </span>
                    ))}
                  </div>
                )}
              </div>

              {/* Stats */}
              <div className="flex items-center gap-3 flex-shrink-0 text-xs text-white/30">
                {c.like_count > 0 && (
                  <span className="flex items-center gap-1">
                    <Heart size={11} className="text-pink-400" />
                    {c.like_count}
                  </span>
                )}
                {c.reply_count > 0 && (
                  <span className="flex items-center gap-1">
                    <MessageCircle size={11} />
                    {c.reply_count}
                  </span>
                )}
                {c.ml_confidence > 0 && (
                  <span className="text-[10px] opacity-50">{(c.ml_confidence * 100).toFixed(0)}%</span>
                )}
              </div>
            </div>
          )
        })}
      </div>

      {/* Load more */}
      {hasMore && (
        <button
          onClick={() => setPage(p => p + 1)}
          className="btn-glass w-full mt-4 text-sm"
        >
          Muat lebih banyak ({total - paginated.length} tersisa)
        </button>
      )}

      {filtered.length === 0 && (
        <div className="text-center py-12 text-white/30 text-sm">
          Tidak ada komentar dengan filter ini
        </div>
      )}
    </div>
  )
}
