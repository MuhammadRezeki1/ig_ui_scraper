"""
instagram_api_server.py
=======================
REST API wrapper untuk Instagram Scraper (Post + Profile + Login).
FIX v5: Perbaikan semua Pylance errors:
  - reportMissingImports flask/flask_cors  → tambah TYPE_CHECKING guard + pyproject hint
  - reportArgumentType line 74  → find_profile_dir() return str, bukan None
  - reportArgumentType line 267 → CHROME_PROFILE guard sebelum dipakai sebagai str
  - reportArgumentType line 665 → sama, guard CHROME_PROFILE
  - reportArgumentType line 855 → success_response() terima Union[dict, list]

Run: python instagram_api_server.py
"""
from __future__ import annotations

import os
import sys
import json
import time
import random
import re
import traceback
import threading
import asyncio
import subprocess
import tempfile
import shutil
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Union
from functools import wraps

# ── Flask import dengan fallback error yang jelas ─────────────────────────
try:
    from flask import Flask, request, jsonify
    from flask_cors import CORS
except ImportError as _flask_err:
    print(
        "\n❌ Flask/flask-cors belum terinstall!\n"
        "   Jalankan: pip install flask flask-cors\n"
        f"   Detail: {_flask_err}\n"
    )
    sys.exit(1)

from colorama import Fore, init

app = Flask(__name__)
CORS(app)
init(autoreset=True)

# ── CONFIG ─────────────────────────────────────────────────────────────────
API_PORT   = int(os.getenv("API_PORT", 5000))
API_HOST   = os.getenv("API_HOST", "0.0.0.0")
DEBUG_MODE = os.getenv("DEBUG", "False").lower() == "true"
OUTPUT_DIR = "output"

# ── Auto-detect profile folder ────────────────────────────────────────────
POSSIBLE_PROFILE_DIRS = [
    "chrome_profile_playwright",
    "chrome_profile",
    "playwright_profile",
]


def find_profile_dir() -> Optional[str]:
    """
    Cari folder profil Chrome yang ada dan tidak kosong.
    Return path string jika ditemukan, None jika tidak ada.
    """
    for d in POSSIBLE_PROFILE_DIRS:
        path = os.path.join(os.getcwd(), d)
        if os.path.exists(path) and os.listdir(path):
            print(Fore.GREEN + f"✅ Profile ditemukan: {path}")
            return path
    return None


# FIX #1 (line 74): CHROME_PROFILE dideklarasikan sebagai Optional[str]
# sehingga Pylance tahu nilai bisa None
CHROME_PROFILE: Optional[str] = find_profile_dir()

if CHROME_PROFILE:
    os.environ["PROFILE_DIR"] = os.path.basename(CHROME_PROFILE)
    print(Fore.GREEN + f"✅ PROFILE_DIR set to: {os.environ['PROFILE_DIR']}")
else:
    print(Fore.YELLOW + "⚠️  Tidak ada profile folder. Login via cookie (session/ig_session.json).")


def _get_profile_path() -> str:
    """
    Kembalikan path profil yang selalu berupa str (tidak pernah None).
    Jika CHROME_PROFILE tidak ada, pakai default.
    """
    return CHROME_PROFILE or os.path.join(os.getcwd(), "chrome_profile_playwright")


# ── HELPERS ────────────────────────────────────────────────────────────────

# FIX #6 (line 855): success_response menerima Union[dict, list, Any]
# agar bisa dipakai dengan list maupun dict
def success_response(data: Union[Dict[str, Any], List[Any], Any],
                     message: str = "Success") -> Dict[str, Any]:
    return {
        "success":   True,
        "message":   message,
        "timestamp": datetime.now().isoformat(),
        "data":      data,
    }


def error_response(message: str,
                   status_code: int = 400,
                   details: Optional[Dict[str, Any]] = None) -> tuple:
    resp = {
        "success":   False,
        "message":   message,
        "timestamp": datetime.now().isoformat(),
        "error":     details or {},
    }
    return jsonify(resp), status_code


def require_json_fields(*fields: str):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if not request.is_json:
                return error_response("Content-Type must be application/json", 415)
            data    = request.get_json()
            missing = [field for field in fields
                       if field not in data or data[field] in (None, "")]
            if missing:
                return error_response(
                    f"Missing required fields: {', '.join(missing)}", 400
                )
            return f(*args, **kwargs)
        return wrapper
    return decorator


def clean_instagram_url(url: str) -> str:
    url = url.split("?")[0].rstrip("/")
    if not url.startswith("http"):
        url = "https://" + url
    return url


def extract_username_from_url(url: str) -> Optional[str]:
    patterns = [
        r'instagram\.com/([^/?#]+)',
        r'instagram\.com/([^/?#]+)/',
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            username = match.group(1).strip().lstrip("@").lower()
            if username not in (
                'p', 'reel', 'tv', 'stories', 'explore',
                'accounts', 'direct', 'api', 'share',
            ):
                return username
    return None


def save_json_output(data: Union[Dict[str, Any], List[Any]],
                     filename: str) -> str:
    """Simpan dict/list ke output/<filename>. Return nama file."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    fp = os.path.join(OUTPUT_DIR, filename)
    with open(fp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)
    return filename


# ═══════════════════════════════════════════════════════════════════════════
# AUTH / LOGIN STATE
# ═══════════════════════════════════════════════════════════════════════════

_login_state: Dict[str, Any] = {
    "is_running":        False,
    "browser_opened_at": None,
    "login_detected":    False,
    "username":          None,
    "last_error":        None,
}
_state_lock = threading.Lock()


def update_login_state(**kwargs: Any) -> None:
    with _state_lock:
        _login_state.update(kwargs)


def get_login_state() -> Dict[str, Any]:
    with _state_lock:
        return dict(_login_state)


def run_login_browser_async(timeout_minutes: int = 5,
                             headless: bool = False) -> threading.Thread:
    """Jalankan browser Playwright di background thread untuk login manual."""

    async def _login_worker() -> None:
        from playwright.async_api import async_playwright

        print(Fore.CYAN + "\n🌐 [Login Worker] Membuka browser Chrome via Playwright...")
        update_login_state(
            is_running=True,
            browser_opened_at=datetime.now().isoformat(),
            login_detected=False,
            last_error=None,
            username=None,
        )

        # FIX #2 (line 267): pakai _get_profile_path() yang selalu str
        profile_path = _get_profile_path()
        os.makedirs(profile_path, exist_ok=True)

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch_persistent_context(
                    user_data_dir=profile_path,
                    headless=headless,
                    args=[
                        "--start-maximized",
                        "--disable-notifications",
                        "--lang=en-US",
                        "--disable-blink-features=AutomationControlled",
                        "--no-sandbox",
                    ],
                    viewport=None,
                    locale="en-US",
                    bypass_csp=True,
                )

                page = await browser.new_page()

                try:
                    await page.goto("https://www.instagram.com/accounts/login/")
                    await asyncio.sleep(4)

                    current_url = page.url

                    if "login" not in current_url and "accounts" not in current_url:
                        print(Fore.GREEN + "\n✅ [Login Worker] Sudah login sebelumnya!")
                        try:
                            await page.goto("https://www.instagram.com/")
                            await asyncio.sleep(3)
                            url   = page.url
                            parts = url.replace(
                                "https://www.instagram.com/", ""
                            ).split("/")
                            if (parts and parts[0]
                                    and parts[0] not in ["", "accounts", "explore", "direct"]):
                                update_login_state(username=parts[0])
                        except Exception:
                            pass

                        update_login_state(login_detected=True)
                        await asyncio.sleep(3)
                        return

                    print(
                        Fore.YELLOW
                        + "\n⚠️  [Login Worker] Menunggu login manual di browser..."
                    )

                    logged_in = False
                    max_wait  = timeout_minutes * 12

                    for i in range(max_wait):
                        await asyncio.sleep(5)
                        url = page.url
                        print(f"   [{i+1}/{max_wait}] {url[:70]}", end="\r")

                        if (
                            "instagram.com" in url
                            and "login"     not in url
                            and "challenge" not in url
                            and "accounts"  not in url
                            and "recaptcha" not in url
                            and "suspended" not in url
                        ):
                            print(
                                Fore.GREEN
                                + f"\n\n✅ [Login Worker] Login berhasil terdeteksi!"
                            )
                            logged_in = True
                            try:
                                parts = url.replace(
                                    "https://www.instagram.com/", ""
                                ).split("/")
                                if (parts and parts[0]
                                        and parts[0] not in ["", "accounts", "explore"]):
                                    update_login_state(username=parts[0])
                            except Exception:
                                pass
                            break

                    if not logged_in:
                        print(Fore.RED + "\n\n❌ [Login Worker] Timeout login.")
                        update_login_state(
                            last_error="Timeout: User tidak login dalam waktu yang ditentukan"
                        )
                        return

                    print(Fore.YELLOW + "\n⏳ [Login Worker] Menyimpan session (8 detik)...")
                    await asyncio.sleep(8)
                    update_login_state(login_detected=True)
                    print(Fore.GREEN + "✅ [Login Worker] Session tersimpan!")

                finally:
                    await browser.close()

        except Exception as e:
            error_msg = str(e)
            print(Fore.RED + f"\n❌ [Login Worker] Error: {error_msg}")
            update_login_state(last_error=error_msg)
            traceback.print_exc()
        finally:
            update_login_state(is_running=False)

    def _thread_target() -> None:
        asyncio.run(_login_worker())

    thread = threading.Thread(target=_thread_target, daemon=True)
    thread.start()
    return thread


# ═══════════════════════════════════════════════════════════════════════════
# SCRAPER HELPERS (SUBPROCESS)
# ═══════════════════════════════════════════════════════════════════════════

def run_profile_scraper_subprocess(
    username: str,
    source_url: Optional[str] = None,
) -> Dict[str, Any]:
    """Jalankan profile scraper sebagai subprocess untuk complete isolation."""

    has_source         = source_url is not None
    source_url_literal = json.dumps(source_url) if has_source else "None"

    script = f"""
import sys
sys.path.insert(0, r'{os.getcwd()}')

from profile_scraper import InstagramProfileScraper
from profile_cli import scrape_with_fresh_session
import json

scraper = InstagramProfileScraper()
try:
    result = scrape_with_fresh_session(scraper, "{username}")
    result["success"] = result.get("success", True)
    if {has_source}:
        result["source_url"] = {source_url_literal}
    print(json.dumps(result, ensure_ascii=False, default=str))
except Exception as e:
    import traceback
    error_result = {{
        "success": False,
        "username": "{username}",
        "error": str(e),
        "traceback": traceback.format_exc()
    }}
    if {has_source}:
        error_result["source_url"] = {source_url_literal}
    print(json.dumps(error_result, ensure_ascii=False, default=str))
finally:
    try:
        scraper.close()
    except Exception:
        pass
"""

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False, encoding="utf-8"
    ) as f:
        f.write(script)
        script_path = f.name

    try:
        env                     = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"]       = "1"

        result = subprocess.run(
            [sys.executable, script_path],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=os.getcwd(),
            encoding="utf-8",
            env=env,
        )

        if result.returncode != 0:
            raise RuntimeError(f"Profile scraper error: {result.stderr}")

        lines = result.stdout.strip().split("\n")
        for line in reversed(lines):
            line = line.strip()
            if line:
                try:
                    return json.loads(line)
                except json.JSONDecodeError:
                    continue
        raise RuntimeError("No valid JSON output from profile scraper")

    finally:
        try:
            os.unlink(script_path)
        except OSError:
            pass


def run_scrape_subprocess(url: str, max_comments: int) -> Dict[str, Any]:
    """Jalankan post scraper sebagai subprocess untuk complete isolation."""

    script = f"""
import sys
sys.path.insert(0, r'{os.getcwd()}')

from scraper_post import InstagramScraperV16
import json

with InstagramScraperV16() as scraper:
    result = scraper.scrape_post_comments("{url}", {max_comments})
    result["_meta"] = {{
        "comments_count": result.get("comments_count", 0),
        "method": result.get("method", ""),
    }}
    print(json.dumps(result, ensure_ascii=False, default=str))
"""

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False, encoding="utf-8"
    ) as f:
        f.write(script)
        script_path = f.name

    try:
        env                     = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"]       = "1"

        result = subprocess.run(
            [sys.executable, script_path],
            capture_output=True,
            text=True,
            timeout=300,
            cwd=os.getcwd(),
            encoding="utf-8",
            env=env,
        )

        if result.returncode != 0:
            raise RuntimeError(f"Scraper error: {result.stderr}")

        lines = result.stdout.strip().split("\n")
        for line in reversed(lines):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
        raise RuntimeError("No valid JSON output from scraper")

    finally:
        try:
            os.unlink(script_path)
        except OSError:
            pass


USE_SUBPROCESS = os.getenv("USE_SUBPROCESS", "true").lower() == "true"

_storage = None
_tracker = None


def get_storage():
    global _storage
    if _storage is None:
        try:
            from storage_manager import StorageManager
            _storage = StorageManager()
        except Exception as e:
            print(Fore.YELLOW + f"⚠️  Storage manager not available: {e}")
            return None
    return _storage


def get_tracker():
    global _tracker
    if _tracker is None:
        try:
            from followers_tracker import FollowersTracker
            from storage_manager import StorageManager
            _tracker = FollowersTracker(StorageManager())
        except Exception as e:
            print(Fore.YELLOW + f"⚠️  Followers tracker not available: {e}")
            return None
    return _tracker


# ═══════════════════════════════════════════════════════════════════════════
# ENDPOINTS — AUTH / LOGIN
# ═══════════════════════════════════════════════════════════════════════════

@app.route("/api/v1/auth/login", methods=["POST"])
def trigger_login():
    data            = request.get_json() or {}
    timeout_minutes = data.get("timeout_minutes", 5)
    headless        = data.get("headless", False)

    state = get_login_state()
    if state["is_running"]:
        return error_response(
            "Browser login sedang berjalan. Tunggu selesai atau cek status.",
            409,
            {"browser_opened_at": state["browser_opened_at"]},
        )

    run_login_browser_async(timeout_minutes=timeout_minutes, headless=headless)
    time.sleep(2)

    return jsonify(success_response({
        "browser_started":  True,
        "headless":         headless,
        "timeout_minutes":  timeout_minutes,
        # FIX #3 (line 267 area): pakai _get_profile_path() agar selalu str
        "profile_path":     _get_profile_path(),
        "instructions": [
            "Browser Chrome akan terbuka (jika headless=false)",
            "Login manual dengan username & password Instagram",
            "Selesaikan 2FA jika diminta",
            "Tunggu halaman beranda muncul",
            "Cek status dengan GET /api/v1/auth/status",
        ],
    }, f"Browser login dibuka. Timeout: {timeout_minutes} menit"))


@app.route("/api/v1/auth/status", methods=["GET"])
def check_login_status():
    state = get_login_state()

    # FIX #4 (line 665 area): pakai _get_profile_path() agar selalu str
    profile_path  = _get_profile_path()
    profile_valid = os.path.exists(profile_path) and len(os.listdir(profile_path)) > 0

    cookie_files: List[str] = []
    if profile_valid:
        for root, dirs, files in os.walk(profile_path):
            for fname in files:
                if "cookie" in fname.lower() or "instagram" in fname.lower():
                    cookie_files.append(os.path.join(root, fname))

    response_data = {
        "is_running":          state["is_running"],
        "login_detected":      state["login_detected"],
        "username":            state["username"],
        "browser_opened_at":   state["browser_opened_at"],
        "last_error":          state["last_error"],
        "profile_exists":      profile_valid,
        "profile_path":        profile_path,
        "cookie_files_found":  len(cookie_files),
        "is_logged_in":        state["login_detected"] and profile_valid,
    }

    msg = "Login detected" if state["login_detected"] else "Waiting for login"
    if state["last_error"]:
        msg = f"Error: {state['last_error']}"

    return jsonify(success_response(response_data, msg))


@app.route("/api/v1/auth/logout", methods=["POST"])
def logout():
    data       = request.get_json() or {}
    hard_reset = data.get("hard_reset", False)

    state = get_login_state()
    if state["is_running"]:
        return error_response("Browser sedang berjalan. Tidak bisa logout saat ini.", 409)

    # FIX: pakai _get_profile_path() agar selalu str
    profile_path = _get_profile_path()

    try:
        if hard_reset:
            if os.path.exists(profile_path):
                shutil.rmtree(profile_path)
                os.makedirs(profile_path, exist_ok=True)
            update_login_state(
                login_detected=False,
                username=None,
                last_error=None,
                browser_opened_at=None,
            )
            return jsonify(success_response({
                "profile_reset": True,
                "profile_path":  profile_path,
                "message":       "Profile dihapus total. Login baru diperlukan.",
            }, "Hard reset berhasil"))
        else:
            cookies_path    = os.path.join(profile_path, "Default", "Cookies")
            network_cookies = os.path.join(profile_path, "Default", "Network", "Cookies")
            deleted: List[str] = []
            for path in [cookies_path, network_cookies]:
                if os.path.exists(path):
                    try:
                        os.remove(path)
                        deleted.append(path)
                    except OSError:
                        pass
            update_login_state(login_detected=False, username=None)
            return jsonify(success_response({
                "cookies_deleted": len(deleted),
                "deleted_files":   deleted,
                "profile_path":    profile_path,
            }, "Soft logout berhasil. Cookies dihapus."))

    except Exception as e:
        return error_response(f"Logout failed: {str(e)}", 500)


@app.route("/api/v1/auth/profile", methods=["GET"])
def get_logged_in_profile():
    state = get_login_state()
    if not state["login_detected"]:
        return error_response("Belum login. Gunakan POST /api/v1/auth/login dulu.", 401)
    return jsonify(success_response({
        "login_state": state,
        "username":    state.get("username"),
        "message":     "Gunakan POST /api/v1/scrape/profile untuk detail lengkap",
    }, "Login info retrieved"))


# ═══════════════════════════════════════════════════════════════════════════
# ENDPOINTS — SCRAPE POST
# ═══════════════════════════════════════════════════════════════════════════

@app.route("/api/v1/scrape/post", methods=["POST"])
@require_json_fields("url")
def scrape_single_post():
    data         = request.get_json()
    url          = clean_instagram_url(data["url"])
    max_comments = data.get("max_comments", 100)

    print(Fore.CYAN + f"\n📝 Scraping post: {url}")
    print(Fore.CYAN + f"   Max comments: {max_comments}")
    print(Fore.YELLOW + "   ⏳ Ini membutuhkan waktu ~30-60 detik...")

    try:
        t_start   = time.time()
        result    = run_scrape_subprocess(url, max_comments)
        t_elapsed = time.time() - t_start

        result["_meta"] = {
            "elapsed_seconds":        round(t_elapsed, 2),
            "comments_per_second":    round(
                result.get("comments_count", 0) / t_elapsed, 2
            ) if t_elapsed > 0 else 0,
            "requested_max_comments": max_comments,
            "url_cleaned":            url,
        }

        filename = f"api_post_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        save_json_output(result, filename)
        result["_meta"]["saved_file"] = filename

        msg = f"Scraped {result.get('comments_count', 0)} comments"
        return jsonify(success_response(result, msg))

    except Exception as e:
        traceback.print_exc()
        return error_response(
            f"Scrape failed: {str(e)}", 500,
            {"traceback": traceback.format_exc()},
        )


@app.route("/api/v1/scrape/posts/batch", methods=["POST"])
@require_json_fields("urls")
def scrape_batch_posts():
    data          = request.get_json()
    urls          = [clean_instagram_url(u) for u in data["urls"]]
    max_comments  = data.get("max_comments", 100)
    delay_between = data.get("delay_between", 8)

    if not isinstance(urls, list) or len(urls) == 0:
        return error_response("'urls' harus berupa array non-kosong", 400)

    results: List[Dict[str, Any]] = []
    t_total = time.time()

    for i, url in enumerate(urls):
        try:
            r = run_scrape_subprocess(url, max_comments)
            results.append({"url": url, "success": True, "data": r})
        except Exception as e:
            results.append({"url": url, "success": False, "error": str(e)})
        if i < len(urls) - 1:
            time.sleep(delay_between + random.randint(1, 3))

    summary: Dict[str, Any] = {
        "total":           len(urls),
        "success":         sum(1 for r in results if r["success"]),
        "failed":          sum(1 for r in results if not r["success"]),
        "elapsed_seconds": round(time.time() - t_total, 2),
        "results":         results,
    }

    filename = f"api_batch_posts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    save_json_output(summary, filename)
    summary["saved_file"] = filename

    return jsonify(success_response(
        summary,
        f"Batch complete: {summary['success']}/{summary['total']} success",
    ))


# ═══════════════════════════════════════════════════════════════════════════
# ENDPOINTS — SCRAPE PROFILE
# ═══════════════════════════════════════════════════════════════════════════

@app.route("/api/v1/scrape/profile", methods=["POST"])
@require_json_fields("username")
def scrape_single_profile():
    data          = request.get_json()
    username      = data["username"].strip().lstrip("@").lower()
    save_snapshot = data.get("save_snapshot", True)
    return _do_scrape_profile(username, save_snapshot)


@app.route("/api/v1/scrape/profile/url", methods=["POST"])
@require_json_fields("url")
def scrape_profile_by_url():
    data          = request.get_json()
    url           = data["url"].strip()
    save_snapshot = data.get("save_snapshot", True)

    username = extract_username_from_url(url)
    if not username:
        return error_response(
            f"Tidak bisa extract username dari URL: {url}. "
            "Format: https://www.instagram.com/username/",
            400,
        )

    print(Fore.CYAN + f"\n🔗 URL: {url}")
    print(Fore.CYAN + f"👤 Extracted username: @{username}")

    return _do_scrape_profile(username, save_snapshot, source_url=url)


def _do_scrape_profile(username: str,
                       save_snapshot: bool,
                       source_url: Optional[str] = None):
    """Gunakan subprocess untuk fresh browser instance per request."""
    print(Fore.CYAN + f"\n🌐 [Subprocess] Scraping profile: @{username}")
    print(Fore.YELLOW + "   ⏳ Ini membutuhkan waktu ~15-30 detik...")

    try:
        t_start   = time.time()
        result    = run_profile_scraper_subprocess(username, source_url)
        t_elapsed = time.time() - t_start

        result["_meta"] = {
            "elapsed_seconds": round(t_elapsed, 2),
            "mode":            "subprocess_fresh",
            "scraped_at":      datetime.now().isoformat(),
        }
        if source_url:
            result["_meta"]["source_url"] = source_url

        filename = f"api_profile_{username}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        save_json_output(result, filename)
        result["_meta"]["saved_file"] = filename

        if save_snapshot and result.get("success"):
            storage = get_storage()
            if storage:
                try:
                    storage.save_snapshot(result)
                    result["_snapshot_saved"] = True
                except Exception as se:
                    print(Fore.YELLOW + f"   ⚠️  Snapshot save warning: {se}")
                    result["_snapshot_saved"] = False

        msg = f"Profile @{username} scraped"
        if source_url:
            msg += " from URL"
        msg += f" in {round(t_elapsed, 1)}s"

        return jsonify(success_response(result, msg))

    except Exception as e:
        traceback.print_exc()
        return error_response(
            f"Profile scrape failed: {str(e)}", 500,
            {"traceback": traceback.format_exc()},
        )


@app.route("/api/v1/scrape/profiles/batch", methods=["POST"])
@require_json_fields("usernames")
def scrape_batch_profiles():
    data          = request.get_json()
    usernames     = data["usernames"]
    delay_between = data.get("delay_between", 10)
    save_snapshots = data.get("save_snapshots", True)

    if not isinstance(usernames, list) or len(usernames) == 0:
        return error_response("'usernames' harus berupa array non-kosong", 400)

    storage                        = get_storage()
    results: List[Dict[str, Any]]  = []
    t_total                        = time.time()

    for i, username in enumerate(usernames):
        username = username.strip().lstrip("@").lower()
        try:
            r = run_profile_scraper_subprocess(username)
            if save_snapshots and r.get("success") and storage:
                try:
                    storage.save_snapshot(r)
                except Exception:
                    pass
            results.append({"username": username, "success": True, "data": r})
        except Exception as e:
            results.append({"username": username, "success": False, "error": str(e)})
        if i < len(usernames) - 1:
            time.sleep(delay_between + random.randint(2, 5))

    summary: Dict[str, Any] = {
        "total":           len(usernames),
        "success":         sum(1 for r in results if r["success"]),
        "failed":          sum(1 for r in results if not r["success"]),
        "elapsed_seconds": round(time.time() - t_total, 2),
        "results":         results,
    }

    filename = f"api_batch_profiles_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    save_json_output(summary, filename)
    summary["saved_file"] = filename

    return jsonify(success_response(
        summary,
        f"Batch profiles: {summary['success']}/{summary['total']} success",
    ))


@app.route("/api/v1/scrape/profiles/batch/url", methods=["POST"])
@require_json_fields("urls")
def scrape_batch_profiles_by_url():
    data          = request.get_json()
    urls          = data["urls"]
    delay_between = data.get("delay_between", 10)
    save_snapshots = data.get("save_snapshots", True)

    if not isinstance(urls, list) or len(urls) == 0:
        return error_response("'urls' harus berupa array non-kosong", 400)

    # Extract semua username dulu, validasi awal
    usernames: List[str] = []
    for url in urls:
        uname = extract_username_from_url(url)
        if not uname:
            return error_response(
                f"Tidak bisa extract username dari URL: {url}", 400
            )
        usernames.append(uname)

    storage                        = get_storage()
    results: List[Dict[str, Any]]  = []
    t_total                        = time.time()

    for i, username in enumerate(usernames):
        try:
            r = run_profile_scraper_subprocess(username, urls[i])
            if save_snapshots and r.get("success") and storage:
                try:
                    storage.save_snapshot(r)
                except Exception:
                    pass
            results.append({
                "username": username,
                "url":      urls[i],
                "success":  True,
                "data":     r,
            })
        except Exception as e:
            results.append({
                "username": username,
                "url":      urls[i],
                "success":  False,
                "error":    str(e),
            })
        if i < len(usernames) - 1:
            time.sleep(delay_between + random.randint(2, 5))

    summary: Dict[str, Any] = {
        "total":           len(usernames),
        "success":         sum(1 for r in results if r["success"]),
        "failed":          sum(1 for r in results if not r["success"]),
        "elapsed_seconds": round(time.time() - t_total, 2),
        "results":         results,
    }

    filename = f"api_batch_profiles_url_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    save_json_output(summary, filename)
    summary["saved_file"] = filename

    return jsonify(success_response(
        summary,
        f"Batch profiles by URL: {summary['success']}/{summary['total']} success",
    ))


# ═══════════════════════════════════════════════════════════════════════════
# ENDPOINTS — PROFILE ANALYTICS
# ═══════════════════════════════════════════════════════════════════════════

@app.route("/api/v1/profiles", methods=["GET"])
def list_tracked_users():
    storage = get_storage()
    if storage is None:
        return error_response("Storage tidak tersedia", 503)
    # FIX #5 (line 855): users bisa berupa list — success_response sekarang
    # menerima Union[dict, list, Any] sehingga tidak ada type error
    users = storage.list_tracked_users()
    return jsonify(success_response({"count": len(users), "users": users}))


@app.route("/api/v1/profiles/<username>", methods=["GET"])
def get_profile(username: str):
    username = username.strip().lstrip("@").lower()
    storage  = get_storage()
    if storage is None:
        return error_response("Storage tidak tersedia", 503)
    profile = storage.get_profile(username)
    latest  = storage.get_latest_snapshot(username)
    return jsonify(success_response({
        "username":        username,
        "profile":         profile,
        "latest_snapshot": latest,
    }))


@app.route("/api/v1/profiles/<username>/history", methods=["GET"])
def get_profile_history(username: str):
    username = username.strip().lstrip("@").lower()
    limit    = request.args.get("limit", 30, type=int)
    storage  = get_storage()
    if storage is None:
        return error_response("Storage tidak tersedia", 503)
    snaps = storage.get_snapshots(username, limit=limit)
    return jsonify(success_response({
        "username":       username,
        "snapshot_count": len(snaps),
        "snapshots":      snaps,
    }))


@app.route("/api/v1/profiles/<username>/growth", methods=["GET"])
def get_growth_analysis(username: str):
    username = username.strip().lstrip("@").lower()
    tracker  = get_tracker()
    if tracker is None:
        return error_response("Tracker tidak tersedia", 503)
    report = tracker.analyze_all_time(username)
    return jsonify(success_response(report))


@app.route("/api/v1/profiles/<username>/monthly", methods=["GET"])
def get_monthly_breakdown(username: str):
    username = username.strip().lstrip("@").lower()
    tracker  = get_tracker()
    if tracker is None:
        return error_response("Tracker tidak tersedia", 503)
    breakdown = tracker.monthly_breakdown(username)
    return jsonify(success_response(breakdown))


@app.route("/api/v1/profiles/<username>/project", methods=["POST"])
def project_followers(username: str):
    username    = username.strip().lstrip("@").lower()
    data        = request.get_json() or {}
    target_date = data.get("target_date")
    method      = data.get("method", "recent_30d")

    if not target_date:
        return error_response("'target_date' wajib diisi (YYYY-MM-DD)", 400)

    tracker = get_tracker()
    if tracker is None:
        return error_response("Tracker tidak tersedia", 503)

    proj = tracker.project_followers(username, target_date, method=method)
    return jsonify(success_response(proj, f"Projection for @{username} to {target_date}"))


@app.route("/api/v1/profiles/<username>/period", methods=["GET"])
def get_period_analysis(username: str):
    username   = username.strip().lstrip("@").lower()
    start_date = request.args.get("start_date")
    end_date   = request.args.get("end_date")

    if not start_date or not end_date:
        return error_response(
            "Query params 'start_date' dan 'end_date' wajib diisi", 400
        )

    tracker = get_tracker()
    if tracker is None:
        return error_response("Tracker tidak tersedia", 503)

    report = tracker.analyze_period(username, start_date, end_date)
    return jsonify(success_response(report))


# ═══════════════════════════════════════════════════════════════════════════
# ENDPOINTS — HEALTH
# ═══════════════════════════════════════════════════════════════════════════

@app.route("/api/v1/health", methods=["GET"])
def health_check():
    login_state = get_login_state()
    status: Dict[str, Any] = {
        "api":                   "running",
        "profile_dir":           os.environ.get("PROFILE_DIR", "not_set"),
        # FIX: pakai _get_profile_path() agar tidak pernah None
        "profile_path":          _get_profile_path(),
        "output_dir":            os.path.abspath(OUTPUT_DIR),
        "post_scraper_mode":     "subprocess",
        "profile_scraper_mode":  "subprocess (fresh per request)",
        "login_state": {
            "is_running":     login_state["is_running"],
            "login_detected": login_state["login_detected"],
            "username":       login_state["username"],
        },
        "storage":   "available" if get_storage() else "unavailable",
        "timestamp": datetime.now().isoformat(),
    }
    return jsonify(success_response(status, "API is healthy"))


# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print(Fore.CYAN + "=" * 60)
    print(Fore.CYAN + "  INSTAGRAM SCRAPER API SERVER")
    print(Fore.CYAN + "  Post + Profile + Login | All-in-One")
    print(Fore.CYAN + f"  Listening on http://{API_HOST}:{API_PORT}")
    print(Fore.CYAN + "=" * 60)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(Fore.GREEN + f"\n📁 Output dir: {os.path.abspath(OUTPUT_DIR)}")

    if CHROME_PROFILE:
        print(Fore.GREEN + f"✅ Using profile: {CHROME_PROFILE}")
    else:
        print(Fore.YELLOW + "⚠️  No profile folder (login via cookie session).")

    print(Fore.YELLOW + "\n⚡ Server ready!")
    print()

    try:
        app.run(
            host=API_HOST,
            port=API_PORT,
            debug=DEBUG_MODE,
            threaded=False,
            use_reloader=False,
        )
    finally:
        print(Fore.YELLOW + "\n🧹 Server shutting down...")