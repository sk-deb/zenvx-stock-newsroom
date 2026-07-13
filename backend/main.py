"""
ZenvX StockMarket Newsroom — fast local stock/finance news aggregator.

Pulls headlines from major finance outlets (RSS or light scrape), detects
common tickers, clusters same-story coverage with Jaccard title similarity
(+ symbol boost), and serves a Ground-News-style live dashboard.

Run from project root:
  python -m uvicorn backend.main:app --host 0.0.0.0 --port 8421
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import feedparser
import requests
from apscheduler.schedulers.background import BackgroundScheduler
from bs4 import BeautifulSoup
from fastapi import Body, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend import market_data

BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR.parent / "frontend"
DB_PATH = BASE_DIR / "news.db"
CONFIG_PATH = BASE_DIR / "feeds_config.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/rss+xml, application/xml, text/xml, text/html, */*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.google.com/",
}

_WORD_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9.&'-]*")
_STOP = {
    "the", "a", "an", "and", "or", "of", "in", "on", "to", "for", "is", "are",
    "was", "were", "with", "from", "by", "at", "as", "this", "that", "it",
    "its", "be", "has", "have", "had", "will", "would", "could", "should",
    "news", "latest", "breaking", "video", "live", "watch", "read", "says",
    "after", "over", "into", "about", "more", "than", "vs", "amid",
}

# Common US + India tickers / company tokens for detection & grouping boost.
# Kept intentionally high-signal (avoid short ambiguous words like AI, IT, ON).
KNOWN_SYMBOLS = {
    # US mega / liquid
    "AAPL", "MSFT", "GOOGL", "GOOG", "AMZN", "META", "NVDA", "TSLA", "AMD",
    "INTC", "NFLX", "AVGO", "ORCL", "CRM", "ADBE", "CSCO", "QCOM", "TXN",
    "IBM", "NOW", "SHOP", "UBER", "LYFT", "ABNB", "COIN", "HOOD", "SQ",
    "PYPL", "V", "MA", "JPM", "BAC", "GS", "MS", "C", "WFC", "BLK", "SCHW",
    "XOM", "CVX", "COP", "BP", "SHEL", "TTE", "BA", "CAT", "GE", "HON",
    "UNH", "JNJ", "PFE", "MRK", "LLY", "ABBV", "BMY", "AMGN", "GILD",
    "KO", "PEP", "WMT", "COST", "TGT", "HD", "LOW", "NKE", "SBUX", "MCD",
    "DIS", "CMCSA", "T", "VZ", "TMUS", "SPOT", "SNAP", "PINS", "RBLX",
    "PLTR", "SNOW", "DDOG", "NET", "CRWD", "PANW", "ZS", "OKTA", "MDB",
    "SMCI", "ARM", "MU", "LRCX", "AMAT", "KLAC", "ASML", "TSM", "BABA",
    "JD", "PDD", "NIO", "XPEV", "LI", "RIVN", "LCID", "F", "GM",
    "SPY", "QQQ", "IWM", "DIA", "VOO", "VTI", "ARKK", "GLD", "SLV", "USO",
    "BTC", "ETH", "BITO",
    # India NSE/BSE style
    "RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK", "SBIN", "BHARTIARTL",
    "ITC", "HINDUNILVR", "LT", "KOTAKBANK", "AXISBANK", "BAJFINANCE",
    "MARUTI", "TATAMOTORS", "TATASTEEL", "JSWSTEEL", "HINDALCO", "ONGC",
    "NTPC", "POWERGRID", "COALINDIA", "ADANIENT", "ADANIPORTS", "ADANIGREEN",
    "WIPRO", "HCLTECH", "TECHM", "SUNPHARMA", "DRREDDY", "CIPLA", "DIVISLAB",
    "ASIANPAINT", "NESTLEIND", "TITAN", "ULTRACEMCO", "GRASIM", "M&M",
    "BAJAJFINSV", "BAJAJ-AUTO", "HEROMOTOCO", "EICHERMOT", "INDUSINDBK",
    "ZOMATO", "PAYTM", "NYKAA", "POLICYBZR", "IRCTC", "HAL", "BEL",
    "NIFTY", "SENSEX", "BANKNIFTY",
}

# Company name → primary symbol (for title mentions without ticker)
NAME_TO_SYMBOL = {
    "nvidia": "NVDA",
    "tesla": "TSLA",
    "apple": "AAPL",
    "microsoft": "MSFT",
    "amazon": "AMZN",
    "alphabet": "GOOGL",
    "google": "GOOGL",
    "meta": "META",
    "facebook": "META",
    "netflix": "NFLX",
    "amd": "AMD",
    "intel": "INTC",
    "reliance": "RELIANCE",
    "infosys": "INFY",
    "hdfc bank": "HDFCBANK",
    "icici bank": "ICICIBANK",
    "state bank": "SBIN",
    "sbi": "SBIN",
    "tcs": "TCS",
    "tata motors": "TATAMOTORS",
    "tata steel": "TATASTEEL",
    "adani": "ADANIENT",
    "bharti airtel": "BHARTIARTL",
    "airtel": "BHARTIARTL",
    "bitcoin": "BTC",
    "ethereum": "ETH",
    "goldman": "GS",
    "jpmorgan": "JPM",
    "jp morgan": "JPM",
    "morgan stanley": "MS",
    "citigroup": "C",
    "bank of america": "BAC",
    "walmart": "WMT",
    "costco": "COST",
    "berkshire": "BRK",
    "palantir": "PLTR",
    "coinbase": "COIN",
    "micron": "MU",
    "broadcom": "AVGO",
    "qualcomm": "QCOM",
    "oracle": "ORCL",
    "salesforce": "CRM",
}


def load_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


CONFIG = load_config()
SOURCES: dict[str, dict] = {
    s["id"]: s for s in CONFIG["sources"] if s.get("enabled", True)
}

SOURCE_HEALTH: dict[str, dict[str, Any]] = {
    sid: {
        "status": "pending",
        "last_success": None,
        "last_error": None,
        "article_count": 0,
        "working_url": None,
    }
    for sid in SOURCES
}

_fetch_lock = threading.Lock()
_last_full_sync: str | None = None
_last_fetch_duration_ms: int | None = None
scheduler = BackgroundScheduler(daemon=True)


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_db()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS articles (
            id TEXT PRIMARY KEY,
            source_id TEXT NOT NULL,
            title TEXT NOT NULL,
            link TEXT NOT NULL,
            summary TEXT,
            published_ts INTEGER,
            fetched_ts INTEGER NOT NULL,
            group_id TEXT,
            symbols TEXT
        )
        """
    )
    # Migrate older DBs
    cols = {r[1] for r in conn.execute("PRAGMA table_info(articles)").fetchall()}
    if "symbols" not in cols:
        conn.execute("ALTER TABLE articles ADD COLUMN symbols TEXT")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_articles_published ON articles(published_ts)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_articles_source ON articles(source_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_articles_group ON articles(group_id)"
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Symbol detection
# ---------------------------------------------------------------------------

_TICKER_RE = re.compile(
    r"(?<![A-Za-z0-9])\$?([A-Z]{1,5}(?:\.[A-Z]{1,2})?)(?![A-Za-z])"
)
_NSE_HINT = re.compile(
    r"\b([A-Z][A-Z0-9&-]{1,14})\b(?:\s*(?:Ltd|Limited|NSE|BSE|shares?))?",
    re.I,
)


def detect_symbols(title: str, summary: str = "") -> list[str]:
    text = f"{title} {summary or ''}"
    found: list[str] = []
    seen: set[str] = set()

    def add(sym: str) -> None:
        sym = sym.upper().strip(".,;:!?()[]\"'")
        if not sym or sym in seen:
            return
        # Reject pure numbers / very common English all-caps noise
        if sym in {
            "A", "I", "AM", "PM", "CEO", "CFO", "IPO", "ETF", "GDP", "CPI",
            "FED", "SEC", "USA", "US", "UK", "EU", "UN", "AI", "IT", "CEO",
            "CEO", "EPS", "PE", "FY", "Q1", "Q2", "Q3", "Q4", "YOY", "MOM",
            "CEO", "NEW", "FOR", "THE", "AND", "WITH", "FROM", "THIS",
        }:
            return
        if sym in KNOWN_SYMBOLS or (len(sym) >= 2 and sym in KNOWN_SYMBOLS):
            seen.add(sym)
            found.append(sym)

    # $TICKER or bare known tickers
    for m in _TICKER_RE.finditer(text):
        cand = m.group(1).upper()
        if cand in KNOWN_SYMBOLS:
            add(cand)

    lower = text.lower()
    for name, sym in NAME_TO_SYMBOL.items():
        if name in lower:
            add(sym)

    # Parenthetical tickers: (NVDA), (RELIANCE)
    for m in re.finditer(r"\(([A-Z]{1,12}(?:\.[A-Z]{1,2})?)\)", text):
        if m.group(1).upper() in KNOWN_SYMBOLS:
            add(m.group(1))

    return found[:12]


# ---------------------------------------------------------------------------
# Fetch helpers
# ---------------------------------------------------------------------------

def article_id(link: str) -> str:
    return hashlib.sha256(link.encode("utf-8")).hexdigest()[:20]


def parse_published(entry: dict) -> int:
    for key in ("published_parsed", "updated_parsed"):
        val = entry.get(key)
        if val:
            try:
                return int(time.mktime(val))
            except (OverflowError, ValueError, TypeError):
                pass
    return int(time.time())


def clean_title(title: str) -> str:
    if not title:
        return ""
    title = BeautifulSoup(title, "html.parser").get_text(" ", strip=True)
    return re.sub(r"\s+", " ", title).strip()


def fetch_url(url: str, timeout: int = 14) -> requests.Response:
    resp = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
    resp.raise_for_status()
    return resp


def fetch_rss_source(source: dict) -> tuple[list[dict], str]:
    errors: list[str] = []
    for url in source.get("rss_urls") or []:
        try:
            resp = fetch_url(url)
            parsed = feedparser.parse(resp.content)
            entries = list(parsed.entries or [])
            if not entries:
                msg = f"{url}: HTTP {resp.status_code}, 0 entries"
                if getattr(parsed, "bozo", False) and getattr(parsed, "bozo_exception", None):
                    msg += f" (parse: {parsed.bozo_exception})"
                errors.append(msg)
                continue

            articles = []
            for entry in entries:
                title = clean_title(entry.get("title") or "")
                link = (entry.get("link") or "").strip()
                if not title or not link:
                    continue
                summary = clean_title(
                    entry.get("summary") or entry.get("description") or ""
                )
                if len(summary) > 360:
                    summary = summary[:357] + "..."
                symbols = detect_symbols(title, summary)
                articles.append(
                    {
                        "id": article_id(link),
                        "source_id": source["id"],
                        "title": title,
                        "link": link,
                        "summary": summary,
                        "published_ts": parse_published(entry),
                        "symbols": symbols,
                    }
                )
            if articles:
                return articles, url
            errors.append(f"{url}: entries present but no valid title/link pairs")
        except requests.HTTPError as e:
            status = e.response.status_code if e.response is not None else "?"
            errors.append(f"{url}: HTTP {status} — {e}")
        except requests.RequestException as e:
            errors.append(f"{url}: {type(e).__name__}: {e}")
        except Exception as e:
            errors.append(f"{url}: {type(e).__name__}: {e}")

    raise RuntimeError("; ".join(errors) if errors else "no rss_urls configured")


def scrape_generic(source: dict) -> tuple[list[dict], str]:
    """Lightweight headline scrape: title + link (+ optional date from URL)."""
    errors: list[str] = []
    now = int(time.time())
    for page_url in source.get("scrape_urls") or [source.get("homepage", "")]:
        if not page_url:
            continue
        try:
            resp = fetch_url(page_url)
            soup = BeautifulSoup(resp.content, "lxml")
            seen: set[str] = set()
            articles: list[dict] = []

            # Prefer semantic article title links
            candidates = []
            for sel in (
                "h2 a",
                "h3 a",
                ".entry-title a",
                "a.entry-title",
                "article h2 a",
                "article h3 a",
            ):
                candidates.extend(soup.select(sel))

            if not candidates:
                candidates = soup.find_all("a", href=True)

            for a in candidates:
                href = a.get("href") or ""
                if not href or href.startswith("#"):
                    continue
                link = urljoin(page_url, href)
                if link in seen:
                    continue
                title = clean_title(a.get_text())
                if len(title) < 28:
                    continue
                # Skip pure nav / utility
                low = title.lower()
                if low in {"read more", "subscribe", "sign in", "home", "markets"}:
                    continue
                # Prefer article-like paths
                path = link.lower()
                if any(
                    x in path
                    for x in (
                        "/tag/",
                        "/author/",
                        "/category/",
                        "javascript:",
                        "mailto:",
                        "/login",
                        "/subscribe",
                    )
                ):
                    continue

                seen.add(link)
                pub = now
                m = re.search(r"/(20\d{2})/(\d{2})/(\d{2})/", link)
                if m:
                    try:
                        pub = int(
                            datetime(
                                int(m.group(1)),
                                int(m.group(2)),
                                int(m.group(3)),
                                tzinfo=timezone.utc,
                            ).timestamp()
                        )
                    except ValueError:
                        pass
                symbols = detect_symbols(title)
                articles.append(
                    {
                        "id": article_id(link),
                        "source_id": source["id"],
                        "title": title,
                        "link": link,
                        "summary": "",
                        "published_ts": pub,
                        "symbols": symbols,
                    }
                )
                if len(articles) >= 60:
                    break

            if articles:
                return articles, page_url
            errors.append(f"{page_url}: scraped 0 headlines")
        except requests.HTTPError as e:
            status = e.response.status_code if e.response is not None else "?"
            errors.append(f"{page_url}: HTTP {status} — {e}")
        except requests.RequestException as e:
            errors.append(f"{page_url}: {type(e).__name__}: {e}")
        except Exception as e:
            errors.append(f"{page_url}: {type(e).__name__}: {e}")

    raise RuntimeError("; ".join(errors) if errors else "no scrape_urls configured")


def fetch_source(source: dict) -> tuple[list[dict], str]:
    mode = (source.get("fetch_mode") or "rss").lower()
    if mode in ("disabled", "skip"):
        raise RuntimeError(
            source.get("notes") or "source disabled in feeds_config.json"
        )
    if mode == "scrape":
        return scrape_generic(source)
    if not source.get("rss_urls"):
        if source.get("scrape_urls"):
            return scrape_generic(source)
        raise RuntimeError(
            source.get("notes") or "no RSS/scrape URLs configured"
        )
    return fetch_rss_source(source)


# ---------------------------------------------------------------------------
# Story grouping
# ---------------------------------------------------------------------------

def normalize_words(title: str) -> frozenset[str]:
    words = _WORD_RE.findall(title.lower())
    return frozenset(
        w.strip(".'-") for w in words if len(w) > 2 and w.lower() not in _STOP
    )


def jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    if inter == 0:
        return 0.0
    return inter / len(a | b)


class UnionFind:
    def __init__(self, n: int):
        self.parent = list(range(n))
        self.rank = [0] * n

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return
        if self.rank[ra] < self.rank[rb]:
            self.parent[ra] = rb
        elif self.rank[ra] > self.rank[rb]:
            self.parent[rb] = ra
        else:
            self.parent[rb] = ra
            self.rank[ra] += 1


def regroup_articles(window_hours: int | None = None) -> None:
    cfg = load_config()
    hours = window_hours or int(cfg.get("story_group_window_hours", 24))
    threshold = float(cfg.get("similarity_threshold", 0.36))
    symbol_boost = float(cfg.get("symbol_boost", 0.12))
    cutoff = int(time.time()) - hours * 3600

    conn = get_db()
    rows = conn.execute(
        """
        SELECT id, source_id, title, published_ts, symbols
        FROM articles
        WHERE published_ts >= ?
        ORDER BY published_ts DESC
        """,
        (cutoff,),
    ).fetchall()

    n = len(rows)
    if n == 0:
        conn.close()
        return

    word_sets = [normalize_words(r["title"]) for r in rows]
    sym_sets = []
    for r in rows:
        raw = r["symbols"] or ""
        sym_sets.append({s for s in raw.split(",") if s})

    uf = UnionFind(n)
    for i in range(n):
        for j in range(i + 1, n):
            sim = jaccard(word_sets[i], word_sets[j])
            shared = sym_sets[i] & sym_sets[j]
            if shared:
                sim = min(1.0, sim + symbol_boost)
            # Shared symbols alone can merge if titles have mild overlap
            if shared and sim >= max(0.22, threshold - 0.1):
                uf.union(i, j)
            elif sim >= threshold:
                uf.union(i, j)

    groups: dict[int, str] = {}
    for i in range(n):
        root = uf.find(i)
        if root not in groups:
            groups[root] = f"g_{rows[root]['id']}"
        conn.execute(
            "UPDATE articles SET group_id = ? WHERE id = ?",
            (groups[root], rows[i]["id"]),
        )

    conn.execute(
        "UPDATE articles SET group_id = NULL WHERE published_ts < ?",
        (cutoff,),
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Fetch cycle (parallel sources for speed)
# ---------------------------------------------------------------------------

def upsert_articles(articles: list[dict]) -> int:
    if not articles:
        return 0
    now = int(time.time())
    conn = get_db()
    for a in articles:
        sym_str = ",".join(a.get("symbols") or [])
        conn.execute(
            """
            INSERT INTO articles
                (id, source_id, title, link, summary, published_ts, fetched_ts, group_id, symbols)
            VALUES (?, ?, ?, ?, ?, ?, ?, NULL, ?)
            ON CONFLICT(id) DO UPDATE SET
                title = excluded.title,
                summary = excluded.summary,
                published_ts = excluded.published_ts,
                fetched_ts = excluded.fetched_ts,
                symbols = excluded.symbols
            """,
            (
                a["id"],
                a["source_id"],
                a["title"],
                a["link"],
                a.get("summary") or "",
                a["published_ts"],
                now,
                sym_str,
            ),
        )
    conn.commit()
    sid = articles[0]["source_id"]
    total = conn.execute(
        "SELECT COUNT(*) AS c FROM articles WHERE source_id = ?", (sid,)
    ).fetchone()["c"]
    conn.close()
    return total


def _fetch_one(source: dict) -> tuple[str, dict]:
    sid = source["id"]
    try:
        articles, working_url = fetch_source(source)
        total = upsert_articles(articles)
        return sid, {
            "status": "ok",
            "last_success": datetime.now(timezone.utc).isoformat(),
            "last_error": None,
            "article_count": total,
            "working_url": working_url,
            "last_batch": len(articles),
        }
    except Exception as e:
        prev = SOURCE_HEALTH.get(sid, {})
        return sid, {
            "status": "error",
            "last_success": prev.get("last_success"),
            "last_error": f"{type(e).__name__}: {e}",
            "article_count": prev.get("article_count", 0),
            "working_url": prev.get("working_url"),
        }


def fetch_all_sources() -> None:
    global _last_full_sync, _last_fetch_duration_ms, CONFIG, SOURCES
    if not _fetch_lock.acquire(blocking=False):
        return
    t0 = time.perf_counter()
    try:
        CONFIG = load_config()
        SOURCES = {s["id"]: s for s in CONFIG["sources"] if s.get("enabled", True)}
        for sid in SOURCES:
            if sid not in SOURCE_HEALTH:
                SOURCE_HEALTH[sid] = {
                    "status": "pending",
                    "last_success": None,
                    "last_error": None,
                    "article_count": 0,
                    "working_url": None,
                }

        # Parallel fetch — finance sites are I/O bound
        max_workers = min(8, max(2, len(SOURCES)))
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futs = [pool.submit(_fetch_one, src) for src in SOURCES.values()]
            for fut in as_completed(futs):
                sid, health = fut.result()
                SOURCE_HEALTH[sid] = health

        # Mark disabled sources from full config for UI
        for s in CONFIG["sources"]:
            if not s.get("enabled", True):
                SOURCE_HEALTH[s["id"]] = {
                    "status": "disabled",
                    "last_success": SOURCE_HEALTH.get(s["id"], {}).get("last_success"),
                    "last_error": s.get("notes") or "disabled in feeds_config.json",
                    "article_count": SOURCE_HEALTH.get(s["id"], {}).get("article_count", 0),
                    "working_url": None,
                }

        try:
            regroup_articles()
        except Exception as e:
            print(f"[regroup] error: {type(e).__name__}: {e}")

        _last_full_sync = datetime.now(timezone.utc).isoformat()
        _last_fetch_duration_ms = int((time.perf_counter() - t0) * 1000)
    finally:
        _fetch_lock.release()


def start_background_fetch() -> None:
    threading.Thread(
        target=fetch_all_sources, daemon=True, name="initial-fetch"
    ).start()


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    minutes = max(1, int(CONFIG.get("refresh_interval_minutes", 5)))
    # Support sub-minute via seconds if < 1 documented as minutes only
    scheduler.add_job(
        fetch_all_sources,
        "interval",
        minutes=minutes,
        id="feed_refresh",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    start_background_fetch()
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(
    title="ZenvX StockMarket Newsroom",
    version="1.0.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/sources")
def api_sources():
    cfg = load_config()
    out = []
    for s in cfg["sources"]:
        sid = s["id"]
        health = SOURCE_HEALTH.get(
            sid,
            {
                "status": "pending" if s.get("enabled", True) else "disabled",
                "last_success": None,
                "last_error": None if s.get("enabled", True) else s.get("notes"),
                "article_count": 0,
                "working_url": None,
            },
        )
        if not s.get("enabled", True) and health.get("status") != "disabled":
            health = {
                **health,
                "status": "disabled",
                "last_error": s.get("notes") or "disabled in feeds_config.json",
            }
        out.append(
            {
                "id": sid,
                "name": s["name"],
                "color": s.get("color", "#888"),
                "publisher": s.get("publisher", ""),
                "type": s.get("type", ""),
                "homepage": s.get("homepage", ""),
                "fetch_mode": s.get("fetch_mode", "rss"),
                "notes": s.get("notes"),
                "enabled": s.get("enabled", True),
                "status": health.get("status", "pending"),
                "last_success": health.get("last_success"),
                "last_error": health.get("last_error"),
                "article_count": health.get("article_count", 0),
                "working_url": health.get("working_url"),
                "last_batch": health.get("last_batch"),
            }
        )
    enabled = [s for s in out if s.get("enabled")]
    ok = sum(1 for s in enabled if s["status"] == "ok")
    return {
        "sources": out,
        "last_full_sync": _last_full_sync,
        "last_fetch_duration_ms": _last_fetch_duration_ms,
        "refresh_interval_minutes": cfg.get("refresh_interval_minutes", 5),
        "similarity_threshold": cfg.get("similarity_threshold", 0.36),
        "story_group_window_hours": cfg.get("story_group_window_hours", 24),
        "sources_ok": ok,
        "sources_enabled": len(enabled),
    }


@app.get("/api/stories")
def api_stories(
    hours: int = Query(24, ge=1, le=168),
    limit: int = Query(100, ge=1, le=400),
    source: str | None = Query(None),
    symbol: str | None = Query(None, description="Filter by ticker e.g. NVDA"),
):
    cfg = load_config()
    source_map = {s["id"]: s for s in cfg["sources"]}
    allowed = None
    if source:
        allowed = {x.strip() for x in source.split(",") if x.strip()}
    want_sym = symbol.upper().strip() if symbol else None

    cutoff = int(time.time()) - hours * 3600
    conn = get_db()
    rows = conn.execute(
        """
        SELECT id, source_id, title, link, summary, published_ts, group_id, symbols
        FROM articles
        WHERE published_ts >= ?
        ORDER BY published_ts DESC
        """,
        (cutoff,),
    ).fetchall()
    conn.close()

    buckets: dict[str, list[dict]] = {}
    for r in rows:
        if allowed and r["source_id"] not in allowed:
            continue
        artsyms = [x for x in (r["symbols"] or "").split(",") if x]
        if want_sym and want_sym not in artsyms:
            continue
        gid = r["group_id"] or f"solo_{r['id']}"
        item = dict(r)
        item["symbols_list"] = artsyms
        buckets.setdefault(gid, []).append(item)

    stories = []
    for gid, arts in buckets.items():
        arts.sort(key=lambda a: a["published_ts"] or 0, reverse=True)
        sources_in = []
        seen_src = set()
        all_syms: set[str] = set()
        for a in arts:
            all_syms.update(a.get("symbols_list") or [])
            sid = a["source_id"]
            if sid in seen_src:
                continue
            seen_src.add(sid)
            meta = source_map.get(sid, {})
            sources_in.append(
                {
                    "id": sid,
                    "name": meta.get("name", sid),
                    "color": meta.get("color", "#888"),
                    "publisher": meta.get("publisher", ""),
                    "type": meta.get("type", ""),
                    "title": a["title"],
                    "link": a["link"],
                    "published_ts": a["published_ts"],
                }
            )

        latest = arts[0]
        stories.append(
            {
                "group_id": gid,
                "title": latest["title"],
                "link": latest["link"],
                "summary": latest.get("summary") or "",
                "published_ts": latest["published_ts"],
                "outlet_count": len(sources_in),
                "article_count": len(arts),
                "sources": sources_in,
                "symbols": sorted(all_syms),
                "primary_source_id": latest["source_id"],
            }
        )

    stories.sort(
        key=lambda s: (s["outlet_count"], s["published_ts"] or 0),
        reverse=True,
    )
    return {
        "stories": stories[:limit],
        "total": len(stories),
        "hours": hours,
        "last_full_sync": _last_full_sync,
        "last_fetch_duration_ms": _last_fetch_duration_ms,
    }


@app.get("/api/pulse")
def api_pulse(hours: int = Query(24, ge=1, le=72)):
    """Lightweight market pulse: top symbols by mention count."""
    cutoff = int(time.time()) - hours * 3600
    conn = get_db()
    rows = conn.execute(
        "SELECT symbols FROM articles WHERE published_ts >= ? AND symbols != '' AND symbols IS NOT NULL",
        (cutoff,),
    ).fetchall()
    ok = sum(1 for h in SOURCE_HEALTH.values() if h.get("status") == "ok")
    conn.close()
    counts: dict[str, int] = {}
    for r in rows:
        for s in (r["symbols"] or "").split(","):
            if s:
                counts[s] = counts.get(s, 0) + 1
    top = sorted(counts.items(), key=lambda x: -x[1])[:12]
    return {
        "top_symbols": [{"symbol": s, "mentions": n} for s, n in top],
        "sources_ok": ok,
        "last_full_sync": _last_full_sync,
        "last_fetch_duration_ms": _last_fetch_duration_ms,
    }


@app.post("/api/refresh")
def api_refresh():
    if _fetch_lock.locked():
        return {
            "status": "already_running",
            "last_full_sync": _last_full_sync,
            "last_fetch_duration_ms": _last_fetch_duration_ms,
        }
    threading.Thread(
        target=fetch_all_sources, daemon=True, name="manual-refresh"
    ).start()
    return {
        "status": "started",
        "last_full_sync": _last_full_sync,
        "last_fetch_duration_ms": _last_fetch_duration_ms,
    }


@app.get("/api/health")
def api_health():
    ok = sum(1 for h in SOURCE_HEALTH.values() if h.get("status") == "ok")
    return {
        "ok": True,
        "sources_ok": ok,
        "sources_total": len(SOURCES),
        "last_full_sync": _last_full_sync,
        "last_fetch_duration_ms": _last_fetch_duration_ms,
        "db": str(DB_PATH),
    }


# ---------------------------------------------------------------------------
# Prices, charts, heuristic bias, TradingView helpers
# ---------------------------------------------------------------------------

@app.get("/api/chart/{symbol}")
def api_chart(
    symbol: str,
    range: str = Query("3mo", description="1d,5d,1mo,3mo,6mo,1y,5y"),
    interval: str = Query("1d", description="1m,5m,15m,1h,1d,1wk"),
):
    try:
        return market_data.fetch_chart(symbol, range_=range, interval=interval)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"{type(e).__name__}: {e}") from e


@app.get("/api/analysis/{symbol}")
def api_analysis(
    symbol: str,
    range: str = Query("3mo"),
    interval: str = Query("1d"),
):
    try:
        return market_data.get_analysis(symbol, range_=range, interval=interval)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"{type(e).__name__}: {e}") from e


@app.get("/api/market-overview")
def api_market_overview(
    symbols: str | None = Query(
        None,
        description="Comma-separated tickers; default watchlist if omitted",
    ),
):
    syms = None
    if symbols:
        syms = [x.strip().upper() for x in symbols.split(",") if x.strip()]
    return market_data.market_overview(syms)


@app.get("/api/tradingview/resolve")
def api_tv_resolve(symbol: str = Query(..., min_length=1)):
    s = symbol.strip().upper()
    return {
        "symbol": s,
        "yahoo_symbol": market_data.resolve_yahoo(s),
        "tradingview_symbol": market_data.resolve_tradingview(s),
        "tradingview_url": (
            f"https://www.tradingview.com/chart/?symbol="
            f"{market_data.resolve_tradingview(s)}"
        ),
        "widget_symbol": market_data.resolve_tradingview(s),
    }


@app.post("/api/tradingview/watchlist")
def api_tv_watchlist(payload: dict = Body(...)):
    """
    Accept a user watchlist (symbols pasted from TradingView or typed).
    Returns resolved Yahoo + TradingView ids and a mini overview.
    Stored client-side; this endpoint only resolves/enriches.
    """
    raw = payload.get("symbols") or []
    if isinstance(raw, str):
        raw = re.split(r"[\s,;]+", raw)
    symbols = []
    for item in raw:
        s = str(item).strip()
        if not s:
            continue
        # TradingView style EXCHANGE:SYMBOL -> bare symbol for Yahoo map
        if ":" in s:
            bare = s.split(":")[-1].replace(".P", "").upper()
            # keep original for TV
            symbols.append({"input": s, "bare": bare.replace("-", "") if bare.count("-") == 0 else bare})
            # special BRK.B
            bare_clean = s.split(":")[-1].upper().replace(".", "-")
            symbols[-1]["bare"] = bare_clean if bare_clean.startswith("BRK") else s.split(":")[-1].upper()
        else:
            symbols.append({"input": s, "bare": s.upper()})

    resolved = []
    for item in symbols[:40]:
        bare = item["bare"]
        # strip .NS if user pasted
        bare = bare.replace(".NS", "").replace(".BO", "")
        try:
            tv = (
                item["input"]
                if ":" in item["input"]
                else market_data.resolve_tradingview(bare)
            )
            resolved.append(
                {
                    "symbol": bare,
                    "tradingview_symbol": tv,
                    "yahoo_symbol": market_data.resolve_yahoo(bare),
                    "tradingview_url": f"https://www.tradingview.com/chart/?symbol={tv}",
                }
            )
        except Exception as e:
            resolved.append(
                {
                    "symbol": bare,
                    "error": f"{type(e).__name__}: {e}",
                }
            )

    overview = market_data.market_overview(
        [r["symbol"] for r in resolved if "error" not in r][:12]
    )
    return {
        "resolved": resolved,
        "overview": overview,
        "note": (
            "TradingView has no free personal-account API. "
            "Paste symbols from your TV watchlist here; we resolve them to free "
            "price charts + embed the official TradingView widget locally."
        ),
    }


if FRONTEND_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


@app.get("/")
def index():
    index_path = FRONTEND_DIR / "index.html"
    if not index_path.exists():
        return {"error": "frontend/index.html missing"}
    return FileResponse(index_path)
