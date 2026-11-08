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
from zoneinfo import ZoneInfo

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "backend"))

from app.investment.alpaca_iex import Credentials, IEXFeed, IEXRefused
from app.services.personal_paper_price_evidence import validate_stock_iex_quote
from scripts.observation_runtime.personal_windows_clock import LocalWindowsClock


def bounded_clock_iex_observation(*, symbol, seconds, credentials_path,
                                  clock_factory=LocalWindowsClock,
                                  feed_factory=IEXFeed, publication=None,
                                  operational_producer=None,
                                  expected_clock_source="time.windows.com,0x9"):
    if (type(symbol) is not str or not symbol.isascii() or not symbol.isalpha()
            or not symbol.isupper() or not 1 <= len(symbol) <= 8
            or type(seconds) is not int or not 1 <= seconds <= 60
            or type(expected_clock_source) is not str or not expected_clock_source
            or len(expected_clock_source) > 1024):
        raise ValueError("CLOCK_IEX_PROBE_ARGUMENTS_REFUSED")
    if operational_producer is not None:
        from app.services.quality_dips_current_producer import QualityDipsCurrentProducer
        if (type(operational_producer) is not QualityDipsCurrentProducer
                or operational_producer.execution_domain != "OPERATIONAL"
                or operational_producer.publication is not publication):
            raise ValueError("CLOCK_IEX_OPERATIONAL_PRODUCER_REQUIRED")
    if publication is not None:
        from app.services.paper_source_publication import QualityDipsSourcePublication
        if type(publication) is not QualityDipsSourcePublication:
            raise ValueError("CLOCK_IEX_NATIVE_PUBLICATION_REQUIRED")
    clock = None
    try:
        # The real clock gate precedes credential access and provider connection.
        # Explicit reviewed roster only. Never discover a new trust binding
        # from current settings or bypass the real clock before provider IO.
        clock = clock_factory(expected_source=expected_clock_source,
                              runtime_id="atlas-clock-iex-readonly-probe", lifetime=seconds + 30)
        clock.require_operational("atlas-clock-iex-readonly-probe")
        initial_operational_revision = None
        if publication is not None:
            # Refuse missing/stale/unaccepted native research *before* loading
            # credentials or opening a network connection. The source must
            # remain valid on every callback via evaluate_published_iex_v3_candidate.
            packet = (operational_producer.read_publication(0.2)
                      if operational_producer is not None else publication.read_current())
            if (type(packet) is not dict or packet.get("schema") != "QD_SCANNER_PUBLICATION_V1"
                    or type(packet.get("bundles")) is not list
                    or not any(type(bundle) is dict
                               and type(bundle.get("instrument")) is dict
                               and bundle["instrument"].get("symbol") == symbol
                               for bundle in packet["bundles"])):
                raise ValueError("CLOCK_IEX_PUBLISHED_SYMBOL_NOT_ENROLLED")
            if operational_producer is not None:
                initial_operational_revision = packet.get("revision")
                if type(initial_operational_revision) is not int or initial_operational_revision < 1:
                    raise ValueError("CLOCK_IEX_OPERATIONAL_REVISION_REQUIRED")
            matching = [bundle for bundle in packet["bundles"]
                        if type(bundle) is dict
                        and type(bundle.get("instrument")) is dict
                        and bundle["instrument"].get("symbol") == symbol]
            if (len(matching) != 1 or type(matching[0].get("observation")) is not dict
                    or matching[0]["observation"].get("symbol") != symbol
                    or matching[0]["observation"].get("evidence_class") != "FORWARD_COLLECTION"
                    or matching[0]["observation"].get("strategy_version") != "QUALITY_DIPS_V3"):
                raise ValueError("CLOCK_IEX_FORWARD_V3_PUBLICATION_REQUIRED")
        accepted = []
        research_checked = []
        callback_count = 0
        feed = feed_factory([symbol])
        if publication is not None:
            from app.services.personal_paper_iex_provider import PersonalPaperIEXProvider
            from app.services.personal_paper_strategy_signal import evaluate_published_iex_v3_candidate
            provider = PersonalPaperIEXProvider(feed)

        def on_quote(event):
            nonlocal callback_count
            # Callback is invoked only by the authenticated/subscribed IEX feed.
            clock.require_operational("atlas-clock-iex-readonly-probe")
            quote = {**event, "state": "FRESH",
                     "timestamp_basis": "PROVIDER_EVENT_TIMESTAMP"}
            evidence = validate_stock_iex_quote(
                quote, symbol=symbol, now=datetime.fromtimestamp(clock(), UTC))
            if accepted and evidence["provider_timestamp"] <= accepted[-1]:
                raise ValueError("CLOCK_IEX_PROVIDER_REPLAY_REFUSED")
            if publication is not None:
                if operational_producer is not None:
                    # A current publication at connection time is not enough:
                    # verify the accepted input authority and native archive
                    # again at the exact callback before evaluating the quote.
                    current = operational_producer.read_publication(0.2)
                    matching_now = [b for b in current.get("bundles", [])
                                    if type(b) is dict and type(b.get("instrument")) is dict
                                    and b["instrument"].get("symbol") == symbol]
                    if (current.get("revision") != initial_operational_revision
                            or type(current.get("revision")) is not int):
                        raise ValueError("CLOCK_IEX_OPERATIONAL_REVISION_CHANGED")
                    if (len(matching_now) != 1
                            or matching_now[0].get("observation", {}).get("evidence_class") != "FORWARD_COLLECTION"
                            or matching_now[0].get("observation", {}).get("strategy_version") != "QUALITY_DIPS_V3"):
                        raise ValueError("CLOCK_IEX_OPERATIONAL_SOURCE_CHANGED")
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
                        or Decimal(str(joined["ask"])) != Decimal(evidence["ask"])
                        or joined.get("bid_lots") != evidence["bid_lots"]
                        or joined.get("ask_lots") != evidence["ask_lots"]):
                    raise ValueError("CLOCK_IEX_PUBLICATION_QUOTE_CHANGED")
                research_checked.append(candidate["candidate"])
            accepted.append(evidence["provider_timestamp"])
            callback_count += 1

        credentials = Credentials.load(credentials_path)
        result = asyncio.run(feed.run(
            credentials, seconds=seconds, max_reconnects=0,
            on_fresh_quote=on_quote))
        if result["authenticated"] is not True or result["subscribed"] is not True:
            raise ValueError("CLOCK_IEX_PROVIDER_NOT_VERIFIED")
        if result["result"]["connection"] != "DISCONNECTED":
            raise ValueError("CLOCK_IEX_PROVIDER_NOT_DISCONNECTED")
        # An authenticated stream is not evidence that it delivered any quote.
        # Keep the no-quote result explicitly unqualified for forward research.
        if callback_count != len(accepted):
            raise ValueError("CLOCK_IEX_CALLBACK_ACCOUNTING_MISMATCH")
        exchange_local = datetime.fromtimestamp(clock(), UTC).astimezone(ZoneInfo("America/New_York"))
        # Calendar context is explanatory only, never a market-open authority.
        calendar_context = ("WEEKEND" if exchange_local.weekday() >= 5
                            else "WEEKDAY_HOURS_OR_HOLIDAY_UNVERIFIED")
        return {"schema": "ATLAS_CLOCK_IEX_READONLY_OBSERVATION_V1",
                "exchange_calendar_context": calendar_context,
                "exchange_local_date": exchange_local.date().isoformat(),
                "market_session_verified": False,
                "native_clock_verified": True,
                "clock_source_binding": expected_clock_source,
                "clock_uncertainty_ms": clock.evidence["bound_ms"],
                "authenticated": True, "subscribed": True,
                "connection_closed": True,
                "fresh_validated_quote_count": len(accepted),
                "published_research_checked_count": len(research_checked),
                "published_research_candidate_count": sum(x is True for x in research_checked),
                "native_publication_supplied": publication is not None,
                "forward_research_observed": (operational_producer is not None
                                              and bool(accepted) and bool(research_checked)),
                "operational_producer_verified": (operational_producer is not None
                                                  and bool(accepted) and bool(research_checked)),
                "forward_paper_session_qualified": False,
                "forward_financial_write_authorized": False,
                "live_order_authorized": False}
    finally:
        if clock is not None:
            clock.revoke()


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", default="MSFT")
    parser.add_argument("--seconds", type=int, default=10)
    parser.add_argument("--expected-clock-source", default="time.windows.com,0x9",
                        help="Exact separately reviewed NTP peer roster; never changes Windows settings")
    args = parser.parse_args(argv)
    try:
        report = bounded_clock_iex_observation(
            symbol=args.symbol, seconds=args.seconds,
            credentials_path=REPO / "config/alpaca.env",
            expected_clock_source=args.expected_clock_source)
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
