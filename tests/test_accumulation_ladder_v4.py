from datetime import datetime, timedelta, timezone

from app.investment.accumulation_ladder import AccumulationLadderStore, SCHEMA_VERSION


def board(price=100.0, stance="ACCUMULATE", quality="FRESH", symbol="ADBE", trigger=None):
    trigger_price = price if trigger is None else trigger
    return [{
        "symbol": symbol,
        "stance": stance,
        "quote_price": price,
        "quote_display_price": price,
        "quote_trigger_price": trigger_price,
        "quote_quality": quality,
        "quote_session": "ROBINHOOD_MARKET_DATA",
        "quote_source": "robinhood_underlying_bid_ask",
        "quote_effective_timestamp": "2026-09-14T14:30:00+00:00",
    }]


def test_accumulate_arms_tighter_frozen_levels_below_current_quote(tmp_path):
    store = AccumulationLadderStore(tmp_path / "ladder.json")
    hits = store.sync(board(100.0), now=datetime(2026, 9, 14, 14, 30, tzinfo=timezone.utc))
    assert hits == []
    state = store.get("ADBE")
    assert state["active"] is True
    assert state["schema_version"] == SCHEMA_VERSION
    assert state["anchor_price"] == 100.0
    assert [x["price"] for x in state["levels"]] == [98.5, 97.0, 95.0, 92.0]
    assert [x["pct_below_anchor"] for x in state["levels"]] == [1.5, 3.0, 5.0, 8.0]


def test_adobe_like_anchor_puts_l1_near_248(tmp_path):
    store = AccumulationLadderStore(tmp_path / "ladder.json")
    now = datetime(2026, 9, 14, 14, 30, tzinfo=timezone.utc)
    store.sync(board(252.20), now=now)
    state = store.get("ADBE")
    assert state["levels"][0]["price"] == 248.417


def test_live_quote_can_arm_and_trigger(tmp_path):
    store = AccumulationLadderStore(tmp_path / "ladder.json")
    now = datetime(2026, 9, 14, 14, 30, tzinfo=timezone.utc)
    store.sync(board(100.0, quality="LIVE"), now=now)
    hits = store.sync(board(98.4, quality="LIVE"), now=now + timedelta(seconds=30))
    assert [x.level for x in hits] == ["L1"]


def test_robinhood_ask_is_used_for_buy_limit_crossing(tmp_path):
    store = AccumulationLadderStore(tmp_path / "ladder.json")
    now = datetime(2026, 9, 14, 14, 30, tzinfo=timezone.utc)
    store.sync(board(100.0, trigger=100.1), now=now)
    # Display midpoint can be under L1 while ask is still above it: no fill alert yet.
    assert store.sync(board(98.4, trigger=98.6), now=now + timedelta(seconds=30)) == []
    hits = store.sync(board(98.3, trigger=98.49), now=now + timedelta(seconds=60))
    assert [x.level for x in hits] == ["L1"]


def test_rising_market_never_chases_ladder_higher(tmp_path):
    store = AccumulationLadderStore(tmp_path / "ladder.json")
    now = datetime(2026, 9, 14, 14, 30, tzinfo=timezone.utc)
    store.sync(board(100.0), now=now)
    store.sync(board(115.0), now=now + timedelta(minutes=1))
    state = store.get("ADBE")
    assert state["anchor_price"] == 100.0
    assert [x["price"] for x in state["levels"]] == [98.5, 97.0, 95.0, 92.0]
    assert all(not x["hit"] for x in state["levels"])


def test_overlay_exposes_next_level_and_distance(tmp_path):
    store = AccumulationLadderStore(tmp_path / "ladder.json")
    now = datetime(2026, 9, 14, 14, 30, tzinfo=timezone.utc)
    row = board(100.0)[0]
    store.sync([row], now=now)
    out = store.overlay([row])[0]
    status = out["accumulation_status"]
    assert status["state"] == "ARMED"
    assert status["next_level"]["level"] == "L1"
    assert status["distance_to_next_level_usd"] == 1.5
    assert status["distance_to_next_level_pct"] == 1.5


def test_each_level_alerts_once_after_successful_delivery(tmp_path):
    store = AccumulationLadderStore(tmp_path / "ladder.json")
    now = datetime(2026, 9, 14, 14, 30, tzinfo=timezone.utc)
    store.sync(board(100.0), now=now)
    first = store.sync(board(98.4), now=now + timedelta(minutes=1))
    assert [x.level for x in first] == ["L1"]
    assert store.mark_delivered("ADBE", first[0].cycle_id, "L1", now=now + timedelta(minutes=1)) is True
    duplicate = store.sync(board(98.0), now=now + timedelta(minutes=2))
    assert duplicate == []
    second = store.sync(board(96.9), now=now + timedelta(minutes=3))
    assert [x.level for x in second] == ["L2"]


def test_undelivered_hit_is_retried_until_marked_delivered(tmp_path):
    store = AccumulationLadderStore(tmp_path / "ladder.json")
    now = datetime(2026, 9, 14, 14, 30, tzinfo=timezone.utc)
    store.sync(board(100.0), now=now)
    first = store.sync(board(98.4), now=now + timedelta(minutes=1))
    retry = store.sync(board(98.0), now=now + timedelta(minutes=2))
    assert [x.level for x in first] == ["L1"]
    assert [x.level for x in retry] == ["L1"]
    overlay = store.overlay(board(98.0))[0]
    assert overlay["accumulation_status"]["state"] == "LEVEL_HIT_DM_PENDING"
    assert overlay["accumulation_status"]["pending_dm"] == 1
    assert store.mark_delivered("ADBE", retry[0].cycle_id, "L1") is True
    assert store.sync(board(97.8), now=now + timedelta(minutes=3)) == []
    delivered = store.overlay(board(97.8))[0]
    assert delivered["accumulation_status"]["state"] == "LEVEL_HIT"
    assert delivered["accumulation_status"]["pending_dm"] == 0


def test_gap_down_emits_every_newly_crossed_level(tmp_path):
    store = AccumulationLadderStore(tmp_path / "ladder.json")
    now = datetime(2026, 9, 14, 14, 30, tzinfo=timezone.utc)
    store.sync(board(100.0), now=now)
    hits = store.sync(board(94.0), now=now + timedelta(minutes=1))
    assert [x.level for x in hits] == ["L1", "L2", "L3"]


def test_stale_quote_cannot_arm_or_trigger(tmp_path):
    store = AccumulationLadderStore(tmp_path / "ladder.json")
    now = datetime(2026, 9, 14, 14, 30, tzinfo=timezone.utc)
    store.sync(board(100.0, quality="REFERENCE"), now=now)
    assert store.get("ADBE") is None
    store.sync(board(100.0), now=now + timedelta(minutes=1))
    hits = store.sync(board(90.0, quality="STALE"), now=now + timedelta(minutes=2))
    assert hits == []
    assert all(not x["hit"] for x in store.get("ADBE")["levels"])


def test_legacy_ladder_is_hidden_then_rearmed_on_fresh_quote(tmp_path):
    path = tmp_path / "ladder.json"
    path.write_text(
        '{"symbols":{"ADBE":{"active":true,"cycle_id":"legacy","anchor_price":300,"levels":[{"level":"L1","price":291,"hit":false}]}}}',
        encoding="utf-8",
    )
    store = AccumulationLadderStore(path)
    pre = store.overlay(board(252.20, quality="REFERENCE"))[0]
    assert pre["accumulation_ladder"] is None
    assert pre["accumulation_status"]["state"] == "WAITING_FOR_FRESH_QUOTE"
    now = datetime(2026, 9, 14, 14, 30, tzinfo=timezone.utc)
    store.sync(board(252.20, quality="LIVE"), now=now)
    state = store.get("ADBE")
    assert state["schema_version"] == SCHEMA_VERSION
    assert state["anchor_price"] == 252.20
    assert state["levels"][0]["price"] == 248.417


def test_leaving_accumulate_closes_cycle_and_reentry_reanchors(tmp_path):
    store = AccumulationLadderStore(tmp_path / "ladder.json")
    now = datetime(2026, 9, 14, 14, 30, tzinfo=timezone.utc)
    store.sync(board(100.0), now=now)
    first_cycle = store.get("ADBE")["cycle_id"]
    store.sync(board(101.0, stance="WATCH"), now=now + timedelta(minutes=1))
    assert store.get("ADBE")["active"] is False
    store.sync(board(90.0), now=now + timedelta(minutes=2))
    state = store.get("ADBE")
    assert state["active"] is True
    assert state["cycle_id"] != first_cycle
    assert state["anchor_price"] == 90.0
    assert state["levels"][0]["price"] == 88.65
