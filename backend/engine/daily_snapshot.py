"""
daily_snapshot.py
=================
Script standalone untuk dijalankan otomatis tiap hari via cron/Task Scheduler.

CARA SETUP AUTO-SCHEDULE:

Windows (Task Scheduler):
    1. Buka Task Scheduler → Create Basic Task
    2. Trigger: Daily, jam 09:00 (atau jam favorit)
    3. Action: Start a program
        - Program: C:\\path\\to\\venv\\Scripts\\python.exe
        - Argument: daily_snapshot.py
        - Start in: C:\\Users\\USER\\ig-scraper
    4. Centang "Run whether user is logged on or not" (jika mau jalan tanpa login)

Linux/Mac (cron):
    crontab -e
    # Tambah baris berikut untuk run tiap hari jam 9 pagi:
    0 9 * * * cd /path/to/ig-scraper && /path/to/venv/bin/python daily_snapshot.py >> logs/daily.log 2>&1

USAGE MANUAL:
    python daily_snapshot.py              # baca usernames.txt
    python daily_snapshot.py user1 user2  # snapshot user spesifik
"""
import os
import sys
import time
import random
from datetime import datetime

from colorama import Fore, init

from profile_scraper import InstagramProfileScraper
from storage_manager  import StorageManager

init(autoreset=True)


USERNAMES_FILE = "usernames.txt"
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)


def load_usernames(file_path: str = USERNAMES_FILE):
    if not os.path.exists(file_path):
        print(Fore.RED + f"❌ File {file_path} tidak ditemukan")
        print(Fore.YELLOW + f"💡 Buat {file_path} dengan 1 username per baris (tanpa @)")
        return []

    with open(file_path, encoding="utf-8") as f:
        return [
            line.strip().lstrip("@").lower()
            for line in f
            if line.strip() and not line.startswith("#")
        ]


def log_run(message: str):
    """Log ke file harian."""
    log_file = os.path.join(LOG_DIR, f"snapshot_{datetime.now().strftime('%Y-%m')}.log")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {message}\n")


def main():
    # Tentukan list username
    if len(sys.argv) > 1:
        usernames = [u.lstrip("@").lower() for u in sys.argv[1:]]
        print(Fore.CYAN + f"📋 Mode CLI args: {len(usernames)} username")
    else:
        usernames = load_usernames()
        if not usernames:
            log_run("ERROR: usernames.txt kosong atau tidak ada")
            sys.exit(1)
        print(Fore.CYAN + f"📋 Mode batch dari {USERNAMES_FILE}: {len(usernames)} username")

    log_run(f"START daily snapshot — {len(usernames)} usernames")

    storage = StorageManager()
    success_count = 0
    fail_count = 0
    fail_users = []

    delay_min = int(os.getenv("DELAY_MIN_SECONDS", "15"))
    delay_max = int(os.getenv("DELAY_MAX_SECONDS", "45"))

    try:
        with InstagramProfileScraper() as scraper:
            for i, username in enumerate(usernames, 1):
                print(Fore.CYAN + f"\n{'='*60}")
                print(Fore.CYAN + f"[{i}/{len(usernames)}] Snapshot @{username}")
                print(Fore.CYAN + "=" * 60)

                try:
                    data = scraper.scrape_profile(username)
                    if data.get("success"):
                        storage.save_snapshot(data)
                        success_count += 1
                        log_run(f"OK @{username}: followers={data.get('followers', 0):,}")
                    else:
                        fail_count += 1
                        fail_users.append(username)
                        log_run(f"FAIL @{username}: {data.get('error', 'unknown')}")
                except Exception as e:
                    fail_count += 1
                    fail_users.append(username)
                    log_run(f"EXCEPTION @{username}: {e}")
                    print(Fore.RED + f"❌ Exception: {e}")

                # Random delay antar request (anti-rate-limit)
                if i < len(usernames):
                    wait = random.randint(delay_min, delay_max)
                    print(Fore.YELLOW + f"⏳ Jeda {wait}s sebelum berikutnya...")
                    time.sleep(wait)
    except Exception as e:
        print(Fore.RED + f"\n❌ Fatal error: {e}")
        log_run(f"FATAL: {e}")
        sys.exit(1)

    # Summary
    print(Fore.CYAN + "\n" + "=" * 60)
    print(Fore.CYAN + "📊 DAILY SNAPSHOT SUMMARY")
    print(Fore.CYAN + "=" * 60)
    print(Fore.GREEN + f"  ✅ Berhasil : {success_count}")
    if fail_count:
        print(Fore.RED + f"  ❌ Gagal    : {fail_count}")
        for u in fail_users:
            print(Fore.RED + f"      - @{u}")

    log_run(f"END daily snapshot — success={success_count} fail={fail_count}")
    print(Fore.CYAN + f"\n📄 Log: {LOG_DIR}/snapshot_{datetime.now().strftime('%Y-%m')}.log")


if __name__ == "__main__":
    main()