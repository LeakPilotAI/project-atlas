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
