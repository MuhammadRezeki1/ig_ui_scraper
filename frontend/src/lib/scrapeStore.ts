// lib/scrapeStore.ts
// ------------------------------------------------------------------
// Menyimpan status "sedang scraping" di level module (bukan di dalam
// komponen). Tujuannya: status tetap hidup walau ScrapePage di-unmount
// ketika user pindah ke halaman lain, lalu kembali lagi.
//
// Dengan begini:
//  - Klik Scrape kedua kali saat scrape pertama belum selesai -> ditolak.
//  - Pindah halaman lalu balik -> ScrapePage tahu masih ada proses jalan,
//    jadi tidak memulai ulang, hanya menampilkan peringatan.
// ------------------------------------------------------------------

export type ScrapeKind = 'single' | 'batch' | 'unified' | 'profile' | 'followers' | 'following' | null

interface ScrapeState {
  isScraping: boolean
  kind: ScrapeKind
  startedAt: number | null
  label: string   // deskripsi singkat, mis. URL atau "3 URL"
}

const state: ScrapeState = {
  isScraping: false,
  kind: null,
  startedAt: null,
  label: '',
}

type Listener = () => void
const listeners = new Set<Listener>()

function emit() {
  listeners.forEach((l) => {
    try { l() } catch { /* ignore */ }
  })
}

export const scrapeStore = {
  get(): ScrapeState {
    return { ...state }
  },

  isBusy(): boolean {
    return state.isScraping
  },

  begin(kind: Exclude<ScrapeKind, null>, label: string): boolean {
    // Tolak kalau sudah ada yang berjalan
    if (state.isScraping) return false
    state.isScraping = true
    state.kind = kind
    state.startedAt = Date.now()
    state.label = label
    emit()
    return true
  },

  finish() {
    state.isScraping = false
    state.kind = null
    state.startedAt = null
    state.label = ''
    emit()
  },

  subscribe(listener: Listener): () => void {
    listeners.add(listener)
    return () => { listeners.delete(listener) }
  },
}