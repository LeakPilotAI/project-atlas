# Project Atlas (ATLAS)

**Advanced Trading & Liquidity Analysis System**

Institutional-grade market intelligence platform that continuously scans perpetual markets (Axiom + adapters) for statistically unusual behavior, ranks opportunities, and delivers actionable alerts + analytics.

## Core Capabilities
- Real-time + historical market data ingestion
- Full technical indicator engine
- Statistical anomaly detection
- Transparent opportunity scoring
- Multi-channel alerting (Discord, Telegram, Email, Desktop)
- Professional dark dashboard (Next.js)
- Backtesting + performance analytics
- Dockerized, production-ready deployment

## Tech Stack
- **Backend**: Python 3.12, FastAPI, AsyncIO, Pydantic
- **Database**: PostgreSQL + TimescaleDB + Redis
- **Frontend**: Next.js 14, React, Tailwind CSS, TradingView Lightweight Charts
- **Infra**: Docker, Nginx, Prometheus/Grafana (later)

## Quick Start (Development)
```bash
cp .env.example .env
# Edit .env with your keys
docker compose up -d
cd backend && pip install -e ".[dev]"
uvicorn app.main:app --reload