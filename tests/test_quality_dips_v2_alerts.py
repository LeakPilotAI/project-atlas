from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.investment.quality_dips_v2_alerts import decide_v2_alert, format_v2_alert


def _cur(state="ACCUMULATION", *, thesis="INTACT", reached=()):
    return {
        "symbol": "TEST",
        "patient_state": state,
        "thesis": thesis,
        "normalization_value": {"conservative": 130.0, "base": 140.0, "optimistic": 150.0},
        "conservative_upside_pct": 44.4,
        "evidence_gate": {"status": "ELIGIBLE_FOR_V2_CLASSIFICATION"},
        "entry_ladder": {
            "levels": [
                {"level": "L1", "reached": "L1" in reached},
                {"level": "L2", "reached": "L2" in reached},
                {"level": "L3", "reached": "L3" in reached},
                {"level": "L4", "reached": "L4" in reached},
            ]
        },
    }


def test_state_upgrade_notifies():
    out = decide_v2_alert(symbol="TEST", previous={"patient_state": "WATCH", "thesis": "INTACT"}, current=_cur("ACCUMULATION"))
    assert out["notify"] is True
    assert out["event_type"] == "STATE_TRANSITION"
    assert out["dedupe_key"] == "V2:TEST:STATE_TRANSITION:ACCUMULATION"


def test_generational_upgrade_is_high_priority():
    out = decide_v2_alert(symbol="TEST", previous={"patient_state": "DEEP_VALUE", "thesis": "INTACT"}, current=_cur("GENERATIONAL"))
    assert out["notify"] is True
    assert out["priority"] == "HIGH"


def test_exceptional_l3_and_l4_zone_notify():
    l3 = decide_v2_alert(symbol="TEST", previous={"patient_state": "ACCUMULATION", "thesis": "INTACT"}, current=_cur(reached=("L3",)))
    assert l3["event_type"] == "EXCEPTIONAL_ZONE"
    assert l3["notify"] is True
    l4 = decide_v2_alert(symbol="TEST", previous={"patient_state": "DEEP_VALUE", "thesis": "INTACT"}, current=_cur("GENERATIONAL", reached=("L3", "L4")))
    assert l4["dedupe_key"] == "V2:TEST:EXCEPTIONAL_ZONE:L4"
    assert l4["priority"] == "HIGH"


def test_thesis_break_overrides_price_events():
    out = decide_v2_alert(symbol="TEST", previous={"patient_state": "DEEP_VALUE", "thesis": "INTACT"}, current=_cur("THESIS_BROKEN", thesis="BROKEN", reached=("L4",)))
    assert out["event_type"] == "THESIS_CHANGE"
    assert out["priority"] == "HIGH"


def test_duplicate_event_suppressed_inside_cooldown():
    now = datetime.now(timezone.utc)
    first = decide_v2_alert(symbol="TEST", previous={"patient_state": "WATCH", "thesis": "INTACT"}, current=_cur("ACCUMULATION"), now=now)
    again = decide_v2_alert(
        symbol="TEST",
        previous={"patient_state": "WATCH", "thesis": "INTACT"},
        current=_cur("ACCUMULATION"),
        prior_event={"dedupe_key": first["dedupe_key"], "last_at": (now - timedelta(hours=1)).isoformat()},
        now=now,
        cooldown_hours=12,
    )
    assert again["notify"] is False
    assert "cooldown/dedupe" in " ".join(again["reasons"])


def test_same_event_allowed_after_cooldown():
    now = datetime.now(timezone.utc)
    out = decide_v2_alert(
        symbol="TEST",
        previous={"patient_state": "WATCH", "thesis": "INTACT"},
        current=_cur("ACCUMULATION"),
        prior_event={"dedupe_key": "V2:TEST:STATE_TRANSITION:ACCUMULATION", "last_at": (now - timedelta(hours=13)).isoformat()},
        now=now,
        cooldown_hours=12,
    )
    assert out["notify"] is True


def test_no_change_no_notification():
    out = decide_v2_alert(symbol="TEST", previous={"patient_state": "WATCH", "thesis": "INTACT"}, current=_cur("WATCH"))
    assert out["notify"] is False
    assert out["event_type"] is None


def test_format_is_manual_only_and_not_guaranteed():
    decision = decide_v2_alert(symbol="TEST", previous={"patient_state": "WATCH", "thesis": "INTACT"}, current=_cur("ACCUMULATION"))
    text = format_v2_alert("TEST", decision, _cur("ACCUMULATION"))
    assert "MANUAL RESEARCH ONLY" in text
    assert "No brokerage order was placed" in text
    assert "not promised returns" in text
    assert decision["live_capital_allowed"] is False
    assert decision["automatic_real_money_execution"] is False
