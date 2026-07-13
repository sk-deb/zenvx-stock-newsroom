"""
Free market data + simple heuristic bias (no API keys).

Price history via Yahoo Finance public chart endpoints.
Bias is rule-based technical heuristics — NOT financial advice.
"""

from __future__ import annotations

import time
from typing import Any

import requests

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json,text/plain,*/*",
}

# Cache: key -> (expires_ts, payload)
_CACHE: dict[str, tuple[float, Any]] = {}
_CACHE_TTL = 90  # seconds

# Display ticker -> Yahoo Finance symbol
YAHOO_MAP = {
    "RELIANCE": "RELIANCE.NS",
    "TCS": "TCS.NS",
    "INFY": "INFY.NS",
    "HDFCBANK": "HDFCBANK.NS",
    "ICICIBANK": "ICICIBANK.NS",
    "SBIN": "SBIN.NS",
    "BHARTIARTL": "BHARTIARTL.NS",
    "ITC": "ITC.NS",
    "HINDUNILVR": "HINDUNILVR.NS",
    "LT": "LT.NS",
    "KOTAKBANK": "KOTAKBANK.NS",
    "AXISBANK": "AXISBANK.NS",
    "BAJFINANCE": "BAJFINANCE.NS",
    "MARUTI": "MARUTI.NS",
    "TATAMOTORS": "TATAMOTORS.NS",
    "TATASTEEL": "TATASTEEL.NS",
    "JSWSTEEL": "JSWSTEEL.NS",
    "HINDALCO": "HINDALCO.NS",
    "ONGC": "ONGC.NS",
    "NTPC": "NTPC.NS",
    "POWERGRID": "POWERGRID.NS",
    "COALINDIA": "COALINDIA.NS",
    "ADANIENT": "ADANIENT.NS",
    "ADANIPORTS": "ADANIPORTS.NS",
    "ADANIGREEN": "ADANIGREEN.NS",
    "WIPRO": "WIPRO.NS",
    "HCLTECH": "HCLTECH.NS",
    "TECHM": "TECHM.NS",
    "SUNPHARMA": "SUNPHARMA.NS",
    "DRREDDY": "DRREDDY.NS",
    "CIPLA": "CIPLA.NS",
    "DIVISLAB": "DIVISLAB.NS",
    "ASIANPAINT": "ASIANPAINT.NS",
    "NESTLEIND": "NESTLEIND.NS",
    "TITAN": "TITAN.NS",
    "ULTRACEMCO": "ULTRACEMCO.NS",
    "GRASIM": "GRASIM.NS",
    "M&M": "M&M.NS",
    "BAJAJFINSV": "BAJAJFINSV.NS",
    "BAJAJ-AUTO": "BAJAJ-AUTO.NS",
    "HEROMOTOCO": "HEROMOTOCO.NS",
    "EICHERMOT": "EICHERMOT.NS",
    "INDUSINDBK": "INDUSINDBK.NS",
    "ZOMATO": "ZOMATO.NS",
    "PAYTM": "PAYTM.NS",
    "NYKAA": "NYKAA.NS",
    "POLICYBZR": "POLICYBZR.NS",
    "IRCTC": "IRCTC.NS",
    "HAL": "HAL.NS",
    "BEL": "BEL.NS",
    "NIFTY": "^NSEI",
    "SENSEX": "^BSESN",
    "BANKNIFTY": "^NSEBANK",
    "BTC": "BTC-USD",
    "ETH": "ETH-USD",
    "BRK": "BRK-B",
}

# TradingView symbol prefix for deep links / widgets
TV_MAP = {
    "RELIANCE": "NSE:RELIANCE",
    "TCS": "NSE:TCS",
    "INFY": "NSE:INFY",
    "HDFCBANK": "NSE:HDFCBANK",
    "ICICIBANK": "NSE:ICICIBANK",
    "SBIN": "NSE:SBIN",
    "BHARTIARTL": "NSE:BHARTIARTL",
    "ITC": "NSE:ITC",
    "NTPC": "NSE:NTPC",
    "ADANIENT": "NSE:ADANIENT",
    "TATAMOTORS": "NSE:TATAMOTORS",
    "TATASTEEL": "NSE:TATASTEEL",
    "NIFTY": "NSE:NIFTY",
    "SENSEX": "BSE:SENSEX",
    "BANKNIFTY": "NSE:BANKNIFTY",
    "BTC": "BITSTAMP:BTCUSD",
    "ETH": "BITSTAMP:ETHUSD",
    "SPY": "AMEX:SPY",
    "QQQ": "NASDAQ:QQQ",
    "AAPL": "NASDAQ:AAPL",
    "MSFT": "NASDAQ:MSFT",
    "NVDA": "NASDAQ:NVDA",
    "TSLA": "NASDAQ:TSLA",
    "META": "NASDAQ:META",
    "GOOGL": "NASDAQ:GOOGL",
    "AMZN": "NASDAQ:AMZN",
    "AMD": "NASDAQ:AMD",
    "GS": "NYSE:GS",
    "JPM": "NYSE:JPM",
    "BRK": "NYSE:BRK.B",
}

DEFAULT_WATCH = [
    "SPY", "QQQ", "NVDA", "AAPL", "TSLA", "MSFT",
    "RELIANCE", "TCS", "HDFCBANK", "NIFTY", "BTC",
]


def resolve_yahoo(symbol: str) -> str:
    s = (symbol or "").strip().upper()
    if not s:
        raise ValueError("empty symbol")
    # Already a Yahoo-style symbol
    if s.startswith("^") or "." in s or "-" in s:
        return s
    return YAHOO_MAP.get(s, s)


def resolve_tradingview(symbol: str) -> str:
    s = (symbol or "").strip().upper()
    if ":" in (symbol or ""):
        return symbol.strip()
    if s in TV_MAP:
        return TV_MAP[s]
    # India heuristic for known mapped NSE names already handled
    if s in YAHOO_MAP and YAHOO_MAP[s].endswith(".NS"):
        return f"NSE:{s}"
    # Default US stock exchange guess for free widget
    return f"NASDAQ:{s}"


def _cache_get(key: str):
    hit = _CACHE.get(key)
    if not hit:
        return None
    exp, val = hit
    if time.time() > exp:
        _CACHE.pop(key, None)
        return None
    return val


def _cache_set(key: str, val: Any, ttl: int = _CACHE_TTL) -> None:
    _CACHE[key] = (time.time() + ttl, val)


def fetch_chart(
    symbol: str,
    range_: str = "3mo",
    interval: str = "1d",
) -> dict:
    """Fetch OHLCV from Yahoo chart API."""
    display = symbol.strip().upper()
    yahoo = resolve_yahoo(display)
    cache_key = f"chart:{yahoo}:{range_}:{interval}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{yahoo}"
    params = {
        "range": range_,
        "interval": interval,
        "includePrePost": "false",
        "events": "div,splits",
    }
    resp = requests.get(url, headers=HEADERS, params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    result = (data.get("chart") or {}).get("result")
    if not result:
        err = (data.get("chart") or {}).get("error") or "no chart data"
        raise RuntimeError(f"{yahoo}: {err}")

    r0 = result[0]
    meta = r0.get("meta") or {}
    ts = r0.get("timestamp") or []
    quote = (r0.get("indicators") or {}).get("quote") or [{}]
    q0 = quote[0] if quote else {}
    opens = q0.get("open") or []
    highs = q0.get("high") or []
    lows = q0.get("low") or []
    closes = q0.get("close") or []
    volumes = q0.get("volume") or []

    points = []
    for i, t in enumerate(ts):
        c = closes[i] if i < len(closes) else None
        if c is None:
            continue
        points.append(
            {
                "t": t,
                "o": opens[i] if i < len(opens) else None,
                "h": highs[i] if i < len(highs) else None,
                "l": lows[i] if i < len(lows) else None,
                "c": c,
                "v": volumes[i] if i < len(volumes) else None,
            }
        )

    if not points:
        raise RuntimeError(f"{yahoo}: empty price series")

    out = {
        "symbol": display,
        "yahoo_symbol": yahoo,
        "tradingview_symbol": resolve_tradingview(display),
        "currency": meta.get("currency"),
        "exchange": meta.get("exchangeName"),
        "timezone": meta.get("timezone"),
        "instrument": meta.get("instrumentType") or meta.get("longName") or display,
        "regular_market_price": meta.get("regularMarketPrice"),
        "previous_close": meta.get("chartPreviousClose") or meta.get("previousClose"),
        "range": range_,
        "interval": interval,
        "points": points,
    }
    _cache_set(cache_key, out)
    return out


def _sma(values: list[float], n: int) -> float | None:
    if len(values) < n:
        return None
    window = values[-n:]
    return sum(window) / n


def _rsi(closes: list[float], period: int = 14) -> float | None:
    if len(closes) < period + 1:
        return None
    gains = []
    losses = []
    for i in range(-period, 0):
        delta = closes[i] - closes[i - 1]
        gains.append(max(delta, 0.0))
        losses.append(max(-delta, 0.0))
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def analyze_series(closes: list[float], volumes: list[float | None] | None = None) -> dict:
    """Rule-based short-term bias from price series."""
    if len(closes) < 5:
        return {
            "bias": "neutral",
            "score": 0,
            "confidence": "low",
            "summary": "Not enough price history to form a view.",
            "signals": [],
        }

    last = closes[-1]
    prev = closes[-2]
    day_chg = ((last - prev) / prev) * 100 if prev else 0.0

    ret_5 = ((last - closes[-6]) / closes[-6] * 100) if len(closes) >= 6 else None
    ret_20 = ((last - closes[-21]) / closes[-21] * 100) if len(closes) >= 21 else None

    sma10 = _sma(closes, 10)
    sma20 = _sma(closes, 20)
    sma50 = _sma(closes, min(50, len(closes)))
    rsi = _rsi(closes, 14)

    score = 0.0
    signals: list[str] = []

    if ret_5 is not None:
        if ret_5 > 2:
            score += 1.2
            signals.append(f"5-day return +{ret_5:.1f}% (momentum up)")
        elif ret_5 < -2:
            score -= 1.2
            signals.append(f"5-day return {ret_5:.1f}% (momentum down)")
        else:
            signals.append(f"5-day return {ret_5:+.1f}% (range-bound short term)")

    if ret_20 is not None:
        if ret_20 > 4:
            score += 1.0
            signals.append(f"20-day return +{ret_20:.1f}%")
        elif ret_20 < -4:
            score -= 1.0
            signals.append(f"20-day return {ret_20:.1f}%")

    if sma20 is not None:
        dist = ((last - sma20) / sma20) * 100
        if last > sma20:
            score += 0.9
            signals.append(f"Price above 20-day SMA ({dist:+.1f}%)")
        else:
            score -= 0.9
            signals.append(f"Price below 20-day SMA ({dist:+.1f}%)")

    if sma10 is not None and sma20 is not None:
        if sma10 > sma20:
            score += 0.7
            signals.append("10-day SMA above 20-day SMA (short-term uptrend structure)")
        else:
            score -= 0.7
            signals.append("10-day SMA below 20-day SMA (short-term downtrend structure)")

    if sma50 is not None and len(closes) >= 50:
        if last > sma50:
            score += 0.6
            signals.append("Price above 50-day SMA (medium-term support)")
        else:
            score -= 0.6
            signals.append("Price below 50-day SMA (medium-term pressure)")

    if rsi is not None:
        if rsi >= 70:
            score -= 0.5
            signals.append(f"RSI ~{rsi:.0f} (overbought — pullback risk)")
        elif rsi <= 30:
            score += 0.5
            signals.append(f"RSI ~{rsi:.0f} (oversold — bounce possible)")
        else:
            signals.append(f"RSI ~{rsi:.0f} (mid-range)")

    # Volume spike on last bar
    if volumes:
        vols = [v for v in volumes if v]
        if len(vols) >= 10:
            avg_v = sum(vols[-11:-1]) / 10
            last_v = vols[-1]
            if avg_v > 0 and last_v > 1.6 * avg_v:
                if day_chg > 0:
                    score += 0.4
                    signals.append("Above-average volume on up day")
                elif day_chg < 0:
                    score -= 0.4
                    signals.append("Above-average volume on down day")

    if score >= 1.5:
        bias = "up"
    elif score <= -1.5:
        bias = "down"
    else:
        bias = "neutral"

    conf = "high" if abs(score) >= 3 else ("medium" if abs(score) >= 1.5 else "low")

    if bias == "up":
        summary = (
            f"Heuristic leans UP (score {score:+.1f}, {conf} confidence). "
            f"Last close shows short-term constructive structure"
            f"{f' with 5d {ret_5:+.1f}%' if ret_5 is not None else ''}. "
            "This is a mechanical read of free price data — not a prediction or advice."
        )
    elif bias == "down":
        summary = (
            f"Heuristic leans DOWN (score {score:+.1f}, {conf} confidence). "
            f"Recent price action shows pressure"
            f"{f' with 5d {ret_5:+.1f}%' if ret_5 is not None else ''}. "
            "This is a mechanical read of free price data — not a prediction or advice."
        )
    else:
        summary = (
            f"Heuristic is NEUTRAL (score {score:+.1f}, {conf} confidence). "
            "Mixed signals — no clear short-term edge from simple trend/momentum rules. "
            "Not financial advice."
        )

    return {
        "bias": bias,
        "score": round(score, 2),
        "confidence": conf,
        "summary": summary,
        "signals": signals,
        "metrics": {
            "last": round(last, 4),
            "day_change_pct": round(day_chg, 3),
            "ret_5d_pct": round(ret_5, 3) if ret_5 is not None else None,
            "ret_20d_pct": round(ret_20, 3) if ret_20 is not None else None,
            "sma10": round(sma10, 4) if sma10 is not None else None,
            "sma20": round(sma20, 4) if sma20 is not None else None,
            "sma50": round(sma50, 4) if sma50 is not None else None,
            "rsi14": round(rsi, 2) if rsi is not None else None,
        },
        "disclaimer": (
            "Educational heuristic only. Not investment advice. "
            "Markets can move against any signal."
        ),
    }


def get_analysis(symbol: str, range_: str = "3mo", interval: str = "1d") -> dict:
    chart = fetch_chart(symbol, range_=range_, interval=interval)
    closes = [p["c"] for p in chart["points"]]
    volumes = [p.get("v") for p in chart["points"]]
    analysis = analyze_series(closes, volumes)

    last = chart["points"][-1]["c"]
    prev_close = chart.get("previous_close") or (
        chart["points"][-2]["c"] if len(chart["points"]) > 1 else last
    )
    chg = last - prev_close
    chg_pct = (chg / prev_close * 100) if prev_close else 0.0

    return {
        "symbol": chart["symbol"],
        "yahoo_symbol": chart["yahoo_symbol"],
        "tradingview_symbol": chart["tradingview_symbol"],
        "name": chart.get("instrument"),
        "currency": chart.get("currency"),
        "exchange": chart.get("exchange"),
        "price": round(last, 4),
        "change": round(chg, 4),
        "change_pct": round(chg_pct, 3),
        "range": range_,
        "interval": interval,
        "chart": {
            "labels": [p["t"] for p in chart["points"]],
            "closes": closes,
            "volumes": volumes,
        },
        "analysis": analysis,
        "tradingview_url": (
            f"https://www.tradingview.com/chart/?symbol="
            f"{chart['tradingview_symbol']}"
        ),
    }


def market_overview(symbols: list[str] | None = None) -> dict:
    syms = symbols or DEFAULT_WATCH
    cards = []
    errors = []
    for s in syms:
        try:
            # Lighter range for overview speed
            a = get_analysis(s, range_="3mo", interval="1d")
            cards.append(
                {
                    "symbol": a["symbol"],
                    "price": a["price"],
                    "change_pct": a["change_pct"],
                    "currency": a["currency"],
                    "bias": a["analysis"]["bias"],
                    "score": a["analysis"]["score"],
                    "confidence": a["analysis"]["confidence"],
                    "summary": a["analysis"]["summary"],
                    "spark": a["chart"]["closes"][-30:],
                    "tradingview_symbol": a["tradingview_symbol"],
                    "tradingview_url": a["tradingview_url"],
                }
            )
        except Exception as e:
            errors.append({"symbol": s, "error": f"{type(e).__name__}: {e}"})
    return {
        "cards": cards,
        "errors": errors,
        "disclaimer": (
            "Prices from free public Yahoo endpoints (delayed). "
            "Bias is a simple local heuristic — not financial advice."
        ),
    }
