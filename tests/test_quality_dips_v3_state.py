from app.investment.quality_dips_v3_state import QualityDipsV3StateStore, detect_v3_events


def plan(state="WATCH", reached=None):
    reached = reached or []
    return {
        "symbol": "MSFT",
        "patient_state": state,
        "entry_ladder": {
            "levels": [
                {"level": "L1", "limit_price": 100, "reached": "L1" in reached},
                {"level": "L2", "limit_price": 90, "reached": "L2" in reached},
            ]
        },
    }


def test_detects_state_improvement_and_new_level_only():
    events = detect_v3_events(plan("WATCH"), plan("ACCUMULATION", ["L1"]))
    kinds = {(e["event_type"], e.get("level"), e.get("state")) for e in events}
    assert ("STATE_IMPROVED", None, "ACCUMULATION") in kinds
    assert ("ENTRY_LEVEL_REACHED", "L1", None) in kinds


def test_does_not_repeat_already_reached_level():
    events = detect_v3_events(plan("ACCUMULATION", ["L1"]), plan("ACCUMULATION", ["L1"]))
    assert events == []


def test_store_persists_snapshot_and_dedupes_event(tmp_path):
    path = tmp_path / "v3.json"
    s = QualityDipsV3StateStore(path)
    s.remember("msft", plan("ACCUMULATION"))
    s.mark_event("V3:MSFT:STATE:ACCUMULATION", symbol="MSFT", event_type="STATE_IMPROVED")
    s.save()
    r = QualityDipsV3StateStore(path)
    assert r.previous("MSFT")["patient_state"] == "ACCUMULATION"
    assert r.event_seen("V3:MSFT:STATE:ACCUMULATION") is True
