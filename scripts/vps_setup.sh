#!/usr/bin/env bash
set -euo pipefail
APP_ROOT="${APP_ROOT:-/opt/project-atlas}"
cd "$APP_ROOT"

sudo apt-get update -y
sudo apt-get install -y python3.12 python3.12-venv python3-pip docker.io docker-compose-v2 git curl

sudo docker compose up -d

cd "$APP_ROOT/backend"
python3.12 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e ".[dev]" 2>/dev/null || true
pip install fastapi uvicorn sqlalchemy asyncpg redis httpx pydantic pydantic-settings yfinance websockets discord.py structlog python-dotenv 2>/dev/null || true

sudo cp "$APP_ROOT/deploy/atlas-api.service" /etc/systemd/system/
sudo cp "$APP_ROOT/deploy/atlas-watchdog.service" /etc/systemd/system/
sudo cp "$APP_ROOT/deploy/atlas-watchdog.timer" /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now atlas-api.service
sudo systemctl enable --now atlas-watchdog.timer

sleep 8
curl -sS http://127.0.0.1:8000/health || true
echo
echo "Done. journalctl -u atlas-api -f"