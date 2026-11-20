from datetime import UTC, datetime, timedelta

import pytest
from app.investment.free_research_providers import FreeResearchBundle

NOW = datetime(2026, 10, 29, 14, 0, tzinfo=UTC)
BAR = {
    "symbol": "MSFT",
    "bars": [
        {
            "t": "2026-10-28T04:00:00Z",
            "o": 10,
            "h": 12,
            "l": 9,
            "c": 11,
            "v": 100,
        }
    ],
    "next_page_token": None,
}
CALENDAR = [{"date": "2026-10-28", "open": "09:30", "close": "16:00"}]
ASSET = {
    "symbol": "MSFT",
    "id": "SYNTHETIC-ASSET",
    "class": "us_equity",
    "status": "active",
    "tradable": True,
    "fractionable": True,
    "exchange": "NASDAQ",
}


class ResearchClient:
    def __init__(self, receipts):
        self.receipts = iter(receipts)

    def get(self, url, *, ttl):
        retrieved_at = next(self.receipts)
        if "/assets/" in url:
            packet = ASSET
        elif "/bars?" in url:
            packet = BAR
        elif "/calendar?" in url:
            packet = CALENDAR
        else:
            raise AssertionError(f"Unexpected endpoint: {url}")
        return packet, {"retrieved_at": retrieved_at.isoformat()}


@pytest.mark.parametrize(("raw_age", "adjusted_age"), [(2, 1), (1, 3)])
def test_daily_bar_receipt_comes_from_oldest_raw_or_adjusted_price_cut(
    raw_age, adjusted_age
):
    raw_retrieved = NOW - timedelta(days=raw_age)
    adjusted_retrieved = NOW - timedelta(days=adjusted_age)
    calendar_retrieved = NOW
    bundle = FreeResearchBundle(
        client=ResearchClient(
            [
                NOW,
                raw_retrieved,
                adjusted_retrieved,
                calendar_retrieved,
            ]
        ),
        now=lambda: NOW,
    )

    result = bundle.load("MSFT", prices_only=True)

    assert len(result["bars"]) == 1
    assert result["bars"][0].retrieved_at == min(raw_retrieved, adjusted_retrieved)
    assert result["bars"][0].retrieved_at != calendar_retrieved
