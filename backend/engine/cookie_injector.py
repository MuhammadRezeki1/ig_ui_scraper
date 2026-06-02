"""
cookie_injector.py
==================
Jembatan antara login-via-cookie (Cookie-Editor JSON) dengan engine
yang memakai Playwright persistent context.

FIX: Path session sekarang ABSOLUT & dicari di beberapa lokasi, supaya
tidak tergantung pada cwd (current working directory). Ini penting karena
main.py menjalankan scraper dengan cwd=engine/, sedangkan file session
bisa berada di backend/session/.
"""
import os
import json
from typing import List, Dict

REQUIRED_COOKIES = {"sessionid", "ds_user_id", "csrftoken"}

_SAMESITE_MAP = {
    "no_restriction": "None",
    "unspecified": "Lax",
    "lax": "Lax",
    "strict": "Strict",
    "none": "None",
}

# ── CARI SESSION FILE DI BEBERAPA LOKASI ─────────────────────────────────────
# Urutan pencarian:
#   1. ENV var SESSION_FILE (kalau di-set manual)
#   2. backend/session/ig_session.json   (folder backend, satu level di atas engine/)
#   3. engine/session/ig_session.json    (folder engine ini sendiri)
#   4. cwd/session/ig_session.json        (current working directory)

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))          # .../backend/engine
_BACKEND_DIR = os.path.dirname(_THIS_DIR)                        # .../backend

def _candidate_paths() -> List[str]:
    candidates = []
    env_path = os.getenv("SESSION_FILE")
    if env_path:
        candidates.append(env_path)
    candidates.extend([
        os.path.join(_BACKEND_DIR, "session", "ig_session.json"),  # backend/session/
        os.path.join(_THIS_DIR,    "session", "ig_session.json"),  # engine/session/
        os.path.join(os.getcwd(),  "session", "ig_session.json"),  # cwd/session/
    ])
    return candidates


def _find_session_file() -> str:
    """Cari file session yang benar-benar ada. Return path pertama yang ketemu."""
    for path in _candidate_paths():
        if path and os.path.exists(path):
            return path
    # Kalau tidak ketemu, kembalikan kandidat utama (backend/session) untuk pesan error
    return os.path.join(_BACKEND_DIR, "session", "ig_session.json")


# Path final (dievaluasi saat import)
SESSION_FILE = _find_session_file()
SESSION_DIR = os.path.dirname(SESSION_FILE)


# ── LOAD ─────────────────────────────────────────────────────────────────────

def load_raw_cookies() -> List[Dict]:
    """Muat cookies mentah (Cookie-Editor format) dari session file."""
    # Re-cari setiap kali (kalau file baru dibuat setelah import)
    path = _find_session_file()
    if not os.path.exists(path):
        searched = "\n  ".join(_candidate_paths())
        raise FileNotFoundError(
            f"Session belum ada. Dicari di:\n  {searched}\n"
            "Login dulu lewat UI (paste cookies)."
        )
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    cookies = data.get("cookies", [])
    if not cookies:
        raise ValueError("Session file tidak berisi cookies.")
    return cookies


def has_valid_session() -> bool:
    """Cek cepat apakah session file ada & punya cookie wajib."""
    try:
        cookies = load_raw_cookies()
    except Exception:
        return False
    names = {c.get("name") for c in cookies}
    return REQUIRED_COOKIES.issubset(names)


# ── KONVERSI ─────────────────────────────────────────────────────────────────

def to_playwright_cookies(cookies: List[Dict]) -> List[Dict]:
    """Cookie-Editor format → format add_cookies() Playwright."""
    out = []
    for c in cookies:
        name = c.get("name")
        value = c.get("value")
        if not name or value is None:
            continue

        pw = {
            "name": name,
            "value": value,
            "domain": c.get("domain", ".instagram.com"),
            "path": c.get("path", "/"),
            "httpOnly": bool(c.get("httpOnly", False)),
            "secure": bool(c.get("secure", True)),
            "sameSite": _SAMESITE_MAP.get(str(c.get("sameSite", "unspecified")).lower(), "Lax"),
        }
        exp = c.get("expirationDate")
        pw["expires"] = float(exp) if exp is not None else -1
        out.append(pw)
    return out


# ── INJECT (SYNC) ────────────────────────────────────────────────────────────

def inject_cookies_sync(context) -> int:
    """
    Inject cookies ke sync Playwright BrowserContext.
    Panggil SETELAH launch_persistent_context, SEBELUM page.goto pertama.
    """
    cookies = load_raw_cookies()
    pw_cookies = to_playwright_cookies(cookies)
    context.add_cookies(pw_cookies)
    return len(pw_cookies)


# ── INJECT (ASYNC) ───────────────────────────────────────────────────────────

async def inject_cookies_async(context) -> int:
    cookies = load_raw_cookies()
    pw_cookies = to_playwright_cookies(cookies)
    await context.add_cookies(pw_cookies)
    return len(pw_cookies)