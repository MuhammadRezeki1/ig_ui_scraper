'use client'

import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend } from 'recharts'
import type { SentimentSummary } from '@/types'

interface SentimentChartProps {
  summary: SentimentSummary
}

const SENTIMENT_CONFIG = [
  { key: 'positive_count',    label: 'Positif',     color: '#22c55e' },
  { key: 'neutral_count',     label: 'Netral',      color: '#94a3b8' },
  { key: 'humor_count',       label: 'Humor',       color: '#818cf8' },
  { key: 'negative_count',    label: 'Negatif',     color: '#f87171' },
  { key: 'toxic_count',       label: 'Toxic',       color: '#fde047' },
  { key: 'hate_speech_count', label: 'Hate Speech', color: '#ef4444' },
] as const

const CustomTooltip = ({ active, payload }: { active?: boolean; payload?: { name: string; value: number; payload: { color: string } }[] }) => {
  if (!active || !payload?.length) return null
  const p = payload[0]
  return (
    <div className="glass rounded-xl px-3 py-2 text-sm">
      <div className="flex items-center gap-2">
        <div className="w-2.5 h-2.5 rounded-full" style={{ background: p.payload.color }} />
        <span className="text-white/70">{p.name}</span>
        <span className="font-bold text-white ml-2">{p.value}</span>
      </div>
    </div>
  )
}

export function SentimentChart({ summary }: SentimentChartProps) {
  const data = SENTIMENT_CONFIG
    .map(c => ({
      name: c.label,
      value: (summary[c.key as keyof SentimentSummary] as number) || 0,
      color: c.color,
    }))
    .filter(d => d.value > 0)

  if (data.length === 0) {
    return (
      <div className="flex items-center justify-center h-48 text-white/30 text-sm">
        Tidak ada data sentimen
      </div>
    )
  }

  return (
    // FIX warning "width(-1) height(-1)":
    // - tinggi numerik eksplisit (inline style) supaya parent SELALU punya
    //   dimensi pasti sejak paint pertama (class Tailwind kadang telat apply)
    <div style={{ width: '100%', height: 256, minHeight: 256 }}>
      {/*
        - height={256}: ResponsiveContainer dapat dimensi pasti, tidak menebak parent
        - debounce={50}: tunda pengukuran 50ms sampai layout stabil
        ANIMASI TETAP AKTIF — tidak ada isAnimationActive={false}
      */}
      <ResponsiveContainer width="100%" height={256} debounce={50}>
        <PieChart>
          <Pie
            data={data}
            cx="50%"
            cy="45%"
            innerRadius={55}
            outerRadius={90}
            paddingAngle={3}
            dataKey="value"
            stroke="none"
            animationBegin={0}
            animationDuration={800}
          >
            {data.map((entry, i) => (
              <Cell
                key={i}
                fill={entry.color}
                style={{ filter: `drop-shadow(0 0 6px ${entry.color}60)` }}
              />
            ))}
          </Pie>
          <Tooltip content={<CustomTooltip />} />
          <Legend
            iconType="circle"
            iconSize={8}
            formatter={(value) => <span style={{ color: 'rgba(255,255,255,0.6)', fontSize: 12 }}>{value}</span>}
          />
        </PieChart>
      </ResponsiveContainer>
    </div>
  )
}