from __future__ import annotations

from app.investment.robinhood_universe_discovery import rows_from_rhj_assets


def test_rhj_assets_map_to_research_only_universe_rows():
    payload = {
        "assets": [
            {
                "tokenSymbol": "MSFT",
                "tokenName": "Microsoft • Robinhood Token",
                "status": "ASSET_STATUS_ACTIVE",
                "tradingCapabilities": {
                    "market": {
                        "whole": "TRADING_STATUS_TRADABLE",
                        "fractional": "TRADING_STATUS_TRADABLE",
                    }
                },
            },
            {
                "tokenSymbol": "NEW",
                "tokenName": "New Company • Robinhood Token",
                "status": "ASSET_STATUS_ACTIVE",
                "tradingCapabilities": {
                    "market": {
                        "whole": "TRADING_STATUS_UNTRADABLE",
                        "fractional": "TRADING_STATUS_UNTRADABLE",
                    }
                },
            },
        ]
    }
    rows = rows_from_rhj_assets(payload)
    assert rows[0]["symbol"] == "MSFT"
    assert rows[0]["name"] == "Microsoft"
    assert rows[0]["listing_state"] == "TRADABLE"
    assert rows[0]["tradable"] is True
    assert rows[0]["research_lane"] == "UNCLASSIFIED"
    assert rows[1]["listing_state"] == "ANNOUNCED"
    assert rows[1]["tradable"] is False


def test_rhj_assets_ignore_invalid_rows_without_inventing_symbols():
    rows = rows_from_rhj_assets({"assets": [{}, None, {"tokenSymbol": ""}]})
    assert rows == []
