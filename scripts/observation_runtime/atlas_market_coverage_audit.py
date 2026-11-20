"""Read-only multi-lane coverage inventory; never interprets discovery as paper eligibility."""
import json
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "backend"))
from app.investment.storage import ROBINHOOD_UNIVERSE_PATH, UNIVERSE_PATH


def audit_coverage(universe, registry):
    assets = universe.get("assets", []) if type(universe) is dict else []
    symbols = registry.get("symbols", {}) if type(registry) is dict else {}
    if type(assets) is not list or type(symbols) is not dict:
        raise ValueError("MARKET_COVERAGE_SHAPE_REFUSED")
    configured = {str(x.get("symbol", "")).upper() for x in assets if type(x) is dict and x.get("active", True) and x.get("symbol")}
    configured_types = Counter(str(x.get("asset_type", "UNKNOWN")) for x in assets if type(x) is dict and x.get("active", True) and x.get("symbol"))
    lanes = Counter(str(x.get("research_lane", "UNCLASSIFIED")) for x in symbols.values() if type(x) is dict)
    # Robinhood's RHJ catalog is a stock-token surface. A ticker collision
    # cannot prove the corresponding US brokerage listing is covered.
    token_sources = {"robinhood_official_rhj_assets"}
    token_only = sum(1 for x in symbols.values() if type(x) is dict
                     and x.get("source") in token_sources)
    tradable = sum(1 for x in symbols.values() if type(x) is dict
                   and x.get("listing_state") == "TRADABLE" and x.get("tradable") is True)
    # No authenticated US brokerage catalog has been enrolled in this audit.
    # Never route token symbols into an equity PAPER feed by name alone.
    return {"schema": "ATLAS_MARKET_COVERAGE_AUDIT_V1",
            "configured_active_symbol_count": len(configured),
            "configured_asset_types": dict(sorted(configured_types.items())),
            "robinhood_discovery_symbol_count": len(symbols),
            "robinhood_discovery_lanes": dict(sorted(lanes.items())),
            "robinhood_discovery_tradable_records": tradable,
            "robinhood_stock_token_source_records": token_only,
            "verified_us_brokerage_listings": 0,
            "verified_cross_catalog_symbol_matches": 0,
            "cross_catalog_symbol_matching_authorized": False,
            "configured_symbols_without_matching_token_ticker": len(configured - set(symbols)),
            "configured_symbols_missing_from_discovery": len(configured - set(symbols)),
            "robinhood_us_brokerage_universe_complete": False,
            "stock_token_catalog_is_us_brokerage_universe": False,
            "all_robinhood_markets_covered": False,
            "crypto_and_perpetuals_require_separate_provider_universes": True,
            "paper_execution_eligible_from_discovery": False,
            "live_order_authorized": False}


def main():
    def read(path):
        return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    print(json.dumps(audit_coverage(read(UNIVERSE_PATH), read(ROBINHOOD_UNIVERSE_PATH)), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
