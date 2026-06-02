"""
storage_manager.py
==================
Multi-format storage untuk snapshot data profile Instagram.

Formats:
    - JSON   : Full snapshot per scrape (untuk audit trail & raw data)
    - CSV    : Time-series flat file (mudah dibuka di Excel/Sheets)
    - SQLite : Relational DB (untuk query growth analysis cepat)

Struktur direktori:
    data/
    ├── snapshots.db                          # SQLite database
    ├── csv/
    │   └── <username>_history.csv            # 1 CSV per akun
    └── json/
        └── <username>/
            └── 2025-05-26_143055.json        # 1 JSON per snapshot
"""
import os
import csv
import json
import sqlite3
from datetime import datetime
from typing import Dict, List, Optional
from contextlib import contextmanager

from colorama import Fore, init

init(autoreset=True)

# ── CONFIG ─────────────────────────────────────────────────────────────────
DATA_DIR = "data"
JSON_DIR = os.path.join(DATA_DIR, "json")
CSV_DIR  = os.path.join(DATA_DIR, "csv")
DB_PATH  = os.path.join(DATA_DIR, "snapshots.db")

os.makedirs(JSON_DIR, exist_ok=True)
os.makedirs(CSV_DIR, exist_ok=True)


# ── CSV COLUMNS ────────────────────────────────────────────────────────────
CSV_COLUMNS = [
    "scraped_at",
    "scraped_date",
    "username",
    "full_name",
    "followers",
    "following",
    "posts_count",
    "is_verified",
    "is_business",
    "is_private",
    "category",
    "engagement_rate",
    "avg_likes",
    "avg_comments",
    "avg_views",
    "posts_analyzed",
    "external_url",
    "biography",
    "method",
]


# ── SQLITE SCHEMA ──────────────────────────────────────────────────────────
DDL_PROFILES = """
CREATE TABLE IF NOT EXISTS profiles (
    username        TEXT PRIMARY KEY,
    full_name       TEXT,
    user_id         TEXT,
    is_verified     INTEGER DEFAULT 0,
    is_business     INTEGER DEFAULT 0,
    is_private      INTEGER DEFAULT 0,
    category        TEXT,
    biography       TEXT,
    external_url    TEXT,
    first_seen      TEXT,
    last_updated    TEXT
);
"""

DDL_SNAPSHOTS = """
CREATE TABLE IF NOT EXISTS snapshots (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    username          TEXT NOT NULL,
    scraped_at        TEXT NOT NULL,
    scraped_date      TEXT NOT NULL,
    followers         INTEGER NOT NULL DEFAULT 0,
    following         INTEGER NOT NULL DEFAULT 0,
    posts_count       INTEGER NOT NULL DEFAULT 0,
    engagement_rate   REAL    DEFAULT 0,
    avg_likes         INTEGER DEFAULT 0,
    avg_comments      INTEGER DEFAULT 0,
    avg_views         INTEGER DEFAULT 0,
    posts_analyzed    INTEGER DEFAULT 0,
    method            TEXT,
    FOREIGN KEY (username) REFERENCES profiles(username),
    UNIQUE(username, scraped_date)
);
"""

DDL_RECENT_POSTS = """
CREATE TABLE IF NOT EXISTS recent_posts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_id     INTEGER NOT NULL,
    username        TEXT NOT NULL,
    shortcode       TEXT NOT NULL,
    post_url        TEXT,
    media_type      TEXT,
    likes           INTEGER DEFAULT 0,
    comments        INTEGER DEFAULT 0,
    views           INTEGER DEFAULT 0,
    is_video        INTEGER DEFAULT 0,
    taken_at        INTEGER DEFAULT 0,
    caption         TEXT,
    FOREIGN KEY (snapshot_id) REFERENCES snapshots(id) ON DELETE CASCADE
);
"""

INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_snapshots_username_date ON snapshots(username, scraped_date);",
    "CREATE INDEX IF NOT EXISTS idx_snapshots_date ON snapshots(scraped_date);",
    "CREATE INDEX IF NOT EXISTS idx_posts_username ON recent_posts(username);",
    "CREATE INDEX IF NOT EXISTS idx_posts_snapshot ON recent_posts(snapshot_id);",
]


class StorageManager:
    """Handle penyimpanan multi-format dari snapshot profile."""

    def __init__(self, data_dir: str = DATA_DIR):
        self.data_dir = data_dir
        self.json_dir = os.path.join(data_dir, "json")
        self.csv_dir  = os.path.join(data_dir, "csv")
        self.db_path  = os.path.join(data_dir, "snapshots.db")

        for d in [self.data_dir, self.json_dir, self.csv_dir]:
            os.makedirs(d, exist_ok=True)

        self._init_db()

    # ── DB INIT ────────────────────────────────────────────────────────────

    def _init_db(self):
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(DDL_PROFILES)
            cur.execute(DDL_SNAPSHOTS)
            cur.execute(DDL_RECENT_POSTS)
            for idx in INDEXES:
                cur.execute(idx)
            conn.commit()

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        try:
            yield conn
        finally:
            conn.close()

    # ── SAVE SNAPSHOT (ALL FORMATS) ────────────────────────────────────────

    def save_snapshot(self, profile_data: Dict) -> Dict[str, str]:
        """
        Simpan snapshot ke 3 format sekaligus.
        Returns dict berisi path untuk JSON, CSV, dan ID DB.
        """
        if not profile_data.get("success"):
            print(Fore.YELLOW + "⚠️  Snapshot gagal — tidak disimpan")
            return {}

        username = profile_data.get("username", "").lower()
        if not username:
            print(Fore.RED + "❌ Username kosong — tidak bisa disimpan")
            return {}

        paths = {}

        # 1. JSON (full snapshot)
        paths["json"] = self._save_json(profile_data, username)

        # 2. CSV (append row)
        paths["csv"] = self._save_csv(profile_data, username)

        # 3. SQLite (upsert profile + insert snapshot + posts)
        snapshot_id = self._save_sqlite(profile_data, username)
        paths["sqlite_snapshot_id"] = str(snapshot_id) if snapshot_id else ""

        print(Fore.GREEN + f"\n💾 Snapshot tersimpan ke 3 format:")
        print(Fore.GREEN + f"   📄 JSON   : {paths['json']}")
        print(Fore.GREEN + f"   📊 CSV    : {paths['csv']}")
        print(Fore.GREEN + f"   🗄️  SQLite : snapshot_id={paths['sqlite_snapshot_id']}")

        return paths

    # ── JSON STORAGE ───────────────────────────────────────────────────────

    def _save_json(self, data: Dict, username: str) -> str:
        user_dir = os.path.join(self.json_dir, username)
        os.makedirs(user_dir, exist_ok=True)

        ts = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        fp = os.path.join(user_dir, f"{ts}.json")

        with open(fp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        # Juga simpan "latest.json" untuk akses cepat
        latest = os.path.join(user_dir, "latest.json")
        with open(latest, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        return fp

    # ── CSV STORAGE ────────────────────────────────────────────────────────

    def _save_csv(self, data: Dict, username: str) -> str:
        fp = os.path.join(self.csv_dir, f"{username}_history.csv")
        file_exists = os.path.exists(fp)

        eng = data.get("engagement_summary") or {}
        row = {
            "scraped_at":      data.get("scraped_at", ""),
            "scraped_date":    data.get("scraped_date", ""),
            "username":        data.get("username", ""),
            "full_name":       data.get("full_name", ""),
            "followers":       data.get("followers", 0),
            "following":       data.get("following", 0),
            "posts_count":     data.get("posts_count", 0),
            "is_verified":     int(data.get("is_verified", False)),
            "is_business":     int(data.get("is_business", False)),
            "is_private":      int(data.get("is_private", False)),
            "category":        data.get("category", ""),
            "engagement_rate": eng.get("engagement_rate", 0),
            "avg_likes":       eng.get("avg_likes", 0),
            "avg_comments":    eng.get("avg_comments", 0),
            "avg_views":       eng.get("avg_views", 0),
            "posts_analyzed":  eng.get("posts_analyzed", 0),
            "external_url":    data.get("external_url", ""),
            "biography":       (data.get("biography", "") or "").replace("\n", " | ")[:300],
            "method":          data.get("method", ""),
        }

        with open(fp, "a", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS, extrasaction="ignore")
            if not file_exists:
                writer.writeheader()
            writer.writerow(row)

        return fp

    # ── SQLITE STORAGE ─────────────────────────────────────────────────────

    def _save_sqlite(self, data: Dict, username: str) -> Optional[int]:
        try:
            with self._connect() as conn:
                cur = conn.cursor()

                # 1. Upsert profile
                now = datetime.now().isoformat()
                cur.execute("""
                    INSERT INTO profiles (
                        username, full_name, user_id, is_verified, is_business,
                        is_private, category, biography, external_url,
                        first_seen, last_updated
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(username) DO UPDATE SET
                        full_name    = excluded.full_name,
                        user_id      = excluded.user_id,
                        is_verified  = excluded.is_verified,
                        is_business  = excluded.is_business,
                        is_private   = excluded.is_private,
                        category     = excluded.category,
                        biography    = excluded.biography,
                        external_url = excluded.external_url,
                        last_updated = excluded.last_updated
                """, (
                    username,
                    data.get("full_name", ""),
                    data.get("user_id", ""),
                    int(data.get("is_verified", False)),
                    int(data.get("is_business", False)),
                    int(data.get("is_private", False)),
                    data.get("category", ""),
                    data.get("biography", ""),
                    data.get("external_url", ""),
                    now,
                    now,
                ))

                # 2. Insert snapshot (unique per username+date — replace jika sudah ada)
                eng = data.get("engagement_summary") or {}
                cur.execute("""
                    INSERT INTO snapshots (
                        username, scraped_at, scraped_date,
                        followers, following, posts_count,
                        engagement_rate, avg_likes, avg_comments, avg_views,
                        posts_analyzed, method
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(username, scraped_date) DO UPDATE SET
                        scraped_at      = excluded.scraped_at,
                        followers       = excluded.followers,
                        following       = excluded.following,
                        posts_count     = excluded.posts_count,
                        engagement_rate = excluded.engagement_rate,
                        avg_likes       = excluded.avg_likes,
                        avg_comments    = excluded.avg_comments,
                        avg_views       = excluded.avg_views,
                        posts_analyzed  = excluded.posts_analyzed,
                        method          = excluded.method
                """, (
                    username,
                    data.get("scraped_at", ""),
                    data.get("scraped_date", ""),
                    data.get("followers", 0),
                    data.get("following", 0),
                    data.get("posts_count", 0),
                    eng.get("engagement_rate", 0),
                    eng.get("avg_likes", 0),
                    eng.get("avg_comments", 0),
                    eng.get("avg_views", 0),
                    eng.get("posts_analyzed", 0),
                    data.get("method", ""),
                ))

                # Ambil snapshot_id (lastrowid kalo insert, manual SELECT kalo update)
                snapshot_id = cur.lastrowid
                if snapshot_id == 0:
                    cur.execute(
                        "SELECT id FROM snapshots WHERE username=? AND scraped_date=?",
                        (username, data.get("scraped_date", "")),
                    )
                    row = cur.fetchone()
                    snapshot_id = row["id"] if row else None

                # 3. Recent posts — hapus dulu posts lama untuk snapshot ini, lalu insert
                if snapshot_id:
                    cur.execute("DELETE FROM recent_posts WHERE snapshot_id=?", (snapshot_id,))
                    for p in data.get("recent_posts", []):
                        cur.execute("""
                            INSERT INTO recent_posts (
                                snapshot_id, username, shortcode, post_url,
                                media_type, likes, comments, views,
                                is_video, taken_at, caption
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            snapshot_id, username,
                            p.get("shortcode", ""), p.get("url", ""),
                            p.get("media_type", ""),
                            p.get("likes", 0), p.get("comments", 0), p.get("views", 0),
                            int(p.get("is_video", False)),
                            p.get("taken_at", 0),
                            (p.get("caption", "") or "")[:500],
                        ))

                conn.commit()
                return snapshot_id

        except Exception as e:
            print(Fore.RED + f"❌ SQLite save error: {e}")
            return None

    # ── QUERY METHODS ──────────────────────────────────────────────────────

    def get_snapshots(self, username: str, limit: int = 100) -> List[Dict]:
        """Ambil semua snapshot untuk 1 user, urut dari yang terbaru."""
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT * FROM snapshots
                WHERE username = ?
                ORDER BY scraped_date DESC
                LIMIT ?
            """, (username.lower(), limit))
            return [dict(row) for row in cur.fetchall()]

    def get_snapshots_in_range(self, username: str, start_date: str, end_date: str) -> List[Dict]:
        """
        Ambil snapshot dalam rentang tanggal.
        Format tanggal: 'YYYY-MM-DD'
        """
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT * FROM snapshots
                WHERE username = ?
                  AND scraped_date BETWEEN ? AND ?
                ORDER BY scraped_date ASC
            """, (username.lower(), start_date, end_date))
            return [dict(row) for row in cur.fetchall()]

    def get_latest_snapshot(self, username: str) -> Optional[Dict]:
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT * FROM snapshots
                WHERE username = ?
                ORDER BY scraped_date DESC
                LIMIT 1
            """, (username.lower(),))
            row = cur.fetchone()
            return dict(row) if row else None

    def get_profile(self, username: str) -> Optional[Dict]:
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM profiles WHERE username = ?", (username.lower(),))
            row = cur.fetchone()
            return dict(row) if row else None

    def list_tracked_users(self) -> List[Dict]:
        """List semua user yang pernah di-snapshot."""
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT
                    p.username, p.full_name, p.is_verified, p.category,
                    COUNT(s.id) AS snapshot_count,
                    MIN(s.scraped_date) AS first_snapshot,
                    MAX(s.scraped_date) AS last_snapshot,
                    (SELECT followers FROM snapshots
                     WHERE username=p.username ORDER BY scraped_date DESC LIMIT 1) AS current_followers
                FROM profiles p
                LEFT JOIN snapshots s ON s.username = p.username
                GROUP BY p.username
                ORDER BY last_snapshot DESC
            """)
            return [dict(row) for row in cur.fetchall()]

    def manual_insert_snapshot(
        self, username: str, scraped_date: str,
        followers: int, following: int = 0, posts_count: int = 0,
    ) -> bool:
        """
        Manual insert untuk backfill data historis (mis. dari Social Blade screenshot).
        Format scraped_date: 'YYYY-MM-DD'
        """
        try:
            with self._connect() as conn:
                cur = conn.cursor()
                # Pastikan profile exist (minimal)
                cur.execute("""
                    INSERT INTO profiles (username, first_seen, last_updated)
                    VALUES (?, ?, ?)
                    ON CONFLICT(username) DO NOTHING
                """, (username.lower(), datetime.now().isoformat(), datetime.now().isoformat()))

                cur.execute("""
                    INSERT INTO snapshots (
                        username, scraped_at, scraped_date,
                        followers, following, posts_count, method
                    ) VALUES (?, ?, ?, ?, ?, ?, 'manual_backfill')
                    ON CONFLICT(username, scraped_date) DO UPDATE SET
                        followers   = excluded.followers,
                        following   = excluded.following,
                        posts_count = excluded.posts_count
                """, (
                    username.lower(),
                    f"{scraped_date}T00:00:00",
                    scraped_date,
                    followers, following, posts_count,
                ))
                conn.commit()
                return True
        except Exception as e:
            print(Fore.RED + f"❌ Manual insert error: {e}")
            return False