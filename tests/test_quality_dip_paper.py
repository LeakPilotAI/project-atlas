"""Quality-dip auto paper is stocks-only and does not change perp gates."""

from app.core.config import get_settings
from app.investment.paper_book import PaperBook
from app.services.funnel_research import EXT_LOCK, RR_LOCK, RSI_LONG_LOCK, RSI_SHORT_LOCK


def test_gates_still_locked() -> None:
    assert RSI_LONG_LOCK == 28.0
    assert RSI_SHORT_LOCK == 72.0
    assert EXT_LOCK == 1.4
    assert RR_LOCK == 1.8
    s = get_settings()
    assert s.perp_micro_rsi_long == 28.0
    assert s.perp_micro_min_extension_pct == 1.4
    assert s.perp_micro_min_rr == 1.8
    assert s.quality_dip_discord_enabled is False
    assert s.quality_dip_auto_paper is True


def test_research_buy_is_not_brokerage(tmp_path) -> None:
    book = PaperBook(state_path=tmp_path / "state.json", ledger_path=tmp_path / "ledger.jsonl")
    fill = book.research_buy("SLV", 30.0, 200.0, reason="quality_dip", seed_cash=10_000)
    assert fill is not None
    assert fill["symbol"] == "SLV"
    assert book.positions["SLV"].shares > 0
    again = book.research_buy("SLV", 29.0, 200.0, seed_cash=10_000)
    assert again is None
    try:
        book.execute_broker_order()
        assert False, "brokerage should raise"
    except RuntimeError as e:
        assert "brokerage" in str(e).lower()


def test_majors_pinned_ahead_of_memes() -> None:
    from app.services.perp_micro_coach import PerpMicroCoach

    coach = PerpMicroCoach()
    tickers = [
        {"symbol": "TRUMP", "volume_24h": 9_000_000, "open_interest": 9_000_000, "price": 3.0},
        {"symbol": "BTC", "volume_24h": 8_000_000, "open_interest": 8_000_000, "price": 110000},
        {"symbol": "SOL", "volume_24h": 7_000_000, "open_interest": 7_000_000, "price": 180},
        {"symbol": "ETH", "volume_24h": 7_500_000, "open_interest": 7_500_000, "price": 4000},
    ]
    liquid = coach._build_liquid(tickers)
    assert liquid[0] == "BTC"
    assert "SOL" in liquid[:5]
    assert "ETH" in liquid[:5]
