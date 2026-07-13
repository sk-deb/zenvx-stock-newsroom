# Disclaimer

**ZenvX StockMarket Newsroom** is free, open-source software for personal,
educational, and research use on your own machine.

## Not financial advice

- Charts, prices, “up / down / neutral” bias scores, and short analysis text are
  **mechanical heuristics** based on free public market data (moving averages,
  RSI-style measures, short-term returns, volume spikes).
- They are **not** investment recommendations, predictions, or personalized advice.
- Markets can move against any signal. You are solely responsible for your
  trading and investment decisions.
- If you need advice, consult a qualified, licensed professional.

## Third-party content and data

This app aggregates **publicly available** headlines (RSS or light HTML
scraping) and free price endpoints. It does **not**:

- Store or redistribute full article bodies for commercial republishing
- Act as an official product of CNBC, Reuters, Bloomberg, Economic Times,
  Yahoo, TradingView, or any other named outlet

**Brand names** appear only to identify news sources and chart widgets.

Users must comply with each third party’s **Terms of Service**, robots rules,
and applicable law. Feed URLs, site structure, and free APIs can change or be
blocked without notice.

## TradingView

- There is **no free official API** to log into a personal TradingView account
  and sync private watchlists server-side.
- This project uses TradingView’s **public chart widget embed** and optional
  symbol lists you paste yourself (stored in your browser only).
- TradingView is a trademark of its respective owners. This project is not
  affiliated with or endorsed by TradingView.

## No warranty / liability

The software is provided **“AS IS”** under the MIT License, without warranty of
any kind. Authors and contributors are not liable for losses, data issues,
blocked IPs, broken feeds, or decisions made using the tool.

## Privacy

- Runs **locally** by default; no cloud account is required for core features.
- A local SQLite file (`backend/news.db`) stores headlines on your disk.
- TradingView watchlist symbols (if used) are stored in **browser localStorage**.
- Outbound network calls go only to configured news/price/widget endpoints from
  **your** machine when you run the app.
