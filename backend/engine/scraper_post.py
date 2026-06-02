import os
import re
import json
import time
import random
import requests
from datetime import datetime
from typing import List, Dict, Optional
from collections import Counter
from cookie_injector import inject_cookies_sync, has_valid_session

from dotenv import load_dotenv
from colorama import Fore, init
from playwright.sync_api import sync_playwright, Page, BrowserContext, TimeoutError as PlaywrightTimeout

# Import sentiment analyzer V2
from sentiment_analyzer_v2 import SentimentAnalyzerV2

init(autoreset=True)
load_dotenv()

# ── CONFIG ─────────────────────────────────────────────────────────────────
HEADLESS               = os.getenv("HEADLESS", "true").lower() == "true"
PROXY                  = os.getenv("PROXY", "")
MAX_POSTS              = int(os.getenv("MAX_POSTS", 10))
DELAY_BETWEEN_REQUESTS = int(os.getenv("DELAY_BETWEEN_REQUESTS", 5))
MAX_COMMENTS           = int(os.getenv("MAX_COMMENTS", 100))
SENTIMENT_MODE         = os.getenv("SENTIMENT_MODE", "hybrid")

# ── REPLIES (BARU) ─────────────────────────────────────────────────────────
INCLUDE_REPLIES        = os.getenv("INCLUDE_REPLIES", "true").lower() == "true"
MAX_REPLIES_PER_COMMENT = int(os.getenv("MAX_REPLIES_PER_COMMENT", 20))

PROFILE_DIR = os.getenv("PROFILE_DIR", "chrome_profile_playwright")
CHROME_PROFILE = os.path.join(os.getcwd(), PROFILE_DIR)

OUTPUT_DIR = "output"
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(CHROME_PROFILE, exist_ok=True)

GRAPHQL_QUERY_HASH = "97b41c52301f77ce508f55e66d17620e"


# ============================================================================
# MAIN SCRAPER
# ============================================================================

class InstagramScraperV16:

    def __init__(self, sentiment_mode: str = SENTIMENT_MODE):
        print(Fore.CYAN + f"\n🧠 Initializing Sentiment Analyzer (mode: {sentiment_mode})...")
        self.sentiment = SentimentAnalyzerV2(mode=sentiment_mode, verbose=True)

        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.session: Optional[requests.Session] = None
        self.playwright = None

        os.makedirs(CHROME_PROFILE, exist_ok=True)
        if has_valid_session():
            print(Fore.GREEN + "🍪 Login via cookie session")
        else:
            print(Fore.YELLOW + f"⚠️  Belum ada cookie session, pakai folder {CHROME_PROFILE}")
        print(Fore.GREEN + f"✅ Profile ditemukan: {CHROME_PROFILE}")

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    # ── HELPER ─────────────────────────────────────────────────────────────

    def _require_page(self) -> Page:
        if self.page is None:
            raise RuntimeError("Browser belum di-inisialisasi. Panggil initialize_browser() dulu.")
        return self.page

    def _require_context(self) -> BrowserContext:
        if self.context is None:
            raise RuntimeError("Context belum dibuat. Panggil initialize_browser() dulu.")
        return self.context

    def _require_session(self) -> requests.Session:
        if self.session is None:
            raise RuntimeError("Session belum dibuat.")
        return self.session

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
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications'
                    ? Promise.resolve({state: Notification.permission})
                    : originalQuery(parameters)
            );
        """

        context = self.playwright.chromium.launch_persistent_context(
            CHROME_PROFILE,
            headless=HEADLESS,
            args=args,
            viewport={"width": 1920, "height": 1080} if not HEADLESS else {"width": 1366, "height": 768},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36",
            locale="en-US",
            timezone_id="Asia/Jakarta",
            bypass_csp=True,
            java_script_enabled=True,
        )

        context.on("page", lambda page: page.add_init_script(stealth_script))

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
        page = self.page

        def block_heavy_resources(route):
            resource_type = route.request.resource_type
            url = route.request.url.lower()
            if resource_type in ["image", "media", "font"]:
                if "favicon" in url or "icon" in url:
                    route.continue_()
                else:
                    route.abort()
            else:
                route.continue_()

        page.route("**/*", block_heavy_resources)

        page.goto("https://www.instagram.com/")
        time.sleep(5)
        self._close_popups()

        if "login" in page.url:
            print(Fore.RED + "❌ Session expired. Jalankan login_helper_playwright.py.")
            self.close()
            exit(1)

        print(Fore.GREEN + "✅ Browser siap (LOGGED IN)")

    def _close_popups(self):
        page = self._require_page()
        popup_selectors = [
            "text=Not Now", "text=Sekarang tidak", "text=Cancel",
            "text=Batal", "text=Turn Off", "text=Save Info",
            "button:has-text('Not Now')",
        ]
        for selector in popup_selectors:
            try:
                if page.locator(selector).count() > 0:
                    page.locator(selector).first.click(timeout=2000)
                    time.sleep(0.8)
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

    # ── REQUESTS SESSION ───────────────────────────────────────────────────

    def _build_requests_session(self) -> requests.Session:
        sess = requests.Session()
        context = self._require_context()

        cookies = context.cookies()
        for cookie in cookies:
            name = cookie.get("name")
            value = cookie.get("value")
            if not name or value is None:
                continue
            sess.cookies.set(name, value, domain=cookie.get("domain", ".instagram.com"))

        csrf = next((c.get("value", "") for c in cookies if c.get("name") == "csrftoken"), "")

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
        return sess

    # ── EXTRACT MEDIA ID ───────────────────────────────────────────────────

    def _get_media_id(self) -> Optional[str]:
        page = self._require_page()
        try:
            return page.evaluate(r"""() => {
                const scripts = Array.from(document.querySelectorAll('script'));
                for (const s of scripts) {
                    const txt = s.textContent || '';
                    const m = txt.match(/"media_id":"(\d+)"/)
                        || txt.match(/"id":"(\d+_\d+)"/)
                        || txt.match(/instagram:\/\/media\?id=(\d+)/);
                    if (m) return m[1].split('_')[0];
                }
                const meta = document.querySelector('meta[property="al:ios:url"]');
                if (meta) {
                    const m = meta.content.match(/id=(\d+)/);
                    if (m) return m[1];
                }
                return null;
            }""")
        except Exception:
            return None

    def _get_owner_username(self) -> str:
        page = self._require_page()
        try:
            owner = page.evaluate(r"""() => {
                const cleanUser = (u) => (u || '').trim().replace(/^@/, '').toLowerCase();

                const title = (document.querySelector('meta[property="og:title"]')?.content) || '';
                const desc  = (document.querySelector('meta[property="og:description"]')?.content) || '';

                let m = title.match(/@([\w.]+)/);
                if (m) return cleanUser(m[1]);

                m = desc.match(/comments?\s*-\s*([\w.]+)\s+on\b/i)
                    || title.match(/comments?\s*-\s*([\w.]+)\s+on\b/i);
                if (m) return cleanUser(m[1]);

                m = title.match(/^([\w.]+)\s+on\s+Instagram/i);
                if (m) return cleanUser(m[1]);

                const scripts = Array.from(document.querySelectorAll('script[type="application/json"]'));
                for (const s of scripts) {
                    const t = s.textContent || '';
                    const mm = t.match(/"owner":\{[^}]*?"username":"([\w.]+)"/);
                    if (mm) return cleanUser(mm[1]);
                }

                return '';
            }""")

            if owner and owner not in ("instagram", "p", "reel", "tv"):
                return owner
        except Exception:
            pass
        return ""

    # ── EXTRACT ENGAGEMENT METRICS ─────────────────────────────────────────

    def _fetch_media_info_rest(self, media_id: str) -> Dict:
        url = f"https://www.instagram.com/api/v1/media/{media_id}/info/"
        try:
            sess = self._require_session()
            resp = sess.get(url, timeout=15)
            if resp.status_code != 200:
                return {}
            if 'json' not in resp.headers.get('content-type', ''):
                return {}

            data = resp.json()
            items = data.get("items", [])
            if not items:
                return {}

            item = items[0]
            metrics = {}

            view_count = item.get("view_count") or item.get("ig_play_count") or item.get("video_view_count") or 0
            play_count = item.get("play_count") or item.get("ig_play_count") or item.get("video_play_count") or 0
            metrics["video_views"] = int(view_count)
            metrics["play_count"]  = int(play_count)

            reshare   = item.get("reshare_count", 0) or 0
            direct    = item.get("direct_send_count", 0) or 0
            share_alt = item.get("share_count", 0) or 0
            metrics["shares_count"]  = int(reshare + direct) if (reshare or direct) else int(share_alt)
            metrics["reshare_count"] = int(reshare)
            metrics["direct_send_count"] = int(direct)

            saves_raw = item.get("saved_count") or item.get("save_count") or 0
            metrics["saves_count"] = int(saves_raw)

            like_info = item.get("like_count") or item.get("likes", {})
            if isinstance(like_info, dict):
                metrics["likes"] = int(like_info.get("count", 0))
            else:
                metrics["likes"] = int(like_info or 0)

            user = item.get("user", {}) or item.get("owner", {}) or {}
            uname = user.get("username", "")
            if uname:
                metrics["owner_username"] = uname

            media_type_map = {1: "PHOTO", 2: "VIDEO", 8: "CAROUSEL"}
            metrics["media_type"] = media_type_map.get(item.get("media_type", 0), "UNKNOWN")
            metrics["product_type"] = item.get("product_type", "")

            return metrics

        except Exception as e:
            if self.session:
                print(Fore.YELLOW + f"   ⚠️  REST media info error: {e}")
            return {}

    def _fetch_media_info_cdp(self, media_id: str) -> Dict:
        page = self._require_page()
        try:
            result = page.evaluate(r"""async (mediaId) => {
                try {
                    const resp = await fetch(`/api/v1/media/${mediaId}/info/`, {
                        method: 'GET',
                        credentials: 'include',
                        headers: {
                            'X-IG-App-ID': '936619743392459',
                            'X-ASBD-ID': '129477',
                            'X-Requested-With': 'XMLHttpRequest',
                            'Accept': '*/*',
                        }
                    });
                    const data = await resp.json();
                    return {ok: true, data: data};
                } catch(e) {
                    return {ok: false, error: e.toString()};
                }
            }""", media_id)

            if not result.get("ok"):
                return {}

            data = result["data"]
            items = data.get("items", [])
            if not items:
                return {}

            item = items[0]
            metrics = {}

            view_count = item.get("view_count") or item.get("ig_play_count") or item.get("video_view_count") or 0
            play_count = item.get("play_count") or item.get("ig_play_count") or item.get("video_play_count") or 0
            metrics["video_views"] = int(view_count)
            metrics["play_count"]  = int(play_count)

            reshare   = item.get("reshare_count", 0) or 0
            direct    = item.get("direct_send_count", 0) or 0
            share_alt = item.get("share_count", 0) or 0
            metrics["shares_count"]      = int(reshare + direct) if (reshare or direct) else int(share_alt)
            metrics["reshare_count"]     = int(reshare)
            metrics["direct_send_count"] = int(direct)

            metrics["saves_count"] = int(item.get("saved_count") or item.get("save_count") or 0)

            like_info = item.get("like_count") or item.get("likes", {})
            if isinstance(like_info, dict):
                metrics["likes"] = int(like_info.get("count", 0))
            else:
                metrics["likes"] = int(like_info or 0)

            user = item.get("user", {}) or item.get("owner", {}) or {}
            uname = user.get("username", "")
            if uname:
                metrics["owner_username"] = uname

            media_type_map = {1: "PHOTO", 2: "VIDEO", 8: "CAROUSEL"}
            metrics["media_type"]   = media_type_map.get(item.get("media_type", 0), "UNKNOWN")
            metrics["product_type"] = item.get("product_type", "")

            return metrics

        except Exception as e:
            print(Fore.YELLOW + f"   ⚠️  CDP media info error: {e}")
            return {}

    def _fetch_media_info_from_page(self) -> Dict:
        page = self._require_page()
        try:
            metrics = page.evaluate(r"""() => {
                const scripts = Array.from(document.querySelectorAll('script[type="application/json"]'));
                let combined = {};

                for (const s of scripts) {
                    try {
                        const data = JSON.parse(s.textContent);
                        const str  = JSON.stringify(data);

                        const pc = str.match(/"play_count":(\d+)/);
                        if (pc) combined.play_count = parseInt(pc[1]);

                        const vc = str.match(/"video_view_count":(\d+)/);
                        if (vc) combined.video_views = parseInt(vc[1]);

                        const igp = str.match(/"ig_play_count":(\d+)/);
                        if (igp && !combined.play_count) combined.play_count = parseInt(igp[1]);

                        const sv = str.match(/"saved_count":(\d+)/);
                        if (sv) combined.saves_count = parseInt(sv[1]);

                        const rc = str.match(/"reshare_count":(\d+)/);
                        if (rc) combined.reshare_count = parseInt(rc[1]);

                        const sc = str.match(/"share_count":(\d+)/);
                        if (sc) combined.shares_count = parseInt(sc[1]);

                        const mt = str.match(/"media_type":(\d)/);
                        if (mt) {
                            const map = {1:"PHOTO", 2:"VIDEO", 8:"CAROUSEL"};
                            combined.media_type = map[mt[1]] || "UNKNOWN";
                        }

                        const pt = str.match(/"product_type":"([^"]+)"/);
                        if (pt) combined.product_type = pt[1];

                        const ou = str.match(/"owner":\{[^}]*?"username":"([\w.]+)"/);
                        if (ou && !combined.owner_username) combined.owner_username = ou[1];

                    } catch(e) {}
                }
                return combined;
            }""")
            return metrics if metrics else {}
        except Exception as e:
            print(Fore.YELLOW + f"   ⚠️  Page source metrics error: {e}")
            return {}

    def _get_engagement_metrics(self, media_id: str) -> Dict:
        default = {
            "video_views":       0,
            "play_count":        0,
            "shares_count":      0,
            "reshare_count":     0,
            "direct_send_count": 0,
            "saves_count":       0,
            "media_type":        "UNKNOWN",
            "product_type":      "",
        }

        print(Fore.CYAN + "\n📊 Mengambil engagement metrics...")

        metrics = {}
        if media_id:
            metrics = self._fetch_media_info_rest(media_id)
            if metrics:
                print(Fore.GREEN + f"   ✅ Metrics via REST: views={metrics.get('video_views',0):,} "
                      f"plays={metrics.get('play_count',0):,} "
                      f"shares={metrics.get('shares_count',0):,} "
                      f"saves={metrics.get('saves_count',0):,}")

        if not metrics and media_id:
            print(Fore.YELLOW + "   ↩️  Fallback ke CDP...")
            metrics = self._fetch_media_info_cdp(media_id)

        if not metrics:
            print(Fore.YELLOW + "   ↩️  Fallback ke page source...")
            metrics = self._fetch_media_info_from_page()

        merged = {**default, **{k: v for k, v in metrics.items() if v}}
        return merged

    # ============================================================
    # STRATEGY 1: GraphQL GET  (PRIMARY - parent comments)
    # ============================================================

    def _fetch_via_graphql(self, shortcode: str, max_comments: int) -> List[Dict]:
        all_comments: List[Dict] = []
        end_cursor = None
        page_num = 0
        max_pages = 100
        sess = self._require_session()

        while len(all_comments) < max_comments and page_num < max_pages:
            page_num += 1

            variables = {"shortcode": shortcode, "first": 50}
            if end_cursor:
                variables["after"] = end_cursor

            try:
                resp = sess.get(
                    "https://www.instagram.com/graphql/query/",
                    params={
                        "query_hash": GRAPHQL_QUERY_HASH,
                        "variables": json.dumps(variables),
                    },
                    timeout=20,
                )

                if resp.status_code == 429:
                    print(Fore.YELLOW + "   ⚠️  429 Rate limit, tunggu 60s")
                    time.sleep(60)
                    continue
                if resp.status_code != 200:
                    print(Fore.YELLOW + f"   ⚠️  GraphQL status {resp.status_code}")
                    break

                if 'json' not in resp.headers.get('content-type', ''):
                    print(Fore.YELLOW + "   ⚠️  GraphQL response bukan JSON")
                    break

                data = resp.json()
                if data.get("status") == "fail":
                    print(Fore.YELLOW + f"   ⚠️  GraphQL fail: {data.get('message', '')}")
                    break

                media = data.get("data", {}).get("shortcode_media", {})
                comment_edge = media.get("edge_media_to_parent_comment", {})
                edges = comment_edge.get("edges", [])
                page_info = comment_edge.get("page_info", {})

                if not edges:
                    break

                for e in edges:
                    n = e.get("node", {})
                    username = n.get("owner", {}).get("username", "")
                    text = n.get("text", "")
                    if not username or not text:
                        continue

                    all_comments.append({
                        "username": username,
                        "text": text,
                        "comment_id": n.get("id", ""),
                        "like_count": n.get("edge_liked_by", {}).get("count", 0),
                        "created_at": n.get("created_at", 0),
                        "reply_count": n.get("edge_threaded_comments", {}).get("count", 0),
                    })

                    if len(all_comments) >= max_comments:
                        break

                print(Fore.CYAN + f"   📡 GraphQL page {page_num}: +{len(edges)} (total {len(all_comments)})")

                if not page_info.get("has_next_page"):
                    print(Fore.GREEN + "   ✅ Sudah halaman terakhir")
                    break
                end_cursor = page_info.get("end_cursor")
                if not end_cursor:
                    break

                time.sleep(random.uniform(2.0, 3.5))

            except Exception as e:
                print(Fore.RED + f"   ❌ GraphQL error: {e}")
                break

        return all_comments

    # ============================================================
    # STRATEGY 2: CDP Fetch (FALLBACK - parent comments)
    # ============================================================

    def _fetch_via_cdp(self, media_id: str, max_comments: int) -> List[Dict]:
        all_comments: List[Dict] = []
        next_min_id = None
        page_num = 0
        max_pages = 50
        page = self._require_page()

        while len(all_comments) < max_comments and page_num < max_pages:
            page_num += 1

            try:
                result = page.evaluate(r"""(params) => {
                    const { mediaId, minId } = params;
                    return (async () => {
                        try {
                            let url = `/api/v1/media/${mediaId}/comments/?can_support_threading=true`;
                            if (minId) url += `&min_id=${encodeURIComponent(minId)}`;

                            const resp = await fetch(url, {
                                method: 'GET',
                                credentials: 'include',
                                headers: {
                                    'X-IG-App-ID': '936619743392459',
                                    'X-ASBD-ID': '129477',
                                    'X-Requested-With': 'XMLHttpRequest',
                                    'Accept': '*/*',
                                }
                            });
                            const data = await resp.json();
                            return {ok: true, data: data};
                        } catch(e) {
                            return {ok: false, error: e.toString()};
                        }
                    })();
                }""", {"mediaId": media_id, "minId": next_min_id})

                if not result.get("ok"):
                    print(Fore.YELLOW + f"   ⚠️  CDP error: {result.get('error')}")
                    break

                data = result["data"]
                comments_raw = data.get("comments", [])

                if not comments_raw:
                    break

                for c in comments_raw:
                    username = c.get("user", {}).get("username", "")
                    text = c.get("text", "")
                    if not username or not text:
                        continue

                    all_comments.append({
                        "username": username,
                        "text": text,
                        "comment_id": str(c.get("pk", "")),
                        "like_count": c.get("comment_like_count", 0),
                        "created_at": c.get("created_at", 0),
                        "reply_count": c.get("child_comment_count", 0),
                    })

                    if len(all_comments) >= max_comments:
                        break

                print(Fore.CYAN + f"   📡 CDP page {page_num}: +{len(comments_raw)} (total {len(all_comments)})")

                next_min_id = data.get("next_min_id")
                if not next_min_id or not data.get("has_more_comments", False):
                    break

                time.sleep(random.uniform(2.0, 3.5))

            except Exception as e:
                print(Fore.RED + f"   ❌ CDP error: {e}")
                break

        return all_comments

    # ============================================================
    # STRATEGY 3: REST API (LAST RESORT - parent comments)
    # ============================================================

    def _fetch_via_rest(self, media_id: str, max_comments: int) -> List[Dict]:
        all_comments: List[Dict] = []
        next_min_id = None
        page_num = 0
        max_pages = 50
        sess = self._require_session()

        while len(all_comments) < max_comments and page_num < max_pages:
            page_num += 1

            url = f"https://www.instagram.com/api/v1/media/{media_id}/comments/"
            params = {"can_support_threading": "true"}
            if next_min_id:
                params["min_id"] = next_min_id

            try:
                resp = sess.get(url, params=params, timeout=15)

                if resp.status_code == 429:
                    print(Fore.YELLOW + "   ⚠️  429, tunggu 60s")
                    time.sleep(60)
                    continue
                if resp.status_code != 200:
                    break
                if 'json' not in resp.headers.get('content-type', ''):
                    break

                data = resp.json()
                comments_raw = data.get("comments", [])
                if not comments_raw:
                    break

                for c in comments_raw:
                    username = c.get("user", {}).get("username", "")
                    text = c.get("text", "")
                    if not username or not text:
                        continue

                    all_comments.append({
                        "username": username,
                        "text": text,
                        "comment_id": str(c.get("pk", "")),
                        "like_count": c.get("comment_like_count", 0),
                        "created_at": c.get("created_at", 0),
                        "reply_count": c.get("child_comment_count", 0),
                    })

                    if len(all_comments) >= max_comments:
                        break

                print(Fore.CYAN + f"   📡 REST page {page_num}: +{len(comments_raw)} (total {len(all_comments)})")

                next_min_id = data.get("next_min_id")
                if not next_min_id or not data.get("has_more_comments", False):
                    break

                time.sleep(random.uniform(2.0, 3.5))

            except Exception as e:
                print(Fore.RED + f"   ❌ REST error: {e}")
                break

        return all_comments

    # ============================================================
    # REPLIES (CHILD COMMENTS) - BARU
    # ============================================================
    #
    # Endpoint IG:
    #   /api/v1/media/{media_id}/comments/{parent_pk}/child_comments/
    #
    # Pagination via max_id (cursor) yang dikembalikan di response.
    # Response shape:
    #   {
    #     "child_comments": [...],   // sebagian build pakai "comments"
    #     "has_more_comments": bool,
    #     "next_max_id": "..."
    #   }
    # ============================================================

    def _parse_reply(self, c: Dict, parent_pk: str) -> Optional[Dict]:
        """Normalisasi 1 reply dari response IG."""
        username = c.get("user", {}).get("username", "")
        text = c.get("text", "")
        if not username or not text:
            return None
        return {
            "username":          username,
            "text":              text,
            "comment_id":        str(c.get("pk", "")),
            "like_count":        c.get("comment_like_count", 0) or 0,
            "created_at":        c.get("created_at", 0) or 0,
            "parent_comment_id": str(parent_pk),
        }

    def _fetch_replies_via_cdp(self, media_id: str, parent_pk: str, max_replies: int) -> List[Dict]:
        """Strategy 1: CDP Fetch (browser context) untuk child_comments."""
        all_replies: List[Dict] = []
        next_max_id: Optional[str] = None
        page_num = 0
        max_pages = 5
        page = self._require_page()

        while len(all_replies) < max_replies and page_num < max_pages:
            page_num += 1
            try:
                result = page.evaluate(r"""(params) => {
                    const { mediaId, parentPk, maxId } = params;
                    return (async () => {
                        try {
                            let url = `/api/v1/media/${mediaId}/comments/${parentPk}/child_comments/`;
                            if (maxId) url += `?max_id=${encodeURIComponent(maxId)}`;
                            const resp = await fetch(url, {
                                method: 'GET',
                                credentials: 'include',
                                headers: {
                                    'X-IG-App-ID': '936619743392459',
                                    'X-ASBD-ID': '129477',
                                    'X-Requested-With': 'XMLHttpRequest',
                                    'Accept': '*/*',
                                }
                            });
                            const data = await resp.json();
                            return {ok: true, status: resp.status, data: data};
                        } catch(e) {
                            return {ok: false, error: e.toString()};
                        }
                    })();
                }""", {"mediaId": media_id, "parentPk": parent_pk, "maxId": next_max_id})

                if not result.get("ok"):
                    break

                if result.get("status") and result["status"] != 200:
                    break

                data = result.get("data") or {}
                raw = data.get("child_comments") or data.get("comments") or []
                if not raw:
                    break

                for c in raw:
                    parsed = self._parse_reply(c, parent_pk)
                    if parsed:
                        all_replies.append(parsed)
                    if len(all_replies) >= max_replies:
                        break

                next_max_id = data.get("next_max_id") or data.get("next_min_id")
                has_more = data.get("has_more_comments") or data.get("has_more_headload_comments") or False
                if not next_max_id or not has_more:
                    break

                time.sleep(random.uniform(0.5, 1.2))

            except Exception as e:
                print(Fore.YELLOW + f"      ⚠️  Reply CDP error: {e}")
                break

        return all_replies

    def _fetch_replies_via_rest(self, media_id: str, parent_pk: str, max_replies: int) -> List[Dict]:
        """Strategy 2: REST direct via requests session."""
        all_replies: List[Dict] = []
        next_max_id: Optional[str] = None
        page_num = 0
        max_pages = 5
        sess = self._require_session()

        while len(all_replies) < max_replies and page_num < max_pages:
            page_num += 1
            url = f"https://www.instagram.com/api/v1/media/{media_id}/comments/{parent_pk}/child_comments/"
            params: Dict[str, str] = {}
            if next_max_id:
                params["max_id"] = next_max_id

            try:
                resp = sess.get(url, params=params, timeout=15)
                if resp.status_code == 429:
                    time.sleep(45)
                    continue
                if resp.status_code != 200:
                    break
                if 'json' not in resp.headers.get('content-type', ''):
                    break

                data = resp.json()
                raw = data.get("child_comments") or data.get("comments") or []
                if not raw:
                    break

                for c in raw:
                    parsed = self._parse_reply(c, parent_pk)
                    if parsed:
                        all_replies.append(parsed)
                    if len(all_replies) >= max_replies:
                        break

                next_max_id = data.get("next_max_id") or data.get("next_min_id")
                has_more = data.get("has_more_comments") or data.get("has_more_headload_comments") or False
                if not next_max_id or not has_more:
                    break

                time.sleep(random.uniform(0.5, 1.2))

            except Exception as e:
                print(Fore.YELLOW + f"      ⚠️  Reply REST error: {e}")
                break

        return all_replies

    def _fetch_replies(self, media_id: str, parent_pk: str, max_replies: int) -> List[Dict]:
        """Cascade: CDP → REST. Skip kalau parent_pk kosong."""
        if not media_id or not parent_pk:
            return []

        try:
            replies = self._fetch_replies_via_cdp(media_id, parent_pk, max_replies)
            if replies:
                return replies
        except Exception:
            pass

        try:
            return self._fetch_replies_via_rest(media_id, parent_pk, max_replies)
        except Exception:
            return []

    # ============================================================
    # MAIN SCRAPE FLOW
    # ============================================================

    def scrape_post_comments(
        self,
        post_url: str,
        max_comments: int = MAX_COMMENTS,
        include_replies: bool = INCLUDE_REPLIES,
        max_replies_per_comment: int = MAX_REPLIES_PER_COMMENT,
    ) -> Dict:
        print(Fore.CYAN + "\n" + "=" * 70)
        print(Fore.CYAN + f"📝 {post_url[:70]}")
        print(Fore.CYAN + f"   include_replies={include_replies} "
              f"max_replies_per_comment={max_replies_per_comment}")
        print(Fore.CYAN + "=" * 70)

        m = re.search(r'/(p|reel|tv)/([A-Za-z0-9_-]+)', post_url)
        shortcode = m.group(2) if m else "unknown"

        is_reel_url = bool(re.search(r'/reel/', post_url))
        is_tv_url   = bool(re.search(r'/tv/', post_url))

        result: Dict = {
            "url": post_url,
            "shortcode": shortcode,
            "scraped_at": datetime.now().isoformat(),
            "sentiment_mode": self.sentiment.mode,
            "include_replies": include_replies,
            "max_replies_per_comment": max_replies_per_comment,
            "caption": "",
            "likes": 0,
            "owner_username": "",
            "media_id": "",
            "method": "",
            "media_type":        "UNKNOWN",
            "product_type":      "",
            "video_views":       0,
            "play_count":        0,
            "shares_count":      0,
            "reshare_count":     0,
            "direct_send_count": 0,
            "saves_count":       0,
            "comments": [],
            "comments_count": 0,
            "replies_count": 0,
            "sentiment_summary": {},
        }

        try:
            self.initialize_browser()
            page = self._require_page()

            clean_match = re.search(r'(https://www\.instagram\.com/(p|reel|tv)/[A-Za-z0-9_-]+)', post_url)
            clean = clean_match.group(1) if clean_match else post_url.split("?")[0].rstrip("/")

            print(Fore.YELLOW + f"\n🌍 Buka: {clean}")
            page.goto(clean)
            time.sleep(6)
            self._close_popups()

            if "login" in page.url:
                raise Exception("Redirect login — session expired")
            if "challenge" in page.url:
                raise Exception("Challenge terdeteksi")

            try:
                page.wait_for_selector("article, main", timeout=15000)
            except PlaywrightTimeout:
                pass

            try:
                body_text = page.locator("body").inner_text()
                lm = re.search(r'([\d,]+)\s+likes?', body_text, re.I)
                if lm:
                    result["likes"] = int(lm.group(1).replace(",", ""))
                    print(Fore.CYAN + f"❤️  Likes: {result['likes']:,}")
            except Exception:
                pass

            try:
                cap = page.evaluate(r"""() => {
                    const m = document.querySelector('meta[property="og:description"]');
                    return m ? m.content : '';
                }""")
                if cap:
                    result["caption"] = cap[:500]
                    print(Fore.CYAN + f"📄 Caption: {cap[:80]}...")
            except Exception:
                pass

            owner = self._get_owner_username()
            if owner:
                result["owner_username"] = owner
                print(Fore.CYAN + f"👤 Owner: @{owner}")

            media_id = self._get_media_id()
            if media_id:
                result["media_id"] = media_id
                print(Fore.GREEN + f"✅ Media ID: {media_id}")

            self.session = self._build_requests_session()

            engagement = self._get_engagement_metrics(media_id or "")

            result["media_type"]        = engagement.get("media_type", "UNKNOWN")
            result["product_type"]      = engagement.get("product_type", "")
            result["video_views"]       = engagement.get("video_views", 0)
            result["play_count"]        = engagement.get("play_count", 0)
            result["shares_count"]      = engagement.get("shares_count", 0)
            result["reshare_count"]     = engagement.get("reshare_count", 0)
            result["direct_send_count"] = engagement.get("direct_send_count", 0)
            result["saves_count"]       = engagement.get("saves_count", 0)

            if engagement.get("likes", 0) > 0:
                result["likes"] = engagement["likes"]

            if not result["owner_username"] and engagement.get("owner_username"):
                result["owner_username"] = engagement["owner_username"]
                print(Fore.CYAN + f"👤 Owner (dari media info): @{result['owner_username']}")

            if result["media_type"] == "UNKNOWN":
                if is_reel_url:
                    result["media_type"] = "VIDEO"
                    if not result["product_type"]:
                        result["product_type"] = "clips"
                elif is_tv_url:
                    result["media_type"] = "VIDEO"
                    if not result["product_type"]:
                        result["product_type"] = "igtv"

            print(Fore.CYAN + f"\n📈 Engagement Metrics:")
            print(Fore.CYAN + f"   📌 Media type   : {result['media_type']} ({result['product_type'] or 'feed'})")
            print(Fore.CYAN + f"   ❤️  Likes        : {result['likes']:,}")
            if result["video_views"] > 0:
                print(Fore.CYAN + f"   👁️  Video views  : {result['video_views']:,}")
            if result["play_count"] > 0:
                print(Fore.CYAN + f"   ▶️  Play count   : {result['play_count']:,}")
            if result["shares_count"] > 0:
                print(Fore.CYAN + f"   📤 Shares       : {result['shares_count']:,} "
                      f"(DM: {result['direct_send_count']:,} | Story: {result['reshare_count']:,})")
            if result["saves_count"] > 0:
                print(Fore.CYAN + f"   🔖 Saves        : {result['saves_count']:,}")

            # ── CASCADE: GraphQL → CDP → REST ─────
            raw_comments: List[Dict] = []
            method_used = ""

            print(Fore.CYAN + f"\n📡 [Strategy 1] GraphQL...")
            try:
                raw_comments = self._fetch_via_graphql(shortcode, max_comments)
                if raw_comments:
                    method_used = "graphql"
                    print(Fore.GREEN + f"✅ GraphQL: {len(raw_comments)} komentar")
            except Exception as e:
                print(Fore.YELLOW + f"   ⚠️  GraphQL gagal: {e}")

            if not raw_comments and media_id:
                print(Fore.CYAN + f"\n📡 [Strategy 2] CDP Fetch...")
                try:
                    raw_comments = self._fetch_via_cdp(media_id, max_comments)
                    if raw_comments:
                        method_used = "cdp"
                        print(Fore.GREEN + f"✅ CDP: {len(raw_comments)} komentar")
                except Exception as e:
                    print(Fore.YELLOW + f"   ⚠️  CDP gagal: {e}")

            if not raw_comments and media_id:
                print(Fore.CYAN + f"\n📡 [Strategy 3] REST API...")
                try:
                    raw_comments = self._fetch_via_rest(media_id, max_comments)
                    if raw_comments:
                        method_used = "rest"
                        print(Fore.GREEN + f"✅ REST: {len(raw_comments)} komentar")
                except Exception as e:
                    print(Fore.YELLOW + f"   ⚠️  REST gagal: {e}")

            result["method"] = method_used

            if not raw_comments:
                print(Fore.RED + "\n❌ Semua strategy gagal")

            # Dedup parent comments
            seen_ids = set()
            unique_comments: List[Dict] = []
            for c in raw_comments:
                cid = c.get("comment_id", "")
                if cid and cid in seen_ids:
                    continue
                if cid:
                    seen_ids.add(cid)
                unique_comments.append(c)

            # ── SENTIMENT untuk PARENT ─────
            t_sentiment_start = time.time()
            if unique_comments:
                print(Fore.CYAN + f"\n🧠 Analisis sentimen {len(unique_comments)} komentar...")

            final_comments: List[Dict] = []
            total_replies_fetched = 0

            for i, rc in enumerate(unique_comments, 1):
                text = rc.get("text", "")
                if not text:
                    continue

                entry = self._build_comment_entry(rc, number=i)
                final_comments.append(entry)
                self._print_comment_line(entry, i)

                # ── REPLIES: kalau diaktifkan & komentar punya reply_count > 0 ─
                reply_count_raw = int(rc.get("reply_count", 0) or 0)
                if include_replies and reply_count_raw > 0 and max_replies_per_comment > 0:
                    parent_pk = rc.get("comment_id", "")
                    if parent_pk and media_id:
                        print(Fore.CYAN + f"      ↳ fetch {min(reply_count_raw, max_replies_per_comment)} "
                              f"reply untuk @{rc.get('username','')[:18]}...")
                        raw_replies = self._fetch_replies(
                            media_id, parent_pk, max_replies_per_comment
                        )

                        # Dedup replies
                        seen_reply = set()
                        final_replies: List[Dict] = []
                        for j, rr in enumerate(raw_replies, 1):
                            rid = rr.get("comment_id", "")
                            if rid and rid in seen_reply:
                                continue
                            if rid:
                                seen_reply.add(rid)

                            reply_entry = self._build_comment_entry(
                                rr, number=j, is_reply=True, parent_pk=parent_pk
                            )
                            final_replies.append(reply_entry)
                            self._print_reply_line(reply_entry, j)

                        entry["replies"] = final_replies
                        entry["replies_fetched"] = len(final_replies)
                        total_replies_fetched += len(final_replies)

                        # Jeda kecil antar pemanggilan reply biar tidak hammer
                        time.sleep(random.uniform(0.4, 0.9))
                    else:
                        entry["replies"] = []
                        entry["replies_fetched"] = 0
                else:
                    entry["replies"] = []
                    entry["replies_fetched"] = 0

            if unique_comments:
                t_sentiment = time.time() - t_sentiment_start
                per_item = t_sentiment / max(1, len(unique_comments))
                print(Fore.CYAN + f"\n   ⏱️  Total proses (parent+reply): {t_sentiment:.1f}s "
                      f"(~{per_item*1000:.0f}ms per parent)")

            result["comments"] = final_comments
            result["comments_count"] = len(final_comments)
            result["replies_count"] = total_replies_fetched
            result["sentiment_summary"] = self._summarize(final_comments, result)

        except Exception as e:
            print(Fore.RED + f"\n❌ GAGAL: {e}")
            import traceback
            traceback.print_exc()
            result["error"] = str(e)

        return result

    # ── HELPER: build entry komentar (parent atau reply) ─────────────────

    def _build_comment_entry(
        self,
        rc: Dict,
        number: int,
        is_reply: bool = False,
        parent_pk: str = "",
    ) -> Dict:
        text = rc.get("text", "")
        analysis = self.sentiment.analyze_sentiment(text)
        category = self.sentiment.categorize_comment(text)

        entry = {
            "number":          number,
            "username":        rc.get("username", ""),
            "text":            text,
            "comment_id":      rc.get("comment_id", ""),
            "like_count":      rc.get("like_count", 0),
            "created_at":      rc.get("created_at", 0),
            "reply_count":     rc.get("reply_count", 0) if not is_reply else 0,
            "is_reply":        is_reply,
            "parent_comment_id": parent_pk if is_reply else "",
            "category":        category,
            "sentiment":       analysis["sentiment"],
            "language":        analysis["language"],
            "is_hate_speech":  analysis["is_hate_speech"],
            "is_toxic":        analysis["is_toxic"],
            "is_sarcasm":      analysis.get("is_sarcasm", False),
            "is_wellwish":     analysis.get("is_wellwish", False),
            "hate_score":      analysis["hate_score"],
            "hate_words":      analysis["hate_words"],
            "toxic_words":     analysis["toxic_words"],
            "positive_words":  analysis["positive_words"],
            "negative_words":  analysis.get("negative_words", []),
            "humor_words":     analysis["humor_words"],
            "emojis":          analysis["emojis"],
            "ml_confidence":   analysis.get("ml_confidence", 0.0),
            "decision_source": analysis.get("decision_source", "rule"),
            "vader_compound":  analysis.get("vader_compound", 0.0),
        }
        return entry

    def _print_comment_line(self, entry: Dict, i: int):
        if entry["is_hate_speech"]:
            label = Fore.RED     + "🚨 HATE "
        elif entry["is_toxic"]:
            label = Fore.YELLOW  + "⚠️  TOXIC"
        elif entry["category"] == "POSITIVE":
            label = Fore.GREEN   + "😊 POS  "
        elif entry["category"] == "NEGATIVE":
            label = Fore.MAGENTA + "😞 NEG  "
        elif entry["category"] == "HUMOR":
            label = Fore.CYAN    + "😂 HUMOR"
        else:
            label = Fore.WHITE   + "💬 NEU  "

        indicators = []
        if entry.get("is_sarcasm"):
            indicators.append("🎭")
        if entry.get("is_wellwish"):
            indicators.append("🙏")
        ind_str = "".join(indicators)

        preview = entry["text"][:55].replace("\n", " ")
        likes = entry.get("like_count", 0)
        likes_str = f" [{likes}❤]" if likes > 0 else ""
        rc_str = f" 💬{entry['reply_count']}" if entry.get("reply_count", 0) > 0 else ""
        print(f"{label} #{i:3d} {ind_str} @{entry['username'][:18]}: {preview}{likes_str}{rc_str}")

    def _print_reply_line(self, entry: Dict, j: int):
        if entry["is_hate_speech"]:
            label = Fore.RED     + "🚨"
        elif entry["is_toxic"]:
            label = Fore.YELLOW  + "⚠️"
        elif entry["category"] == "POSITIVE":
            label = Fore.GREEN   + "😊"
        elif entry["category"] == "NEGATIVE":
            label = Fore.MAGENTA + "😞"
        elif entry["category"] == "HUMOR":
            label = Fore.CYAN    + "😂"
        else:
            label = Fore.WHITE   + "💬"

        preview = entry["text"][:45].replace("\n", " ")
        likes = entry.get("like_count", 0)
        likes_str = f" [{likes}❤]" if likes > 0 else ""
        print(f"        ↳ {label} #{j:2d} @{entry['username'][:15]}: {preview}{likes_str}")

    # ── SUMMARY ───────────

    def _summarize(self, comments: List[Dict], post_data: Optional[Dict] = None) -> Dict:
        if not comments:
            base: Dict = {"total_comments": 0}
            if post_data:
                base.update(self._engagement_summary(post_data))
            return base

        total = len(comments)
        counts = {k: 0 for k in ("HATE_SPEECH", "TOXIC", "POSITIVE", "NEGATIVE", "NEUTRAL", "HUMOR")}
        hate_ex = []
        toxic_ex = []
        sarcasm_count = 0
        wellwish_count = 0
        decision_sources: Counter = Counter()
        ml_confidences = []

        # Stats khusus replies
        total_replies = 0
        replies_counts = {k: 0 for k in ("HATE_SPEECH", "TOXIC", "POSITIVE", "NEGATIVE", "NEUTRAL", "HUMOR")}

        for c in comments:
            cat = c.get("category", "NEUTRAL")
            if cat in counts:
                counts[cat] += 1
            if c.get("is_hate_speech"):
                hate_ex.append({
                    "username": c["username"],
                    "text": c["text"],
                    "hate_words": c["hate_words"],
                    "like_count": c.get("like_count", 0),
                })
            if c.get("is_toxic"):
                toxic_ex.append({
                    "username": c["username"],
                    "text": c["text"],
                    "toxic_words": c["toxic_words"],
                })
            if c.get("is_sarcasm"):
                sarcasm_count += 1
            if c.get("is_wellwish"):
                wellwish_count += 1

            ds = c.get("decision_source", "unknown")
            decision_sources[ds] += 1

            mlc = c.get("ml_confidence", 0)
            if mlc > 0:
                ml_confidences.append(mlc)

            # Hitung sentimen di replies
            for r in c.get("replies", []) or []:
                total_replies += 1
                rcat = r.get("category", "NEUTRAL")
                if rcat in replies_counts:
                    replies_counts[rcat] += 1

        sorted_by_likes = sorted(comments, key=lambda x: x.get("like_count", 0), reverse=True)
        top_likes = [{
            "username": c["username"],
            "text": c["text"][:150],
            "like_count": c.get("like_count", 0),
            "category": c.get("category", ""),
            "sentiment": c.get("sentiment", ""),
        } for c in sorted_by_likes[:10] if c.get("like_count", 0) > 0]

        top_hate = sorted(
            [c for c in comments if c.get("is_hate_speech")],
            key=lambda x: x.get("like_count", 0), reverse=True
        )[:5]

        commenter_stats = Counter([c["username"] for c in comments])
        most_active = [{"username": u, "comment_count": n}
                       for u, n in commenter_stats.most_common(5) if n > 1]

        def pct(n):
            return round(n / total * 100, 1)

        def pct_replies(n):
            return round(n / total_replies * 100, 1) if total_replies > 0 else 0.0

        avg_confidence = round(sum(ml_confidences) / len(ml_confidences), 3) if ml_confidences else 0.0

        s = {
            "total_comments":       total,
            "total_replies":        total_replies,
            "hate_speech_count":    counts["HATE_SPEECH"], "hate_percentage":     pct(counts["HATE_SPEECH"]),
            "toxic_count":          counts["TOXIC"],       "toxic_percentage":    pct(counts["TOXIC"]),
            "positive_count":       counts["POSITIVE"],    "positive_percentage": pct(counts["POSITIVE"]),
            "negative_count":       counts["NEGATIVE"],    "negative_percentage": pct(counts["NEGATIVE"]),
            "neutral_count":        counts["NEUTRAL"],     "neutral_percentage":  pct(counts["NEUTRAL"]),
            "humor_count":          counts["HUMOR"],       "humor_percentage":    pct(counts["HUMOR"]),
            "sarcasm_count":        sarcasm_count,         "sarcasm_percentage":  pct(sarcasm_count),
            "wellwish_count":       wellwish_count,        "wellwish_percentage": pct(wellwish_count),
            "avg_ml_confidence":    avg_confidence,
            "decision_source_breakdown": dict(decision_sources),
            "hate_examples":        hate_ex[:10],
            "toxic_examples":       toxic_ex[:10],
            "top_liked":            top_likes,
            "top_hate_liked":       [{"username": c["username"], "text": c["text"][:150],
                                       "like_count": c.get("like_count", 0)} for c in top_hate],
            "most_active_users":    most_active,
            "replies_sentiment_breakdown": {
                "positive_count":   replies_counts["POSITIVE"],
                "negative_count":   replies_counts["NEGATIVE"],
                "neutral_count":    replies_counts["NEUTRAL"],
                "humor_count":      replies_counts["HUMOR"],
                "toxic_count":      replies_counts["TOXIC"],
                "hate_speech_count":replies_counts["HATE_SPEECH"],
                "positive_percentage":   pct_replies(replies_counts["POSITIVE"]),
                "negative_percentage":   pct_replies(replies_counts["NEGATIVE"]),
                "neutral_percentage":    pct_replies(replies_counts["NEUTRAL"]),
                "humor_percentage":      pct_replies(replies_counts["HUMOR"]),
                "toxic_percentage":      pct_replies(replies_counts["TOXIC"]),
                "hate_percentage":       pct_replies(replies_counts["HATE_SPEECH"]),
            },
        }

        if post_data:
            s["engagement"] = self._engagement_summary(post_data)

        # Print ringkasan
        print(Fore.CYAN + "\n" + "=" * 55)
        print(Fore.CYAN + "📊 RINGKASAN SENTIMEN (PARENT)")
        print(Fore.CYAN + "=" * 55)
        print(f"  💬 Total komentar     : {total}")
        if total_replies > 0:
            print(f"  💬 Total balasan      : {total_replies}")
        print(Fore.RED     + f"  🚨 Hate Speech        : {counts['HATE_SPEECH']:>4} ({pct(counts['HATE_SPEECH']):>5}%)")
        print(Fore.YELLOW  + f"  ⚠️  Toxic             : {counts['TOXIC']:>4} ({pct(counts['TOXIC']):>5}%)")
        print(Fore.GREEN   + f"  😊 Positif            : {counts['POSITIVE']:>4} ({pct(counts['POSITIVE']):>5}%)")
        print(Fore.MAGENTA + f"  😞 Negatif            : {counts['NEGATIVE']:>4} ({pct(counts['NEGATIVE']):>5}%)")
        print(Fore.WHITE   + f"  😐 Netral             : {counts['NEUTRAL']:>4} ({pct(counts['NEUTRAL']):>5}%)")
        print(Fore.CYAN    + f"  😂 Humor              : {counts['HUMOR']:>4} ({pct(counts['HUMOR']):>5}%)")

        if total_replies > 0:
            print(Fore.CYAN + "\n" + "=" * 55)
            print(Fore.CYAN + "📊 RINGKASAN SENTIMEN (BALASAN)")
            print(Fore.CYAN + "=" * 55)
            print(Fore.GREEN   + f"  😊 Positif            : {replies_counts['POSITIVE']:>4} ({pct_replies(replies_counts['POSITIVE']):>5}%)")
            print(Fore.MAGENTA + f"  😞 Negatif            : {replies_counts['NEGATIVE']:>4} ({pct_replies(replies_counts['NEGATIVE']):>5}%)")
            print(Fore.WHITE   + f"  😐 Netral             : {replies_counts['NEUTRAL']:>4} ({pct_replies(replies_counts['NEUTRAL']):>5}%)")
            print(Fore.CYAN    + f"  😂 Humor              : {replies_counts['HUMOR']:>4} ({pct_replies(replies_counts['HUMOR']):>5}%)")
            print(Fore.YELLOW  + f"  ⚠️  Toxic             : {replies_counts['TOXIC']:>4} ({pct_replies(replies_counts['TOXIC']):>5}%)")
            print(Fore.RED     + f"  🚨 Hate Speech        : {replies_counts['HATE_SPEECH']:>4} ({pct_replies(replies_counts['HATE_SPEECH']):>5}%)")

        print(Fore.CYAN    + f"\n  🎭 Sarkasme           : {sarcasm_count:>4} ({pct(sarcasm_count):>5}%)")
        print(Fore.CYAN    + f"  🙏 Wellwish           : {wellwish_count:>4} ({pct(wellwish_count):>5}%)")

        if avg_confidence > 0:
            print(Fore.CYAN + f"\n  🎯 Avg ML confidence  : {avg_confidence:.1%}")

        if post_data:
            print(Fore.CYAN + "\n" + "=" * 55)
            print(Fore.CYAN + "📈 RINGKASAN ENGAGEMENT")
            print(Fore.CYAN + "=" * 55)
            print(Fore.CYAN + f"  📌 Tipe konten  : {post_data.get('media_type','?')} "
                  f"({post_data.get('product_type','feed') or 'feed'})")
            print(Fore.CYAN + f"  ❤️  Likes       : {post_data.get('likes', 0):>10,}")
            if post_data.get("video_views", 0) > 0:
                print(Fore.CYAN + f"  👁️  Video views : {post_data.get('video_views', 0):>10,}")
            if post_data.get("saves_count", 0) > 0:
                print(Fore.CYAN + f"  🔖 Saves        : {post_data.get('saves_count', 0):>10,}")
            print(Fore.CYAN + f"  💬 Komentar     : {total:>10,}")
            if total_replies > 0:
                print(Fore.CYAN + f"  💬 Balasan      : {total_replies:>10,}")

        if hate_ex:
            print(Fore.RED + f"\n🚨 Contoh hate speech ({len(hate_ex)} total):")
            for he in hate_ex[:3]:
                print(f"   @{he['username']}: {he['text'][:70]}")

        return s

    def _engagement_summary(self, post_data: Dict) -> Dict:
        return {
            "media_type":        post_data.get("media_type", "UNKNOWN"),
            "product_type":      post_data.get("product_type", ""),
            "likes":             post_data.get("likes", 0),
            "video_views":       post_data.get("video_views", 0),
            "play_count":        post_data.get("play_count", 0),
            "shares_count":      post_data.get("shares_count", 0),
            "reshare_count":     post_data.get("reshare_count", 0),
            "direct_send_count": post_data.get("direct_send_count", 0),
            "saves_count":       post_data.get("saves_count", 0),
        }

    def save(self, data: Dict, filename: str) -> str:
        fp = os.path.join(OUTPUT_DIR, filename)
        with open(fp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(Fore.GREEN + f"\n💾 Tersimpan: {fp}")
        return fp

    # ── CLI ────────────────────────────────────────────────────

    def run(self):
        print(Fore.CYAN + "\n" + "=" * 70)
        print(Fore.CYAN + "  INSTAGRAM SCRAPER V16.2 PLAYWRIGHT + Sentiment V2")
        print(Fore.CYAN + "  GraphQL → CDP → REST  |  + REPLIES (child_comments)")
        print(Fore.CYAN + "=" * 70)

        while True:
            print(Fore.CYAN + "\n📋 MENU")
            print("  1. Scrape Single Post")
            print("  2. Scrape Multiple Posts (dari url.txt)")
            print("  3. Exit")

            choice = input(Fore.WHITE + "\nPilih [1-3]: ").strip()

            if choice == "1":
                url = input("\n🔗 URL: ").strip()
                if not url:
                    continue
                raw = input(f"Max komentar [{MAX_COMMENTS}]: ").strip()
                max_c = int(raw) if raw.isdigit() else MAX_COMMENTS

                raw_inc = input(f"Sertakan balasan? [Y/n]: ").strip().lower()
                inc_replies = raw_inc not in ("n", "no", "0")

                raw_mr = input(f"Max balasan per komentar [{MAX_REPLIES_PER_COMMENT}]: ").strip()
                max_r = int(raw_mr) if raw_mr.isdigit() else MAX_REPLIES_PER_COMMENT

                t_start = time.time()
                result = self.scrape_post_comments(url, max_c, inc_replies, max_r)
                t_elapsed = time.time() - t_start

                print(Fore.CYAN + f"\n⏱️  Waktu total: {t_elapsed:.1f} detik")
                total_items = result.get("comments_count", 0) + result.get("replies_count", 0)
                if total_items > 0:
                    print(Fore.CYAN + f"📈 Rate: {total_items / t_elapsed:.1f} item/detik")

                self.save(result, f"instagram_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")

            elif choice == "2":
                url_file = input("\n📄 File URL (default: url.txt): ").strip() or "url.txt"
                if not os.path.exists(url_file):
                    print(Fore.RED + f"❌ {url_file} tidak ditemukan")
                    continue

                with open(url_file, "r", encoding="utf-8") as f:
                    urls = [l.strip() for l in f if l.strip() and not l.startswith("#")]

                total = len(urls)
                raw = input(f"Max post (tersedia {total}, Enter=semua): ").strip()
                urls = urls[:int(raw)] if raw.isdigit() else urls

                raw = input(f"Max komentar per post [{MAX_COMMENTS}]: ").strip()
                max_c = int(raw) if raw.isdigit() else MAX_COMMENTS

                raw_inc = input(f"Sertakan balasan? [Y/n]: ").strip().lower()
                inc_replies = raw_inc not in ("n", "no", "0")

                raw_mr = input(f"Max balasan per komentar [{MAX_REPLIES_PER_COMMENT}]: ").strip()
                max_r = int(raw_mr) if raw_mr.isdigit() else MAX_REPLIES_PER_COMMENT

                t_total = time.time()
                for idx, url in enumerate(urls, 1):
                    print(Fore.CYAN + f"\n[{idx}/{len(urls)}]")
                    result = self.scrape_post_comments(url, max_c, inc_replies, max_r)
                    self.save(result, f"instagram_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{idx}.json")
                    if idx < len(urls):
                        d = DELAY_BETWEEN_REQUESTS + random.randint(3, 8)
                        print(Fore.YELLOW + f"⏳ Jeda {d}s antar post...")
                        time.sleep(d)

                print(Fore.GREEN + f"\n✅ Selesai! {len(urls)} post dalam {time.time()-t_total:.1f}s")

            elif choice == "3":
                print(Fore.CYAN + "\n👋 Bye!")
                break
            else:
                print(Fore.RED + "❌ Pilihan tidak valid")


if __name__ == "__main__":
    with InstagramScraperV16(sentiment_mode=SENTIMENT_MODE) as scraper:
        scraper.run()