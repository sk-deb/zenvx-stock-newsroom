# ZenvX StockMarket Newsroom

Fast, **local-only** stock market news aggregator (Ground News–style), plus free price charts, a simple momentum bias read, and a TradingView widget desk.

> **Not financial advice.** Bias scores are mechanical heuristics on free public data. See [DISCLAIMER.md](DISCLAIMER.md).

[![License: MIT](https://img.shields.io/badge/License-MIT-00FF88.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-00D4FF.svg)](https://www.python.org/)
[![Runs locally](https://img.shields.io/badge/Runs-locally-9F7AEA.svg)](#quick-start)

## Features

- Multi-source finance **headlines** with same-story **clustering**
- **Ticker detection** (US + India) and market **news pulse**
- **Price charts** + sparklines (free Yahoo public endpoints, no API key)
- Short **up / down / neutral** analysis (SMA / RSI / returns — not a prediction)
- **TradingView** free chart widget + paste-your-watchlist symbols
- Config-driven feeds (`backend/feeds_config.json`) — no code change to add sources
- Dark cyberpunk UI · FastAPI + SQLite · port **8421**

## Quick start

### Requirements

- Python **3.10+**
- Internet access (RSS + free price data + optional TradingView widget)

### Windows

```bat
cd zenvx-stock-newsroom
run.bat
```

Open **http://127.0.0.1:8421**

### Mac / Linux

```bash
cd zenvx-stock-newsroom
chmod +x run.sh
./run.sh
```

### Manual

```bash
python3 -m venv .venv
# Windows: .venv\Scripts\activate
source .venv/bin/activate
pip install -r backend/requirements.txt
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8421
```

> First fetch may take ~10–25s. Use the **Source health** panel for exact errors.

## Screens / API

| Area | What it does |
|------|----------------|
| Price desk | Free quotes + sparkline + bias pill |
| Chart & bias | Full chart + short written heuristic |
| TradingView | Paste watchlist; embed public TV widget |
| News grid | Clustered stories across outlets |

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/api/stories?hours=24&limit=100` | Grouped stories |
| `GET` | `/api/stories?symbol=NVDA` | Filter by ticker |
| `GET` | `/api/sources` | Feed health |
| `GET` | `/api/pulse` | Top mentioned symbols |
| `GET` | `/api/market-overview` | Prices + bias cards |
| `GET` | `/api/chart/{symbol}?range=3mo` | OHLCV series |
| `GET` | `/api/analysis/{symbol}` | Chart + bias write-up |
| `POST` | `/api/tradingview/watchlist` | Resolve pasted TV symbols |
| `POST` | `/api/refresh` | Force fetch cycle |
| `GET` | `/api/health` | Liveness |

## News sources

Reliability over quantity. Blocked outlets stay in config as `"enabled": false`.

| Source | Mode | Notes |
|--------|------|--------|
| CNBC Markets | RSS | Working when built |
| Economic Times Markets | RSS | Working |
| Financial Express Market | Scrape | RSS empty/HTML |
| MarketWatch | RSS | Working |
| Yahoo Finance | RSS | Working |
| Mint Markets | RSS | Working |
| Investing.com | RSS | Working |
| CNBC-TV18 Market | RSS | Working |
| Business Today Markets | RSS | Working |
| Business Line Markets | RSS | Working |
| WSJ Markets (DJ public) | RSS | Working |
| Reuters | Disabled | 401 from this network |
| Bloomberg | Disabled | 403 without credentials |
| Moneycontrol | Disabled | RSS + HTML 403 |

Edit sources only in `backend/feeds_config.json`.

## Story grouping

Default window **24h**, Jaccard threshold **0.36**, optional **symbol_boost** when tickers match.

```json
"refresh_interval_minutes": 5,
"story_group_window_hours": 24,
"similarity_threshold": 0.36,
"symbol_boost": 0.12
```

## TradingView

TradingView has **no free private account API**. This project:

1. Lets you **paste** symbols from your TV watchlist (browser `localStorage`)
2. Embeds the **public** chart widget
3. Links out to the full TradingView chart

Not affiliated with TradingView.

## Run as a service

### Linux (systemd user)

```ini
# ~/.config/systemd/user/zenvx-stock-newsroom.service
[Unit]
Description=ZenvX StockMarket Newsroom
After=network-online.target

[Service]
Type=simple
WorkingDirectory=%h/zenvx-stock-newsroom
ExecStart=%h/zenvx-stock-newsroom/.venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 8421
Restart=on-failure
RestartSec=8

[Install]
WantedBy=default.target
```

### Windows (Task Scheduler)

Point a startup task at `.venv\Scripts\python.exe` with  
`-m uvicorn backend.main:app --host 127.0.0.1 --port 8421`  
and “Start in” = project folder (run `run.bat` once first).

## Project layout

```
zenvx-stock-newsroom/
  backend/
    main.py              # API, feeds, grouping
    market_data.py       # Yahoo charts + bias heuristic
    feeds_config.json    # sources & thresholds
    requirements.txt
  frontend/
    index.html           # dashboard (no build step)
  run.bat / run.sh
  LICENSE                # MIT
  DISCLAIMER.md
  README.md
```

## License

[MIT](LICENSE) — free to use, modify, and redistribute with attribution.

## Disclaimer (summary)

- **Not financial advice.**  
- Third-party news/price endpoints are used as-is; respect their ToS.  
- No warranty; feeds and free APIs can break.  
- Full text: [DISCLAIMER.md](DISCLAIMER.md).

## Contributing

Issues and PRs welcome: dead feeds, better symbol maps, UI polish, safer scrapers. Please keep the project **local-first**, **no mandatory API keys**, and **no invented bias “ratings”** that claim editorial authority.
