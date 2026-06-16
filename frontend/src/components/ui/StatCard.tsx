'use client'

import { clsx } from 'clsx'

interface StatCardProps {
  label: string
  value: string | number
  sub?: string
  icon?: React.ReactNode
  color?: 'pink' | 'purple' | 'orange' | 'blue' | 'green' | 'yellow' | 'red' | 'default'
  percentage?: number
  loading?: boolean
}

const colorMap: Record<string, { bg: string; border: string; text: string; glow: string }> = {
  pink:    { bg: 'rgba(193,53,132,0.08)',  border: 'rgba(193,53,132,0.15)',  text: '#C13584', glow: 'rgba(193,53,132,0.2)' },
  purple:  { bg: 'rgba(131,58,180,0.08)', border: 'rgba(131,58,180,0.15)', text: '#833AB4', glow: 'rgba(131,58,180,0.2)' },
  orange:  { bg: 'rgba(247,119,55,0.08)', border: 'rgba(247,119,55,0.15)', text: '#F77737', glow: 'rgba(247,119,55,0.2)' },
  blue:    { bg: 'rgba(64,93,230,0.08)',  border: 'rgba(64,93,230,0.15)',  text: '#405DE6', glow: 'rgba(64,93,230,0.2)' },
  green:   { bg: 'rgba(34,197,94,0.08)',  border: 'rgba(34,197,94,0.15)',  text: '#22c55e', glow: 'rgba(34,197,94,0.2)' },
  yellow:  { bg: 'rgba(252,175,69,0.08)', border: 'rgba(252,175,69,0.15)', text: '#FCAF45', glow: 'rgba(252,175,69,0.2)' },
  red:     { bg: 'rgba(220,38,38,0.08)',  border: 'rgba(220,38,38,0.15)',  text: '#dc2626', glow: 'rgba(220,38,38,0.2)' },
  default: { bg: 'var(--glass-bg)', border: 'var(--glass-border)', text: 'var(--text-primary)', glow: 'transparent' },
}

export function StatCard({ label, value, sub, icon, color = 'default', percentage, loading }: StatCardProps) {
  const c = colorMap[color]

  if (loading) {
    return (
      <div className="glass-card p-5">
        <div className="skeleton h-4 w-20 mb-3" />
        <div className="skeleton h-8 w-16 mb-2" />
        <div className="skeleton h-3 w-24" />
      </div>
    )
  }

  return (
    <div
      className="glass-card p-5 relative overflow-hidden"
      style={{ background: c.bg, borderColor: c.border }}
    >
      {/* Glow */}
      <div
        className="absolute -top-6 -right-6 w-24 h-24 rounded-full blur-2xl opacity-40 pointer-events-none"
        style={{ background: c.glow }}
      />

      <div className="relative">
        <div className="flex items-start justify-between mb-3">
          <p className="text-xs font-medium uppercase tracking-widest" style={{ color: 'var(--text-secondary)' }}>{label}</p>
          {icon && (
            <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ background: c.glow }}>
              {icon}
            </div>
          )}
        </div>

        <p className="stat-num text-3xl mb-1" style={{ color: c.text }}>
          {typeof value === 'number' ? value.toLocaleString('id-ID') : value}
        </p>

        {sub && <p className="text-xs" style={{ color: 'var(--text-muted)' }}>{sub}</p>}

        {percentage !== undefined && (
          <div className="mt-3">
            <div className="progress-bar">
              <div
                className="progress-fill"
                style={{
                  width: `${Math.min(percentage, 100)}%`,
                  background: c.text,
                  boxShadow: `0 0 8px ${c.glow}`,
                }}
              />
            </div>
            <p className="text-[11px] mt-1" style={{ color: 'var(--text-muted)' }}>{percentage.toFixed(1)}%</p>
          </div>
        )}
      </div>
    </div>
  )
}