from app.investment.robinhood_equity_quotes import RobinhoodEquityQuoteClient


def test_rhj_quote_uses_buy_side_ask_and_preserves_bid():
    payload = {
        "quotes": [{
            "tokenSymbol": "ADBE",
            "bid": "252.00",
            "ask": "252.20",
            "generatedAt": "2026-09-14T03:30:00Z",
        }]
    }
    row = RobinhoodEquityQuoteClient._parse_rhj("ADBE", payload)
    assert row is not None
    assert row["source"] == "robinhood_underlying_bid_ask"
    assert row["bid"] == 252.0
    assert row["ask"] == 252.2
    assert row["display_price"] == 252.2
    assert row["trigger_price"] == 252.2
    assert row["midpoint"] == 252.1
    assert row["effective_timestamp"] == "2026-09-14T03:30:00+00:00"


def test_classic_quote_uses_ask_when_available_but_timestamp_remains_visible():
    payload = {
        "last_trade_price": "251.50",
        "last_extended_hours_trade_price": "252.00",
        "bid_price": "252.05",
        "ask_price": "252.15",
        "updated_at": "2026-09-12T00:00:00Z",
    }
    row = RobinhoodEquityQuoteClient._parse_classic("ADBE", payload)
    assert row is not None
    assert row["display_price"] == 252.15
    assert row["trigger_price"] == 252.15
    assert row["source"] == "robinhood_public_quote"
    assert row["effective_timestamp"] == "2026-09-12T00:00:00+00:00"
