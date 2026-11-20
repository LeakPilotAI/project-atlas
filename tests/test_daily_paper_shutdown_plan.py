import pytest
from app.services.daily_paper_shutdown_plan import plan_shutdown


@pytest.mark.parametrize("stamp,verified,price,eligible", [(100, True, "12", True), (89, True, "12", False),
                                                         (101, True, "12", False), (None, True, "12", False),
                                                         (100, False, "12", False), (100, True, "NaN", False)])
def test_quote_evidence_never_invents_fill(stamp, verified, price, eligible):
    positions = [{"trade_id": "one", "symbol": "TEST"}]
    quotes = {"TEST": {"price": price, "observed_at": stamp, "verified": verified, "source_id": "fixture"}}
    result = plan_shutdown("session", positions, quotes, now=100, max_age=10)
    assert len(result["intents"]) == int(eligible)
    assert len(result["unresolved"]) == int(not eligible)
    assert result["executed_n"] == 0 and result["shutdown_complete"] is False
    assert result == plan_shutdown("session", positions, quotes, now=100, max_age=10)


def test_duplicates_refuse_and_missing_quote_preserves_position():
    positions = [{"trade_id": "one", "symbol": "TEST"}]
    assert plan_shutdown("s", positions, {}, now=100, max_age=10)["unresolved"]
    with pytest.raises(ValueError):
        plan_shutdown("s", positions * 2, {}, now=100, max_age=10)
