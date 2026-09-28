from __future__ import annotations

import json

from app.investment import robinhood_universe_registry as registry


def test_registry_separates_coverage_from_research_lane(tmp_path):
    path = tmp_path / "universe.json"
    events = tmp_path / "events.jsonl"
    result = registry.upsert_discovery(
        [
            {"symbol": "AAA", "listing_state": "TRADABLE", "tradable": True, "research_lane": "QUALITY_DIPS"},
            {"symbol": "NEW", "listing_state": "PRE_LISTING", "tradable": False, "research_lane": "EMERGING_COMPOUNDER"},
        ],
        source="test-read-only",
        observed_at="2026-09-28T12:00:00+00:00",
        path=path,
        events_path=events,
    )
    assert result["total_symbols"] == 2
    assert result["listing_state_counts"] == {"TRADABLE": 1, "PRE_LISTING": 1}
    assert result["research_lane_counts"] == {"QUALITY_DIPS": 1, "EMERGING_COMPOUNDER": 1}
    assert result["live_capital_allowed"] is False
    assert result["automatic_real_money_execution"] is False
    state = json.loads(path.read_text(encoding="utf-8"))
    assert state["symbols"]["NEW"]["tradable"] is False


def test_registry_is_idempotent_and_only_events_material_changes(tmp_path):
    path = tmp_path / "universe.json"
    events = tmp_path / "events.jsonl"
    row = {"symbol": "AAA", "listing_state": "ANNOUNCED", "tradable": False}
    registry.upsert_discovery([row], source="test", observed_at="2026-09-28T12:00:00+00:00", path=path, events_path=events)
    second = registry.upsert_discovery([row], source="test", observed_at="2026-09-28T12:01:00+00:00", path=path, events_path=events)
    assert second["added"] == 0
    assert second["material_changes"] == 0
    assert len(events.read_text(encoding="utf-8").splitlines()) == 1

    changed = registry.upsert_discovery(
        [{"symbol": "AAA", "listing_state": "TRADABLE", "tradable": True}],
        source="test",
        observed_at="2026-09-28T12:02:00+00:00",
        path=path,
        events_path=events,
    )
    assert changed["material_changes"] == 1
    assert len(events.read_text(encoding="utf-8").splitlines()) == 2


def test_missing_from_batch_does_not_delist_existing_symbol(tmp_path):
    path = tmp_path / "universe.json"
    events = tmp_path / "events.jsonl"
    registry.upsert_discovery(
        [{"symbol": "AAA", "listing_state": "TRADABLE", "tradable": True}],
        source="test",
        path=path,
        events_path=events,
    )
    registry.upsert_discovery([], source="test", path=path, events_path=events)
    assert registry.snapshot(path)["symbols"]["AAA"]["listing_state"] == "TRADABLE"
