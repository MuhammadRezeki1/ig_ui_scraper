"""
session_manager.py
==================
Mengelola session Instagram berbasis cookies (bukan username/password).

FIX: Path session sekarang ABSOLUT (backend/session/ig_session.json),
selaras dengan cookie_injector.py, supaya file yang DISIMPAN sama dengan
file yang DIBACA — tidak tergantung cwd.
"""
import os
import json
import time
from datetime import datetime
from typing import List, Dict, Optional, Tuple

from colorama import Fore

# ── KONFIG PATH (ABSOLUT) ────────────────────────────────────────────────────
# File ini ada di backend/engine/session_manager.py
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))   # .../backend/engine
_BACKEND_DIR = os.path.dirname(_THIS_DIR)                 # .../backend

# Simpan session di backend/session/ (satu lokasi tetap, dibaca cookie_injector)
SESSION_DIR = os.getenv("SESSION_DIR") or os.path.join(_BACKEND_DIR, "session")
SESSION_FILE = os.getenv("SESSION_FILE") or os.path.join(SESSION_DIR, "ig_session.json")

# Cookie minimal yang harus ada untuk login dianggap valid
REQUIRED_COOKIES = {"sessionid", "ds_user_id", "csrftoken"}


def _ensure_dir():
    os.makedirs(SESSION_DIR, exist_ok=True)


# ── PARSING & VALIDASI ────────────────────────────────────────────────────────

def parse_cookie_json(raw: str) -> List[Dict]:
    raw = raw.strip()
    if not raw:
        raise ValueError("Input cookie kosong.")

    data = json.loads(raw)

    if isinstance(data, dict) and "cookies" in data:
        data = data["cookies"]

    if not isinstance(data, list):
        raise ValueError("Format cookie harus berupa array (list) JSON.")

    cookies = []
    for c in data:
        if not isinstance(c, dict):
            continue
        if "name" not in c or "value" not in c:
            continue
        cookies.append(c)

    if not cookies:
        raise ValueError("Tidak ada cookie valid (name/value) ditemukan.")

    return cookies


def validate_cookies(cookies: List[Dict]) -> Tuple[bool, List[str], Dict[str, str]]:
    names = {c["name"]: c["value"] for c in cookies}
    missing = [r for r in REQUIRED_COOKIES if r not in names or not names[r]]
    is_valid = len(missing) == 0
    return is_valid, missing, names


def extract_user_id(cookies: List[Dict]) -> Optional[str]:
    for c in cookies:
        if c["name"] == "ds_user_id":
            return c["value"]
    for c in cookies:
        if c["name"] == "sessionid":
            val = c["value"]
            if "%3A" in val:
                return val.split("%3A")[0]
            if ":" in val:
                return val.split(":")[0]
    return None


# ── SIMPAN & MUAT ──────────────────────────────────────────────────────────────

def save_session(cookies: List[Dict]) -> Dict:
    _ensure_dir()

    is_valid, missing, names = validate_cookies(cookies)
    if not is_valid:
        raise ValueError(
            f"Cookie wajib tidak lengkap. Hilang: {', '.join(missing)}. "
            "Pastikan kamu sudah login penuh di browser sebelum export."
        )

    user_id = extract_user_id(cookies)

    payload = {
        "saved_at": datetime.now().isoformat(),
        "user_id": user_id,
        "cookie_count": len(cookies),
        "cookies": cookies,
    }

    with open(SESSION_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(Fore.GREEN + f"💾 Session disimpan ke: {SESSION_FILE}")
    return payload


def load_session() -> Optional[Dict]:
    if not os.path.exists(SESSION_FILE):
        return None
    try:
        with open(SESSION_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def session_exists() -> bool:
    s = load_session()
    if not s:
        return False
    cookies = s.get("cookies", [])
    is_valid, _, _ = validate_cookies(cookies)
    return is_valid


def clear_session() -> bool:
    if os.path.exists(SESSION_FILE):
        os.remove(SESSION_FILE)
        return True
    return False


def is_session_expired(session: Dict) -> bool:
    for c in session.get("cookies", []):
        if c["name"] == "sessionid":
            exp = c.get("expirationDate")
            if exp is None:
                return False
            return time.time() > float(exp)
    return False


# ── KONVERSI KE FORMAT PLAYWRIGHT ────────────────────────────────────────────

def to_playwright_cookies(cookies: List[Dict]) -> List[Dict]:
    samesite_map = {
        "no_restriction": "None",
        "unspecified": "Lax",
        "lax": "Lax",
        "strict": "Strict",
        "none": "None",
    }

    pw_cookies = []
    for c in cookies:
        name = c.get("name")
        value = c.get("value")
        if not name or value is None:
            continue

        domain = c.get("domain", ".instagram.com")
        path = c.get("path", "/")

        pw = {
            "name": name,
            "value": value,
            "domain": domain,
            "path": path,
            "httpOnly": bool(c.get("httpOnly", False)),
            "secure": bool(c.get("secure", True)),
        }

        exp = c.get("expirationDate")
        if exp is not None:
            pw["expires"] = float(exp)
        else:
            pw["expires"] = -1

        raw_ss = str(c.get("sameSite", "unspecified")).lower()
        pw["sameSite"] = samesite_map.get(raw_ss, "Lax")

        pw_cookies.append(pw)

    return pw_cookies


def get_playwright_cookies_from_disk() -> List[Dict]:
    session = load_session()
    if not session:
        raise RuntimeError("Belum ada session. Login dulu (paste cookies).")
    return to_playwright_cookies(session.get("cookies", []))


# ── RINGKASAN UNTUK CLI ──────────────────────────────────────────────────────

def session_summary(session: Optional[Dict] = None) -> str:
    if session is None:
        session = load_session()
    if not session:
        return f"{Fore.RED}● Belum login (tidak ada session)"

    user_id = session.get("user_id", "?")
    saved_at = session.get("saved_at", "?")
    count = session.get("cookie_count", 0)
    expired = is_session_expired(session)
    status = f"{Fore.RED}EXPIRED (berbasis tanggal)" if expired else f"{Fore.GREEN}AKTIF"

    return (
        f"{Fore.GREEN}● Login Status: {status}\n"
        f"  user_id   : {user_id}\n"
        f"  cookies   : {count}\n"
        f"  disimpan  : {saved_at}"
    )