# GitHub publish report — ZenvX StockMarket Newsroom

**Date prepared:** 2026-07-13  
**Project path:** `C:\Users\sriha\zenvx-stock-newsroom`  
**Intended use:** public GitHub repo others can clone and run locally

---

## What was completed for you (automated)

| Item | Status | File / action |
|------|--------|----------------|
| MIT License | Done | `LICENSE` |
| Legal / usage disclaimer | Done | `DISCLAIMER.md` |
| GitHub-ready README | Done | `README.md` (badges, features, API, sources, TV limits) |
| `.gitignore` | Done | Ignores `.venv/`, `news.db`, `__pycache__/`, `.env`, IDE junk |
| Source code ready | Done | `backend/`, `frontend/`, `run.bat`, `run.sh` |
| No API keys / secrets in code | Done | App is key-free by design |
| Local git repo + initial commit | **Blocked** | Git is **not installed** on this PC (`git` not in PATH) |
| This report | Done | `PUBLISH_REPORT.md` |

**Intentionally not pushed to GitHub** — needs Git + your GitHub account.

---

## What you must do manually

### 0. Install Git (required once on this machine)

Download and install: [https://git-scm.com/download/win](https://git-scm.com/download/win)  
During setup, leave “Git from the command line” enabled. **Restart the terminal** after install.

Then set your name/email once:

```powershell
git config --global user.name "Your Name"
git config --global user.email "you@example.com"
```

### 1. Create the GitHub repository

1. Go to [https://github.com/new](https://github.com/new)
2. Name e.g. `zenvx-stock-newsroom`
3. **Public** (or Private if you prefer)
4. **Do not** add README / License / .gitignore on GitHub (we already have them)
5. Create repository

### 2. Init git, commit, and push

In PowerShell (replace `YOUR_USERNAME`):

```powershell
cd C:\Users\sriha\zenvx-stock-newsroom

git init
git add .
git status
# Confirm .venv and news.db are NOT listed

git commit -m "Initial public release: ZenvX StockMarket Newsroom"

git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/zenvx-stock-newsroom.git
git push -u origin main
```

If GitHub asks you to log in, use a **Personal Access Token** or GitHub CLI (`gh auth login`), not your account password.

### 3. Optional polish on GitHub

- Repo description:  
  `Local stock market news aggregator with free charts, bias heuristic & TradingView widget`
- Topics: `fastapi`, `stock-market`, `rss`, `sqlite`, `tradingview`, `python`
- About → website: leave empty (local app) or your personal site
- Enable Issues if you want bug reports

### 4. Optional: don’t commit this report

`PUBLISH_REPORT.md` is for **you**. After pushing, you can delete it from the repo if you don’t want it public:

```powershell
git rm PUBLISH_REPORT.md
git commit -m "Remove internal publish report"
git push
```

Or keep it — harmless.

### 5. Not included (separate project)

The Malayalam app at `C:\Users\sriha\zenvx-newsroom` is **not** part of this publish pack. Publish that separately if you want.

---

## Safety checklist (pre-publish)

| Check | Result |
|-------|--------|
| API keys / passwords in repo? | **None** |
| `.venv` ignored? | **Yes** |
| `news.db` ignored? | **Yes** (local headlines only; not for git) |
| Financial advice claim? | **No** — disclaimer present |
| TradingView “official login” claim? | **No** — widget + paste symbols only |
| License for others to use? | **MIT** |

---

## Risks when others download it (normal for this type of app)

1. **Feed breakage** — sites change RSS or block scrapers → users edit `feeds_config.json`
2. **Yahoo chart endpoints** — unofficial; may rate-limit or change
3. **ToS of news sites** — users run fetches from *their* IPs; your README/DISCLAIMER put responsibility on them
4. **People treat bias as “tips”** — mitigated by visible disclaimer text
5. **Support load** — open Issues only if you’re willing to answer

You are **not** hosting other people’s traffic by putting source on GitHub.

---

## Suggested first commit message (already used if commit succeeded)

```
Initial public release: ZenvX StockMarket Newsroom

Local FastAPI news aggregator with story clustering, free Yahoo charts,
heuristic bias, and TradingView widget desk. MIT licensed.
```

---

## One-command verify after clone (for you or others)

```powershell
cd zenvx-stock-newsroom
.\run.bat
# open http://127.0.0.1:8421
```

---

## Summary

| Who | Action |
|-----|--------|
| **Agent (done)** | License, disclaimer, README, gitignore, clean layout, this report |
| **You (manual)** | Install Git → create GitHub repo → `git init` / commit / push → optional topics |

That’s all that’s required to publish safely.
