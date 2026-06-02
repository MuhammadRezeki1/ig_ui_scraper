"""
profile_scraper.py
==================
Scrape data lengkap profile Instagram.

FIX:
- PROFILE_DIR default disamakan dengan scraper_post.py ("chrome_profile_playwright")
- result SELALU berisi field lengkap (followers, following, dst) walau gagal,
  supaya frontend tidak dapat undefined
- Error handling lebih defensif
"""
import os
import re
import json
import time
import random
import requests
from datetime import datetime
from typing import Dict, List, Optional, Any
from cookie_injector import inject_cookies_sync, has_valid_session

from dotenv import load_dotenv
from colorama import Fore, init
from playwright.sync_api import sync_playwright, Page, BrowserContext, TimeoutError as PlaywrightTimeout

init(autoreset=True)
load_dotenv()

# ── CONFIG ─────────────────────────────────────────────────────────────────
HEADLESS    = os.getenv("HEADLESS", "true").lower() == "true"
PROXY       = os.getenv("PROXY", "")
# FIX: samakan dengan scraper_post.py supaya konsisten
PROFILE_DIR = os.getenv("PROFILE_DIR", "chrome_profile_playwright")
CHROME_PROFILE = os.path.join(os.getcwd(), PROFILE_DIR)


def _empty_profile_fields(username: str) -> Dict[str, Any]:
    """Field default supaya result SELALU lengkap (frontend tidak dapat undefined)."""
    return {
        "user_id":          "",
        "username":         username,
        "full_name":        "",
        "biography":        "",
        "external_url":     "",
        "external_url_linkshimmed": "",
        "bio_links":        [],
        "category":         "",
        "category_enum":    "",
        "business_email":   "",
        "business_phone":   "",
        "business_address": "",
        "is_verified":      False,
        "is_private":       False,
        "is_business":      False,
        "is_professional":  False,
        "is_joined_recently": False,
        "profile_pic_url":  "",
        "profile_pic_url_hd": "",
        "followers":        0,
        "following":        0,
        "posts_count":      0,
        "recent_posts":     [],
    }


class InstagramProfileScraper:
    """Scraper khusus untuk data profile (bukan post)."""

    def __init__(self):
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.session: Optional[requests.Session] = None
        self.playwright = None

        os.makedirs(CHROME_PROFILE, exist_ok=True)
        if has_valid_session():
            print(Fore.GREEN + "🍪 Login via cookie session")
        else:
            print(Fore.YELLOW + f"⚠️  Belum ada cookie session, pakai folder {CHROME_PROFILE}")

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    # ── ASSERT HELPERS ──────────────────────────────────────────────────────

    def _assert_page(self) -> Page:
        if self.page is None:
            raise RuntimeError("Browser page belum diinisialisasi.")
        return self.page

    def _assert_session(self) -> requests.Session:
        if self.session is None:
            raise RuntimeError("Requests session belum diinisialisasi.")
        return self.session

    def _assert_context(self) -> BrowserContext:
        if self.context is None:
            raise RuntimeError("Browser context belum diinisialisasi.")
        return self.context

    # ── BROWSER SETUP ──────────────────────────────────────────────────────

    def _build_context(self) -> BrowserContext:
        self.playwright = sync_playwright().start()

        args = [
            "--start-maximized" if not HEADLESS else "",
            "--disable-blink-features=AutomationControlled",
            "--disable-notifications",
            "--no-sandbox",
            "--mute-audio",
            "--disable-infobars",
            "--disable-background-timer-throttling",
            "--disable-backgrounding-occluded-windows",
            "--disable-renderer-backgrounding",
            "--disable-features=IsolateOrigins,site-per-process",
        ]
        if PROXY:
            args.append(f"--proxy-server={PROXY}")
        args = [a for a in args if a]

        stealth_script = r"""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
            window.chrome = { runtime: {} };
            Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
            Object.defineProperty(navigator, 'deviceMemory', {get: () => 8});
            Object.defineProperty(navigator, 'hardwareConcurrency', {get: () => 4});
            delete navigator.__proto__.webdriver;
        """

        context = self.playwright.chromium.launch_persistent_context(
            CHROME_PROFILE,
            headless=HEADLESS,
            args=args,
            viewport={"width": 1920, "height": 1080} if not HEADLESS else {"width": 1366, "height": 768},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36",
            locale="en-US",
            timezone_id="Asia/Jakarta",
            bypass_csp=True,
            java_script_enabled=True,
        )
        context.on("page", lambda p: p.add_init_script(stealth_script))

        try:
            if has_valid_session():
                n = inject_cookies_sync(context)
                print(Fore.GREEN + f"🍪 Inject {n} cookies dari session file")
        except Exception as e:
            print(Fore.YELLOW + f"⚠️  Cookie inject dilewati: {e}")

        return context

    def initialize_browser(self):
        if self.context:
            return

        print(Fore.CYAN + "\n🌐 Membuka browser (Playwright)...")
        self.context = self._build_context()
        self.page = self.context.pages[0] if self.context.pages else self.context.new_page()

        def block_heavy(route):
            rt = route.request.resource_type
            url = route.request.url.lower()
            if rt in ["image", "media", "font"]:
                if "favicon" in url or "icon" in url:
                    route.continue_()
                else:
                    route.abort()
            else:
                route.continue_()

        page = self._assert_page()
        page.route("**/*", block_heavy)

        page.goto("https://www.instagram.com/")
        time.sleep(5)
        self._close_popups()

        # FIX: jangan langsung raise kalau ada "login" di url — cukup warning.
        # Strategy API tetap dicoba; kalau benar2 gagal baru ketahuan nanti.
        if "login" in page.url:
            print(Fore.YELLOW + "⚠️  URL mengandung 'login' — cookie mungkin belum aktif, tetap lanjut coba.")
        else:
            print(Fore.GREEN + "✅ Browser siap (LOGGED IN)")

    def _close_popups(self):
        if self.page is None:
            return
        popup_selectors = [
            "text=Not Now", "text=Sekarang tidak", "text=Cancel",
            "text=Batal", "text=Turn Off", "text=Save Info",
            "button:has-text('Not Now')",
        ]
        for sel in popup_selectors:
            try:
                if self.page.locator(sel).count() > 0:
                    self.page.locator(sel).first.click(timeout=2000)
                    time.sleep(0.5)
            except Exception:
                pass

    def close(self):
        try:
            if self.session:
                self.session.close()
                self.session = None
            if self.context:
                self.context.close()
                self.context = None
            if self.playwright:
                self.playwright.stop()
                self.playwright = None
        except Exception:
            pass

    # ── REQUESTS SESSION ────────────────────────────────────────────────────

    def _build_requests_session(self) -> requests.Session:
        sess = requests.Session()
        context = self._assert_context()
        cookies = context.cookies()

        for c in cookies:
            name = c.get("name")
            value = c.get("value")
            if name is None or value is None:
                continue
            sess.cookies.set(name, value, domain=c.get("domain", ".instagram.com"))

        csrf = ""
        for c in cookies:
            if c.get("name") == "csrftoken":
                csrf = c.get("value", "")
                break

        sess.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                          '(KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36',
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.9',
            'X-IG-App-ID': '936619743392459',
            'X-ASBD-ID': '129477',
            'X-IG-WWW-Claim': '0',
            'X-CSRFToken': csrf,
            'X-Requested-With': 'XMLHttpRequest',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
            'Referer': 'https://www.instagram.com/',
            'Origin': 'https://www.instagram.com',
        })
        self.session = sess
        return sess

    # ── STRATEGY 1: Web Profile API ─────────────────────────────────────────

    def _fetch_via_web_profile_api(self, username: str) -> Dict[str, Any]:
        url = "https://www.instagram.com/api/v1/users/web_profile_info/"
        try:
            session = self._assert_session()
            resp = session.get(url, params={"username": username}, timeout=15)

            if resp.status_code != 200:
                print(Fore.YELLOW + f"   ⚠️  Web Profile API status {resp.status_code}")
                return {}
            if 'json' not in resp.headers.get('content-type', ''):
                print(Fore.YELLOW + "   ⚠️  Web Profile API response bukan JSON")
                return {}

            data = resp.json()
            user = data.get("data", {}).get("user", {})
            if not user:
                return {}

            return self._normalize_user(user)
        except Exception as e:
            print(Fore.YELLOW + f"   ⚠️  Web Profile API error: {e}")
            return {}

    # ── STRATEGY 2: CDP Fetch ───────────────────────────────────────────────

    def _fetch_via_cdp(self, username: str) -> Dict[str, Any]:
        try:
            page = self._assert_page()
            # FIX: evaluate hanya boleh 1 argumen → bungkus jadi async IIFE
            result = page.evaluate(r"""(username) => {
                return (async () => {
                    try {
                        const resp = await fetch(
                            `/api/v1/users/web_profile_info/?username=${encodeURIComponent(username)}`,
                            {
                                method: 'GET',
                                credentials: 'include',
                                headers: {
                                    'X-IG-App-ID': '936619743392459',
                                    'X-ASBD-ID': '129477',
                                    'X-Requested-With': 'XMLHttpRequest',
                                    'Accept': '*/*',
                                }
                            }
                        );
                        const data = await resp.json();
                        return {ok: true, data: data};
                    } catch(e) {
                        return {ok: false, error: e.toString()};
                    }
                })();
            }""", username)

            if not result.get("ok"):
                print(Fore.YELLOW + f"   ⚠️  CDP error: {result.get('error')}")
                return {}

            user = result["data"].get("data", {}).get("user", {})
            if not user:
                return {}
            return self._normalize_user(user)
        except Exception as e:
            print(Fore.YELLOW + f"   ⚠️  CDP profile error: {e}")
            return {}

    # ── STRATEGY 3: HTML Parse ──────────────────────────────────────────────

    def _fetch_via_html(self, username: str) -> Dict[str, Any]:
        try:
            page = self._assert_page()
            page.goto(f"https://www.instagram.com/{username}/")
            time.sleep(5)
            self._close_popups()

            data = page.evaluate(r"""() => {
                const result = {};

                const metaDesc = document.querySelector('meta[property="og:description"]');
                if (metaDesc) result.meta_description = metaDesc.content;

                const metaTitle = document.querySelector('meta[property="og:title"]');
                if (metaTitle) result.meta_title = metaTitle.content;

                const metaImg = document.querySelector('meta[property="og:image"]');
                if (metaImg) result.profile_pic_url = metaImg.content;

                const scripts = Array.from(document.querySelectorAll('script[type="application/json"]'));
                for (const s of scripts) {
                    try {
                        const json = JSON.parse(s.textContent);
                        const str = JSON.stringify(json);

                        const followers = str.match(/"edge_followed_by":\{"count":(\d+)/);
                        if (followers && !result.followers) result.followers = parseInt(followers[1]);

                        const following = str.match(/"edge_follow":\{"count":(\d+)/);
                        if (following && !result.following) result.following = parseInt(following[1]);

                        const posts = str.match(/"edge_owner_to_timeline_media":\{"count":(\d+)/);
                        if (posts && !result.posts_count) result.posts_count = parseInt(posts[1]);

                        const verified = str.match(/"is_verified":(true|false)/);
                        if (verified && result.is_verified === undefined) result.is_verified = verified[1] === 'true';

                        const fullName = str.match(/"full_name":"([^"]+)"/);
                        if (fullName && !result.full_name) result.full_name = fullName[1];

                        const bio = str.match(/"biography":"([^"]*)"/);
                        if (bio && !result.biography) result.biography = bio[1];

                        const externalUrl = str.match(/"external_url":"([^"]*)"/);
                        if (externalUrl && !result.external_url) result.external_url = externalUrl[1];

                        const category = str.match(/"category_name":"([^"]*)"/);
                        if (category && !result.category) result.category = category[1];
                    } catch(e) {}
                }

                if (result.meta_description) {
                    const md = result.meta_description.replace(/,/g, '');
                    const fm = md.match(/([\d.KMB]+)\s+Followers/i);
                    const fmw = md.match(/([\d.KMB]+)\s+Following/i);
                    const pm = md.match(/([\d.KMB]+)\s+Posts/i);
                    if (fm && !result.followers_str) result.followers_str = fm[1];
                    if (fmw && !result.following_str) result.following_str = fmw[1];
                    if (pm && !result.posts_count_str) result.posts_count_str = pm[1];
                }

                return result;
            }""")

            return self._normalize_html(data, username)
        except Exception as e:
            print(Fore.YELLOW + f"   ⚠️  HTML parse error: {e}")
            return {}

    # ── NORMALIZERS ─────────────────────────────────────────────────────────

    def _normalize_user(self, user: Dict[str, Any]) -> Dict[str, Any]:
        followers = user.get("edge_followed_by", {}).get("count", 0)
        following = user.get("edge_follow", {}).get("count", 0)
        posts_count = user.get("edge_owner_to_timeline_media", {}).get("count", 0)

        recent_posts = []
        timeline = user.get("edge_owner_to_timeline_media", {}).get("edges", [])
        for edge in timeline[:12]:
            node = edge.get("node", {})
            recent_posts.append({
                "shortcode":  node.get("shortcode", ""),
                "id":         node.get("id", ""),
                "media_type": self._map_media_type(node),
                "likes":      node.get("edge_liked_by", {}).get("count", 0) or
                              node.get("edge_media_preview_like", {}).get("count", 0),
                "comments":   node.get("edge_media_to_comment", {}).get("count", 0),
                "views":      node.get("video_view_count", 0) or 0,
                "is_video":   node.get("is_video", False),
                "taken_at":   node.get("taken_at_timestamp", 0),
                "caption":    self._extract_caption(node)[:200],
                "url":        f"https://www.instagram.com/p/{node.get('shortcode', '')}/",
            })

        out = _empty_profile_fields(user.get("username", ""))
        out.update({
            "user_id":             user.get("id", ""),
            "username":            user.get("username", ""),
            "full_name":           user.get("full_name", ""),
            "biography":           user.get("biography", ""),
            "external_url":        user.get("external_url", "") or "",
            "external_url_linkshimmed": user.get("external_url_linkshimmed", "") or "",
            "bio_links":           [
                {"title": link.get("title", ""), "url": link.get("url", "")}
                for link in (user.get("bio_links") or [])
            ],
            "category":            user.get("category_name", "") or user.get("category", "") or "",
            "category_enum":       user.get("category_enum", "") or "",
            "business_email":      user.get("business_email", "") or "",
            "business_phone":      user.get("business_phone_number", "") or "",
            "business_address":    user.get("business_address_json", "") or "",
            "is_verified":         bool(user.get("is_verified", False)),
            "is_private":          bool(user.get("is_private", False)),
            "is_business":         bool(user.get("is_business_account", False)),
            "is_professional":     bool(user.get("is_professional_account", False)),
            "is_joined_recently":  bool(user.get("is_joined_recently", False)),
            "profile_pic_url":     user.get("profile_pic_url", "") or "",
            "profile_pic_url_hd":  user.get("profile_pic_url_hd", "") or "",
            "followers":           followers,
            "following":           following,
            "posts_count":         posts_count,
            "recent_posts":        recent_posts,
        })
        return out

    def _normalize_html(self, raw: Dict[str, Any], username: str) -> Dict[str, Any]:
        def to_int(val: Any) -> int:
            if isinstance(val, int):
                return val
            if isinstance(val, str):
                v = val.upper().replace(",", "").strip()
                multiplier = 1
                if v.endswith("K"):
                    multiplier = 1_000
                    v = v[:-1]
                elif v.endswith("M"):
                    multiplier = 1_000_000
                    v = v[:-1]
                elif v.endswith("B"):
                    multiplier = 1_000_000_000
                    v = v[:-1]
                try:
                    return int(float(v) * multiplier)
                except (ValueError, TypeError):
                    return 0
            return 0

        followers = raw.get("followers") or to_int(raw.get("followers_str", "0"))
        following = raw.get("following") or to_int(raw.get("following_str", "0"))
        posts = raw.get("posts_count") or to_int(raw.get("posts_count_str", "0"))

        out = _empty_profile_fields(username)
        out.update({
            "full_name":       raw.get("full_name", ""),
            "biography":       raw.get("biography", ""),
            "external_url":    raw.get("external_url", ""),
            "category":        raw.get("category", ""),
            "is_verified":     raw.get("is_verified", False),
            "profile_pic_url": raw.get("profile_pic_url", ""),
            "followers":       followers,
            "following":       following,
            "posts_count":     posts,
        })
        return out

    @staticmethod
    def _map_media_type(node: Dict[str, Any]) -> str:
        typename = node.get("__typename", "")
        if typename == "GraphSidecar":
            return "CAROUSEL"
        if typename == "GraphVideo" or node.get("is_video"):
            return "VIDEO"
        if typename == "GraphImage":
            return "PHOTO"
        pt = node.get("product_type", "")
        if pt == "clips":
            return "VIDEO"
        return "PHOTO"

    @staticmethod
    def _extract_caption(node: Dict[str, Any]) -> str:
        edges = node.get("edge_media_to_caption", {}).get("edges", [])
        if edges:
            return edges[0].get("node", {}).get("text", "") or ""
        return ""

    # ── ENGAGEMENT SUMMARY ──────────────────────────────────────────────────

    @staticmethod
    def _compute_engagement_summary(recent_posts: List[Dict[str, Any]], followers: int) -> Dict[str, Any]:
        if not recent_posts:
            return {
                "posts_analyzed":   0,
                "avg_likes":        0,
                "avg_comments":     0,
                "avg_views":        0,
                "engagement_rate":  0.0,
                "best_post":        None,
                "worst_post":       None,
                "by_media_type":    {},
            }

        n = len(recent_posts)
        total_likes = sum(p["likes"] for p in recent_posts)
        total_comments = sum(p["comments"] for p in recent_posts)

        video_posts = [p for p in recent_posts if p.get("is_video") and p.get("views", 0) > 0]
        total_views = sum(p["views"] for p in video_posts)

        avg_likes = total_likes // n
        avg_comments = total_comments // n
        avg_views = total_views // len(video_posts) if video_posts else 0

        er = (avg_likes + avg_comments) / followers * 100 if followers > 0 else 0.0

        scored = sorted(recent_posts, key=lambda p: p["likes"] + p["comments"], reverse=True)
        best = scored[0]
        worst = scored[-1]

        by_type: Dict[str, Dict[str, Any]] = {}
        for p in recent_posts:
            mt = p["media_type"]
            if mt not in by_type:
                by_type[mt] = {"count": 0, "total_likes": 0, "total_comments": 0, "total_views": 0}
            by_type[mt]["count"] += 1
            by_type[mt]["total_likes"] += p["likes"]
            by_type[mt]["total_comments"] += p["comments"]
            by_type[mt]["total_views"] += p["views"]

        for mt, stats in by_type.items():
            cnt = stats["count"]
            stats["avg_likes"]    = stats["total_likes"] // cnt
            stats["avg_comments"] = stats["total_comments"] // cnt
            stats["avg_views"]    = stats["total_views"] // cnt if stats["total_views"] else 0

        return {
            "posts_analyzed":  n,
            "avg_likes":       avg_likes,
            "avg_comments":    avg_comments,
            "avg_views":       avg_views,
            "engagement_rate": round(er, 3),
            "best_post": {
                "url": best["url"], "likes": best["likes"],
                "comments": best["comments"], "media_type": best["media_type"],
            },
            "worst_post": {
                "url": worst["url"], "likes": worst["likes"],
                "comments": worst["comments"], "media_type": worst["media_type"],
            },
            "by_media_type": by_type,
        }

    # ── MAIN ENTRY POINT ────────────────────────────────────────────────────

    def scrape_profile(self, username: str) -> Dict[str, Any]:
        username = username.strip().lstrip("@").lower()

        print(Fore.CYAN + "\n" + "=" * 70)
        print(Fore.CYAN + f"👤 Scraping profile: @{username}")
        print(Fore.CYAN + "=" * 70)

        # FIX: result SELALU mulai dengan field lengkap
        result: Dict[str, Any] = _empty_profile_fields(username)
        result.update({
            "scraped_at":   datetime.now().isoformat(),
            "scraped_date": datetime.now().strftime("%Y-%m-%d"),
            "method":       "",
            "success":      False,
        })

        try:
            self.initialize_browser()
            self._build_requests_session()

            print(Fore.YELLOW + f"\n🌍 Membuka https://www.instagram.com/{username}/")
            page = self._assert_page()
            page.goto(f"https://www.instagram.com/{username}/")
            time.sleep(random.uniform(4, 6))
            self._close_popups()

            if "challenge" in page.url:
                raise RuntimeError("Challenge terdeteksi — buka akun manual di browser dulu")

            # ── STRATEGY 1: Web Profile API ────────────────────────────
            print(Fore.CYAN + "\n📡 [Strategy 1] Web Profile API...")
            data = self._fetch_via_web_profile_api(username)
            if data and data.get("followers", 0) > 0:
                result.update(data)
                result["method"] = "web_profile_api"
                result["success"] = True
                print(Fore.GREEN + "   ✅ Berhasil via Web Profile API")
            else:
                print(Fore.YELLOW + "   ⚠️  Web Profile API kosong / 0")

            # ── STRATEGY 2: CDP Fetch ──────────────────────────────────
            if not result["success"]:
                print(Fore.CYAN + "\n📡 [Strategy 2] CDP Fetch...")
                data = self._fetch_via_cdp(username)
                if data and data.get("followers", 0) > 0:
                    result.update(data)
                    result["method"] = "cdp_fetch"
                    result["success"] = True
                    print(Fore.GREEN + "   ✅ Berhasil via CDP Fetch")
                else:
                    print(Fore.YELLOW + "   ⚠️  CDP Fetch kosong / 0")

            # ── STRATEGY 3: HTML Parse ─────────────────────────────────
            if not result["success"]:
                print(Fore.CYAN + "\n📡 [Strategy 3] HTML Parse...")
                data = self._fetch_via_html(username)
                if data and data.get("followers", 0) > 0:
                    result.update(data)
                    result["method"] = "html_parse"
                    result["success"] = True
                    print(Fore.GREEN + "   ✅ Berhasil via HTML Parse")
                else:
                    print(Fore.YELLOW + "   ⚠️  HTML Parse kosong / 0")

            # ── ENGAGEMENT SUMMARY ─────────────────────────────────────
            if result.get("success") and result.get("recent_posts"):
                result["engagement_summary"] = self._compute_engagement_summary(
                    result["recent_posts"], result.get("followers", 0),
                )
            else:
                result["engagement_summary"] = self._compute_engagement_summary([], 0)

            if not result["success"]:
                result["error"] = "Semua strategy gagal — cookie mungkin expired atau akun private/diblokir"

            self._print_summary(result)

        except Exception as e:
            print(Fore.RED + f"\n❌ GAGAL: {e}")
            import traceback
            traceback.print_exc()
            result["error"] = str(e)
            # Pastikan engagement_summary tetap ada walau crash
            if "engagement_summary" not in result:
                result["engagement_summary"] = self._compute_engagement_summary([], 0)

        return result

    # ── PRETTY PRINT ────────────────────────────────────────────────────────

    @staticmethod
    def _print_summary(d: Dict[str, Any]) -> None:
        if not d.get("success"):
            print(Fore.RED + "\n❌ Tidak ada data berhasil di-scrape")
            return

        print(Fore.CYAN + "\n" + "=" * 60)
        print(Fore.CYAN + "📋 PROFILE SUMMARY")
        print(Fore.CYAN + "=" * 60)
        print(f"  👤 Username     : @{d.get('username','')}")
        print(f"  📛 Full name    : {d.get('full_name','')}")
        if d.get("is_verified"):
            print(Fore.BLUE + "  ✔️  Verified     : YES")
        if d.get("is_business"):
            print(f"  🏢 Business     : YES")
        if d.get("is_private"):
            print(Fore.YELLOW + "  🔒 Private      : YES")
        if d.get("category"):
            print(f"  🏷️  Category     : {d.get('category')}")
        if d.get("biography"):
            bio = d["biography"].replace("\n", " | ")[:100]
            print(f"  📝 Bio          : {bio}")
        if d.get("external_url"):
            print(f"  🔗 URL          : {d.get('external_url')}")

        print(Fore.CYAN + "\n  📊 STATS:")
        print(f"     👥 Followers : {d.get('followers', 0):>12,}")
        print(f"     ➡️  Following : {d.get('following', 0):>12,}")
        print(f"     📷 Posts     : {d.get('posts_count', 0):>12,}")

        eng = d.get("engagement_summary") or {}
        if eng.get("posts_analyzed", 0) > 0:
            print(Fore.CYAN + "\n  📈 ENGAGEMENT (dari {} post terakhir):".format(eng["posts_analyzed"]))
            print(f"     ❤️  Avg likes    : {eng['avg_likes']:>10,}")
            print(f"     💬 Avg comments : {eng['avg_comments']:>10,}")
            if eng["avg_views"] > 0:
                print(f"     👁️  Avg views    : {eng['avg_views']:>10,}")
            print(Fore.GREEN + f"     📊 Engagement Rate: {eng['engagement_rate']}% "
                  + InstagramProfileScraper._classify_er(eng['engagement_rate']))

    @staticmethod
    def _classify_er(er: float) -> str:
        if er >= 6.0:
            return Fore.GREEN + "(🔥 Excellent)"
        elif er >= 3.0:
            return Fore.GREEN + "(✅ Good)"
        elif er >= 1.0:
            return Fore.YELLOW + "(👍 Average)"
        elif er > 0:
            return Fore.RED + "(⚠️  Below average)"
        return ""


# ── STANDALONE TEST ────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python profile_scraper.py <username>")
        sys.exit(1)

    username = sys.argv[1]
    with InstagramProfileScraper() as scraper:
        data = scraper.scrape_profile(username)

        out_dir = "output"
        os.makedirs(out_dir, exist_ok=True)
        fp = os.path.join(out_dir, f"profile_{username}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        with open(fp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(Fore.GREEN + f"\n💾 Saved: {fp}")