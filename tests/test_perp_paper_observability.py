from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone


def _write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")


def test_pending_health_exposes_age_backing_and_cancel_reasons(tmp_path, monkeypatch):
    import app.services.perp_paper_observability as obs

    pending_path = tmp_path / "limits.jsonl"
    now = datetime.now(timezone.utc)
    armed = {
        "event": "armed",
        "timestamp": (now - timedelta(hours=2)).isoformat(),
        "setup_instance_id": "BTC:LONG|first|epoch",
        "setup_key": "BTC:LONG",
        "symbol": "BTC",
        "side": "LONG",
        "tier": "QUALIFIED",
        "limit_price": 100.0,
    }
    cancelled = {
        "event": "cancelled",
        "timestamp": (now - timedelta(minutes=1)).isoformat(),
        "setup_instance_id": "OLD|first|epoch",
        "reason": "SETUP_INVALIDATED",
    }
    _write_jsonl(pending_path, [armed, cancelled])
    monkeypatch.setattr(obs, "PENDING_EVENT_PATH", pending_path)

    setups = [{
        "setup_key": "BTC:LONG",
        "first_seen_at": "first",
        "paper_mirror_epoch_at": "epoch",
        "state": "PREPARE",
        "discovery_stale": False,
    }]
    out = obs.pending_health(setups)
    assert out["pending_count"] == 1
    assert out["currently_backed"] == 1
    assert out["not_in_current_snapshot"] == 0
    assert out["age_buckets"]["h1_6"] == 1
    assert out["cancel_reason_counts"]["SETUP_INVALIDATED"] == 1
    assert out["oldest_pending"][0]["symbol"] == "BTC"
    assert out["review_recommended"] is False


def test_pending_health_flags_only_old_or_unknown_for_review(tmp_path, monkeypatch):
    import app.services.perp_paper_observability as obs

    pending_path = tmp_path / "limits.jsonl"
    now = datetime.now(timezone.utc)
    _write_jsonl(pending_path, [{
        "event": "armed",
        "timestamp": (now - timedelta(hours=30)).isoformat(),
        "setup_instance_id": "ETH:SHORT|first|epoch",
        "setup_key": "ETH:SHORT",
        "symbol": "ETH",
        "side": "SHORT",
        "limit_price": 200.0,
    }])
    monkeypatch.setattr(obs, "PENDING_EVENT_PATH", pending_path)
    out = obs.pending_health([])
    assert out["pending_count"] == 1
    assert out["not_in_current_snapshot"] == 1
    assert out["age_buckets"]["gt_24h"] == 1
    assert out["review_recommended"] is True


def test_clean_cohort_is_entry_time_scoped(tmp_path, monkeypatch):
    import app.services.perp_paper_observability as obs

    journal = tmp_path / "journal.jsonl"
    marker = tmp_path / "cohort.json"
    cutoff = datetime.now(timezone.utc) - timedelta(hours=1)
    marker.write_text(json.dumps({
        "cohort": obs.COHORT_NAME,
        "started_at": cutoff.isoformat(),
        "source": obs.SOURCE,
    }), encoding="utf-8")
    rows = [
        {"event": "open", "trade_id": "old", "source": obs.SOURCE, "entry_timestamp": (cutoff - timedelta(minutes=1)).isoformat()},
        {"event": "close", "trade_id": "old", "exit_timestamp": (cutoff + timedelta(minutes=2)).isoformat()},
        {"event": "open", "trade_id": "new_closed", "source": obs.SOURCE, "entry_timestamp": (cutoff + timedelta(minutes=1)).isoformat()},
        {"event": "close", "trade_id": "new_closed", "exit_timestamp": (cutoff + timedelta(minutes=3)).isoformat()},
        {"event": "open", "trade_id": "new_open", "source": obs.SOURCE, "entry_timestamp": (cutoff + timedelta(minutes=4)).isoformat()},
    ]
    _write_jsonl(journal, rows)
    monkeypatch.setattr(obs, "JOURNAL_PATH", journal)
    out = obs.cohort_summary(marker)
    assert out["opened"] == 2
    assert out["closed"] == 1
    assert out["open"] == 1
    assert out["entry_time_scoped"] is True
    assert out["live_capital_allowed"] is False
