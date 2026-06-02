"""
main.py — FastAPI Backend untuk Instagram Scraper
==================================================
Versi ini memanggil engine scraper LANGSUNG (via subprocess), tanpa perlu
menjalankan Flask server terpisah. Cukup 1 proses Python.

Struktur:
  backend/
    ├── main.py          ← file ini
    └── engine/          ← semua kode scraper kamu
         ├── scraper_post.py
         ├── profile_scraper.py
         ├── session_manager.py
         └── ...

Run:
  cd backend
  uvicorn main:app --reload --port 8000
"""
import os
import re
import sys
import json
import time
import subprocess
import tempfile
import traceback
from datetime import datetime
from typing import Optional, List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# ── PATH SETUP ──────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENGINE_DIR = os.path.join(BASE_DIR, "engine")
OUTPUT_DIR = os.path.join(ENGINE_DIR, "output")

sys.path.insert(0, ENGINE_DIR)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ── APP ──────────────────────────────────────────────────────────────────────
app = FastAPI(title="Instagram Scraper API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── MODELS ───────────────────────────────────────────────────────────────────

class ScrapePostRequest(BaseModel):
    url: str
    max_comments: int = 100

class ScrapePostsRequest(BaseModel):
    urls: List[str]
    max_comments: int = 100
    delay_between: int = 8

class ScrapeProfileRequest(BaseModel):
    username: str
    save_snapshot: bool = True

class LoginCookieRequest(BaseModel):
    cookies_json: str


# ── HELPERS ──────────────────────────────────────────────────────────────────

def success(data: dict, message: str = "Success"):
    return {
        "success": True,
        "message": message,
        "timestamp": datetime.now().isoformat(),
        "data": data,
    }

def failure(message: str, data: Optional[dict] = None):
    """Response gagal TAPI HTTP 200, supaya frontend bisa baca pesannya."""
    return {
        "success": False,
        "message": message,
        "timestamp": datetime.now().isoformat(),
        "data": data or {},
    }


# RESERVED: path Instagram yang BUKAN username
_IG_RESERVED = {
    "p", "reel", "reels", "tv", "stories", "explore",
    "accounts", "direct", "api", "share", "about",
}

def extract_username(raw: str) -> str:
    """
    Terima username ATAU URL Instagram, kembalikan username bersih.
      "prabowo"                              -> "prabowo"
      "@prabowo"                             -> "prabowo"
      "https://www.instagram.com/prabowo/"  -> "prabowo"
      "instagram.com/prabowo?hl=en"         -> "prabowo"
    """
    s = (raw or "").strip()

    if "instagram.com" in s.lower():
        m = re.search(r'instagram\.com/([^/?#]+)', s, re.I)
        if m:
            candidate = m.group(1).strip().lstrip("@").lower()
            if candidate and candidate not in _IG_RESERVED:
                return candidate
        return ""

    return s.lstrip("@").lower()


def sanitize_filename(name: str) -> str:
    """Buang karakter ilegal untuk nama file Windows/Linux."""
    cleaned = re.sub(r'[^A-Za-z0-9._-]', "_", name)
    return cleaned or "unknown"


def save_json_output(data: dict, filename: str) -> str:
    # FIX: sanitize nama file supaya tidak ada karakter ilegal (: / \ dll)
    safe_name = sanitize_filename(filename)
    fp = os.path.join(OUTPUT_DIR, safe_name)
    with open(fp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)
    return safe_name


def run_post_scraper(url: str, max_comments: int) -> dict:
    """Jalankan scraper_post.py sebagai subprocess (isolasi penuh)."""
    script = f"""
import sys
sys.path.insert(0, r'{ENGINE_DIR}')
from scraper_post import InstagramScraperV16
import json

with InstagramScraperV16() as scraper:
    result = scraper.scrape_post_comments({json.dumps(url)}, {max_comments})
    print("___RESULT_START___")
    print(json.dumps(result, ensure_ascii=False, default=str))
"""
    return _run_subprocess(script, timeout=300)


def run_profile_scraper(username: str) -> dict:
    """Jalankan profile_scraper.py sebagai subprocess."""
    script = f"""
import sys
sys.path.insert(0, r'{ENGINE_DIR}')
from profile_scraper import InstagramProfileScraper
import json

with InstagramProfileScraper() as scraper:
    result = scraper.scrape_profile({json.dumps(username)})
    print("___RESULT_START___")
    print(json.dumps(result, ensure_ascii=False, default=str))
"""
    return _run_subprocess(script, timeout=120)


def _run_subprocess(script: str, timeout: int) -> dict:
    """Jalankan script Python di subprocess, ambil JSON setelah marker."""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False, encoding="utf-8"
    ) as f:
        f.write(script)
        script_path = f.name

    try:
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"

        result = subprocess.run(
            [sys.executable, script_path],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=ENGINE_DIR,
            encoding="utf-8",
            errors="replace",
            env=env,
        )

        out = result.stdout or ""
        if "___RESULT_START___" in out:
            json_part = out.split("___RESULT_START___", 1)[1].strip()
            for line in json_part.split("\n"):
                line = line.strip()
                if line.startswith("{"):
                    try:
                        return json.loads(line)
                    except json.JSONDecodeError:
                        continue

        stderr_tail = (result.stderr or "")[-800:]
        stdout_tail = out[-400:]
        raise Exception(
            f"Tidak ada output JSON valid (returncode={result.returncode}).\n"
            f"STDERR: {stderr_tail}\n"
            f"STDOUT: {stdout_tail}"
        )

    finally:
        try:
            os.unlink(script_path)
        except Exception:
            pass


# ════════════════════════════════════════════════════════════════════════════
# ENDPOINTS - HEALTH
# ════════════════════════════════════════════════════════════════════════════

@app.get("/api/health")
def health():
    return success({
        "api": "running",
        "engine_dir": ENGINE_DIR,
        "output_dir": OUTPUT_DIR,
        "engine_files_found": os.path.exists(os.path.join(ENGINE_DIR, "scraper_post.py")),
    }, "FastAPI backend running")


# ════════════════════════════════════════════════════════════════════════════
# ENDPOINTS - AUTH (cookie based)
# ════════════════════════════════════════════════════════════════════════════

@app.post("/api/auth/cookies")
def save_cookies(req: LoginCookieRequest):
    try:
        import session_manager as sm
        cookies = sm.parse_cookie_json(req.cookies_json)
        ok, missing, _ = sm.validate_cookies(cookies)
        if not ok:
            raise HTTPException(400, f"Cookie wajib hilang: {', '.join(missing)}")
        payload = sm.save_session(cookies)
        return success({
            "user_id": payload.get("user_id"),
            "cookie_count": payload.get("cookie_count"),
            "saved_at": payload.get("saved_at"),
        }, "Cookies berhasil disimpan")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/auth/session")
def session_info():
    try:
        import session_manager as sm
        s = sm.load_session()
        if not s:
            return success({"has_session": False, "user_id": None}, "Belum login")
        expired = sm.is_session_expired(s)
        is_valid, missing, _ = sm.validate_cookies(s.get("cookies", []))
        return success({
            "has_session": True,
            "user_id": s.get("user_id"),
            "cookie_count": s.get("cookie_count"),
            "saved_at": s.get("saved_at"),
            "is_expired": expired,
            "is_valid": is_valid,
            "missing_cookies": missing,
        }, "Session info retrieved")
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/auth/logout")
def logout():
    try:
        import session_manager as sm
        sm.clear_session()
        return success({"cleared": True}, "Session dihapus")
    except Exception as e:
        raise HTTPException(500, str(e))


# ════════════════════════════════════════════════════════════════════════════
# ENDPOINTS - SCRAPE
# ════════════════════════════════════════════════════════════════════════════

@app.post("/api/scrape/post")
def scrape_post(req: ScrapePostRequest):
    try:
        t0 = time.time()
        result = run_post_scraper(req.url, req.max_comments)
        elapsed = round(time.time() - t0, 2)

        filename = f"api_post_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        save_json_output(result, filename)

        result["_meta"] = {"elapsed_seconds": elapsed, "saved_file": filename}
        msg = f"Scraped {result.get('comments_count', 0)} comments in {elapsed}s"
        return success(result, msg)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, f"Scrape failed: {str(e)}")


@app.post("/api/scrape/posts/batch")
def scrape_posts_batch(req: ScrapePostsRequest):
    import random
    results = []
    t0 = time.time()
    for i, url in enumerate(req.urls):
        try:
            r = run_post_scraper(url, req.max_comments)
            results.append({"url": url, "success": True, "data": r})
        except Exception as e:
            results.append({"url": url, "success": False, "error": str(e)})
        if i < len(req.urls) - 1:
            time.sleep(req.delay_between + random.randint(1, 3))

    summary = {
        "total": len(req.urls),
        "success": sum(1 for r in results if r["success"]),
        "failed": sum(1 for r in results if not r["success"]),
        "elapsed_seconds": round(time.time() - t0, 2),
        "results": results,
    }
    filename = f"api_batch_posts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    save_json_output(summary, filename)
    summary["saved_file"] = filename
    return success(summary, f"Batch: {summary['success']}/{summary['total']} success")


@app.post("/api/scrape/profile")
def scrape_profile(req: ScrapeProfileRequest):
    # FIX: terima username ATAU URL, lalu bersihkan
    username = extract_username(req.username)
    if not username:
        return failure(
            f"Tidak bisa menentukan username dari input: '{req.username}'. "
            "Masukkan username (mis. 'prabowo') atau URL profil yang valid.",
            {"profile": {"username": req.username, "success": False}},
        )

    try:
        t0 = time.time()
        result = run_profile_scraper(username)
        elapsed = round(time.time() - t0, 2)

        # FIX: nama file pakai username yang sudah bersih + sanitize
        filename = f"api_profile_{username}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        saved = save_json_output(result, filename)

        result["_meta"] = {"elapsed_seconds": elapsed, "saved_file": saved}

        if not result.get("success"):
            err = result.get("error", "Scrape gagal tanpa detail")
            return failure(
                f"Profile @{username} gagal: {err}",
                {"profile": result, **result},
            )

        return success(
            {"profile": result, **result},
            f"Profile @{username} scraped in {elapsed}s",
        )
    except Exception as e:
        traceback.print_exc()
        return failure(
            f"Profile @{username} error: {str(e)}",
            {"profile": {"username": username, "success": False, "error": str(e)}},
        )


# ════════════════════════════════════════════════════════════════════════════
# ENDPOINTS - OUTPUT FILES
# ════════════════════════════════════════════════════════════════════════════

@app.get("/api/output/list")
def list_output_files():
    files = []
    if os.path.exists(OUTPUT_DIR):
        for f in sorted(os.listdir(OUTPUT_DIR), reverse=True):
            if f.endswith(".json"):
                fp = os.path.join(OUTPUT_DIR, f)
                st = os.stat(fp)
                files.append({
                    "name": f,
                    "size": st.st_size,
                    "modified": datetime.fromtimestamp(st.st_mtime).isoformat(),
                })
    return success({"files": files, "count": len(files)})


@app.get("/api/output/{filename}")
def get_output_file(filename: str):
    if "/" in filename or "\\" in filename or not filename.endswith(".json"):
        raise HTTPException(400, "Nama file tidak valid")
    fp = os.path.join(OUTPUT_DIR, filename)
    if not os.path.exists(fp):
        raise HTTPException(404, "File tidak ditemukan")
    with open(fp, "r", encoding="utf-8") as f:
        return json.load(f)


# ════════════════════════════════════════════════════════════════════════════
# ENDPOINTS - ANALYTICS (placeholder: butuh storage_manager)
# ════════════════════════════════════════════════════════════════════════════

@app.get("/api/profiles")
def list_profiles():
    """List tracked profiles. Butuh storage_manager.py di engine."""
    try:
        from storage_manager import StorageManager
        storage = StorageManager()
        users = storage.list_tracked_users()
        return success({"users": users, "count": len(users)})
    except ImportError:
        return success({"users": [], "count": 0}, "storage_manager tidak tersedia")
    except Exception as e:
        return success({"users": [], "count": 0}, f"Error: {str(e)}")


@app.get("/api/profiles/{username}")
def get_profile_detail(username: str):
    try:
        from storage_manager import StorageManager
        storage = StorageManager()
        username = extract_username(username)
        profile = storage.get_profile(username)
        return success({"profile": profile, "username": username})
    except ImportError:
        raise HTTPException(503, "storage_manager tidak tersedia")
    except Exception as e:
        raise HTTPException(500, str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)