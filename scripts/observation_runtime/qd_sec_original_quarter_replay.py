"""Read-only cached SEC original-quarter corroboration for Quality Dips.

Direct SEC submissions, SEC Company Facts and original inline-XBRL must match
by issuer, accession, reporting period and reported diluted EPS. This check
does NOT attest corporate-action/share-basis, 12-quarter completeness, native
source authority, simulated fills, or real-money trading.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from app.investment.free_research_transport import decode, ResearchRefused
from app.investment.sec_filing_evidence import filing_rows, parse_original_filing

SCHEMA = "ATLAS_QD_SEC_ORIGINAL_QUARTER_CORROBORATION_V1"
CACHE_ROOT = Path("D:/Work/Project Atlas/logs/diagnostics/qd-free-research-acquisition")


def _cached(root, url, provider, *, now, max_bytes):
    root = Path(root)
    path = root / (hashlib.sha256(url.encode("utf-8")).hexdigest() + ".json")
    if (not root.is_dir() or root.is_symlink() or root.is_junction()
            or not path.is_file() or path.is_symlink() or path.is_junction()
            or not 0 < path.stat().st_size <= max_bytes):
        raise ValueError("QD_SEC_CACHED_EXACT_ORIGINAL_REQUIRED")
    record = decode(path.read_bytes())
    if (type(record) is not dict or set(record) != {
            "schema", "provider", "url", "domain", "retrieved_at", "sha256", "raw"}
            or record["schema"] != "FREE_RESEARCH_CACHE_V1"
            or record["provider"] != provider or record["url"] != url
            or record["domain"] != "TLS_PUBLIC_PROVIDER"
            or type(record["raw"]) is not str
            or type(record["sha256"]) is not str
            or re.fullmatch("[0-9a-f]{64}", record["sha256"]) is None):
        raise ValueError("QD_SEC_CACHE_ORIGIN_OR_PROVIDER_REFUSED")
    try:
        retrieved = datetime.fromisoformat(record["retrieved_at"])
    except (ValueError, TypeError):
        raise ValueError("QD_SEC_CACHE_RETRIEVAL_TIME_INVALID") from None
    if (retrieved.utcoffset() is None
            or not 0 <= (now - retrieved).total_seconds() <= 7*86400):
        raise ValueError("QD_SEC_CACHE_AGE_OR_TIME_REFUSED")
    raw = record["raw"].encode("utf-8")
    if (not raw or len(raw) > max_bytes
            or hashlib.sha256(raw).hexdigest() != record["sha256"]):
        raise ValueError("QD_SEC_CACHE_RAW_HASH_REFUSED")
    return raw, record["sha256"]


def _one(values, *, code):
    if len(values) != 1:
        raise ValueError(code)
    return values[0]


def inspect_original_quarter(*, symbol, cik, cache_root=CACHE_ROOT, now=None,
                             accession=None):
    now = datetime.now(UTC) if now is None else now
    if (type(symbol) is not str or re.fullmatch("[A-Z]{1,8}",symbol) is None
            or type(cik) is not str or re.fullmatch("[0-9]{10}",cik) is None
            or type(now) is not datetime or now.utcoffset() is None):
        raise ValueError("QD_SEC_EXPLICIT_SECURITY_AND_UTC_REQUIRED")
    if accession is not None and (type(accession) is not str
            or re.fullmatch(r"[0-9]{10}-[0-9]{2}-[0-9]{6}", accession) is None):
        raise ValueError("QD_SEC_EXACT_HISTORICAL_ACCESSION_REQUIRED")
    base = "https://data.sec.gov/"
    submission_url = base + "submissions/CIK" + cik + ".json"
    facts_url = base + "api/xbrl/companyfacts/CIK" + cik + ".json"
    submissions_raw, submissions_hash = _cached(
        cache_root, submission_url, "SEC_EDGAR", now=now, max_bytes=4*1024*1024)
    companyfacts_raw, facts_hash = _cached(
        cache_root, facts_url, "SEC_EDGAR", now=now, max_bytes=12*1024*1024)
    submissions, companyfacts = decode(submissions_raw), decode(companyfacts_raw)
    filings = filing_rows(submissions,cik=cik,symbol=symbol)
    refs = sorted((r for r in filings.values() if r["form"] == "10-Q"),
                  key=lambda r: (r["filed"],r["accession"]), reverse=True)
    matching = ([r for r in refs if r['accession'] == accession]
                if accession is not None else refs[:1])
    reference = _one(matching, code="QD_SEC_SUBMISSIONS_10Q_ACCESSION_REQUIRED")
    if str(companyfacts.get("cik", "")).zfill(10) != cik:
        raise ValueError("QD_SEC_COMPANYFACTS_ISSUER_MISMATCH")
    original_raw, original_hash = _cached(
        cache_root, reference["url"], "SEC_EDGAR_DOCUMENT",
        now=now, max_bytes=16*1024*1024)
    try:
        original = original_raw.decode("utf-8")
    except UnicodeError:
        raise ValueError("QD_SEC_ORIGINAL_DOCUMENT_ENCODING") from None
    parsed = parse_original_filing(original,reference,now=now)
    if parsed["sha256"] != original_hash:
        raise ValueError("QD_SEC_ORIGINAL_DOCUMENT_HASH_CHANGED")
    data = companyfacts.get("facts", {}).get("us-gaap", {})
    if type(data) is not dict:
        raise ValueError("QD_SEC_COMPANYFACTS_SCHEMA_REFUSED")
    def compare(concept,units,*,requires_quarter):
        rows = data.get(concept, {}).get("units", {}).get(units, [])
        if type(rows) is not list:
            raise ValueError("QD_SEC_COMPANYFACTS_CONCEPT_REQUIRED")
        candidates = [r for r in rows if (type(r) is dict
                      and r.get("accn") == reference["accession"]
                      and r.get("form") == reference["form"]
                      and r.get("filed") == reference["filed"]
                      and r.get("end") == reference["report_date"]
                      and type(r.get("start")) is str)]
        if requires_quarter:
            candidates = [r for r in candidates if
                70 <= (datetime.fromisoformat(r["end"])-datetime.fromisoformat(r["start"])).days + 1 <= 110]
        # Do not use amendments, YTD values, duplicate framed values, or
        # SEC's derived period extraction as substitutes for the original.
        by_period = {(r["start"],r["end"]) for r in candidates}
        periods = {(r["start"],r["end"]) for r in parsed["facts"] if
                   r["concept"] == concept and r["units"] == units
                   and r["end"] == reference["report_date"] and r["start"] is not None}
        shared = by_period & periods
        if len(shared) != 1:
            raise ValueError("QD_SEC_ORIGINAL_QUARTER_PERIOD_MISMATCH")
        start,end = next(iter(shared))
        recorded = [r for r in candidates if (r["start"],r["end"]) == (start,end)]
        direct = [r for r in parsed["facts"] if r["concept"] == concept
                  and r["units"] == units and r["start"] == start and r["end"] == end]
        value = _one(direct,code="QD_SEC_ORIGINAL_DUPLICATE_OR_MISSING_FACT")["value"]
        try:
            matched = (len(recorded) == 1 and all(
                type(r.get("val")) in (int, float, str)
                and Decimal(str(r["val"])) == Decimal(value)
                for r in recorded))
        except InvalidOperation:
            matched = False
        if not matched:
            raise ValueError("QD_SEC_ORIGINAL_COMPANYFACTS_VALUE_MISMATCH")
        if not Decimal(value).is_finite():
            raise ValueError("QD_SEC_ORIGINAL_NONFINITE_FACT")
        return {"start":start,"end":end,"value":value}
    eps = compare("EarningsPerShareDiluted","USD/shares",requires_quarter=True)
    shares = compare("WeightedAverageNumberOfDilutedSharesOutstanding","shares",requires_quarter=True)
    if (eps["start"],eps["end"]) != (shares["start"],shares["end"]) or Decimal(shares["value"]) <= 0:
        raise ValueError("QD_SEC_ORIGINAL_QUARTER_SHARE_PERIOD_MISMATCH")
    return {
        "schema": SCHEMA, "status": "DIRECT_SEC_ORIGINAL_AND_COMPANYFACTS_CORROBORATED",
        "symbol":symbol,"cik":cik,"accession":reference["accession"],
        "filed":reference["filed"],"period_start":eps["start"],
        "period_end":eps["end"],"diluted_eps_usd":eps["value"],
        "diluted_weighted_average_shares":shares["value"],
        "original_filing_url":reference["url"],
        "original_filing_sha256":original_hash,
        "companyfacts_sha256":facts_hash,"submissions_sha256":submissions_hash,
        "original_filing_and_companyfacts_matched":True,
        "share_adjustment_basis_accepted":False,
        "twelve_quarter_history_accepted":False,
        "operational_source_accepted":False,
        "financial_paper_authorized":False,
        "live_order_authorized":False,
        "external_provider_requests":0,
    }


def inspect_original_avgo_split(*, cache_root=CACHE_ROOT, now=None):
    """Strict original AVGO July 2024 split factor; NOT price-basis approval.

    Original public SEC 10-Q and separately published SEC Company Facts must
    agree by accession, exact corporate-action date and the reported ratio.
    A confirmed split increases the need for adjusted-price certification;
    it cannot itself assert that any Alpaca historical bars are split-safe.
    """
    from app.investment.sec_filing_evidence import _Inline

    now = datetime.now(UTC) if now is None else now
    symbol, cik, accession = "AVGO", "0001730168", "0001730168-24-000099"
    split_date, expected_ratio = "2024-07-12", Decimal(10)
    # This also checks original document DEI, CIK, GAAP quarterly EPS and
    # weighted diluted shares against independent SEC Company Facts.
    quarter = inspect_original_quarter(
        symbol=symbol, cik=cik, accession=accession,
        cache_root=cache_root, now=now)
    source_url = quarter["original_filing_url"]
    original, digest = _cached(cache_root, source_url, "SEC_EDGAR_DOCUMENT",
                               now=now, max_bytes=16*1024*1024)
    parser = _Inline()
    try:
        parser.feed(original.decode("utf-8"))
        parser.close()
    except UnicodeError:
        raise ValueError("QD_SEC_AVGO_SPLIT_INLINE_UTF8_REQUIRED") from None
    if parser.stack or not re.fullmatch(
            r"https?://fasb.org/us-gaap/202[34](?:-\d{2}-\d{2})?",
            parser.namespaces.get("us-gaap", "")):
        raise ValueError("QD_SEC_AVGO_SPLIT_STANDARD_NAMESPACE_REQUIRED")
    wanted = "us-gaap:StockholdersEquityNoteStockSplitConversionRatio1"
    facts = [n for n in parser.roots if
             n.tag.split(":")[-1] == "nonfraction"
             and n.attrs.get("name") == wanted]
    if len(facts) != 1:
        raise ValueError("QD_SEC_AVGO_SPLIT_EXACT_ORIGINAL_FACT_REQUIRED")
    fact = facts[0]
    if (fact.attrs.get("format", "").lower() != "ixt-sec:numwordsen"
            or fact.attrs.get("decimals") != "0"
            or fact.attrs.get("scale") != "0"
            or fact.attrs.get("sign", "") != ""
            or fact.attrs.get("continuedat") is not None
            or fact.attrs.get("unitref") != "number"
            or fact.attrs.get("xsi:nil") in ("true", "1")
            or fact.text().strip().lower() != "ten"):
        raise ValueError("QD_SEC_AVGO_SPLIT_ORIGINAL_TEN_TO_ONE_REQUIRED")
    context = [n for n in parser.roots if
               n.tag.split(":")[-1] == "context"
               and n.attrs.get("id") == fact.attrs.get("contextref")]
    units = [n for n in parser.roots if
             n.tag.split(":")[-1] == "unit"
             and n.attrs.get("id") == fact.attrs.get("unitref")]
    if len(context) != 1 or len(units) != 1:
        raise ValueError("QD_SEC_AVGO_SPLIT_CONTEXT_OR_UNIT_REQUIRED")
    ctx, unit = context[0], units[0]
    starts, ends = ctx.find("startdate"), ctx.find("enddate")
    identities = ctx.find("identifier")
    measures = unit.find("measure")
    if (len(starts) != 1 or len(ends) != 1
            or starts[0].text().strip() != split_date
            or ends[0].text().strip() != split_date
            or ctx.find("instant") or ctx.find("segment") or ctx.find("scenario")
            or len(identities) != 1
            or str(int(identities[0].text().strip())).zfill(10) != cik
            or identities[0].attrs.get("scheme") not in (
                "http://www.sec.gov/CIK", "https://www.sec.gov/CIK")
            or len(measures) != 1
            or measures[0].text().strip().lower() != "xbrli:pure"):
        raise ValueError("QD_SEC_AVGO_SPLIT_EFFECTIVE_CONTEXT_REQUIRED")
    companyfacts_url = "https://data.sec.gov/api/xbrl/companyfacts/CIK" + cik + ".json"
    facts_bytes, companyfacts_sha = _cached(
        cache_root, companyfacts_url, "SEC_EDGAR",
        now=now, max_bytes=12*1024*1024)
    packet = decode(facts_bytes)
    if str(packet.get("cik", "")).zfill(10) != cik:
        raise ValueError("QD_SEC_AVGO_SPLIT_ISSUER_REFUSED")
    rows = packet.get("facts", {}).get("us-gaap", {}).get(
        "StockholdersEquityNoteStockSplitConversionRatio1", {}).get(
        "units", {}).get("pure", [])
    if type(rows) is not list:
        raise ValueError("QD_SEC_AVGO_SPLIT_COMPANYFACTS_SCHEMA_REQUIRED")
    same_filing = [r for r in rows if type(r) is dict
                   and r.get("accn") == accession]
    if (len(same_filing) != 1
            or same_filing[0].get("form") != "10-Q"
            or same_filing[0].get("filed") != quarter["filed"]
            or same_filing[0].get("end") != split_date
            or same_filing[0].get("start") is not None
            or type(same_filing[0].get("val")) not in (int, float)
            or Decimal(str(same_filing[0]["val"])) != expected_ratio):
        raise ValueError("QD_SEC_AVGO_SPLIT_COMPANYFACTS_RATIO_CONFLICT")
    return {
        "schema": "ATLAS_AVGO_ORIGINAL_SEC_SPLIT_FACTOR_CORROBORATION_V1",
        "status": "ORIGINAL_SEC_SPLIT_RATIO_AND_DATE_VERIFIED",
        "symbol": symbol, "cik": cik, "accession": accession,
        "filing_date": quarter["filed"],
        "stock_split_effective_date": split_date,
        "forward_split_new_shares_per_old_share": 10,
        "split_factor_source": "ORIGINAL_10Q_INLINE_XBRL_AND_SEC_COMPANYFACTS",
        "original_document_url": source_url,
        "original_document_sha256": digest,
        "sec_companyfacts_sha256": companyfacts_sha,
        "original_sec_quarter_facts_also_corroborated": True,
        "pre_split_history_price_adjustment_verified": False,
        "historical_share_basis_operationally_accepted": False,
        "historical_valuation_12_anchors_accepted": False,
        "paper_financial_order_authorized": False,
        "real_money_order_authorized": False,
        "external_provider_requests": 0,
    }


def inspect_avgo_split_only_history(*, cache_root=CACHE_ROOT, now=None):
    """SEC split witness + bounded historical raw/split-only IEX cache comparison.

    Precisely validates returned price and volume conversion across a known
    original issuer action. A matching provider response does NOT certify
    continuous exchange-calendar coverage, provider rights, EPS share basis,
    executable quotes or financial PAPER orders. No network is performed.
    """
    from datetime import date as calendar_date
    from decimal import InvalidOperation
    from urllib.parse import urlencode
    from zoneinfo import ZoneInfo

    now = datetime.now(UTC) if now is None else now
    split = inspect_original_avgo_split(cache_root=cache_root, now=now)
    split_day = calendar_date.fromisoformat(split["stock_split_effective_date"])
    bounds = ("2021-11-03", "2026-11-07")
    source = "https://data.alpaca.markets/v2/stocks/AVGO/bars?"
    eastern = ZoneInfo("America/New_York")
    observed = {}
    receipts = {}
    for adjustment in ("raw", "split"):
        query = {"feed": "iex", "timeframe": "1Day", "adjustment": adjustment,
                 "sort": "asc", "start": bounds[0], "end": bounds[1],
                 "limit": 1000}
        rows = []
        sha = []
        seen_tokens = set()
        previous = None
        for page in range(3):
            raw, content_sha = _cached(
                cache_root, source + urlencode(query), "ALPACA_BASIC_IEX",
                now=now, max_bytes=4*1024*1024)
            packet = decode(raw)
            if (type(packet) is not dict
                    or set(packet) != {"symbol", "bars", "next_page_token"}
                    or packet["symbol"] != "AVGO"
                    or type(packet["bars"]) is not list
                    or not 1 <= len(packet["bars"]) <= 1000):
                raise ValueError("QD_AVGO_SPLIT_PRICE_EXACT_PAGE_REQUIRED")
            sha.append(content_sha)
            for record in packet["bars"]:
                if (type(record) is not dict or not
                        {"t", "o", "h", "l", "c", "v"} <= set(record)
                        or type(record["t"]) is not str):
                    raise ValueError("QD_AVGO_SPLIT_PRICE_BAR_SCHEMA")
                try:
                    stamp = datetime.fromisoformat(record["t"])
                except ValueError:
                    raise ValueError("QD_AVGO_SPLIT_PRICE_BAR_DATE") from None
                if stamp.tzinfo is None or stamp.utcoffset() is None:
                    raise ValueError("QD_AVGO_SPLIT_PRICE_UTC_REQUIRED")
                local = stamp.astimezone(eastern)
                day = local.date()
                if (local.hour or local.minute or local.second
                        or day.weekday() > 4 or not bounds[0] <= str(day) < bounds[1]
                        or previous is not None and stamp <= previous):
                    raise ValueError("QD_AVGO_SPLIT_PRICE_SESSION_ORDER")
                previous = stamp
                try:
                    values = {}
                    for k in ("o", "h", "l", "c", "v"):
                        value = record[k]
                        if type(value) not in (int, float, str):
                            raise InvalidOperation()
                        values[k] = Decimal(str(value))
                except (InvalidOperation, ValueError):
                    raise ValueError("QD_AVGO_SPLIT_PRICE_BAR_NUMERIC") from None
                o, h, l, c, v = (values[k] for k in ("o", "h", "l", "c", "v"))
                if (not all(n.is_finite() for n in values.values())
                        or min(o, h, l, c) <= 0 or v < 0
                        or v != v.to_integral_value()
                        or not l <= min(o, c) <= max(o, c) <= h):
                    raise ValueError("QD_AVGO_SPLIT_PRICE_BAR_OHLCV_REFUSED")
                rows.append((stamp, day, values))
                if len(rows) > 1600:
                    raise ValueError("QD_AVGO_SPLIT_PRICE_CAPACITY")
            token = packet["next_page_token"]
            if token is None:
                break
            if (type(token) is not str or not 1 <= len(token) <= 2048
                    or token in seen_tokens or page >= 2):
                raise ValueError("QD_AVGO_SPLIT_PRICE_PAGINATION_REFUSED")
            seen_tokens.add(token)
            query["page_token"] = token
        else:
            raise ValueError("QD_AVGO_SPLIT_PRICE_PAGINATION_UNFINISHED")
        if len(rows) < 4:
            raise ValueError("QD_AVGO_SPLIT_PRICE_INSUFFICIENT_SESSIONS")
        observed[adjustment] = rows
        receipts[adjustment] = sha
    raw_rows, split_rows = observed["raw"], observed["split"]
    if (len(raw_rows) != len(split_rows)
            or [r[0] for r in raw_rows] != [r[0] for r in split_rows]):
        raise ValueError("QD_AVGO_SPLIT_PRICE_COVERAGE_MISMATCH")
    pre = post = 0
    maximum_difference = Decimal(0)
    tolerance = Decimal("0.006")
    for (_, day, unadjusted), (_, _, adjusted) in zip(
            raw_rows, split_rows, strict=True):
        factor = Decimal(10 if day <= split_day else 1)
        if factor == 10:
            pre += 1
        else:
            post += 1
        if adjusted["v"] != unadjusted["v"] * factor:
            raise ValueError("QD_AVGO_SPLIT_VOLUME_FACTOR_MISMATCH")
        for k in ("o", "h", "l", "c"):
            difference = abs(unadjusted[k] / factor - adjusted[k])
            if difference > tolerance:
                raise ValueError("QD_AVGO_SPLIT_PRICE_FACTOR_MISMATCH")
            maximum_difference = max(maximum_difference, difference)
    if not pre or not post:
        raise ValueError("QD_AVGO_SPLIT_DATE_NOT_BRACKETED")
    # An independent provider corporate-action snapshot is required in
    # addition to SEC XBRL and a coherent raw/split-adjusted price ratio.
    # This confirms the declared event but is NOT entitlement/completeness.
    action_query = {"symbols": "AVGO", "start": bounds[0], "end": bounds[1],
                    "region": "us", "limit": 1000, "data_quality": "all"}
    action_url = ("https://data.alpaca.markets/v1/corporate-actions?"
                  + urlencode(action_query))
    action_raw, action_sha = _cached(cache_root, action_url,
                                     "ALPACA_BASIC_IEX", now=now,
                                     max_bytes=200_000)
    actions = decode(action_raw)
    if (type(actions) is not dict
            or set(actions) != {"corporate_actions", "next_page_token"}
            or actions["next_page_token"] is not None
            or type(actions["corporate_actions"]) is not dict
            or set(actions["corporate_actions"]) != {
                "forward_splits", "cash_dividends", "stock_mergers"}):
        raise ValueError("QD_AVGO_SPLIT_PROVIDER_ACTION_SNAPSHOT_REQUIRED")
    categories = actions["corporate_actions"]
    if (any(type(v) is not list or len(v) > 1000
            for v in categories.values())
            or len(categories["forward_splits"]) != 1):
        raise ValueError("QD_AVGO_SPLIT_PROVIDER_ACTION_SCOPE_REFUSED")
    event = categories["forward_splits"][0]
    if (type(event) is not dict
            or type(event.get("id")) is not str
            or re.fullmatch("[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}",
                            event["id"]) is None
            or event.get("symbol") != "AVGO"
            or type(event.get("new_rate")) not in (int, float)
            or type(event.get("old_rate")) not in (int, float)
            or Decimal(str(event["new_rate"])) != Decimal(10)
            or Decimal(str(event["old_rate"])) != Decimal(1)
            or event.get("payable_date") != str(split_day)
            or event.get("ex_date") != "2024-07-15"
            or event.get("due_bill_redemption_date") != "2024-07-15"
            or event.get("process_date") != "2024-07-15"
            or event.get("record_date") != "2024-07-11"):
        raise ValueError("QD_AVGO_SPLIT_ORIGINAL_PROVIDER_ACTION_MISMATCH")
    if not {"2024-07-12", event["ex_date"]} <= {
            str(r[1]) for r in raw_rows}:
        raise ValueError("QD_AVGO_SPLIT_EXDATE_SESSIONS_MISSING")
    # Exact official provider calendar interval must cover every returned bar
    # and contain NO omitted or extra completed trading sessions. A provider
    # calendar is not an independent exchange or legal-data-rights certificate.
    from app.investment.free_research_providers import calendar_sessions

    calendar_url = ("https://paper-api.alpaca.markets/v2/calendar?"
                    + urlencode({"start": bounds[0], "end": bounds[1]}))
    calendar_bytes, calendar_sha = _cached(cache_root, calendar_url,
                                          "ALPACA_BASIC_IEX", now=now,
                                          max_bytes=2_000_000)
    sessions = calendar_sessions(decode(calendar_bytes))
    expected = {day for day, (opened, closed) in sessions.items()
                if bounds[0] <= str(day) < bounds[1]
                and opened < closed <= now}
    actual = {row[1] for row in raw_rows}
    if (not expected or expected != actual
            or len(raw_rows) != len(expected)
            or len(expected) > 1600
            or any(not bounds[0] <= str(day) < bounds[1] for day in sessions)):
        raise ValueError("QD_AVGO_SPLIT_PROVIDER_CALENDAR_COVERAGE_REFUSED")
    return {
        "schema": "ATLAS_AVGO_SEC_SPLIT_ONLY_PRICE_PAIR_REPLAY_V1",
        "status": "RETURNED_PROVIDER_RAW_AND_SPLIT_PRICE_PAIRS_CORROBORATED",
        "sec_original_split_sha256": split["original_document_sha256"],
        "sec_original_split_date": split["stock_split_effective_date"],
        "sec_original_new_shares_per_old_share": 10,
        "source": "ALPACA_BASIC_IEX_HISTORICAL_BARS",
        "request_adjustment_pair": ["raw", "split"],
        "source_content_sha256_by_adjustment": receipts,
        "provider_corporate_action_sha256": action_sha,
        "provider_original_split_event_corroborated": True,
        "provider_split_ex_date": event["ex_date"],
        "provider_non_split_actions_seen": {
            "cash_dividends": len(categories["cash_dividends"]),
            "stock_mergers": len(categories["stock_mergers"]),
        },
        "matching_returned_daily_bar_count": len(raw_rows),
        "pre_split_returned_bars": pre,
        "post_split_returned_bars": post,
        "first_returned_session": str(raw_rows[0][1]),
        "last_returned_session": str(raw_rows[-1][1]),
        "maximum_split_adjustment_rounding_difference_usd": str(maximum_difference),
        "returned_provider_sessions_match": True,
        "provider_calendar_sha256": calendar_sha,
        "provider_calendar_expected_completed_sessions": len(expected),
        "provider_calendar_session_coverage_verified": True,
        "complete_exchange_calendar_sessions_verified": False,
        "all_corporate_actions_covered": False,
        "provider_price_data_rights_accepted": False,
        "split_adjusted_share_basis_for_historical_valuation_accepted": False,
        "twelve_historical_valuation_anchors_accepted": False,
        "native_source_publisher_enrolled": False,
        "financial_paper_order_authorized": False,
        "real_money_order_authorized": False,
        "network_requests": 0,
    }


def reconcile_avgo_original_eps_split_basis(
        original_quarters, split_price_proof):
    """Research-only 2024 AVGO SEC EPS/share translation to post-split units.

    This is NOT a SEC-reported restatement, GAAP audit, accepted valuation,
    native financial issuer, or a substitute for a full 15-quarter witness
    chain. Original, separately reported figures are retained without edits.
    """
    from datetime import timedelta

    identity = (
        ("0001730168-24-000023", "2023-10-30", "2024-02-04", "2024-03-14"),
        ("0001730168-24-000080", "2024-02-05", "2024-05-05", "2024-06-13"),
        ("0001730168-24-000099", "2024-05-06", "2024-08-04", "2024-09-11"),
    )
    if (type(original_quarters) is not list or len(original_quarters) != 3
            or type(split_price_proof) is not dict
            or split_price_proof.get("schema") !=
                "ATLAS_AVGO_SEC_SPLIT_ONLY_PRICE_PAIR_REPLAY_V1"
            or split_price_proof.get("sec_original_split_date") != "2024-07-12"
            or type(split_price_proof.get("sec_original_new_shares_per_old_share")) is not int
            or split_price_proof["sec_original_new_shares_per_old_share"] != 10
            or split_price_proof.get("provider_original_split_event_corroborated") is not True
            or split_price_proof.get("provider_calendar_session_coverage_verified") is not True
            or split_price_proof.get("provider_split_ex_date") != "2024-07-15"
            or split_price_proof.get("matching_returned_daily_bar_count") != 1258
            or split_price_proof.get("pre_split_returned_bars") != 675
            or split_price_proof.get("post_split_returned_bars") != 583
            or split_price_proof.get("provider_calendar_expected_completed_sessions") != 1258
            or any(split_price_proof.get(flag) is not False for flag in (
                "complete_exchange_calendar_sessions_verified",
                "provider_price_data_rights_accepted",
                "split_adjusted_share_basis_for_historical_valuation_accepted",
                "twelve_historical_valuation_anchors_accepted",
                "financial_paper_order_authorized",
                "real_money_order_authorized"))):
        raise ValueError("QD_AVGO_SPLIT_EPS_ORIGIN_PRICE_PROOF_REQUIRED")
    hashes = ("sec_original_split_sha256", "provider_corporate_action_sha256",
              "provider_calendar_sha256")
    if any(type(split_price_proof.get(k)) is not str
           or re.fullmatch("[0-9a-f]{64}", split_price_proof[k]) is None
           for k in hashes):
        raise ValueError("QD_AVGO_SPLIT_EPS_SOURCE_HASHES_REQUIRED")
    factor = Decimal(10)
    cut = datetime.fromisoformat("2024-07-12").date()
    translated = []
    for index, (report, expected) in enumerate(zip(original_quarters, identity, strict=True)):
        acc, start, end, filed = expected
        if (type(report) is not dict
                or report.get("schema") != SCHEMA
                or report.get("symbol") != "AVGO"
                or report.get("cik") != "0001730168"
                or tuple(report.get(k) for k in (
                    "accession", "period_start", "period_end", "filed")) != expected
                or report.get("original_filing_and_companyfacts_matched") is not True
                or any(report.get(flag) is not False for flag in (
                    "share_adjustment_basis_accepted", "twelve_quarter_history_accepted",
                    "operational_source_accepted", "financial_paper_authorized",
                    "live_order_authorized"))
                or type(report.get("original_filing_sha256")) is not str
                or re.fullmatch("[0-9a-f]{64}", report["original_filing_sha256"]) is None
                or type(report.get("companyfacts_sha256")) is not str
                or re.fullmatch("[0-9a-f]{64}", report["companyfacts_sha256"]) is None
                or type(report.get("diluted_eps_usd")) is not str
                or type(report.get("diluted_weighted_average_shares")) is not str):
            raise ValueError("QD_AVGO_SPLIT_EPS_EXACT_ORIGINAL_QUARTER_REQUIRED")
        try:
            eps = Decimal(report["diluted_eps_usd"])
            shares = Decimal(report["diluted_weighted_average_shares"])
        except InvalidOperation:
            raise ValueError("QD_AVGO_SPLIT_EPS_ORIGINAL_FACT_INVALID") from None
        if (not eps.is_finite() or not shares.is_finite()
                or shares != shares.to_integral_value()
                or not -1000 < eps < 1000
                or (index < 2 and not Decimal(300_000_000) <= shares <= Decimal(600_000_000))
                or (index == 2 and not Decimal(3_000_000_000) <= shares <= Decimal(6_000_000_000))
                or (index < 2 and not datetime.fromisoformat(end).date() <
                    datetime.fromisoformat(filed).date() < cut)
                or (index == 2 and not datetime.fromisoformat(start).date() < cut <
                    datetime.fromisoformat(end).date() <
                    datetime.fromisoformat(filed).date())):
            raise ValueError("QD_AVGO_SPLIT_EPS_SHARE_PERIOD_OR_SCALE_REFUSED")
        multiplier = factor if index < 2 else Decimal(1)
        adjusted_eps = eps / multiplier
        adjusted_shares = shares * multiplier
        if (adjusted_eps * adjusted_shares != eps * shares
                or not Decimal(3_000_000_000) <= adjusted_shares <= Decimal(6_000_000_000)):
            raise ValueError("QD_AVGO_SPLIT_EPS_VALUE_OR_COUNT_INVARIANT")
        translated.append({
            "original_sec_accession": acc,
            "reported_period_start": start,
            "reported_period_end": end,
            "original_filing_sha256": report["original_filing_sha256"],
            "sec_companyfacts_sha256": report["companyfacts_sha256"],
            "as_reported_diluted_eps_usd": str(eps),
            "as_reported_weighted_diluted_shares": str(shares),
            "split_equivalent_eps_usd_research_only": str(adjusted_eps),
            "split_equivalent_weighted_shares_research_only": str(adjusted_shares),
            "derived_new_shares_per_reported_share": int(multiplier),
            "transformed_not_sec_reported": multiplier == factor,
        })
    for older, newer in zip(translated, translated[1:]):
        if (datetime.fromisoformat(newer["reported_period_start"]).date() !=
                datetime.fromisoformat(older["reported_period_end"]).date() +
                timedelta(days=1)):
            raise ValueError("QD_AVGO_SPLIT_EPS_NONCONSECUTIVE_QUARTERS")
    if Decimal(translated[2]["as_reported_diluted_eps_usd"]) >= 0:
        raise ValueError("QD_AVGO_SPLIT_EPS_ORIGINAL_LOSS_MUST_BE_RETAINED")
    return {
        "schema": "ATLAS_AVGO_DIRECT_SEC_EPS_SPLIT_EQUIVALENCE_RESEARCH_V1",
        "status": "ORIGINAL_EPS_AND_SPLIT_EQUIVALENT_UNITS_RECONCILED",
        "issuer": "AVGO", "cik": "0001730168",
        "split_effective_date": str(cut),
        "original_split_and_prices_corroborated": True,
        "split_price_and_calendar_origin_hashes": {
            k: split_price_proof[k] for k in hashes},
        "quarter_count": len(translated),
        "quarters": translated,
        "method": "RESEARCH_ONLY_EXACT_10_FOR_1_PER_SHARE_CONVERSION",
        "original_sec_gaap_values_preserved": True,
        "derived_values_are_not_restatements_of_original_sec_filings": True,
        "full_15_quarter_earnings_witness_chain_complete": False,
        "entire_historical_eps_price_basis_accepted": False,
        "operational_qd_financial_source_enrolled": False,
        "financial_paper_authorized": False,
        "live_order_authorized": False,
        "network_requests": 0,
    }


def inspect_avgo_original_eps_split_basis(*, cache_root=CACHE_ROOT, now=None):
    """Apply verified SEC original quarter witnesses to corroborated split prices."""
    now = datetime.now(UTC) if now is None else now
    split = inspect_avgo_split_only_history(cache_root=cache_root, now=now)
    quarters = [
        inspect_original_quarter(
            symbol="AVGO", cik="0001730168", accession=accession,
            cache_root=cache_root, now=now)
        for accession in (
            "0001730168-24-000023",
            "0001730168-24-000080",
            "0001730168-24-000099",
        )
    ]
    return reconcile_avgo_original_eps_split_basis(quarters, split)


def assess_avgo_split_research_multiples(quarter_chain, split_proof, session_prices, *, now):
    """Independent read-only diagnostic; NEVER a financial valuation publisher.

    Requires exactly fifteen independently documented consecutive as-reported
    quarters, explicitly derived post-split EPS and matching split-only
    sessions. Prices are measured after every trailing quarter is published.
    Existing HistoricalEarningsMultipleV1 5..60x cap is reported, not relaxed.
    """
    from bisect import bisect_right
    from datetime import date, timedelta

    if (type(quarter_chain) is not dict
            or quarter_chain.get("schema") !=
                "ATLAS_AVGO_15_ORIGINAL_SEC_QUARTERS_AND_SPLIT_ONLY_RESEARCH_V1"
            or quarter_chain.get("symbol") != "AVGO"
            or quarter_chain.get("cik") != "0001730168"
            or quarter_chain.get("source_origin_documents") != 15
            or quarter_chain.get("quarterly_original_documents_consecutive") is not True
            or quarter_chain.get("original_sec_reporting_values_preserved") is not True
            or quarter_chain.get("split_adjusted_equivalents_derived_not_sec_reported") is not True
            or quarter_chain.get("actual_valuation_anchors_accepted") != 0
            or quarter_chain.get("price_to_eps_historical_multiple_approved") is not False
            or quarter_chain.get("provider_data_rights_accepted") is not False
            or quarter_chain.get("financial_paper_start_authorized") is not False
            or quarter_chain.get("real_money_trading_authorized") is not False
            or type(split_proof) is not dict
            or split_proof.get("schema") !=
                "ATLAS_AVGO_SEC_SPLIT_ONLY_PRICE_PAIR_REPLAY_V1"
            or split_proof.get("provider_calendar_session_coverage_verified") is not True
            or split_proof.get("provider_original_split_event_corroborated") is not True
            or split_proof.get("sec_original_new_shares_per_old_share") != 10
            or split_proof.get("sec_original_split_date") != "2024-07-12"
            or split_proof.get("matching_returned_daily_bar_count") != 1258
            or split_proof.get("provider_price_data_rights_accepted") is not False
            or split_proof.get("financial_paper_order_authorized") is not False
            or quarter_chain.get("original_split_sha256") !=
                split_proof.get("sec_original_split_sha256")
            or quarter_chain.get("alpaca_calendar_sha256") !=
                split_proof.get("provider_calendar_sha256")
            or quarter_chain.get("alpaca_split_corporate_action_sha256") !=
                split_proof.get("provider_corporate_action_sha256")):
        raise ValueError("QD_AVGO_RESEARCH_SPLIT_AND_ORIGIN_PROOFS_REQUIRED")
    quarters = quarter_chain.get("original_sec_quarters")
    windows = quarter_chain.get("possible_unapproved_trailing_four_quarter_research_windows")
    if (type(quarters) is not list or len(quarters) != 15
            or type(windows) is not list or len(windows) != 12
            or type(session_prices) is not dict or len(session_prices) != 1258):
        raise ValueError("QD_AVGO_RESEARCH_COMPLETE_15_Q_AND_1258_PRICES_REQUIRED")
    now_date = now.date()
    last_end = None
    previous_publication = None
    eps_values = []
    accession_keys = set()
    original_hashes = []
    split_day = date(2024, 7, 12)
    for i, q in enumerate(quarters):
        if (type(q) is not dict
                or q.get("original_form") not in ("10-Q", "8-K")
                or type(q.get("original_evidence_sha256")) is not str
                or re.fullmatch("[0-9a-f]{64}", q["original_evidence_sha256"]) is None
                or type(q.get("accession")) is not str
                or not re.fullmatch(r"0001730168-\d{2}-\d{6}", q["accession"])
                or q["accession"] in accession_keys):
            raise ValueError("QD_AVGO_RESEARCH_QUARTER_ORIGINAL_IDENTITY_REFUSED")
        accession_keys.add(q["accession"])
        original_hashes.append(q["original_evidence_sha256"])
        try:
            start, end, filed = (
                date.fromisoformat(q[k]) for k in (
                    "period_start", "period_end", "original_sec_filing_date"))
            reported = Decimal(q["as_reported_diluted_eps"])
            reported_shares = Decimal(q["as_reported_diluted_shares"])
            equivalent = Decimal(q["research_derived_post_split_equivalent_eps"])
            eq_shares = Decimal(q["research_derived_post_split_equivalent_shares"])
        except (ValueError, TypeError, KeyError, InvalidOperation):
            raise ValueError("QD_AVGO_RESEARCH_QUARTER_NUMERIC_OR_DATE_REFUSED") from None
        factor = 10 if filed < split_day else 1
        if (q.get("applied_research_conversion_factor") != factor
                or not all(v.is_finite() for v in (
                    reported, reported_shares, equivalent, eq_shares))
                or reported_shares <= 0 or reported_shares != reported_shares.to_integral_value()
                or equivalent != reported / factor
                or eq_shares != reported_shares * factor
                or not Decimal(3_000_000_000) < eq_shares < Decimal(6_000_000_000)
                or not 70 <= (end - start).days+1 <= 110
                or filed < end or filed > now_date
                or last_end is not None and start != last_end + timedelta(days=1)
                or previous_publication is not None and filed <= previous_publication
                or (i % 4 == 3) != (q["original_form"] == "8-K")):
            raise ValueError("QD_AVGO_RESEARCH_PERIOD_SPLIT_OR_PUBLISH_ORDER_REFUSED")
        last_end = end
        previous_publication = filed
        eps_values.append(equivalent)
    if (quarters[0]["period_start"] != "2022-10-31"
            or quarters[-1]["period_end"] != "2026-08-02"
            or quarter_chain.get("first_period_start") != "2022-10-31"
            or quarter_chain.get("last_period_end") != "2026-08-02"):
        raise ValueError("QD_AVGO_RESEARCH_QUARTER_CHAIN_SPAN_REFUSED")
    parsed_prices = {}
    for d, value in session_prices.items():
        if type(d) is not str:
            raise ValueError("QD_AVGO_RESEARCH_PRICE_DATE_REFUSED")
        try:
            day = date.fromisoformat(d)
            px = Decimal(str(value))
        except (ValueError, TypeError, InvalidOperation):
            raise ValueError("QD_AVGO_RESEARCH_PRICE_VALUE_REFUSED") from None
        if (day in parsed_prices or not px.is_finite() or px <= 0
                or day < date(2021, 11, 3) or day > now_date):
            raise ValueError("QD_AVGO_RESEARCH_PRICE_SCOPE_REFUSED")
        parsed_prices[day] = px
    session_dates = sorted(parsed_prices)
    observations = []
    for i in range(3, len(quarters)):
        segment = quarters[i-3:i+1]
        cut = max(date.fromisoformat(q["original_sec_filing_date"]) for q in segment)
        j = bisect_right(session_dates, cut)
        if j == len(session_dates):
            raise ValueError("QD_AVGO_RESEARCH_NEXT_SESSION_MISSING")
        day = session_dates[j]
        if (day - cut).days > 7 or day > now_date:
            raise ValueError("QD_AVGO_RESEARCH_PUBLICATION_TO_PRICE_LAG")
        trailing = sum(eps_values[i-3:i+1], Decimal(0))
        if trailing <= 0:
            raise ValueError("QD_AVGO_RESEARCH_NEGATIVE_TRAILING_EPS_REFUSED")
        expected_window = windows[i-3]
        if (type(expected_window) is not dict
                or expected_window.get("period_end") != segment[-1]["period_end"]
                or Decimal(expected_window.get(
                    "derived_four_quarter_eps_on_split_comparable_basis", "NaN")) != trailing):
            raise ValueError("QD_AVGO_RESEARCH_TTM_EPS_CORROBORATION_REFUSED")
        multiple = parsed_prices[day] / trailing
        observations.append({
            "original_sec_report_end": segment[-1]["period_end"],
            "last_required_sec_publication": str(cut),
            "first_following_completed_iex_session": str(day),
            "split_only_iex_close_usd": str(parsed_prices[day]),
            "derived_split_equivalent_trailing_eps_usd": str(trailing),
            "observed_derived_pe_multiple": str(multiple),
            "within_existing_v1_5_to_60_multiple_bounds":
                Decimal(5) <= multiple <= Decimal(60),
        })
    span_start = date.fromisoformat(observations[0]["original_sec_report_end"])
    span_end = date.fromisoformat(observations[-1]["original_sec_report_end"])
    months = (span_end.year-span_start.year)*12+span_end.month-span_start.month
    if len(observations) != 12 or months < 33:
        raise ValueError("QD_AVGO_RESEARCH_ANCHOR_SPAN_REFUSED")
    noncompliant = [r for r in observations if not
                    r["within_existing_v1_5_to_60_multiple_bounds"]]
    return {
        "schema": "ATLAS_AVGO_SPLIT_AWARE_HISTORICAL_PE_DIAGNOSTIC_V1",
        "status": ("RESEARCH_VALUATION_REFUSED_EXISTING_MULTIPLE_LIMITS"
                   if noncompliant else "RESEARCH_OBSERVATIONS_WITHIN_BOUNDS_ONLY"),
        "original_sec_evidence_count": 15,
        "hypothetical_trailing_earnings_observations": len(observations),
        "observations_exceeding_existing_v1_pe_bounds": len(noncompliant),
        "historical_v1_pe_bounds": ["5", "60"],
        "min_observed_pe": str(min(Decimal(r["observed_derived_pe_multiple"]) for r in observations)),
        "max_observed_pe": str(max(Decimal(r["observed_derived_pe_multiple"]) for r in observations)),
        "observations": observations,
        "original_sec_filing_hashes": original_hashes,
        "original_reporting_retained": True,
        "published_at_or_before_historical_trade_day": True,
        "financial_valuation_anchors_approved": 0,
        "data_rights_accepted": False,
        "native_source_issuer_accepted": False,
        "financial_paper_authorized": False,
        "live_trading_authorized": False,
        "research_only": True,
        "network_requests": 0,
    }


def inspect_avgo_split_research_valuation(*, cache_root=CACHE_ROOT,
                                          now=None):
    """No-network original-source pinned AVGO P/E diagnostic. No issuer authority.

    Pinning a previously independently corroborated SEC quarter receipt guards
    against silently substituting new EPS or altering archived GAAP facts.
    Split-only bars and SEC action/calendar are freshly checked from cache.
    """
    from urllib.parse import urlencode
    from app.investment.free_research_transport import decode
    from app.investment.market_hours import ET

    now = datetime.now(UTC) if now is None else now
    root = Path(cache_root)
    evidence = (root.parent / "qd-original-sec-quarter-corroboration"
                / "direct-sec-avgo-15-original-quarters-split-comparable-research-20261110.json")
    if (not evidence.is_file() or evidence.is_symlink()
            or evidence.is_junction() or not 0 < evidence.stat().st_size < 20000):
        raise ValueError("QD_AVGO_RESEARCH_PINNED_ORIGINAL_EVIDENCE_MISSING")
    document = evidence.read_bytes()
    original_digest = hashlib.sha256(document).hexdigest()
    if original_digest != (
            "377c62672367aa3b83e4b6118eb6be928a7f7e311bf48aac1a3400a52cf163a2"):
        raise ValueError("QD_AVGO_RESEARCH_ORIGINAL_SEC_CHAIN_PIN_MISMATCH")
    chain = decode(document)
    split_proof = inspect_avgo_split_only_history(cache_root=root, now=now)
    query = {"feed": "iex", "timeframe": "1Day", "adjustment": "split",
             "sort": "asc", "start": "2021-11-03", "end": "2026-11-07",
             "limit": 1000}
    prices = {}
    source_hashes = []
    seen_tokens = set()
    for i in range(3):
        url = ("https://data.alpaca.markets/v2/stocks/AVGO/bars?"
               + urlencode(query))
        data, sha = _cached(root, url, "ALPACA_BASIC_IEX",
                            now=now, max_bytes=4*1024*1024)
        packet = decode(data)
        if (type(packet) is not dict
                or set(packet) != {"symbol", "bars", "next_page_token"}
                or packet["symbol"] != "AVGO"
                or type(packet["bars"]) is not list
                or not 1 <= len(packet["bars"]) <= 1000):
            raise ValueError("QD_AVGO_RESEARCH_SPLIT_ONLY_PAGE_REFUSED")
        source_hashes.append(sha)
        for row in packet["bars"]:
            if type(row) is not dict or type(row.get("t")) is not str:
                raise ValueError("QD_AVGO_RESEARCH_BAR_SECURITY_REFUSED")
            # Verify exact UTC midnight mapped to the provider's ET session.
            stamp = datetime.fromisoformat(row["t"])
            if stamp.tzinfo is None or stamp.utcoffset() is None:
                raise ValueError("QD_AVGO_RESEARCH_DAILY_BAR_UTC_REQUIRED")
            local = stamp.astimezone(ET)
            if local.hour or local.minute or local.second:
                raise ValueError("QD_AVGO_RESEARCH_DAILY_BAR_ET_TIME")
            day = str(local.date())
            if day in prices:
                raise ValueError("QD_AVGO_RESEARCH_DUPLICATE_SPLIT_SESSION")
            prices[day] = str(row["c"])
        token = packet["next_page_token"]
        if token is None:
            break
        if (type(token) is not str or not 0 < len(token) <= 2048
                or token in seen_tokens or i == 2):
            raise ValueError("QD_AVGO_RESEARCH_SPLIT_PAGINATION_REFUSED")
        seen_tokens.add(token)
        query["page_token"] = token
    else:
        raise ValueError("QD_AVGO_RESEARCH_SPLIT_PAGES_INCOMPLETE")
    if (source_hashes !=
            split_proof["source_content_sha256_by_adjustment"]["split"]):
        raise ValueError("QD_AVGO_RESEARCH_SPLIT_SOURCE_HASH_MISMATCH")
    result = assess_avgo_split_research_multiples(
        chain, split_proof, prices, now=now)
    result["original_sec_chain_receipt_sha256"] = original_digest
    result["alpaca_split_only_bar_source_hashes"] = source_hashes
    return result


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--symbol",required=True)
    p.add_argument("--cik",required=True)
    p.add_argument("--accession",default=None,
                   help="Exact SEC submissions 10-Q accession; defaults to latest")
    args=p.parse_args(argv)
    try:
        result=inspect_original_quarter(symbol=args.symbol,cik=args.cik,
                                        accession=args.accession)
    except (ValueError,ResearchRefused,TypeError,KeyError,OSError):
        print(json.dumps({"schema":SCHEMA,"status":"REFUSED",
            "financial_paper_authorized":False,"live_order_authorized":False},sort_keys=True))
        return 2
    print(json.dumps(result,sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
