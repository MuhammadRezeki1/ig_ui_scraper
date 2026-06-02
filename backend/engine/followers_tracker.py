"""
followers_tracker.py
====================
Analytics module untuk tracking pertumbuhan followers.

Metrik yang dihitung (standar industri Social Blade / HypeAuditor):
    - Absolute growth (net followers gained/lost)
    - Growth rate (%) — daily, weekly, monthly
    - CAGR (Compound Annual Growth Rate) untuk periode panjang
    - Daily/weekly average gain
    - Projection: estimasi followers di tanggal X berdasarkan trend
    - Growth velocity (akselerasi/deselerasi)
    - Engagement trend over time

Formula referensi:
    - Growth Rate (%)  = ((new - old) / old) * 100
    - CAGR             = ((end/start)^(1/years) - 1) * 100
    - Daily avg gain   = (new - old) / days
    - Velocity         = current_daily_avg - previous_daily_avg
"""
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Tuple

from colorama import Fore, init

from storage_manager import StorageManager

init(autoreset=True)


class FollowersTracker:
    """Hitung & analisis pertumbuhan followers."""

    def __init__(self, storage: Optional[StorageManager] = None):
        self.storage = storage or StorageManager()

    # ── HELPER ─────────────────────────────────────────────────────────────

    @staticmethod
    def _parse_date(d: str) -> date:
        """Parse 'YYYY-MM-DD' → date object."""
        return datetime.strptime(d, "%Y-%m-%d").date()

    @staticmethod
    def _days_between(d1: str, d2: str) -> int:
        return (FollowersTracker._parse_date(d2) - FollowersTracker._parse_date(d1)).days

    @staticmethod
    def _safe_pct(num: float, denom: float) -> float:
        if denom == 0:
            return 0.0
        return round((num / denom) * 100, 3)

    # ── GROWTH BETWEEN 2 SNAPSHOTS ─────────────────────────────────────────

    def compute_growth(self, old: Dict, new: Dict) -> Dict:
        """
        Hitung growth antara 2 snapshot.
        Mengembalikan dict dengan absolute, percentage, daily avg, dst.
        """
        old_f  = old["followers"]
        new_f  = new["followers"]
        old_fw = old.get("following", 0)
        new_fw = new.get("following", 0)
        old_p  = old.get("posts_count", 0)
        new_p  = new.get("posts_count", 0)

        days = self._days_between(old["scraped_date"], new["scraped_date"])
        if days <= 0:
            days = 1

        followers_gained = new_f - old_f
        following_changed = new_fw - old_fw
        posts_added = new_p - old_p

        return {
            "from_date":            old["scraped_date"],
            "to_date":              new["scraped_date"],
            "days":                 days,
            "from_followers":       old_f,
            "to_followers":         new_f,
            "followers_gained":     followers_gained,
            "followers_growth_pct": self._safe_pct(followers_gained, old_f),
            "avg_daily_gain":       round(followers_gained / days, 2),
            "from_following":       old_fw,
            "to_following":         new_fw,
            "following_changed":    following_changed,
            "from_posts":           old_p,
            "to_posts":             new_p,
            "posts_added":          posts_added,
        }

    # ── PERIOD ANALYSIS ────────────────────────────────────────────────────

    def analyze_period(self, username: str, start_date: str, end_date: str) -> Dict:
        """
        Analisis pertumbuhan dari start_date sampai end_date.
        Format tanggal: 'YYYY-MM-DD'

        Menggunakan snapshot TERDEKAT dengan start & end (bukan harus exact match).
        """
        username = username.lower()
        snapshots = self.storage.get_snapshots(username, limit=10_000)

        if len(snapshots) < 2:
            return {
                "error": f"Snapshot tidak cukup untuk @{username} "
                         f"(butuh ≥2, tersedia {len(snapshots)})",
                "snapshot_count": len(snapshots),
            }

        # Cari snapshot terdekat dengan start_date dan end_date
        snap_in_range = self.storage.get_snapshots_in_range(username, start_date, end_date)
        if len(snap_in_range) < 2:
            return {
                "error": f"Hanya {len(snap_in_range)} snapshot dalam rentang "
                         f"{start_date} s/d {end_date}. Butuh minimal 2.",
                "snapshots_in_range": len(snap_in_range),
                "tip": "Pakai analyze_all_time() atau perlebar rentang tanggal.",
            }

        old = snap_in_range[0]
        new = snap_in_range[-1]
        growth = self.compute_growth(old, new)

        # Hitung weekly & monthly equivalent
        days = growth["days"]
        daily_gain = growth["avg_daily_gain"]
        weekly_equiv  = round(daily_gain * 7,  2)
        monthly_equiv = round(daily_gain * 30, 2)

        # CAGR (annualized)
        if old["followers"] > 0 and days > 0:
            years = days / 365.25
            try:
                cagr = ((new["followers"] / old["followers"]) ** (1 / years) - 1) * 100
                cagr = round(cagr, 3)
            except (ZeroDivisionError, ValueError):
                cagr = 0.0
        else:
            cagr = 0.0

        # Engagement trend
        old_er = old.get("engagement_rate") or 0
        new_er = new.get("engagement_rate") or 0
        er_change = round(new_er - old_er, 3)

        # Snapshots untuk plotting / display
        timeline = [
            {
                "date": s["scraped_date"],
                "followers": s["followers"],
                "following": s["following"],
                "posts": s["posts_count"],
                "er": s.get("engagement_rate") or 0,
            }
            for s in snap_in_range
        ]

        return {
            "username":              username,
            "period_start":          start_date,
            "period_end":            end_date,
            "actual_start_date":     old["scraped_date"],
            "actual_end_date":       new["scraped_date"],
            "snapshots_count":       len(snap_in_range),
            **growth,
            "weekly_equiv_gain":     weekly_equiv,
            "monthly_equiv_gain":    monthly_equiv,
            "cagr_pct":              cagr,
            "from_engagement_rate":  old_er,
            "to_engagement_rate":    new_er,
            "engagement_rate_change": er_change,
            "trend":                 self._classify_trend(growth["followers_growth_pct"], days),
            "timeline":              timeline,
        }

    def analyze_all_time(self, username: str) -> Dict:
        """Analisis dari snapshot pertama sampai terakhir."""
        snapshots = self.storage.get_snapshots(username.lower(), limit=10_000)
        if len(snapshots) < 2:
            return {
                "error": f"Snapshot tidak cukup (tersedia {len(snapshots)}, butuh ≥2)",
                "snapshot_count": len(snapshots),
            }
        # snapshots di-order DESC, jadi snapshot tertua di posisi -1
        start_date = snapshots[-1]["scraped_date"]
        end_date   = snapshots[0]["scraped_date"]
        return self.analyze_period(username, start_date, end_date)

    # ── MONTH-OVER-MONTH BREAKDOWN ─────────────────────────────────────────

    def monthly_breakdown(self, username: str) -> List[Dict]:
        """
        Breakdown growth per bulan kalender.
        Untuk tiap bulan: ambil snapshot pertama & terakhir di bulan itu,
        hitung growth-nya.
        """
        snapshots = self.storage.get_snapshots(username.lower(), limit=10_000)
        if not snapshots:
            return []

        # Group by year-month
        by_month: Dict[str, List[Dict]] = {}
        for s in snapshots:
            ym = s["scraped_date"][:7]  # "YYYY-MM"
            by_month.setdefault(ym, []).append(s)

        result = []
        prev_end_followers = None

        for ym in sorted(by_month.keys()):
            month_snaps = sorted(by_month[ym], key=lambda x: x["scraped_date"])
            first = month_snaps[0]
            last  = month_snaps[-1]

            growth = self.compute_growth(first, last)

            # Growth dibanding akhir bulan sebelumnya (untuk MoM yang lebih akurat)
            mom_gain = None
            mom_pct  = None
            if prev_end_followers is not None and prev_end_followers > 0:
                mom_gain = last["followers"] - prev_end_followers
                mom_pct  = self._safe_pct(mom_gain, prev_end_followers)

            result.append({
                "year_month":          ym,
                "snapshots_in_month":  len(month_snaps),
                "start_date":          first["scraped_date"],
                "end_date":            last["scraped_date"],
                "start_followers":     first["followers"],
                "end_followers":       last["followers"],
                "intra_month_gain":    growth["followers_gained"],
                "intra_month_pct":     growth["followers_growth_pct"],
                "mom_gain":            mom_gain,
                "mom_pct":             mom_pct,
                "avg_daily_gain":      growth["avg_daily_gain"],
                "engagement_rate":     last.get("engagement_rate") or 0,
            })

            prev_end_followers = last["followers"]

        return result

    # ── PROJECTION ─────────────────────────────────────────────────────────

    def project_followers(
        self, username: str, target_date: str,
        method: str = "linear",
    ) -> Dict:
        """
        Project followers di tanggal target berdasarkan trend terkini.

        Methods:
            - 'linear'        : pakai avg daily gain dari semua data
            - 'recent_30d'    : pakai trend 30 hari terakhir (lebih akurat untuk short-term)
            - 'compound'      : pakai growth rate compound (untuk long-term)
        """
        snapshots = self.storage.get_snapshots(username.lower(), limit=10_000)
        if len(snapshots) < 2:
            return {"error": "Butuh minimal 2 snapshot untuk proyeksi"}

        latest = snapshots[0]
        target = self._parse_date(target_date)
        latest_date = self._parse_date(latest["scraped_date"])
        days_forward = (target - latest_date).days

        if days_forward <= 0:
            return {
                "error": f"Target date ({target_date}) harus setelah snapshot terakhir "
                         f"({latest['scraped_date']})"
            }

        if method == "recent_30d":
            cutoff = (latest_date - timedelta(days=30)).strftime("%Y-%m-%d")
            recent = [s for s in snapshots if s["scraped_date"] >= cutoff]
            if len(recent) < 2:
                return {"error": "Data 30 hari terakhir kurang dari 2 snapshot"}
            oldest_recent = recent[-1]
            growth = self.compute_growth(oldest_recent, latest)
            daily_gain = growth["avg_daily_gain"]
            projected = latest["followers"] + int(daily_gain * days_forward)

        elif method == "compound":
            oldest = snapshots[-1]
            days_history = self._days_between(oldest["scraped_date"], latest["scraped_date"])
            if days_history < 1:
                return {"error": "Data historis terlalu pendek untuk compound projection"}
            if oldest["followers"] <= 0:
                return {"error": "Followers awal nol — tidak bisa compound"}
            try:
                daily_growth_rate = (latest["followers"] / oldest["followers"]) ** (1 / days_history) - 1
                projected = int(latest["followers"] * (1 + daily_growth_rate) ** days_forward)
                daily_gain = (projected - latest["followers"]) / days_forward
            except (ValueError, ZeroDivisionError):
                return {"error": "Gagal hitung compound projection"}

        else:  # linear (default) — pakai semua data
            oldest = snapshots[-1]
            growth = self.compute_growth(oldest, latest)
            daily_gain = growth["avg_daily_gain"]
            projected = latest["followers"] + int(daily_gain * days_forward)

        diff = projected - latest["followers"]

        return {
            "username":           username,
            "method":             method,
            "from_date":          latest["scraped_date"],
            "from_followers":     latest["followers"],
            "target_date":        target_date,
            "days_forward":       days_forward,
            "projected_followers": projected,
            "projected_gain":     diff,
            "projected_gain_pct": self._safe_pct(diff, latest["followers"]),
            "implied_daily_gain": round(daily_gain, 2),
            "note":               "Proyeksi adalah estimasi berdasarkan trend historis. "
                                  "Akurasinya tergantung volatilitas akun & event eksternal.",
        }

    # ── HELPERS ────────────────────────────────────────────────────────────

    @staticmethod
    def _classify_trend(growth_pct: float, days: int) -> str:
        """Klasifikasi pertumbuhan jadi label."""
        # Normalisasi ke monthly equivalent untuk perbandingan adil
        monthly_pct = (growth_pct / max(days, 1)) * 30 if days > 0 else 0

        if monthly_pct >= 10:
            return "🚀 VIRAL GROWTH"
        elif monthly_pct >= 5:
            return "🔥 RAPID GROWTH"
        elif monthly_pct >= 2:
            return "📈 HEALTHY GROWTH"
        elif monthly_pct >= 0.5:
            return "↗️  STEADY GROWTH"
        elif monthly_pct >= -0.5:
            return "➡️  STAGNANT"
        elif monthly_pct >= -2:
            return "↘️  SLIGHT DECLINE"
        else:
            return "📉 DECLINING"

    # ── PRETTY PRINT REPORTS ───────────────────────────────────────────────

    @staticmethod
    def print_period_report(report: Dict):
        if "error" in report:
            print(Fore.RED + f"\n❌ {report['error']}")
            if "tip" in report:
                print(Fore.YELLOW + f"💡 Tip: {report['tip']}")
            return

        print(Fore.CYAN + "\n" + "=" * 65)
        print(Fore.CYAN + "📊 LAPORAN PERTUMBUHAN FOLLOWERS")
        print(Fore.CYAN + "=" * 65)
        print(f"  👤 Username       : @{report['username']}")
        print(f"  📅 Periode diminta: {report['period_start']} → {report['period_end']}")
        print(f"  📅 Periode actual : {report['actual_start_date']} → {report['actual_end_date']}")
        print(f"  📊 # Snapshot     : {report['snapshots_count']}")
        print(f"  ⏱️  Durasi         : {report['days']} hari")
        print(Fore.CYAN + "\n  📈 PERTUMBUHAN FOLLOWERS:")
        print(f"     Awal   : {report['from_followers']:>10,}")
        print(f"     Akhir  : {report['to_followers']:>10,}")

        gained = report["followers_gained"]
        gain_color = Fore.GREEN if gained >= 0 else Fore.RED
        sign = "+" if gained >= 0 else ""
        print(gain_color + f"     Gain   : {sign}{gained:>9,} ({sign}{report['followers_growth_pct']}%)")

        print(Fore.CYAN + "\n  📐 RATA-RATA:")
        print(f"     Per hari   : {report['avg_daily_gain']:+,.2f}")
        print(f"     Per minggu : {report['weekly_equiv_gain']:+,.2f}")
        print(f"     Per bulan  : {report['monthly_equiv_gain']:+,.2f}")
        print(f"     CAGR (yoy) : {report['cagr_pct']:+.3f}%")

        print(Fore.CYAN + f"\n  🎯 TREND: {report['trend']}")

        if report.get("from_engagement_rate") or report.get("to_engagement_rate"):
            print(Fore.CYAN + "\n  💬 ENGAGEMENT RATE:")
            print(f"     Awal  : {report['from_engagement_rate']}%")
            print(f"     Akhir : {report['to_engagement_rate']}%")
            er_change = report["engagement_rate_change"]
            er_color = Fore.GREEN if er_change >= 0 else Fore.RED
            print(er_color + f"     Change: {er_change:+.3f}%")

    @staticmethod
    def print_monthly_breakdown(breakdown: List[Dict], username: str):
        if not breakdown:
            print(Fore.RED + "\n❌ Belum ada data snapshot")
            return

        print(Fore.CYAN + "\n" + "=" * 80)
        print(Fore.CYAN + f"📅 MONTHLY BREAKDOWN — @{username}")
        print(Fore.CYAN + "=" * 80)

        header = f"  {'Bulan':<10} {'Start':>9} {'End':>9} {'Δ Bulan':>10} {'Δ %':>8} {'MoM %':>8} {'/hari':>9}"
        print(Fore.YELLOW + header)
        print(Fore.YELLOW + "  " + "─" * 76)

        for m in breakdown:
            gain = m["intra_month_gain"]
            pct  = m["intra_month_pct"]
            mom  = m["mom_pct"]
            color = Fore.GREEN if gain >= 0 else Fore.RED
            mom_str = f"{mom:+.2f}%" if mom is not None else "  —   "

            print(color + f"  {m['year_month']:<10} "
                          f"{m['start_followers']:>9,} {m['end_followers']:>9,} "
                          f"{gain:>+10,} {pct:>+7.2f}% {mom_str:>8} "
                          f"{m['avg_daily_gain']:>+9.1f}")

    @staticmethod
    def print_projection(proj: Dict):
        if "error" in proj:
            print(Fore.RED + f"\n❌ {proj['error']}")
            return

        print(Fore.CYAN + "\n" + "=" * 60)
        print(Fore.CYAN + "🔮 PROYEKSI FOLLOWERS")
        print(Fore.CYAN + "=" * 60)
        print(f"  👤 Username     : @{proj['username']}")
        print(f"  📐 Method       : {proj['method']}")
        print(f"  📅 Dari         : {proj['from_date']} ({proj['from_followers']:,} followers)")
        print(f"  🎯 Target tgl   : {proj['target_date']} ({proj['days_forward']} hari ke depan)")

        gain_color = Fore.GREEN if proj['projected_gain'] >= 0 else Fore.RED
        print(gain_color + f"  📊 Proyeksi    : {proj['projected_followers']:,} followers")
        sign = "+" if proj['projected_gain'] >= 0 else ""
        print(gain_color + f"     Gain        : {sign}{proj['projected_gain']:,} "
                           f"({sign}{proj['projected_gain_pct']}%)")
        print(f"  📐 Implied daily gain: {proj['implied_daily_gain']:+,.2f}")
        print(Fore.YELLOW + f"\n  ⚠️  {proj['note']}")