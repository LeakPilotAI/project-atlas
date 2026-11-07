"""Explicit bounded native-clock + authenticated IEX quote acceptance probe.

No startup, publication, account creation, watermark, or financial writer.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "backend"))

from app.investment.alpaca_iex import Credentials, IEXFeed, IEXRefused
from app.services.personal_paper_price_evidence import validate_stock_iex_quote
from scripts.observation_runtime.personal_windows_clock import LocalWindowsClock


def bounded_clock_iex_observation(*, symbol, seconds, credentials_path,
                                  clock_factory=LocalWindowsClock,
                                  feed_factory=IEXFeed, publication=None):
    if (type(symbol) is not str or not symbol.isascii() or not symbol.isalpha()
            or not symbol.isupper() or not 1 <= len(symbol) <= 8
            or type(seconds) is not int or not 1 <= seconds <= 60):
        raise ValueError("CLOCK_IEX_PROBE_ARGUMENTS_REFUSED")
    if publication is not None:
        from app.services.paper_source_publication import QualityDipsSourcePublication
        if type(publication) is not QualityDipsSourcePublication:
            raise ValueError("CLOCK_IEX_NATIVE_PUBLICATION_REQUIRED")
    clock = None
    try:
        # The real clock gate precedes credential access and provider connection.
        clock = clock_factory(expected_source="time.windows.com,0x9",
                              runtime_id="atlas-clock-iex-readonly-probe", lifetime=seconds + 30)
        clock.require_operational("atlas-clock-iex-readonly-probe")
        if publication is not None:
            # Refuse missing/stale/unaccepted native research *before* loading
            # credentials or opening a network connection. The source must
            # remain valid on every callback via evaluate_published_iex_v3_candidate.
            packet = publication.read_current()
            if (type(packet) is not dict or packet.get("schema") != "QD_SCANNER_PUBLICATION_V1"
                    or type(packet.get("bundles")) is not list
                    or not any(type(bundle) is dict
                               and type(bundle.get("instrument")) is dict
                               and bundle["instrument"].get("symbol") == symbol
                               for bundle in packet["bundles"])):
                raise ValueError("CLOCK_IEX_PUBLISHED_SYMBOL_NOT_ENROLLED")
        accepted = []
        research_checked = []
        feed = feed_factory([symbol])
        if publication is not None:
            from app.services.personal_paper_iex_provider import PersonalPaperIEXProvider
            from app.services.personal_paper_strategy_signal import evaluate_published_iex_v3_candidate
            provider = PersonalPaperIEXProvider(feed)

        def on_quote(event):
            # Callback is invoked only by the authenticated/subscribed IEX feed.
            clock.require_operational("atlas-clock-iex-readonly-probe")
            quote = {**event, "state": "FRESH",
                     "timestamp_basis": "PROVIDER_EVENT_TIMESTAMP"}
            evidence = validate_stock_iex_quote(
                quote, symbol=symbol, now=datetime.fromtimestamp(clock(), UTC))
            if accepted and evidence["provider_timestamp"] <= accepted[-1]:
                raise ValueError("CLOCK_IEX_PROVIDER_REPLAY_REFUSED")
            if publication is not None:
                # This reads the accepted native source and the same connected
                # provider snapshot; no synthetic research dict or fill route.
                candidate = evaluate_published_iex_v3_candidate(
                    publication=publication, provider=provider, symbol=symbol,
                    now=datetime.fromtimestamp(clock(), UTC))
                # The publication must be evaluated against the *same* quote,
                # not a later quote sharing the source timestamp. Decimal
                # normalization allows equivalent numeric wire representations.
                from decimal import Decimal
                joined = candidate["quote_evidence"]
                if (joined["provider_timestamp"] != evidence["provider_timestamp"]
                        or Decimal(str(joined["bid"])) != Decimal(evidence["bid"])
                        or Decimal(str(joined["ask"])) != Decimal(evidence["ask"])):
                    raise ValueError("CLOCK_IEX_PUBLICATION_QUOTE_CHANGED")
                research_checked.append(candidate["candidate"])
            accepted.append(evidence["provider_timestamp"])

        credentials = Credentials.load(credentials_path)
        result = asyncio.run(feed.run(
            credentials, seconds=seconds, max_reconnects=0,
            on_fresh_quote=on_quote))
        if result["authenticated"] is not True or result["subscribed"] is not True:
            raise ValueError("CLOCK_IEX_PROVIDER_NOT_VERIFIED")
        if result["result"]["connection"] != "DISCONNECTED":
            raise ValueError("CLOCK_IEX_PROVIDER_NOT_DISCONNECTED")
        return {"schema": "ATLAS_CLOCK_IEX_READONLY_OBSERVATION_V1",
                "native_clock_verified": True,
                "clock_uncertainty_ms": clock.evidence["bound_ms"],
                "authenticated": True, "subscribed": True,
                "connection_closed": True,
                "fresh_validated_quote_count": len(accepted),
                "published_research_checked_count": len(research_checked),
                "published_research_candidate_count": sum(x is True for x in research_checked),
                "native_publication_supplied": publication is not None,
                "forward_financial_write_authorized": False,
                "live_order_authorized": False}
    finally:
        if clock is not None:
            clock.revoke()


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", default="MSFT")
    parser.add_argument("--seconds", type=int, default=10)
    args = parser.parse_args(argv)
    try:
        report = bounded_clock_iex_observation(
            symbol=args.symbol, seconds=args.seconds,
            credentials_path=REPO / "config/alpaca.env")
        print(json.dumps(report, sort_keys=True))
        return 0
    except (ValueError, IEXRefused, OSError):
        print(json.dumps({"schema": "ATLAS_CLOCK_IEX_READONLY_OBSERVATION_V1",
                          "status": "REFUSED", "reason": "CLOCK_OR_PROVIDER_GATE_REFUSED",
                          "forward_financial_write_authorized": False,
                          "live_order_authorized": False}, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
