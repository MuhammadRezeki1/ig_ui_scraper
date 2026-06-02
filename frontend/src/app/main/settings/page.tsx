'use client'

import { useState, useEffect } from 'react'
import { Settings, Key, CheckCircle, AlertCircle, Loader2, Trash2, RefreshCw, Copy } from 'lucide-react'
import { getSession, saveCookies, triggerLogout, getAuthStatus } from '@/lib/api'
import type { SessionInfo } from '@/types'

export default function SettingsPage() {
  const [session, setSession] = useState<SessionInfo | null>(null)
  const [loading, setLoading] = useState(true)
  const [cookieInput, setCookieInput] = useState('')
  const [saving, setSaving] = useState(false)
  const [msg, setMsg] = useState<{ type: 'ok' | 'err'; text: string } | null>(null)

  const loadSession = () => {
    setLoading(true)
    getSession()
      .then(r => setSession(r.data))
      .catch(() => {})
      .finally(() => setLoading(false))
  }

  useEffect(() => { loadSession() }, [])

  async function handleSaveCookies() {
    if (!cookieInput.trim()) { setMsg({ type: 'err', text: 'Paste cookies JSON dulu' }); return }
    setSaving(true)
    setMsg(null)
    try {
      const resp = await saveCookies(cookieInput.trim())
      if (resp.success) {
        setMsg({ type: 'ok', text: `Cookies tersimpan! User ID: ${(resp.data as { user_id: string }).user_id}` })
        setCookieInput('')
        loadSession()
      } else {
        setMsg({ type: 'err', text: resp.message })
      }
    } catch (e: unknown) {
      setMsg({ type: 'err', text: e instanceof Error ? e.message : 'Gagal menyimpan cookies' })
    } finally {
      setSaving(false)
    }
  }

  async function handleLogout() {
    if (!confirm('Hapus session cookies?')) return
    await triggerLogout()
    loadSession()
    setMsg({ type: 'ok', text: 'Session dihapus' })
  }

  return (
    <div className="p-8 max-w-3xl">
      <div className="flex items-center gap-3 mb-8">
        <div className="w-10 h-10 rounded-xl glass flex items-center justify-center">
          <Settings size={20} className="text-white/60" />
        </div>
        <div>
          <h1 className="text-2xl font-bold" style={{ fontFamily: 'var(--font-display)' }}>Settings</h1>
          <p className="text-sm text-white/40">Konfigurasi session & koneksi engine</p>
        </div>
      </div>

      {/* Session Status */}
      <div className="glass-card p-6 mb-6">
        <h2 className="font-semibold mb-4 flex items-center gap-2 text-sm uppercase tracking-widest text-white/50">
          <Key size={14} /> Status Session
        </h2>

        {loading ? (
          <div className="space-y-2">
            <div className="skeleton h-5 w-40 rounded" />
            <div className="skeleton h-4 w-64 rounded" />
          </div>
        ) : (
          <div className="space-y-3">
            <div className="flex items-center gap-3">
              {session?.is_valid ? (
                <CheckCircle size={20} className="text-emerald-400" />
              ) : (
                <AlertCircle size={20} className="text-orange-400" />
              )}
              <span className="font-medium">
                {session?.is_valid ? 'Session Aktif' : session?.has_session ? 'Session Tidak Valid' : 'Belum Login'}
              </span>
            </div>
            {session?.has_session && (
              <div className="glass rounded-xl p-4 space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-white/50">User ID</span>
                  <span className="font-mono text-white/80">{session.user_id || '—'}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-white/50">Jumlah Cookies</span>
                  <span className="text-white/80">{session.cookie_count}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-white/50">Disimpan</span>
                  <span className="text-white/80">{session.saved_at ? new Date(session.saved_at).toLocaleString('id-ID') : '—'}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-white/50">Status</span>
                  <span className={session.is_expired ? 'text-red-400' : session.is_valid ? 'text-emerald-400' : 'text-orange-400'}>
                    {session.is_expired ? 'Expired' : session.is_valid ? 'Valid' : 'Tidak Valid'}
                  </span>
                </div>
                {session.missing_cookies?.length > 0 && (
                  <div className="flex justify-between">
                    <span className="text-white/50">Cookie Hilang</span>
                    <span className="text-red-400 text-xs">{session.missing_cookies.join(', ')}</span>
                  </div>
                )}
              </div>
            )}
            <div className="flex gap-2 pt-1">
              <button onClick={loadSession} className="btn-glass flex items-center gap-2 text-sm">
                <RefreshCw size={13} /> Refresh
              </button>
              {session?.has_session && (
                <button onClick={handleLogout} className="btn-glass flex items-center gap-2 text-sm text-red-400/80 hover:text-red-400">
                  <Trash2 size={13} /> Hapus Session
                </button>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Cookie Login */}
      <div className="glass-card p-6 mb-6">
        <h2 className="font-semibold mb-2 text-sm uppercase tracking-widest text-white/50">Login via Cookies</h2>
        <p className="text-sm text-white/40 mb-4">
          Export cookies dari browser menggunakan ekstensi{' '}
          <a href="https://cookie-editor.com" target="_blank" rel="noopener noreferrer" className="text-pink-400 hover:underline">
            Cookie-Editor
          </a>
          {' '}lalu paste JSON di sini.
        </p>

        {/* Guide */}
        <div className="glass rounded-xl p-4 mb-4 text-xs text-white/50 space-y-1.5">
          <p className="text-white/70 font-semibold mb-2">📋 Cara Export Cookies:</p>
          {[
            'Login Instagram di browser kamu',
            'Install ekstensi Cookie-Editor',
            'Buka instagram.com (sudah login)',
            'Klik Cookie-Editor → Export → Export as JSON',
            'Copy semua teks JSON, paste di bawah ini',
          ].map((step, i) => (
            <div key={i} className="flex gap-2">
              <span className="w-4 h-4 rounded-full bg-pink-500/20 text-pink-400 flex items-center justify-center shrink-0 text-[10px] font-bold">{i+1}</span>
              <span>{step}</span>
            </div>
          ))}
          <div className="pt-2 border-t border-white/10 mt-2">
            <span className="text-emerald-400 font-medium">Wajib ada: </span>
            <span className="font-mono">sessionid, ds_user_id, csrftoken</span>
          </div>
        </div>

        <textarea
          value={cookieInput}
          onChange={e => setCookieInput(e.target.value)}
          placeholder='[{"name":"sessionid","value":"...","domain":".instagram.com",...}]'
          className="input-glass min-h-36 resize-y font-mono text-xs"
        />

        {msg && (
          <div className={`mt-3 flex items-center gap-2 text-sm glass rounded-xl px-4 py-3 ${
            msg.type === 'ok' ? 'text-emerald-400' : 'text-red-400'
          }`}>
            {msg.type === 'ok' ? <CheckCircle size={15} /> : <AlertCircle size={15} />}
            {msg.text}
          </div>
        )}

        <button
          onClick={handleSaveCookies}
          disabled={saving || !cookieInput.trim()}
          className="btn-ig flex items-center gap-2 mt-4"
        >
          {saving ? <Loader2 size={16} className="animate-spin" /> : <Key size={16} />}
          {saving ? 'Menyimpan...' : 'Simpan Cookies'}
        </button>
      </div>

      {/* Engine Config */}
      <div className="glass-card p-6">
        <h2 className="font-semibold mb-4 text-sm uppercase tracking-widest text-white/50">Engine Configuration</h2>
        <div className="space-y-3 text-sm">
          {[
            { label: 'FastAPI Bridge', value: 'http://localhost:8000', status: 'running' },
            { label: 'Flask Engine',   value: 'http://localhost:5000', status: 'required' },
            { label: 'Sentiment Mode', value: 'hybrid (IndoBERT + Rules)', status: 'info' },
          ].map(item => (
            <div key={item.label} className="flex items-center justify-between py-2.5 border-b border-white/5 last:border-0">
              <span className="text-white/60">{item.label}</span>
              <div className="flex items-center gap-2">
                <span className="font-mono text-white/70 text-xs">{item.value}</span>
                <span className={`badge ${
                  item.status === 'running' ? 'badge-positive' :
                  item.status === 'required' ? 'badge-neutral' : 'badge-humor'
                }`}>{item.status}</span>
              </div>
            </div>
          ))}
        </div>
        <div className="mt-4 glass rounded-xl p-4 text-xs text-white/40">
          <p className="font-semibold text-white/60 mb-2">💡 Setup Reminder:</p>
          <ol className="space-y-1 list-decimal list-inside">
            <li>Jalankan <code className="text-pink-400">python instagram_api_server.py</code> (port 5000)</li>
            <li>Jalankan <code className="text-blue-400">python backend/main.py</code> (port 8000)</li>
            <li>Jalankan <code className="text-emerald-400">npm run dev</code> di folder frontend (port 3000)</li>
          </ol>
        </div>
      </div>
    </div>
  )
}
