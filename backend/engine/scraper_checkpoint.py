"""
search_checkpoint.py — Deep Search Job Manager untuk Instagram Scraper
=======================================================================
Menjalankan pencarian hashtag/keyword secara mendalam di background thread.
State disimpan ke JSON sehingga bisa di-resume jika server restart.

Strategi "dorking" Instagram:
  • Hashtag  : iterasi recent sections page demi page hingga exhausted
               + expand ke related hashtags (recursive satu level)
  • Keyword  : topsearch → semua hashtag relevan → tiap hashtag di-dorking
  • Jeda adaptif: makin banyak yang sudah diambil → jeda makin panjang
  • Auto-backoff saat 429 / error beruntun
  • Dedup ketat via shortcode set
"""

from __future__ import annotations

import json
import os
import random
import threading
import time
import traceback
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional


# ── Path setup ─────────────────────────────────────────────────────────────
BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
ENGINE_DIR = os.path.join(BASE_DIR, "engine")
JOBS_DIR   = os.path.join(BASE_DIR, "engine", "output", "search_jobs")
os.makedirs(JOBS_DIR, exist_ok=True)

# ── Konstanta jeda (detik) ─────────────────────────────────────────────────
DELAY_BETWEEN_PAGES        = (2.5,  5.0)   # jeda antar halaman recent
DELAY_BETWEEN_HASHTAGS     = (4.0,  9.0)   # jeda antar hashtag
DELAY_RELATED_HASHTAG      = (6.0, 12.0)   # jeda saat expand related tag
DELAY_AFTER_RATE_LIMIT     = (90,  150)    # jeda saat kena 429
DELAY_CHECKPOINT_SAVE      = 50            # simpan checkpoint setiap N post baru
MAX_CONSECUTIVE_ERRORS     = 5            # batas error beruntun sebelum berhenti
MAX_PAGES_PER_HASHTAG      = 50           # maks halaman recent per hashtag
MAX_RELATED_DEPTH          = 1            # kedalaman ekspansi related hashtag


# ══════════════════════════════════════════════════════════════════════════════
# JOB STATE
# ══════════════════════════════════════════════════════════════════════════════

class JobStatus:
    PENDING    = "pending"
    RUNNING    = "running"
    PAUSED     = "paused"       # rate-limited, akan lanjut otomatis
    COMPLETED  = "completed"
    CANCELLED  = "cancelled"
    ERROR      = "error"


def _now_iso() -> str:
    return datetime.now().isoformat()


def _job_path(job_id: str) -> str:
    return os.path.join(JOBS_DIR, f"job_{job_id}.json")


def _save_job(state: dict) -> None:
    path = _job_path(state["job_id"])
    tmp  = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, default=str)
    os.replace(tmp, path)


def _load_job(job_id: str) -> Optional[dict]:
    path = _job_path(job_id)
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _list_jobs() -> List[dict]:
    jobs = []
    for fname in sorted(os.listdir(JOBS_DIR), reverse=True):
        if fname.startswith("job_") and fname.endswith(".json"):
            try:
                with open(os.path.join(JOBS_DIR, fname), "r", encoding="utf-8") as f:
                    data = json.load(f)
                # Kembalikan ringkasan (tanpa posts penuh)
                jobs.append(_job_summary(data))
            except Exception:
                pass
    return jobs


def _job_summary(state: dict) -> dict:
    return {
        "job_id":          state.get("job_id"),
        "mode":            state.get("mode"),
        "query":           state.get("query"),
        "status":          state.get("status"),
        "total_fetched":   state.get("total_fetched", 0),
        "hashtags_done":   state.get("hashtags_done", 0),
        "hashtags_total":  state.get("hashtags_total", 0),
        "pages_done":      state.get("pages_done", 0),
        "created_at":      state.get("created_at"),
        "updated_at":      state.get("updated_at"),
        "elapsed_seconds": state.get("elapsed_seconds", 0),
        "error":           state.get("error"),
        "log_tail":        state.get("log", [])[-10:],   # 10 baris terakhir log
    }


def _job_detail(state: dict) -> dict:
    """Semua field kecuali posts (terlalu besar untuk polling). Sertakan posts hanya jika completed."""
    out = dict(state)
    if state.get("status") != JobStatus.COMPLETED:
        out["posts"] = []   # Jangan kirim ribuan post saat masih running
    return out


# ══════════════════════════════════════════════════════════════════════════════
# JOB REGISTRY (in-memory, agar bisa cancel thread)
# ══════════════════════════════════════════════════════════════════════════════

_registry_lock  = threading.Lock()
_active_threads: Dict[str, threading.Thread] = {}
_cancel_flags:   Dict[str, threading.Event]  = {}


def _register(job_id: str, thread: threading.Thread, cancel_event: threading.Event):
    with _registry_lock:
        _active_threads[job_id] = thread
        _cancel_flags[job_id]   = cancel_event


def _unregister(job_id: str):
    with _registry_lock:
        _active_threads.pop(job_id, None)
        _cancel_flags.pop(job_id, None)


def request_cancel(job_id: str) -> bool:
    with _registry_lock:
        ev = _cancel_flags.get(job_id)
    if ev:
        ev.set()
        return True
    # Job mungkin sudah selesai — coba update state di file
    state = _load_job(job_id)
    if state and state.get("status") in (JobStatus.RUNNING, JobStatus.PENDING, JobStatus.PAUSED):
        state["status"]     = JobStatus.CANCELLED
        state["updated_at"] = _now_iso()
        _save_job(state)
        return True
    return False


# ══════════════════════════════════════════════════════════════════════════════
# DEEP SEARCH WORKER
# ══════════════════════════════════════════════════════════════════════════════

class DeepSearchWorker:
    """
    Worker yang dijalankan di background thread.
    Menggunakan InstagramSearchScraper dari search_scraper.py.
    """

    def __init__(self, state: dict, cancel_event: threading.Event):
        self.state        = state
        self.cancel       = cancel_event
        self.job_id       = state["job_id"]
        self.seen:        set  = set(state.get("seen_shortcodes", []))
        self.posts:       list = list(state.get("posts", []))
        self.log_lines:   list = list(state.get("log", []))
        self.error_count: int  = 0
        self._scraper     = None
        self._last_save   = 0   # jumlah post saat terakhir checkpoint disimpan

    # ── Logging ────────────────────────────────────────────────
    def _log(self, msg: str):
        ts  = datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] {msg}"
        self.log_lines.append(line)
        if len(self.log_lines) > 500:
            self.log_lines = self.log_lines[-500:]
        print(f"[DeepSearch:{self.job_id[:8]}] {msg}")

    # ── State persistence ──────────────────────────────────────
    def _flush(self):
        s = self.state
        s["posts"]            = self.posts
        s["seen_shortcodes"]  = list(self.seen)
        s["total_fetched"]    = len(self.posts)
        s["log"]              = self.log_lines
        s["updated_at"]       = _now_iso()
        s["elapsed_seconds"]  = round(time.time() - self._t0, 1)
        _save_job(s)
        self._last_save = len(self.posts)

    def _checkpoint_if_needed(self):
        if len(self.posts) - self._last_save >= DELAY_CHECKPOINT_SAVE:
            self._flush()

    # ── Adaptive delay ─────────────────────────────────────────
    def _sleep(self, lo: float, hi: float, reason: str = ""):
        dur = random.uniform(lo, hi)
        msg = f"Jeda {dur:.1f}s" + (f" ({reason})" if reason else "")
        self._log(msg)
        # Sleep dalam potongan kecil agar bisa di-cancel
        end = time.time() + dur
        while time.time() < end:
            if self.cancel.is_set():
                return
            time.sleep(min(1.0, end - time.time()))

    def _adaptive_page_delay(self, pages_so_far: int):
        """Jeda makin panjang seiring banyaknya halaman yang sudah diambil."""
        base_lo, base_hi = DELAY_BETWEEN_PAGES
        multiplier = 1.0 + (pages_so_far // 10) * 0.3   # +30% tiap 10 page
        multiplier = min(multiplier, 3.0)                # max 3x
        self._sleep(base_lo * multiplier, base_hi * multiplier,
                    f"page delay (×{multiplier:.1f})")

    # ── Scraper access ─────────────────────────────────────────
    def _get_scraper(self):
        if self._scraper is None:
            import sys
            sys.path.insert(0, ENGINE_DIR)
            from search_scraper import InstagramSearchScraper
            self._scraper = InstagramSearchScraper()
            self._scraper.initialize_browser()
            self._scraper.session = self._scraper._build_requests_session()
        return self._scraper

    def _close_scraper(self):
        if self._scraper:
            try:
                self._scraper.close()
            except Exception:
                pass
            self._scraper = None

    # ── Core: scrape satu hashtag secara mendalam ──────────────
    def _scrape_hashtag_deep(
        self,
        tag: str,
        include_top: bool = True,
        max_pages: int = MAX_PAGES_PER_HASHTAG,
        depth: int = 0,         # 0 = hashtag utama, 1 = related
    ) -> int:
        """Scrape satu hashtag sampai exhausted. Return jumlah post baru."""
        if self.cancel.is_set():
            return 0

        scraper = self._get_scraper()
        self._log(f"{'  ' * depth}🔍 Mulai scrape #{tag} (depth={depth}, max_pages={max_pages})")

        added = 0

        # ── Ambil web_info (top + recent page 1) ──────────────
        try:
            info = scraper._api_get(f"/api/v1/tags/web_info/?tag_name={tag}")
            if not info or "data" not in info:
                self._log(f"  ⚠️  #{tag}: web_info gagal")
                self.error_count += 1
                return 0
            self.error_count = 0
        except Exception as e:
            self._log(f"  ❌ #{tag}: web_info error — {e}")
            self.error_count += 1
            return 0

        d = info.get("data", {}) or {}

        # Top posts
        if include_top:
            top_medias = scraper._extract_medias_from_sections(
                (d.get("top", {}) or {}).get("sections", [])
            )
            for media in top_medias:
                if self.cancel.is_set():
                    return added
                parsed = scraper._parse_media(media, "top", len(self.posts) + 1)
                if parsed and self._add_post(parsed, tag):
                    added += 1

        # Recent page 1
        recent       = d.get("recent", {}) or {}
        more         = bool(recent.get("more_available", False))
        next_max_id  = recent.get("next_max_id")
        next_mids    = recent.get("next_media_ids", []) or []

        for media in scraper._extract_medias_from_sections(recent.get("sections", [])):
            if self.cancel.is_set():
                return added
            parsed = scraper._parse_media(media, "recent", len(self.posts) + 1)
            if parsed and self._add_post(parsed, tag):
                added += 1

        self.state["pages_done"] = self.state.get("pages_done", 0) + 1
        self._checkpoint_if_needed()

        # ── Iterasi halaman recent berikutnya ──────────────────
        page_num = 1
        consecutive_empty = 0

        while more and next_max_id and page_num < max_pages:
            if self.cancel.is_set():
                break
            if self.error_count >= MAX_CONSECUTIVE_ERRORS:
                self._log(f"  🛑 #{tag}: terlalu banyak error, berhenti")
                break

            self._adaptive_page_delay(page_num)
            if self.cancel.is_set():
                break

            page_num += 1
            self._log(f"  {'  ' * depth}📄 #{tag} page {page_num} (total_posts={len(self.posts)})")

            try:
                sec = scraper._fetch_hashtag_sections(tag, next_max_id, next_mids, page_num)
                if not sec:
                    self._log(f"  ⚠️  #{tag} page {page_num}: respons kosong")
                    self.error_count += 1
                    consecutive_empty += 1
                    if consecutive_empty >= 3:
                        self._log(f"  🛑 #{tag}: 3 halaman kosong beruntun, berhenti")
                        break
                    self._sleep(*DELAY_AFTER_RATE_LIMIT, "backoff empty")
                    continue

                self.error_count = 0
                consecutive_empty = 0

                page_added = 0
                for media in scraper._extract_medias_from_sections(sec.get("sections", [])):
                    if self.cancel.is_set():
                        break
                    parsed = scraper._parse_media(media, "recent", len(self.posts) + 1)
                    if parsed and self._add_post(parsed, tag):
                        added      += 1
                        page_added += 1

                self._log(f"  {'  ' * depth}   +{page_added} post (subtotal #{tag}: {added})")
                self.state["pages_done"] = self.state.get("pages_done", 0) + 1
                self._checkpoint_if_needed()

                more        = bool(sec.get("more_available", False))
                next_max_id = sec.get("next_max_id")
                next_mids   = sec.get("next_media_ids", []) or []

                if page_added == 0 and not more:
                    break

            except Exception as e:
                tb = traceback.format_exc()
                self._log(f"  ❌ #{tag} page {page_num}: {e}")
                self._log(f"     {tb[:200]}")
                self.error_count += 1
                if "429" in str(e) or "rate" in str(e).lower():
                    self._sleep(*DELAY_AFTER_RATE_LIMIT, "rate limit backoff")
                else:
                    self._sleep(3.0, 8.0, "error backoff")

        self._log(f"  {'  ' * depth}✅ #{tag} selesai: {added} post baru (total {len(self.posts)})")
        return added

    def _add_post(self, parsed: dict, tag: str) -> bool:
        key = parsed.get("media_id") or parsed.get("shortcode")
        if not key or key in self.seen:
            return False
        self.seen.add(key)
        parsed["hashtag"] = tag
        parsed["rank"]    = len(self.posts) + 1
        self.posts.append(parsed)
        return True

    # ── HASHTAG MODE ───────────────────────────────────────────
    def run_hashtag_mode(self):
        s   = self.state
        tag = s["query"].strip().lstrip("#").lower()

        self._log(f"🚀 Deep Hashtag Search: #{tag}")
        s["status"]           = JobStatus.RUNNING
        s["hashtags_total"]   = 1
        s["hashtags_done"]    = 0
        self._flush()

        # Scraper mulai
        scraper = self._get_scraper()

        # Ambil related hashtags dulu
        related = []
        try:
            disc = scraper._topsearch(tag)
            related = [h["name"] for h in disc.get("hashtags", []) if h.get("name") and h["name"] != tag]
            self._log(f"📊 Related hashtags: {', '.join('#' + r for r in related[:20])}")
            s["hashtags_total"] = 1 + len(related)
            self._flush()
        except Exception as e:
            self._log(f"⚠️  Gagal ambil related: {e}")

        # Scrape hashtag utama (full depth)
        self._scrape_hashtag_deep(tag, include_top=True, max_pages=MAX_PAGES_PER_HASHTAG, depth=0)
        s["hashtags_done"] = 1
        self._flush()

        # Expand ke related hashtags (depth=1)
        if MAX_RELATED_DEPTH > 0:
            for i, rtag in enumerate(related[:20], 1):   # max 20 related
                if self.cancel.is_set():
                    break
                if self.error_count >= MAX_CONSECUTIVE_ERRORS:
                    self._log("🛑 Terlalu banyak error, hentikan ekspansi")
                    break
                self._sleep(*DELAY_RELATED_HASHTAG, f"antar related hashtag #{rtag}")
                self._log(f"\n🔗 Related [{i}/{len(related[:20])}]: #{rtag}")
                # Related: max 15 halaman (lebih sedikit dari hashtag utama)
                self._scrape_hashtag_deep(rtag, include_top=False, max_pages=15, depth=1)
                s["hashtags_done"] += 1
                self._flush()

    # ── KEYWORD MODE ───────────────────────────────────────────
    def run_keyword_mode(self):
        s      = self.state
        kw     = s["query"].strip()
        config = s.get("config", {})
        max_hashtags = int(config.get("max_hashtags", 10))

        self._log(f"🚀 Deep Keyword Search: '{kw}'")
        s["status"] = JobStatus.RUNNING
        self._flush()

        scraper = self._get_scraper()

        # Topsearch untuk dapatkan hashtag relevan
        self._log("🔎 Mencari hashtag relevan via topsearch...")
        try:
            disc   = scraper._topsearch(kw)
            h_list = [h["name"] for h in disc.get("hashtags", []) if h.get("name")]
        except Exception as e:
            self._log(f"❌ Topsearch gagal: {e}")
            s["status"] = JobStatus.ERROR
            s["error"]  = str(e)
            self._flush()
            return

        if not h_list:
            # Fallback: normalisasi keyword jadi hashtag
            from search_scraper import InstagramSearchScraper as _ISS
            h_list = [_ISS._normalize_hashtag.__func__(None, kw)]
            if not h_list[0]:
                self._log("❌ Tidak ada hashtag relevan ditemukan")
                s["status"] = JobStatus.ERROR
                s["error"]  = "Tidak ada hashtag relevan"
                self._flush()
                return

        chosen = h_list[:max_hashtags]
        self._log(f"🏷️  Hashtag dipilih ({len(chosen)}): {', '.join('#' + t for t in chosen)}")
        s["hashtags_total"] = len(chosen)
        s["searched_hashtags"] = chosen
        self._flush()

        for i, tag in enumerate(chosen, 1):
            if self.cancel.is_set():
                break
            if self.error_count >= MAX_CONSECUTIVE_ERRORS:
                self._log("🛑 Terlalu banyak error, berhenti")
                break

            self._log(f"\n📌 [{i}/{len(chosen)}] Scrape #{tag}")
            self._scrape_hashtag_deep(tag, include_top=True,
                                      max_pages=MAX_PAGES_PER_HASHTAG, depth=0)
            s["hashtags_done"] = i
            self._flush()

            if i < len(chosen):
                self._sleep(*DELAY_BETWEEN_HASHTAGS, f"antar hashtag (#{tag} → #{chosen[i]})")

        # Re-ranking gabungan
        self.posts.sort(key=lambda x: (x.get("like_count", 0), x.get("comment_count", 0)), reverse=True)
        for idx, p in enumerate(self.posts, 1):
            p["rank"] = idx

    # ── MAIN RUN ───────────────────────────────────────────────
    def run(self):
        s    = self.state
        self._t0 = time.time()

        try:
            s["status"]     = JobStatus.RUNNING
            s["started_at"] = _now_iso()
            self._flush()

            if s["mode"] == "hashtag":
                self.run_hashtag_mode()
            else:
                self.run_keyword_mode()

            if self.cancel.is_set():
                s["status"] = JobStatus.CANCELLED
                self._log("🚫 Job dibatalkan oleh pengguna")
            else:
                s["status"] = JobStatus.COMPLETED
                self._log(f"🎉 Selesai! Total: {len(self.posts)} post unik")

        except Exception as e:
            tb = traceback.format_exc()
            self._log(f"💥 Fatal error: {e}")
            self._log(tb[:500])
            s["status"] = JobStatus.ERROR
            s["error"]  = str(e)

        finally:
            s["elapsed_seconds"] = round(time.time() - self._t0, 1)
            self._flush()
            self._close_scraper()
            _unregister(self.job_id)


# ══════════════════════════════════════════════════════════════════════════════
# PUBLIC API
# ══════════════════════════════════════════════════════════════════════════════

def create_job(
    mode: str,          # "hashtag" | "keyword"
    query: str,
    config: Optional[dict] = None,
) -> str:
    """Buat dan jalankan job baru. Return job_id."""
    job_id = uuid.uuid4().hex[:12]
    state: dict = {
        "job_id":            job_id,
        "mode":              mode,
        "query":             query,
        "config":            config or {},
        "status":            JobStatus.PENDING,
        "total_fetched":     0,
        "hashtags_done":     0,
        "hashtags_total":    0,
        "pages_done":        0,
        "searched_hashtags": [],
        "posts":             [],
        "seen_shortcodes":   [],
        "log":               [],
        "error":             None,
        "created_at":        _now_iso(),
        "updated_at":        _now_iso(),
        "started_at":        None,
        "elapsed_seconds":   0,
    }
    _save_job(state)

    cancel_ev = threading.Event()
    worker    = DeepSearchWorker(state, cancel_ev)
    thread    = threading.Thread(
        target=worker.run,
        name=f"deep-search-{job_id}",
        daemon=True,
    )
    _register(job_id, thread, cancel_ev)
    thread.start()

    return job_id


def get_job(job_id: str) -> Optional[dict]:
    state = _load_job(job_id)
    if not state:
        return None
    return _job_detail(state)


def get_job_summary(job_id: str) -> Optional[dict]:
    state = _load_job(job_id)
    if not state:
        return None
    return _job_summary(state)


def list_all_jobs() -> List[dict]:
    return _list_jobs()


def cancel_job(job_id: str) -> bool:
    return request_cancel(job_id)


def delete_job(job_id: str) -> bool:
    cancel_job(job_id)
    path = _job_path(job_id)
    if os.path.exists(path):
        os.remove(path)
        return True
    return False


def get_job_posts(job_id: str) -> Optional[List[dict]]:
    """Ambil semua posts dari job (hanya dipanggil saat completed)."""
    state = _load_job(job_id)
    if not state:
        return None
    return state.get("posts", [])