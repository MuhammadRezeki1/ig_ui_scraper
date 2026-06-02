"""
ig_cli.py
=========
CLI interaktif untuk Instagram Scraper.

Arsitektur: CLI ini adalah HTTP CLIENT yang memanggil REST API
(instagram_api_server.py). Engine scraping canggih (sentiment analysis,
engagement metrics, cascade GraphQL->CDP->REST, analytics) tetap berjalan di
server. CLI hanya mengirim request & menampilkan hasil dengan rapi.

Login via COOKIE:
  CLI menyimpan cookies hasil paste (Cookie-Editor JSON) ke
  session/ig_session.json. Server membaca file itu saat scraping.

Setelah scrape, CLI menampilkan LOKASI FILE hasil di folder output/.

Run: python ig_cli.py
"""
import os
import sys
import json
import time
from datetime import datetime, timedelta
from typing import Optional

import requests
from colorama import Fore, init

import session_manager as sm

init(autoreset=True)

API_BASE    = os.getenv("API_BASE", "http://127.0.0.1:5000/api/v1")
REQ_TIMEOUT = int(os.getenv("CLI_TIMEOUT", "360"))
LINE        = "=" * 64


def clear() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def banner() -> None:
    print(Fore.CYAN + LINE)
    print(Fore.CYAN + "   INSTAGRAM SCRAPER CLI")
    print(Fore.CYAN + "   HTTP client -> REST API  |  Login via cookie")
    print(Fore.CYAN + f"   API: {API_BASE}")
    print(Fore.CYAN + LINE)


def pause() -> None:
    input(Fore.WHITE + "\nTekan ENTER untuk lanjut...")


def header(title: str) -> None:
    print(Fore.MAGENTA + "\n" + "-" * 64)
    print(Fore.MAGENTA + f"  {title}")
    print(Fore.MAGENTA + "-" * 64)


# ---- HTTP ----

def api_get(path: str, params: Optional[dict] = None) -> dict:
    r = requests.get(API_BASE + path, params=params, timeout=REQ_TIMEOUT)
    return _handle(r)


def api_post(path: str, body: Optional[dict] = None) -> dict:
    r = requests.post(API_BASE + path, json=body or {}, timeout=REQ_TIMEOUT)
    return _handle(r)


def _handle(r: requests.Response) -> dict:
    try:
        return r.json()
    except Exception:
        return {"success": False, "message": f"HTTP {r.status_code}: {r.text[:200]}"}


def server_alive() -> bool:
    try:
        return requests.get(API_BASE + "/health", timeout=5).status_code == 200
    except Exception:
        return False


def _output_base() -> str:
    """Coba ambil path absolut folder output dari server (health)."""
    try:
        resp = api_get("/health")
        if resp.get("success"):
            od = resp["data"].get("output_dir")
            if od:
                return str(od)
    except Exception:
        pass
    return os.path.join(os.getcwd(), "output")


def _show_saved(saved_file: Optional[str]) -> None:
    """
    Tampilkan lokasi file hasil scrape.

    FIX Pylance reportOperatorIssue (baris 346, 380):
      saved_file bisa None (dari dict.get() tanpa default).
      Cek eksplisit sebelum konkatenasi string agar tidak
      terjadi TypeError / Pylance error:
        "Operator + not supported for str and None"
    """
    if not saved_file:
        return
    # saved_file dijamin str di sini — aman untuk konkatenasi
    base      = _output_base()
    full_path = os.path.join(base, saved_file)
    print(Fore.CYAN + "\n  -- File tersimpan --")
    print(Fore.GREEN + f"  {full_path}")


# ---- LOGIN (paste cookies) ----

COOKIE_GUIDE = (
    f"\n{Fore.YELLOW}CARA AMBIL COOKIES (sekali saja):\n\n"
    f"{Fore.WHITE}  1. Login Instagram di browser kamu\n"
    f"  2. Install extension {Fore.CYAN}Cookie-Editor{Fore.WHITE}\n"
    f"  3. Buka {Fore.CYAN}instagram.com{Fore.WHITE} (sudah login)\n"
    f"  4. Cookie-Editor -> {Fore.CYAN}Export -> Export as JSON{Fore.WHITE}\n"
    f"  5. Paste di sini\n\n"
    f"{Fore.YELLOW}Wajib ada: {Fore.GREEN}sessionid, ds_user_id, csrftoken\n"
)


def read_multiline_paste() -> str:
    print(Fore.WHITE + "\nPaste JSON cookies. Selesai -> ketik END lalu ENTER:\n")
    lines = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if line.strip() == "END":
            break
        lines.append(line)
    return "\n".join(lines)


def menu_login() -> None:
    header("LOGIN - Paste Session Cookies")
    print(COOKIE_GUIDE)
    print(Fore.WHITE + "  [1] Paste langsung   [2] Dari file .json   [0] Batal")
    choice = input(Fore.CYAN + "\n> Pilih: ").strip()
    if choice == "0":
        return

    raw = ""
    if choice == "1":
        raw = read_multiline_paste()
    elif choice == "2":
        path = input(Fore.CYAN + "Path file JSON: ").strip().strip('"')
        if not os.path.exists(path):
            print(Fore.RED + f"File tidak ditemukan: {path}")
            pause()
            return
        with open(path, "r", encoding="utf-8") as f:
            raw = f.read()
    else:
        print(Fore.RED + "Pilihan tidak valid.")
        pause()
        return

    try:
        cookies = sm.parse_cookie_json(raw)
    except Exception as e:
        print(Fore.RED + f"\nGagal parse JSON: {e}")
        pause()
        return

    ok, missing, _ = sm.validate_cookies(cookies)
    if not ok:
        print(Fore.RED + f"\nCookie wajib hilang: {', '.join(missing)}")
        pause()
        return

    try:
        payload = sm.save_session(cookies)
    except Exception as e:
        print(Fore.RED + f"\nGagal simpan: {e}")
        pause()
        return

    print(Fore.GREEN + "\nSession tersimpan!")
    print(Fore.WHITE + f"   user_id : {payload['user_id']}")
    print(Fore.WHITE + f"   cookies : {payload['cookie_count']}")
    print(Fore.WHITE + f"   file    : {sm.SESSION_FILE}")
    print(Fore.CYAN + "\nServer akan otomatis membaca cookies ini saat scraping.")
    pause()


def menu_logout() -> None:
    header("LOGOUT")
    if not sm.session_exists():
        print(Fore.YELLOW + "Belum ada session.")
        pause()
        return
    if input(Fore.RED + "Yakin hapus session? (y/n): ").strip().lower() == "y":
        sm.clear_session()
        print(Fore.GREEN + "Session lokal dihapus.")
        if server_alive():
            try:
                api_post("/auth/logout", {"hard_reset": False})
            except Exception:
                pass
    else:
        print(Fore.YELLOW + "Dibatalkan.")
    pause()


def menu_session_info() -> None:
    header("STATUS SESSION")
    print(sm.session_summary())
    s = sm.load_session()
    if s and sm.is_session_expired(s):
        print(Fore.RED + "\nsessionid lewat tanggal expired. Login ulang disarankan.")
    if server_alive():
        resp = api_get("/auth/status")
        if resp.get("success"):
            d = resp["data"]
            print(Fore.CYAN + "\n-- Server --")
            print(Fore.WHITE + f"  login_detected: {d.get('login_detected')}  (cookie login: abaikan flag ini)")
            print(Fore.WHITE + f"  is_logged_in  : {d.get('is_logged_in')}")
    else:
        print(Fore.YELLOW + "\nServer API tidak aktif.")
    pause()


# ---- GUARD ----

def _guard() -> bool:
    if not sm.session_exists():
        print(Fore.RED + "\nBelum login. Pilih menu Login dulu.")
        pause()
        return False
    if not server_alive():
        print(Fore.RED + f"\nServer API tidak aktif di {API_BASE}")
        print(Fore.YELLOW + "   Jalankan: python instagram_api_server.py")
        pause()
        return False
    return True


def _read_targets(label: str) -> list:
    print(Fore.WHITE + f"\nMasukkan {label} (1 per baris). Ketik END untuk selesai:")
    items = []
    while True:
        line = input().strip()
        if line == "END":
            break
        if line:
            items.append(line)
    return items


def _ask_username() -> str:
    return input(Fore.CYAN + "Username (tanpa @): ").strip().lstrip("@").lower()


# ---- SCRAPE ----

def menu_scrape_post() -> None:
    header("SCRAPE POST (komentar + sentiment + engagement)")
    if not _guard():
        return
    url = input(Fore.CYAN + "URL post/reel: ").strip()
    if not url:
        return
    try:
        max_c = int(input(Fore.CYAN + "Max komentar [100]: ").strip() or "100")
    except ValueError:
        max_c = 100

    print(Fore.YELLOW + "\nMemproses di server (~30-60s)...")
    resp = api_post("/scrape/post", {"url": url, "max_comments": max_c})
    if not resp.get("success"):
        print(Fore.RED + f"\n{resp.get('message')}")
        pause()
        return

    d = resp["data"]
    print(Fore.GREEN + f"\n{resp.get('message')}")
    _print_post_brief(d)
    # FIX: gunakan .get() dengan default "" agar tidak None
    _show_saved(d.get("_meta", {}).get("saved_file") or "")
    pause()


def menu_scrape_batch_post() -> None:
    header("BATCH SCRAPE POST")
    if not _guard():
        return
    urls = _read_targets("URL post")
    if not urls:
        return
    try:
        max_c = int(input(Fore.CYAN + "Max komentar/post [100]: ").strip() or "100")
        delay = int(input(Fore.CYAN + "Delay antar post [8]: ").strip() or "8")
    except ValueError:
        max_c, delay = 100, 8

    print(Fore.YELLOW + f"\nMemproses {len(urls)} post...")
    resp = api_post(
        "/scrape/posts/batch",
        {"urls": urls, "max_comments": max_c, "delay_between": delay},
    )
    if not resp.get("success"):
        print(Fore.RED + f"\n{resp.get('message')}")
        pause()
        return

    s = resp["data"]
    print(Fore.GREEN + f"\n{s['success']}/{s['total']} sukses dalam {s['elapsed_seconds']}s")
    # FIX baris 346: s.get("saved_file") bisa None → pakai `or ""`
    saved: str = s.get("saved_file") or ""
    _show_saved(saved)
    pause()


def menu_scrape_profile() -> None:
    header("SCRAPE PROFILE")
    if not _guard():
        return
    target = input(Fore.CYAN + "Username atau URL: ").strip()
    if not target:
        return
    save = input(Fore.CYAN + "Simpan snapshot? (Y/n): ").strip().lower() != "n"

    print(Fore.YELLOW + "\nMemproses di server (~15-30s)...")
    if "instagram.com" in target:
        resp = api_post("/scrape/profile/url", {"url": target, "save_snapshot": save})
    else:
        resp = api_post(
            "/scrape/profile",
            {"username": target.lstrip("@").lower(), "save_snapshot": save},
        )

    if not resp.get("success"):
        print(Fore.RED + f"\n{resp.get('message')}")
        pause()
        return

    d = resp["data"]
    print(Fore.GREEN + f"\n{resp.get('message')}")
    _print_profile_brief(d)
    # FIX: gunakan .get() dengan default "" agar tidak None
    _show_saved(d.get("_meta", {}).get("saved_file") or "")
    pause()


def menu_scrape_batch_profile() -> None:
    header("BATCH SCRAPE PROFILE")
    if not _guard():
        return
    print(Fore.WHITE + "  [1] Daftar username   [2] Daftar URL")
    kind  = input(Fore.CYAN + "> Pilih: ").strip()
    items = _read_targets("username" if kind == "1" else "URL")
    if not items:
        return
    try:
        delay = int(input(Fore.CYAN + "Delay antar profile [10]: ").strip() or "10")
    except ValueError:
        delay = 10

    print(Fore.YELLOW + f"\nMemproses {len(items)} profile...")
    if kind == "1":
        resp = api_post("/scrape/profiles/batch", {"usernames": items, "delay_between": delay})
    else:
        resp = api_post("/scrape/profiles/batch/url", {"urls": items, "delay_between": delay})

    if not resp.get("success"):
        print(Fore.RED + f"\n{resp.get('message')}")
        pause()
        return

    s = resp["data"]
    print(Fore.GREEN + f"\n{s['success']}/{s['total']} sukses dalam {s['elapsed_seconds']}s")
    # FIX baris 380: s.get("saved_file") bisa None → pakai `or ""`
    saved: str = s.get("saved_file") or ""
    _show_saved(saved)
    pause()


# ---- ANALYTICS ----

def menu_list_users() -> None:
    header("TRACKED USERS")
    if not server_alive():
        print(Fore.RED + "Server tidak aktif.")
        pause()
        return
    resp = api_get("/profiles")
    if not resp.get("success"):
        print(Fore.RED + resp.get("message", "Error"))
        pause()
        return
    d = resp["data"]
    print(Fore.CYAN + f"\nTotal: {d.get('count', 0)} user\n")
    for u in d.get("users", []):
        v = "[v]" if u.get("is_verified") else "   "
        print(
            Fore.WHITE
            + f"  {v} @{u.get('username', ''):<22} "
            + f"followers={u.get('current_followers') or 0:>10,}  "
            + f"snaps={u.get('snapshot_count', 0)}"
        )
    pause()


def menu_profile_detail() -> None:
    header("PROFILE DETAIL")
    if not server_alive():
        print(Fore.RED + "Server tidak aktif.")
        pause()
        return
    u = _ask_username()
    if u:
        _dump_json(api_get(f"/profiles/{u}"))
    pause()


def menu_history() -> None:
    header("SNAPSHOT HISTORY")
    if not server_alive():
        print(Fore.RED + "Server tidak aktif.")
        pause()
        return
    u = _ask_username()
    if not u:
        return
    try:
        limit = int(input(Fore.CYAN + "Limit [30]: ").strip() or "30")
    except ValueError:
        limit = 30

    resp = api_get(f"/profiles/{u}/history", {"limit": limit})
    if not resp.get("success"):
        print(Fore.RED + resp.get("message", "Error"))
        pause()
        return

    d = resp["data"]
    print(Fore.CYAN + f"\n@{u} - {d.get('snapshot_count', 0)} snapshot\n")
    print(Fore.YELLOW + f"  {'Tanggal':<12}{'Followers':>12}{'Following':>11}{'Posts':>8}")
    print(Fore.YELLOW + "  " + "-" * 43)
    for snap in reversed(d.get("snapshots", [])):
        print(
            Fore.WHITE
            + f"  {snap.get('scraped_date', ''):<12}"
            + f"{snap.get('followers', 0):>12,}"
            + f"{snap.get('following', 0):>11,}"
            + f"{snap.get('posts_count', 0):>8,}"
        )
    pause()


def menu_growth() -> None:
    header("ALL-TIME GROWTH")
    if not server_alive():
        print(Fore.RED + "Server tidak aktif.")
        pause()
        return
    u = _ask_username()
    if u:
        _dump_json(api_get(f"/profiles/{u}/growth"))
    pause()


def menu_monthly() -> None:
    header("MONTHLY BREAKDOWN")
    if not server_alive():
        print(Fore.RED + "Server tidak aktif.")
        pause()
        return
    u = _ask_username()
    if u:
        _dump_json(api_get(f"/profiles/{u}/monthly"))
    pause()


def menu_projection() -> None:
    header("PROYEKSI FOLLOWERS")
    if not server_alive():
        print(Fore.RED + "Server tidak aktif.")
        pause()
        return
    u = _ask_username()
    if not u:
        return
    dd     = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
    target = input(Fore.CYAN + f"Target tanggal [default {dd}]: ").strip() or dd
    print(Fore.WHITE + "  [1] linear  [2] recent_30d  [3] compound")
    mmap   = {"1": "linear", "2": "recent_30d", "3": "compound"}
    method = mmap.get(input(Fore.CYAN + "Method [2]: ").strip() or "2", "recent_30d")
    _dump_json(api_post(f"/profiles/{u}/project", {"target_date": target, "method": method}))
    pause()


def menu_period() -> None:
    header("PERIOD ANALYSIS")
    if not server_alive():
        print(Fore.RED + "Server tidak aktif.")
        pause()
        return
    u = _ask_username()
    if not u:
        return
    start = input(Fore.CYAN + "Start (YYYY-MM-DD): ").strip()
    end   = input(Fore.CYAN + "End (YYYY-MM-DD): ").strip()
    _dump_json(api_get(f"/profiles/{u}/period", {"start_date": start, "end_date": end}))
    pause()


def menu_health() -> None:
    header("SERVER HEALTH")
    if not server_alive():
        print(Fore.RED + f"Server tidak merespons di {API_BASE}")
        print(Fore.YELLOW + "   Jalankan: python instagram_api_server.py")
        pause()
        return
    _dump_json(api_get("/health"))
    pause()


# ---- PRINT HELPERS ----

def _dump_json(resp: dict) -> None:
    if not resp.get("success"):
        print(Fore.RED + f"\n{resp.get('message', 'Error')}")
        return
    print(Fore.WHITE + json.dumps(resp.get("data", {}), ensure_ascii=False, indent=2)[:4000])


def _print_post_brief(d: dict) -> None:
    print(Fore.CYAN + "\n  -- Post --")
    print(Fore.WHITE + f"  Owner       : @{d.get('owner_username', '?')}")
    print(Fore.WHITE + f"  Media type  : {d.get('media_type', '?')} ({d.get('product_type', 'feed') or 'feed'})")
    print(Fore.WHITE + f"  Likes       : {d.get('likes', 0):,}")
    if d.get("video_views"):
        print(Fore.WHITE + f"  Video views : {d.get('video_views', 0):,}")
    if d.get("saves_count"):
        print(Fore.WHITE + f"  Saves       : {d.get('saves_count', 0):,}")
    if d.get("shares_count"):
        print(Fore.WHITE + f"  Shares      : {d.get('shares_count', 0):,}")
    print(Fore.WHITE + f"  Komentar    : {d.get('comments_count', 0)}")
    s = d.get("sentiment_summary", {})
    if s:
        print(Fore.CYAN + "\n  -- Sentiment --")
        print(Fore.RED     + f"  Hate    : {s.get('hate_speech_count', 0)} ({s.get('hate_percentage', 0)}%)")
        print(Fore.YELLOW  + f"  Toxic   : {s.get('toxic_count', 0)} ({s.get('toxic_percentage', 0)}%)")
        print(Fore.GREEN   + f"  Positif : {s.get('positive_count', 0)} ({s.get('positive_percentage', 0)}%)")
        print(Fore.MAGENTA + f"  Negatif : {s.get('negative_count', 0)} ({s.get('negative_percentage', 0)}%)")
        print(Fore.WHITE   + f"  Netral  : {s.get('neutral_count', 0)} ({s.get('neutral_percentage', 0)}%)")
        print(Fore.CYAN    + f"  Humor   : {s.get('humor_count', 0)} ({s.get('humor_percentage', 0)}%)")


def _print_profile_brief(d: dict) -> None:
    p = d.get("profile", d) if isinstance(d.get("profile"), dict) else d
    print(Fore.CYAN + "\n  -- Profile --")
    print(Fore.WHITE + f"  @{p.get('username', '?')}  ({p.get('full_name', '')})")
    print(Fore.WHITE + f"  Followers : {p.get('followers', 0):,}")
    print(Fore.WHITE + f"  Following : {p.get('following', 0):,}")
    print(Fore.WHITE + f"  Posts     : {p.get('posts_count', 0):,}")
    if p.get("category"):
        print(Fore.WHITE + f"  Category  : {p.get('category')}")
    eng = p.get("engagement_summary") or d.get("engagement_summary")
    if eng and eng.get("posts_analyzed", 0) > 0:
        print(Fore.CYAN + f"\n  -- Engagement ({eng['posts_analyzed']} post) --")
        print(Fore.WHITE + f"  Avg likes    : {eng.get('avg_likes', 0):,}")
        print(Fore.WHITE + f"  Avg comments : {eng.get('avg_comments', 0):,}")
        print(Fore.GREEN + f"  Eng. rate    : {eng.get('engagement_rate', 0)}%")


# ---- MENU UTAMA ----

def main_menu() -> None:
    while True:
        clear()
        banner()
        logged = sm.session_exists()
        srv    = server_alive()
        sess   = sm.load_session() or {}

        print(
            "\n"
            + (Fore.GREEN + f"LOGIN: user_id {sess.get('user_id', '?')}"
               if logged
               else Fore.RED + "BELUM LOGIN (paste cookies)")
        )
        print(Fore.GREEN + "SERVER: aktif" if srv else Fore.RED + "SERVER: mati")

        print(Fore.WHITE + "\n  --- AUTH ---")
        print("  [1] Login (paste cookies)   [2] Status   [3] Logout")
        print(Fore.WHITE + "\n  --- SCRAPE ---")
        print("  [4] Post        [5] Batch Post")
        print("  [6] Profile     [7] Batch Profile")
        print(Fore.WHITE + "\n  --- ANALYTICS ---")
        print("  [8]  List users   [9]  Profile detail  [10] History")
        print("  [11] Growth       [12] Monthly         [13] Projection")
        print("  [14] Period analysis")
        print(Fore.WHITE + "\n  --- SERVER ---")
        print("  [15] Health check")
        print(Fore.WHITE + "\n  [0] Keluar")

        c       = input(Fore.CYAN + "\n> Pilih menu: ").strip()
        actions = {
            "1":  menu_login,
            "2":  menu_session_info,
            "3":  menu_logout,
            "4":  menu_scrape_post,
            "5":  menu_scrape_batch_post,
            "6":  menu_scrape_profile,
            "7":  menu_scrape_batch_profile,
            "8":  menu_list_users,
            "9":  menu_profile_detail,
            "10": menu_history,
            "11": menu_growth,
            "12": menu_monthly,
            "13": menu_projection,
            "14": menu_period,
            "15": menu_health,
        }
        if c == "0":
            print(Fore.CYAN + "\nSampai jumpa!")
            break
        action = actions.get(c)
        if action:
            action()
        else:
            print(Fore.RED + "Pilihan tidak valid.")
            time.sleep(1)


if __name__ == "__main__":
    try:
        main_menu()
    except KeyboardInterrupt:
        print(Fore.CYAN + "\n\nDihentikan. Sampai jumpa!")
        sys.exit(0)