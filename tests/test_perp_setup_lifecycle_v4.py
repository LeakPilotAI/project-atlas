from datetime import datetime, timedelta, timezone

from app.trading_core.perp_setup_lifecycle import SetupTier, classify_tier, reconcile_setups


NOW = datetime(2026, 9, 10, 12, 0, tzinfo=timezone.utc)


def _setup(score=75.0, state="PREPARE"):
    return {"symbol": "BTC", "side": "LONG", "score": score, "state": state}


def test_tier_thresholds():
    assert classify_tier(69.99) is SetupTier.WATCH
    assert classify_tier(70.0) is SetupTier.QUALIFIED
    assert classify_tier(82.0) is SetupTier.PRIME


def test_watch_setup_does_not_alert():
    row = reconcile_setups([_setup(score=65.0)], now=NOW)[0]
    assert row["tier"] == "WATCH"
    assert row["alert_eligible"] is False


def test_qualified_prepare_alerts_first_time():
    row = reconcile_setups([_setup(score=75.0)], now=NOW)[0]
    assert row["tier"] == "QUALIFIED"
    assert row["alert_eligible"] is True
    assert row["setup_key"] == "BTC:LONG"


def test_wait_state_does_not_alert_even_if_prime():
    row = reconcile_setups([_setup(score=90.0, state="WAIT")], now=NOW)[0]
    assert row["tier"] == "PRIME"
    assert row["alert_eligible"] is False


def test_duplicate_alert_suppressed_inside_cooldown():
    prior = {
        **_setup(score=75.0),
        "tier": "QUALIFIED",
        "last_alert_at": (NOW - timedelta(minutes=5)).isoformat(),
        "first_seen_at": (NOW - timedelta(hours=1)).isoformat(),
    }
    row = reconcile_setups([_setup(score=75.0)], previous=[prior], now=NOW, cooldown_minutes=30)[0]
    assert row["alert_eligible"] is False
    assert row["first_seen_at"] == prior["first_seen_at"]


def test_cooldown_expiry_allows_repeat_actionable_alert():
    prior = {
        **_setup(score=75.0),
        "tier": "QUALIFIED",
        "last_alert_at": (NOW - timedelta(minutes=31)).isoformat(),
    }
    row = reconcile_setups([_setup(score=75.0)], previous=[prior], now=NOW, cooldown_minutes=30)[0]
    assert row["alert_eligible"] is True


def test_promotion_to_prime_alerts_even_inside_cooldown():
    prior = {
        **_setup(score=75.0),
        "tier": "QUALIFIED",
        "last_alert_at": (NOW - timedelta(minutes=2)).isoformat(),
    }
    row = reconcile_setups([_setup(score=85.0)], previous=[prior], now=NOW, cooldown_minutes=30)[0]
    assert row["tier"] == "PRIME"
    assert row["alert_eligible"] is True
