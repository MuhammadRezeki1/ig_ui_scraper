"""
search_deep_endpoints.py
========================
Tambahkan ke main.py — endpoint untuk Deep Search dengan checkpoint backend.

Sisipkan:
  1. import di bagian atas main.py
  2. Model Pydantic di bagian MODELS
  3. Endpoint di bagian SEARCH (setelah /api/download/search-csv)

Atau include router ini langsung:
  app.include_router(deep_search_router)
"""

from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
import traceback

# Import job manager (letakkan search_checkpoint.py di folder yang sama dengan main.py)
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import search_checkpoint as sc

deep_search_router = APIRouter(prefix="/api/search/deep", tags=["Deep Search"])


# ── Models ─────────────────────────────────────────────────────────────────

class DeepHashtagRequest(BaseModel):
    hashtag: str
    # Config bisa dikosongkan — worker pakai default yang sudah optimal
    max_related_hashtags: int = 20   # berapa related hashtag yang di-expand
    include_top: bool = True


class DeepKeywordRequest(BaseModel):
    keyword: str
    max_hashtags: int = 10           # berapa hashtag relevan yang di-scrape


# ── Helper response ────────────────────────────────────────────────────────

def _ok(data: dict, msg: str = "OK"):
    from datetime import datetime
    return {"success": True, "message": msg, "timestamp": datetime.now().isoformat(), "data": data}

def _fail(msg: str):
    from datetime import datetime
    return {"success": False, "message": msg, "timestamp": datetime.now().isoformat(), "data": {}}


# ── Endpoints ──────────────────────────────────────────────────────────────

@deep_search_router.post("/hashtag")
def deep_search_hashtag(req: DeepHashtagRequest):
    """
    Mulai deep search hashtag.
    Scrape top + semua halaman recent + expand ke related hashtags.
    Return job_id untuk di-polling.
    """
    tag = req.hashtag.strip().lstrip("#").lower()
    if not tag:
        return _fail("Hashtag kosong")
    try:
        config = {
            "max_related_hashtags": req.max_related_hashtags,
            "include_top":          req.include_top,
        }
        job_id = sc.create_job("hashtag", tag, config)
        return _ok({"job_id": job_id, "mode": "hashtag", "query": tag},
                   f"Deep search #{tag} dimulai (job: {job_id})")
    except Exception as e:
        traceback.print_exc()
        return _fail(f"Gagal memulai job: {e}")


@deep_search_router.post("/keyword")
def deep_search_keyword(req: DeepKeywordRequest):
    """
    Mulai deep search keyword.
    Cari hashtag relevan via topsearch → scrape tiap hashtag secara mendalam.
    Return job_id untuk di-polling.
    """
    kw = req.keyword.strip()
    if not kw:
        return _fail("Keyword kosong")
    try:
        config = {"max_hashtags": req.max_hashtags}
        job_id = sc.create_job("keyword", kw, config)
        return _ok({"job_id": job_id, "mode": "keyword", "query": kw},
                   f"Deep search '{kw}' dimulai (job: {job_id})")
    except Exception as e:
        traceback.print_exc()
        return _fail(f"Gagal memulai job: {e}")


@deep_search_router.get("/jobs")
def list_deep_jobs():
    """Daftar semua job (ringkasan tanpa posts)."""
    try:
        jobs = sc.list_all_jobs()
        return _ok({"jobs": jobs, "count": len(jobs)})
    except Exception as e:
        return _fail(str(e))


@deep_search_router.get("/jobs/{job_id}")
def get_deep_job(job_id: str):
    """
    Status + progres job.
    Saat masih running: posts=[]. Saat completed: posts berisi semua hasil.
    """
    state = sc.get_job(job_id)
    if not state:
        return _fail(f"Job '{job_id}' tidak ditemukan")
    return _ok(state, f"Job {job_id}: {state.get('status')} ({state.get('total_fetched', 0)} posts)")


@deep_search_router.get("/jobs/{job_id}/posts")
def get_deep_job_posts(job_id: str):
    """
    Ambil HANYA posts dari job yang sudah completed.
    Endpoint terpisah agar tidak membebani polling status.
    """
    state = sc.get_job(job_id)
    if not state:
        return _fail(f"Job '{job_id}' tidak ditemukan")
    if state.get("status") != sc.JobStatus.COMPLETED:
        return _fail(f"Job belum selesai (status: {state.get('status')})")
    posts = sc.get_job_posts(job_id)
    return _ok({"posts": posts or [], "total": len(posts or [])})


@deep_search_router.post("/jobs/{job_id}/cancel")
def cancel_deep_job(job_id: str):
    """Cancel job yang sedang berjalan."""
    ok = sc.cancel_job(job_id)
    if ok:
        return _ok({"job_id": job_id, "cancelled": True}, "Job dibatalkan")
    return _fail(f"Job '{job_id}' tidak ditemukan atau sudah selesai")


@deep_search_router.delete("/jobs/{job_id}")
def delete_deep_job(job_id: str):
    """Hapus job (cancel + hapus file state)."""
    ok = sc.delete_job(job_id)
    if ok:
        return _ok({"job_id": job_id, "deleted": True}, "Job dihapus")
    return _fail(f"Job '{job_id}' tidak ditemukan")