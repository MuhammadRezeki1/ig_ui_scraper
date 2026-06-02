'use client'

import { useState, useEffect } from 'react'
import { listOutputFiles, getOutputFile } from '@/lib/api'
import type { OutputFile, PostResult } from '@/types'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts'
import { BarChart2, Loader2 } from 'lucide-react'
import { IGLogoFilled } from '@/components/ui/IGLogo'

interface AggregatedData {
  totalPosts: number
  totalComments: number
  totalLikes: number
  totalViews: number
  totalSaves: number
  totalShares: number
  avgSentiment: {
    positive: number
    negative: number
    neutral: number
    hate: number
    toxic: number
    humor: number
  }
  postsData: {
    name: string
    likes: number
    comments: number
    views: number
    saves: number
  }[]
}

const CustomTooltip = ({ active, payload, label }: { active?: boolean; payload?: { name: string; value: number; fill: string }[]; label?: string }) => {
  if (!active || !payload?.length) return null
  return (
    <div className="glass rounded-xl px-3 py-2 text-xs">
      <p className="text-white/60 mb-1">{label}</p>
      {payload.map((p, i) => (
        <div key={i} className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full" style={{ background: p.fill }} />
          <span className="text-white/70">{p.name}</span>
          <span className="font-bold text-white ml-1">{Number(p.value).toLocaleString('id-ID')}</span>
        </div>
      ))}
    </div>
  )
}

export default function AnalyticsPage() {
  const [data, setData] = useState<AggregatedData | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function load() {
      try {
        const filesResp = await listOutputFiles()
        if (!filesResp.success) return
        const postFiles = filesResp.data.files
          .filter(f => f.name.startsWith('api_post') || f.name.startsWith('instagram_'))
          .slice(0, 20)

        const results = await Promise.all(
          postFiles.map((f: OutputFile) => getOutputFile(f.name).catch(() => null))
        )

        const validResults = results.filter(Boolean) as PostResult[]
        if (validResults.length === 0) {
          setLoading(false)
          return
        }

        const agg: AggregatedData = {
          totalPosts: validResults.length,
          totalComments: validResults.reduce((s, r) => s + (r.comments_count || 0), 0),
          totalLikes: validResults.reduce((s, r) => s + (r.likes || 0), 0),
          totalViews: validResults.reduce((s, r) => s + (r.video_views || 0), 0),
          totalSaves: validResults.reduce((s, r) => s + (r.saves_count || 0), 0),
          totalShares: validResults.reduce((s, r) => s + (r.shares_count || 0), 0),
          avgSentiment: {
            positive: 0, negative: 0, neutral: 0, hate: 0, toxic: 0, humor: 0,
          },
          postsData: validResults.slice(0, 10).map(r => ({
            name: r.owner_username || r.shortcode?.slice(0, 8) || 'unknown',
            likes: r.likes || 0,
            comments: r.comments_count || 0,
            views: r.video_views || 0,
            saves: r.saves_count || 0,
          })),
        }

        // Average sentiment
        const counts = validResults.map(r => r.sentiment_summary).filter(Boolean)
        if (counts.length > 0) {
          const total = counts.reduce((s, c) => s + (c?.total_comments || 0), 0)
          agg.avgSentiment = {
            positive: Math.round(counts.reduce((s, c) => s + (c?.positive_count || 0), 0) / total * 100),
            negative: Math.round(counts.reduce((s, c) => s + (c?.negative_count || 0), 0) / total * 100),
            neutral:  Math.round(counts.reduce((s, c) => s + (c?.neutral_count || 0), 0) / total * 100),
            hate:     Math.round(counts.reduce((s, c) => s + (c?.hate_speech_count || 0), 0) / total * 100),
            toxic:    Math.round(counts.reduce((s, c) => s + (c?.toxic_count || 0), 0) / total * 100),
            humor:    Math.round(counts.reduce((s, c) => s + (c?.humor_count || 0), 0) / total * 100),
          }
        }

        setData(agg)
      } catch { /* skip */ }
      finally { setLoading(false) }
    }
    load()
  }, [])

  if (loading) {
    return (
      <div className="p-8 flex items-center justify-center h-96">
        <div className="text-center">
          <Loader2 size={32} className="animate-spin mx-auto mb-3 text-pink-400" />
          <p className="text-white/40 text-sm">Memuat data analytics...</p>
        </div>
      </div>
    )
  }

  if (!data) {
    return (
      <div className="p-8 text-center text-white/30">
        <BarChart2 size={48} className="mx-auto mb-3 opacity-20" />
        <p>Belum ada data untuk ditampilkan. Scrape beberapa post terlebih dahulu.</p>
      </div>
    )
  }

  return (
    <div className="p-8 max-w-6xl">
      <div className="flex items-center gap-3 mb-8">
        <IGLogoFilled size={36} />
        <div>
          <h1 className="text-2xl font-bold" style={{ fontFamily: 'var(--font-display)' }}>Analytics</h1>
          <p className="text-sm text-white/40">Analisis agregat dari {data.totalPosts} post</p>
        </div>
      </div>

      {/* Summary Stats */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 mb-8">
        {[
          { l: 'Total Post',     v: data.totalPosts,    c: '#E1306C' },
          { l: 'Total Komentar', v: data.totalComments, c: '#833AB4' },
          { l: 'Total Likes',    v: data.totalLikes,    c: '#F77737' },
          { l: 'Total Views',    v: data.totalViews,    c: '#405DE6' },
          { l: 'Total Saves',    v: data.totalSaves,    c: '#FCAF45' },
          { l: 'Total Shares',   v: data.totalShares,   c: '#22c55e' },
        ].map(s => (
          <div key={s.l} className="glass-card p-4 text-center">
            <p className="text-xl font-bold" style={{ color: s.c, fontFamily: 'var(--font-display)' }}>
              {s.v.toLocaleString('id-ID')}
            </p>
            <p className="text-[11px] text-white/40 mt-1">{s.l}</p>
          </div>
        ))}
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        {/* Engagement by Post */}
        <div className="glass-card p-6">
          <h3 className="font-semibold mb-4 text-sm uppercase tracking-widest text-white/50">Engagement per Post</h3>
          <div className="h-64">
            <ResponsiveContainer>
              <BarChart data={data.postsData} barGap={2}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                <XAxis dataKey="name" tick={{ fill: 'rgba(255,255,255,0.4)', fontSize: 10 }} />
                <YAxis tick={{ fill: 'rgba(255,255,255,0.4)', fontSize: 10 }} />
                <Tooltip content={<CustomTooltip />} />
                <Bar dataKey="likes"    name="Likes"    fill="#E1306C" radius={[4,4,0,0]} />
                <Bar dataKey="comments" name="Komentar" fill="#833AB4" radius={[4,4,0,0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Sentiment Overview */}
        <div className="glass-card p-6">
          <h3 className="font-semibold mb-4 text-sm uppercase tracking-widest text-white/50">Sentimen Rata-rata (%)</h3>
          <div className="space-y-3">
            {[
              { l: '😊 Positif',     v: data.avgSentiment.positive, c: '#22c55e' },
              { l: '😞 Negatif',     v: data.avgSentiment.negative, c: '#f87171' },
              { l: '😐 Netral',      v: data.avgSentiment.neutral,  c: '#94a3b8' },
              { l: '😂 Humor',       v: data.avgSentiment.humor,    c: '#818cf8' },
              { l: '⚠️ Toxic',       v: data.avgSentiment.toxic,    c: '#fde047' },
              { l: '🚨 Hate Speech', v: data.avgSentiment.hate,     c: '#ef4444' },
            ].map(item => (
              <div key={item.l}>
                <div className="flex justify-between text-sm mb-1">
                  <span className="text-white/60">{item.l}</span>
                  <span className="text-white/50 font-mono">{item.v}%</span>
                </div>
                <div className="progress-bar">
                  <div
                    className="progress-fill"
                    style={{ width: `${item.v}%`, background: item.c, boxShadow: `0 0 8px ${item.c}60` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Views / Saves */}
      {data.postsData.some(p => p.views > 0 || p.saves > 0) && (
        <div className="glass-card p-6">
          <h3 className="font-semibold mb-4 text-sm uppercase tracking-widest text-white/50">Views & Saves per Post</h3>
          <div className="h-64">
            <ResponsiveContainer>
              <BarChart data={data.postsData.filter(p => p.views > 0 || p.saves > 0)}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                <XAxis dataKey="name" tick={{ fill: 'rgba(255,255,255,0.4)', fontSize: 10 }} />
                <YAxis tick={{ fill: 'rgba(255,255,255,0.4)', fontSize: 10 }} />
                <Tooltip content={<CustomTooltip />} />
                <Bar dataKey="views" name="Views" fill="#405DE6" radius={[4,4,0,0]} />
                <Bar dataKey="saves" name="Saves" fill="#FCAF45" radius={[4,4,0,0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}
    </div>
  )
}
