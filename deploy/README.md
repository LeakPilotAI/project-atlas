# Project Atlas — Deploy

## Local (Windows)
1. Docker: `docker compose up -d`
2. Backend venv + `python -m uvicorn app.main:app --host 0.0.0.0 --port 8000`
3. Optional: `python scripts/atlas_watchdog.py` with `ATLAS_WATCHDOG_LOOP=1`

## VPS (Ubuntu)
1. Clone repo to `/opt/project-atlas`
2. Copy `.env` via scp (never commit secrets)
3. `sudo bash scripts/vps_setup.sh`
4. Set `ATLAS_DISCORD_WEBHOOK` in `.env` for crash alerts
5. `curl http://127.0.0.1:8000/health`
6. Logs: `journalctl -u atlas-api -f`

## Units
- `atlas-api.service` — API + scanners + Discord
- `atlas-watchdog.timer` — health check every minute