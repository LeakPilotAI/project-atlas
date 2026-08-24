#!/usr/bin/env python3
"""Atlas health watchdog."""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

HEALTH_URL = os.environ.get("ATLAS_HEALTH_URL", "http://127.0.0.1:8000/health")
WEBHOOK_URL = os.environ.get("ATLAS_DISCORD_WEBHOOK", "")
FAIL_THRESHOLD = int(os.environ.get("ATLAS_WATCHDOG_FAILS", "3"))
INTERVAL = int(os.environ.get("ATLAS_WATCHDOG_INTERVAL", "60"))
STATE_FILE = Path(os.environ.get("ATLAS_WATCHDOG_STATE", "/tmp/atlas_watchdog_state.json"))


def _load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            pass
    return {"fails": 0, "alerted": False}


def _save_state(st: dict) -> None:
    try:
        STATE_FILE.write_text(json.dumps(st))
    except Exception:
        pass


def check_health() -> tuple[bool, str]:
    try:
        req = urllib.request.Request(HEALTH_URL, method="GET")
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            if resp.status != 200:
                return False, f"status={resp.status}"
            data = json.loads(body)
            if str(data.get("status", "")).lower() not in ("ok", "healthy", "up"):
                return False, body[:300]
            return True, body[:300]
    except Exception as e:
        return False, str(e)


def notify(msg: str) -> None:
    print(msg, flush=True)
    if not WEBHOOK_URL:
        return
    payload = json.dumps({"content": msg[:1900]}).encode("utf-8")
    req = urllib.request.Request(
        WEBHOOK_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        urllib.request.urlopen(req, timeout=15)
    except Exception as e:
        print(f"webhook failed: {e}", flush=True)


def main() -> int:
    st = _load_state()
    ok, detail = check_health()
    if ok:
        if st.get("alerted"):
            notify("✅ **Atlas recovered** — health OK again.")
        st = {"fails": 0, "alerted": False}
        _save_state(st)
        print(f"OK {detail[:120]}", flush=True)
        return 0

    st["fails"] = int(st.get("fails") or 0) + 1
    print(f"FAIL ({st['fails']}): {detail}", flush=True)
    if st["fails"] >= FAIL_THRESHOLD and not st.get("alerted"):
        notify(
            f"🚨 **Atlas health FAIL** ×{st['fails']}\n"
            f"`{HEALTH_URL}`\n```{detail[:500]}```"
        )
        st["alerted"] = True
    _save_state(st)
    return 1


if __name__ == "__main__":
    if os.environ.get("ATLAS_WATCHDOG_LOOP") == "1":
        while True:
            main()
            time.sleep(INTERVAL)
    sys.exit(main())