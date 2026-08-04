# Project Atlas

![Project Atlas](docs/brand/logo-primary.jpg)

**Advanced Trading & Liquidity Analysis System**

Institutional-style market intelligence for Hyperliquid perpetual markets and high-quality equity dip monitoring.

![Splash](docs/brand/splash.jpg)

---

## What it does

- Continuously scans Hyperliquid perps for abnormal movement
- Tracks opportunities with confidence, regime, and risk context
- Optional paper-trade performance tracking
- Discord DM alerts (subscribe-only, no channel spam)
- Quality Dip scanner for large-cap names (ADBE, META, GOOGL, AMZN, MSFT)
- FastAPI backend + optional Next.js frontend dashboard

This is an **alert and analysis system**. It does not auto-trade.

---

## Brand

| Asset | Path |
|-------|------|
| Primary logo | `docs/brand/logo-primary.jpg` |
| App icon | `docs/brand/logo-icon.jpg` |
| Favicon | `docs/brand/favicon.jpg` |
| Splash / social | `docs/brand/splash.jpg` |

---

## Screenshots

> Add real captures to `docs/screenshots/` then uncomment below.

<!--
### Dashboard
![Dashboard](docs/screenshots/dashboard.png)

### Opportunities
![Opportunities](docs/screenshots/opportunities.png)

### Discord alert
![Discord Alert](docs/screenshots/discord-alert.png)

### Quality dips
![Quality Dips](docs/screenshots/quality-dips.png)

### Health
![Health](docs/screenshots/health.png)
-->

---

## Stack

- Python 3.12, FastAPI, asyncio
- PostgreSQL / TimescaleDB, Redis
- Discord.py
- yfinance (equity dips)
- Next.js frontend (optional)
- Docker Compose for local infra

---

## Quick start (Windows)

### 1. Clone

```bash
git clone https://github.com/LeakPilotAI/project-atlas.git
cd project-atlas
