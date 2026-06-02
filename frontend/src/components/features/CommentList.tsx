'use client'

import { useState } from 'react'
import { ChevronDown, ChevronUp, CornerDownRight } from 'lucide-react'
import type { Comment } from '@/types'

// ── Helper: badge sentimen ────────────────────────────────────────
function badge(c: Comment): { label: string; cls: string } {
  if (c.is_hate_speech) return { label: '🚨 Hate',   cls: 'bg-red-500/15 text-red-400' }
  if (c.is_toxic)       return { label: '⚠️ Toxic',  cls: 'bg-yellow-500/15 text-yellow-300' }
  switch (c.category) {
    case 'POSITIVE': return { label: '😊 Positif', cls: 'bg-emerald-500/15 text-emerald-400' }
    case 'NEGATIVE': return { label: '😞 Negatif', cls: 'bg-rose-500/15 text-rose-400' }
    case 'HUMOR':    return { label: '😂 Humor',   cls: 'bg-indigo-500/15 text-indigo-300' }
    default:         return { label: '😐 Netral',  cls: 'bg-white/10 text-white/50' }
  }
}

// ── Subkomponen: 1 reply row ──────────────────────────────────────
function ReplyRow({ reply }: { reply: Comment }) {
  const b = badge(reply)
  return (
    <div className="flex gap-2 items-start py-2 pl-3 border-l border-white/5">
      <CornerDownRight size={12} className="text-white/20 shrink-0 mt-1" />
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between gap-2 mb-0.5">
          <span className="text-xs font-medium text-white/70 truncate">@{reply.username}</span>
          <div className="flex items-center gap-2 shrink-0">
            <span className={`text-[10px] px-1.5 py-0.5 rounded-full ${b.cls}`}>{b.label}</span>
            {reply.like_count > 0 && (
              <span className="text-[11px] text-pink-400 font-medium">
                ❤ {reply.like_count.toLocaleString('id-ID')}
              </span>
            )}
          </div>
        </div>
        <p className="text-xs text-white/55 leading-relaxed wrap-break-word">{reply.text}</p>
        {(reply.is_sarcasm || reply.is_wellwish) && (
          <p className="text-[10px] text-white/30 mt-0.5">
            {reply.is_sarcasm && '🎭 Sarkasme '}
            {reply.is_wellwish && '🙏 Doa/Wellwish'}
          </p>
        )}
      </div>
    </div>
  )
}

// ── Subkomponen: 1 parent comment + nested replies ───────────────
function CommentRow({ comment }: { comment: Comment }) {
  const b = badge(comment)
  const hasReplies = Array.isArray(comment.replies) && comment.replies.length > 0
  const [showReplies, setShowReplies] = useState(false)

  return (
    <div className="glass rounded-xl p-3">
      {/* Header */}
      <div className="flex items-center justify-between gap-2 mb-1">
        <span className="text-sm font-medium text-white/80 truncate">@{comment.username}</span>
        <div className="flex items-center gap-2 shrink-0">
          <span className={`text-[10px] px-2 py-0.5 rounded-full ${b.cls}`}>{b.label}</span>
          {comment.like_count > 0 && (
            <span className="text-xs text-pink-400 font-semibold">
              ❤ {comment.like_count.toLocaleString('id-ID')}
            </span>
          )}
        </div>
      </div>

      {/* Text */}
      <p className="text-sm text-white/60 leading-relaxed wrap-break-word">{comment.text}</p>

      {/* Indicators */}
      {(comment.is_sarcasm || comment.is_wellwish) && (
        <p className="text-[11px] text-white/30 mt-1">
          {comment.is_sarcasm && '🎭 Sarkasme '}
          {comment.is_wellwish && '🙏 Doa/Wellwish'}
        </p>
      )}

      {/* Replies toggle */}
      {hasReplies && (
        <div className="mt-2">
          <button
            onClick={() => setShowReplies(v => !v)}
            className="flex items-center gap-1.5 text-[11px] text-white/40 hover:text-white/70 transition-colors"
          >
            {showReplies ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
            <span>
              {showReplies ? 'Sembunyikan' : 'Lihat'} balasan ({comment.replies!.length})
            </span>
          </button>

          {showReplies && (
            <div className="mt-2 space-y-1">
              {comment.replies!.map((r, i) => (
                <ReplyRow key={r.comment_id || i} reply={r} />
              ))}
            </div>
          )}
        </div>
      )}

      {/* Hint kalau parent punya reply_count tapi tidak di-fetch */}
      {!hasReplies && comment.reply_count > 0 && (
        <p className="text-[10px] text-white/25 mt-1.5 italic">
          💬 {comment.reply_count} balasan (tidak di-fetch)
        </p>
      )}
    </div>
  )
}

// ── MAIN COMPONENT ─────────────────────────────────────────────────
interface CommentListProps {
  comments: Comment[]
  /**
   * Tinggi maksimum container (default 480px). Set "auto" untuk tanpa scroll.
   */
  maxHeight?: string
}

export function CommentList({ comments, maxHeight = '480px' }: CommentListProps) {
  if (!comments?.length) {
    return <p className="text-sm text-white/40 italic">Tidak ada komentar.</p>
  }

  return (
    <div
      className="space-y-2 overflow-y-auto pr-1 custom-scrollbar"
      style={{ maxHeight }}
    >
      {comments.map((c, i) => (
        <CommentRow key={c.comment_id || i} comment={c} />
      ))}
    </div>
  )
}