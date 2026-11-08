"""Bounded genuine Alpaca/SEC acquisition; diagnostic only, never source authority.

Explicit SEC contact required. No financial writer, operational publication or
operator activation. Existing free-provider refusal reasons remain authoritative.
"""
import argparse
import json
import os
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "backend"))
from app.investment.alpaca_iex import Credentials
from app.investment.free_research_providers import FreeResearchBundle
from app.investment.free_research_transport import FreeResearchClient, ResearchRefused
from app.investment.quality_dips_v2_valuation import build_normalization_window


def inspect_free_research(*, symbol, contact, credentials_path, client_factory=FreeResearchClient,
                          bundle_factory=FreeResearchBundle):
    if (type(symbol) is not str or re.fullmatch(r"[A-Z]{1,8}", symbol) is None
            or type(contact) is not str
            or re.fullmatch(r"ProjectAtlas/1\.0 [A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", contact) is None
            or contact.lower().endswith(('.invalid', '.test', '.example', '@example.com', '@example.org', '@example.net'))):
        raise ResearchRefused("QD_REAL_SYMBOL_AND_SEC_CONTACT_REQUIRED")
    credentials = Credentials.load(credentials_path)
    now = lambda: datetime.now(UTC)
    client = client_factory(cache_root=REPO / "logs" / "diagnostics" / "qd-free-research-acquisition",
                            now=now, sec_user_agent=contact, credentials=credentials,
                            max_attempts=12, seconds=60)
    if client.domain != "TLS_PUBLIC_PROVIDER":
        raise ResearchRefused("QD_REAL_PROVIDER_TRANSPORT_REQUIRED")
    data = bundle_factory(client=client, now=now).load(symbol)
    if type(data) is not dict or data.get("paper_eligible") is not False:
        raise ResearchRefused("QD_RESEARCH_NOT_DIAGNOSTIC")
    # Only explicit target estimates may satisfy the existing V2/V3 window.
    # Derived ratios and daily closes are not independent fair-value targets.
    targets = ("target_low_price", "target_mean_price", "target_high_price")
    valuation = data["valuation"]
    target_available = {name: bool(valuation[name].availability) for name in targets}
    if any(target_available.values()):
        # Acquisition alone never attests independent issuer/source custody.
        raise ResearchRefused("QD_UNATTESTED_TARGET_PRICE_PRESENT")
    window = build_normalization_window([], now=now())
    if window["complete"] or window["source_count"] != 0:
        raise ResearchRefused("QD_UNEXPECTED_NORMALIZATION_ESTIMATES")
    return {"schema": "ATLAS_QD_FREE_RESEARCH_ACQUISITION_V1",
            "symbol": symbol, "transport": "TLS_PUBLIC_PROVIDER",
            "provider_receipt_count": len(data["receipts"]),
            "completed_daily_bar_count": len(data["bars"]),
            "fundamental_metric_count": len(data["fundamentals"]),
            "normalization_estimates_accepted": False,
            "explicit_target_availability": target_available,
            "normalization_source_count": window["source_count"],
            "refusals": data["refusals"],
            "operational_source_accepted": False,
            "paper_fill_authorized": False, "live_order_authorized": False}



def inspect_prices_only(*, symbol, contact, credentials_path, client_factory=FreeResearchClient,
                        bundle_factory=FreeResearchBundle):
    """ETF-compatible read-only price history, without claiming SEC fundamentals."""
    if type(symbol) is not str or re.fullmatch(r"[A-Z]{1,8}",symbol) is None:
        raise ResearchRefused('QD_REAL_SYMBOL_REQUIRED')
    # Price-only Alpaca acquisition makes no SEC request; SEC contact is optional.
    # Never accept arbitrary contact strings as a request header.
    if contact is not None and (type(contact) is not str or
            re.fullmatch(r"ProjectAtlas/1\.0 [A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",contact) is None):
        raise ResearchRefused('QD_SEC_CONTACT_FORMAT_REFUSED')
    credentials=Credentials.load(credentials_path)
    now=lambda: datetime.now(UTC)
    client=client_factory(cache_root=REPO/'logs'/'diagnostics'/'qd-free-research-acquisition',
                          now=now,sec_user_agent=contact or "ProjectAtlas/1.0 prices-only-no-sec",credentials=credentials,max_attempts=12,seconds=60)
    if client.domain!='TLS_PUBLIC_PROVIDER':
        raise ResearchRefused('QD_REAL_PROVIDER_TRANSPORT_REQUIRED')
    data=bundle_factory(client=client,now=now).load(symbol,prices_only=True)
    if (type(data) is not dict or data.get('paper_eligible') is not False
            or type(data.get('bars')) is not list or not data['bars']
            or type(data.get('receipts')) is not list or not data['receipts']):
        raise ResearchRefused('QD_PRICE_ONLY_EVIDENCE_INCOMPLETE_OR_UNAUTHORIZED')
    return {'schema':'ATLAS_QD_PRICE_ONLY_RESEARCH_V1','symbol':symbol,
            'completed_daily_bar_count':len(data['bars']),
            'provider_receipt_count':len(data['receipts']),
            'fundamentals_available':False,'independent_analyst_targets_verified':False,
            'operational_source_accepted':False,'paper_fill_authorized':False,'live_order_authorized':False}



def inspect_bounded_prices_only(*, symbols, contact, credentials_path,
                                inspect=inspect_prices_only):
    """Bounded independent price-history checks; partial failure is never success."""
    if (type(symbols) is not list or not 1 <= len(symbols) <= 8
            or any(type(symbol) is not str or re.fullmatch(r"[A-Z]{1,8}",symbol) is None
                   for symbol in symbols) or len(set(symbols))!=len(symbols)):
        raise ResearchRefused('QD_BOUNDED_UNIQUE_SYMBOLS_REQUIRED')
    results=[]
    for symbol in symbols:
        try:
            result=inspect(symbol=symbol,contact=contact,credentials_path=credentials_path)
            if (type(result) is not dict or result.get('schema')!='ATLAS_QD_PRICE_ONLY_RESEARCH_V1'
                    or result.get('symbol')!=symbol
                    or type(result.get('completed_daily_bar_count')) is not int
                    or result['completed_daily_bar_count']<=0
                    or type(result.get('provider_receipt_count')) is not int
                    or result['provider_receipt_count']<=0
                    or result.get('fundamentals_available') is not False
                    or result.get('independent_analyst_targets_verified') is not False
                    or result.get('operational_source_accepted') is not False
                    or result.get('paper_fill_authorized') is not False
                    or result.get('live_order_authorized') is not False):
                raise ResearchRefused('QD_PRICE_ONLY_RESULT_AUTHORITY_REFUSED')
            results.append(result)
        except (ValueError,OSError,KeyError,TypeError) as exc:
            # Stable categories only: never echo provider exception messages,
            # which can include URLs, request headers, or credentials.
            if isinstance(exc, OSError):
                category='PROVIDER_IO_FAILURE'
            elif isinstance(exc, (KeyError,TypeError)):
                category='MALFORMED_PROVIDER_DATA'
            elif str(exc)=='QD_PRICE_ONLY_RESULT_AUTHORITY_REFUSED':
                category='INVALID_RESEARCH_AUTHORITY_OR_SCHEMA'
            elif str(exc)=='QD_PRICE_ONLY_EVIDENCE_INCOMPLETE_OR_UNAUTHORIZED':
                category='MISSING_RESEARCH_EVIDENCE'
            else:
                category='PROVIDER_REFUSED_OR_UNAVAILABLE'
            results.append({'symbol':symbol,'status':'REFUSED','failure_category':category,
                            'operational_source_accepted':False,'paper_fill_authorized':False,
                            'live_order_authorized':False})
    refused=sum(row.get('status')=='REFUSED' for row in results)
    return {'schema':'ATLAS_QD_BOUNDED_PRICES_ONLY_V1','symbols':symbols,'results':results,
            'acquired_count':len(results)-refused,'refused_count':refused,
            'operational_source_accepted':False,'paper_fill_authorized':False,
            'live_order_authorized':False}


def inspect_bounded_universe(*, symbols, contact, credentials_path,
                             inspect=inspect_free_research):
    """Bounded multi-symbol genuine research; never converts research to fills."""
    if (type(symbols) is not list or not 1 <= len(symbols) <= 8
            or any(type(symbol) is not str or re.fullmatch(r"[A-Z]{1,8}", symbol) is None
                   for symbol in symbols)
            or len(set(symbols)) != len(symbols)):
        raise ResearchRefused("QD_BOUNDED_UNIQUE_SYMBOLS_REQUIRED")
    results = []
    for symbol in symbols:
        try:
            result = inspect(symbol=symbol, contact=contact, credentials_path=credentials_path)
            if (type(result) is not dict or result.get("symbol") != symbol
                    or result.get("schema") != "ATLAS_QD_FREE_RESEARCH_ACQUISITION_V1"
                    or result.get("transport") != "TLS_PUBLIC_PROVIDER"
                    or result.get("operational_source_accepted") is not False
                    or result.get("paper_fill_authorized") is not False
                    or result.get("live_order_authorized") is not False):
                raise ResearchRefused("QD_DIAGNOSTIC_AUTHORITY_PROMOTION_REFUSED")
            results.append(result)
        except (ValueError, OSError, KeyError, TypeError) as exc:
            results.append({"symbol": symbol, "status": "REFUSED", "reason": type(exc).__name__,
                            "operational_source_accepted": False, "paper_fill_authorized": False})
    return {"schema": "ATLAS_QD_BOUNDED_RESEARCH_UNIVERSE_V1", "symbols": symbols,
            "results": results, "acquired_count": sum("status" not in row for row in results),
            "refused_count": sum(row.get("status") == "REFUSED" for row in results),
            "operational_source_accepted": False,
            "paper_fill_authorized": False, "live_order_authorized": False}


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", default="MSFT")
    parser.add_argument("--prices-only", action="store_true", help="Read-only price history without SEC fundamentals")
    parser.add_argument("--symbols", nargs="+", help="Up to eight distinct real symbols; diagnostic only")
    parser.add_argument("--sec-contact", default=os.environ.get("ATLAS_SEC_CONTACT"))
    args = parser.parse_args(argv)
    try:
        if args.prices_only and args.symbols is not None:
            result = inspect_bounded_prices_only(symbols=args.symbols, contact=args.sec_contact,
                                                 credentials_path=REPO / "config/alpaca.env")
        elif args.prices_only:
            result = inspect_prices_only(symbol=args.symbol, contact=args.sec_contact,
                                         credentials_path=REPO / "config/alpaca.env")
        elif args.symbols is not None:
            result = inspect_bounded_universe(symbols=args.symbols, contact=args.sec_contact,
                                               credentials_path=REPO / "config/alpaca.env")
        else:
            result = inspect_free_research(symbol=args.symbol, contact=args.sec_contact,
                                           credentials_path=REPO / "config/alpaca.env")
    except (ValueError, OSError, KeyError, TypeError):
        result = {"schema": "ATLAS_QD_FREE_RESEARCH_ACQUISITION_V1", "status": "REFUSED",
                  "operational_source_accepted": False, "paper_fill_authorized": False,
                  "live_order_authorized": False}
        print(json.dumps(result, sort_keys=True))
        return 1
    print(json.dumps(result, sort_keys=True))
    # Partial acquisition is observable but not a successful full-universe scan.
    # Supervisors must never mistake refused symbols for a complete research cut.
    if result.get("schema") in ("ATLAS_QD_BOUNDED_RESEARCH_UNIVERSE_V1", "ATLAS_QD_BOUNDED_PRICES_ONLY_V1"):
        return 2 if result["refused_count"] else 0
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
