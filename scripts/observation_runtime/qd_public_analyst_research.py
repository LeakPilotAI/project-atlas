"""Bounded free public *secondary* analyst target research for Quality Dips.

A syndicated listing is NOT a primary-firm report, independent issuer
attestation, source publication, executable quote, or PAPER trading grant.
One explicit HTML read; no credentials, session, daemon, or account access.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
from urllib.request import Request, urlopen

MAX_PAGE_BYTES = 262144
MAX_ROWS = 30
MAX_AGE_DAYS = 90
SYMBOL = re.compile(r"[A-Z]{1,8}\Z")
TARGET = re.compile(r"\$([0-9]{1,6}(?:\.[0-9]{1,2})?)\Z")
# Dated analyst target revisions commonly display BOTH the previous and
# current targets. Only the value AFTER the arrow is the new analyst target.
TARGET_REVISION = re.compile(
    r"\$([0-9]{1,6}(?:\.[0-9]{1,2})?)\s*(?:→|->)\s*\$([0-9]{1,6}(?:\.[0-9]{1,2})?)\Z"
)
FIRM = re.compile(r"[A-Za-z][A-Za-z0-9 .,&'/-]{1,79}\Z")
ANALYST = re.compile(r"[A-Za-z][A-Za-z .,'-]{2,79}\Z")
SCHEMA = "ATLAS_QD_PUBLIC_SYNDICATED_FIRM_TARGET_RESEARCH_V1"


class _Rows(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows = []
        self.cells = None
        self.cell = None
        self.analyst = None
        self.in_analyst = False

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "tr":
            self.cells, self.cell, self.analyst = [], None, None
        elif tag == "td" and self.cells is not None:
            self.cell = []
        elif tag == "a" and self.cell is not None:
            self.in_analyst = str(attributes.get("href", "")).startswith("/analysts/")

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)
            if self.in_analyst:
                self.analyst = (self.analyst or "") + data

    def handle_endtag(self, tag):
        if tag == "a":
            self.in_analyst = False
        elif tag == "td" and self.cell is not None:
            self.cells.append(" ".join(" ".join(self.cell).split()))
            self.cell = None
        elif tag == "tr" and self.cells is not None:
            self.rows.append((self.analyst, self.cells))
            self.cells, self.cell, self.analyst = None, None, None


def parse_public_targets(raw, *, symbol, retrieved_at):
    """Parse firm-attributed dated targets; never authenticate the issuing firms."""
    if (type(raw) is not bytes or not 0 < len(raw) <= MAX_PAGE_BYTES
            or type(symbol) is not str or SYMBOL.fullmatch(symbol) is None
            or type(retrieved_at) is not datetime or retrieved_at.utcoffset() is None):
        raise ValueError("QD_PUBLIC_TARGET_BOUNDED_EXACT_INPUT_REQUIRED")
    try:
        page = raw.decode("utf-8")
    except UnicodeError:
        raise ValueError("QD_PUBLIC_TARGET_UTF8_REQUIRED") from None
    if re.search(r"<title>[^<]*\(" + symbol + r"\) Analyst Ratings</title>", page,
                 re.IGNORECASE) is None:
        raise ValueError("QD_PUBLIC_TARGET_SYMBOL_AND_PAGE_TITLE_REQUIRED")
    table = _Rows()
    table.feed(page)
    by_firm = {}
    for analyst, cells in table.rows:
        if len(cells) != 8 or type(analyst) is not str:
            continue
        firm, target, date_label = cells[1], cells[5], cells[7]
        current = TARGET.fullmatch(target)
        revision = TARGET_REVISION.fullmatch(target)
        if not (ANALYST.fullmatch(analyst) and FIRM.fullmatch(firm)
                and (current or revision) and len(by_firm) <= MAX_ROWS):
            continue
        try:
            # Never mistake a revised FROM value for the current target.
            # A malformed, zero, or nonfinite prior value refuses that row.
            if revision and not 0 < Decimal(revision.group(1)) < 1000000:
                continue
            estimate = Decimal(current.group(1) if current else revision.group(2))
            day = datetime.strptime(date_label, "%b %d, %Y").replace(tzinfo=UTC)
        except (InvalidOperation, ValueError):
            continue
        days = (retrieved_at.astimezone(UTC) - day).total_seconds() / 86400
        if not (estimate.is_finite() and 0 < estimate < 1000000
                and 0 <= days <= MAX_AGE_DAYS):
            continue
        value = {"firm": firm, "analyst": analyst, "target_usd": str(estimate),
                 "published_at": day.date().isoformat()}
        key = firm.casefold()
        old = by_firm.get(key)
        if old is not None and (old["published_at"], old["target_usd"]) == (
                value["published_at"], value["target_usd"]):
            continue
        if old is None or value["published_at"] > old["published_at"]:
            by_firm[key] = value
        elif value["published_at"] == old["published_at"]:
            # Conflicting same-day targets by one firm cannot count twice.
            raise ValueError("QD_PUBLIC_TARGET_SAME_FIRM_DATE_CONFLICT")
    targets = sorted(by_firm.values(), key=lambda x: (-int(x["published_at"].replace("-", "")), x["firm"]))
    if len(targets) < 3:
        raise ValueError("QD_PUBLIC_TARGET_THREE_DATED_DISTINCT_FIRMS_REQUIRED")
    if len(targets) > MAX_ROWS:
        raise ValueError("QD_PUBLIC_TARGET_CAPACITY_REFUSED")
    return {
        "schema": SCHEMA,
        "symbol": symbol,
        "secondary_source_url": "https://stockanalysis.com/stocks/" + symbol.lower() + "/ratings/",
        "retrieved_at": retrieved_at.astimezone(UTC).isoformat(),
        "original_html_sha256": hashlib.sha256(raw).hexdigest(),
        "individual_firm_count": len(targets),
        "individually_attributed_targets": targets[:10],
        "all_firm_targets_previewed": len(targets) <= 10,
        "three_distinct_firms_observed": True,
        "syndicated_secondary_evidence": True,
        "original_firm_reports_verified": False,
        "independent_issuer_authenticated": False,
        "valuation_source_operationally_accepted": False,
        "native_forward_publication_created": False,
        "simulated_paper_order_authorized": False,
        "live_order_authorized": False,
    }


def fetch_public_targets(symbol, *, now=None, opener=urlopen):
    if type(symbol) is not str or SYMBOL.fullmatch(symbol) is None:
        raise ValueError("QD_PUBLIC_TARGET_SYMBOL_REQUIRED")
    url = "https://stockanalysis.com/stocks/" + symbol.lower() + "/ratings/"
    request = Request(url, headers={"User-Agent": "ProjectAtlasResearch/1.0",
                                    "Accept": "text/html"})
    try:
        with opener(request, timeout=8) as response:
            if response.status != 200 or response.geturl() != url:
                raise ValueError("QD_PUBLIC_TARGET_EXACT_PUBLIC_PAGE_REQUIRED")
            raw = response.read(MAX_PAGE_BYTES + 1)
    except (OSError, TimeoutError):
        raise ValueError("QD_PUBLIC_TARGET_NETWORK_UNAVAILABLE") from None
    return parse_public_targets(raw, symbol=symbol,
                                retrieved_at=now if now is not None else datetime.now(UTC))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbol", required=True)
    args = parser.parse_args(argv)
    try:
        result = fetch_public_targets(args.symbol)
    except (ValueError, TypeError, KeyError):
        print(json.dumps({"status": "REFUSED", "schema": SCHEMA,
                          "independent_issuer_authenticated": False,
                          "simulated_paper_order_authorized": False}, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


def review_syndicated_receipt(receipt, *, now):
    """Carry one syndicated upstream into Atlas's EXISTING valuation review.

    Several named firms on one aggregating website are NOT separate original
    authenticated issuer domains. Review exactly one most recent observed
    individual target as a secondary-source RESEARCH observation. The others
    remain visible in the unchanged raw receipt, not independently certified.
    The existing review's one-source window MUST remain incomplete.
    """
    from scripts.observation_runtime.qd_explicit_valuation_review import review_estimates

    if (type(receipt) is not dict
            or set(receipt) != {
                "schema", "symbol", "secondary_source_url", "retrieved_at",
                "original_html_sha256", "individual_firm_count",
                "individually_attributed_targets", "all_firm_targets_previewed",
                "three_distinct_firms_observed", "syndicated_secondary_evidence",
                "original_firm_reports_verified", "independent_issuer_authenticated",
                "valuation_source_operationally_accepted",
                "native_forward_publication_created",
                "simulated_paper_order_authorized", "live_order_authorized",
            }
            or receipt["schema"] != SCHEMA
            or type(receipt["symbol"]) is not str
            or SYMBOL.fullmatch(receipt["symbol"]) is None
            or receipt["secondary_source_url"] !=
            "https://stockanalysis.com/stocks/" + receipt["symbol"].lower() + "/ratings/"
            or type(receipt["original_html_sha256"]) is not str
            or re.fullmatch("[0-9a-f]{64}", receipt["original_html_sha256"]) is None
            or any(receipt[flag] is not False for flag in (
                "original_firm_reports_verified", "independent_issuer_authenticated",
                "valuation_source_operationally_accepted",
                "native_forward_publication_created",
                "simulated_paper_order_authorized", "live_order_authorized"))
            or receipt["syndicated_secondary_evidence"] is not True
            or receipt["three_distinct_firms_observed"] is not True
            or receipt["all_firm_targets_previewed"] is not True
            or type(receipt["individual_firm_count"]) is not int
            or not 3 <= receipt["individual_firm_count"] <= 10
            or type(receipt["individually_attributed_targets"]) is not list
            or len(receipt["individually_attributed_targets"]) != receipt["individual_firm_count"]
            or type(now) is not datetime or now.utcoffset() is None):
        raise ValueError("QD_SECONDARY_RECEIPT_EXACT_SCOPE_REQUIRED")
    try:
        retrieved = datetime.fromisoformat(receipt["retrieved_at"])
    except (TypeError, ValueError):
        raise ValueError("QD_SECONDARY_RECEIPT_RETRIEVAL_TIME_REQUIRED") from None
    if (retrieved.utcoffset() is None
            or not 0 <= (now - retrieved).total_seconds() <= 86400):
        raise ValueError("QD_SECONDARY_RECEIPT_EXPIRED_OR_FUTURE")
    firms = set()
    for row in receipt["individually_attributed_targets"]:
        if (type(row) is not dict or set(row) != {
                "firm", "analyst", "target_usd", "published_at"}
                or type(row["firm"]) is not str or FIRM.fullmatch(row["firm"]) is None
                or type(row["analyst"]) is not str or ANALYST.fullmatch(row["analyst"]) is None
                or type(row["target_usd"]) is not str
                or re.fullmatch("[0-9]{1,6}(?:\\.[0-9]{1,2})?", row["target_usd"]) is None):
            raise ValueError("QD_SECONDARY_RECEIPT_ATTRIBUTION_INVALID")
        try:
            value = Decimal(row["target_usd"])
            date = datetime.strptime(row["published_at"], "%Y-%m-%d").replace(tzinfo=UTC)
        except (ValueError, InvalidOperation):
            raise ValueError("QD_SECONDARY_RECEIPT_ORIGINAL_DATE_INVALID") from None
        if not (value.is_finite() and 0 < value < 1000000
                and 0 <= (now - date).total_seconds() / 86400 <= MAX_AGE_DAYS
                and row["firm"].casefold() not in firms):
            raise ValueError("QD_SECONDARY_RECEIPT_FIRM_OR_DATE_REFUSED")
        firms.add(row["firm"].casefold())
    selected = sorted(receipt["individually_attributed_targets"],
                      key=lambda x: (x["published_at"], x["firm"]), reverse=True)[0]
    review = review_estimates({
        "schema": "QD_EXPLICIT_VALUATION_REVIEW_V1",
        "symbol": receipt["symbol"],
        "estimates": [{
            "value": selected["target_usd"],
            "provenance": "MANUAL_RESEARCH",
            "as_of": selected["published_at"],
            "source_url": receipt["secondary_source_url"],
            "source_name": "StockAnalysis syndicated analyst listing",
            "issuer_family": "SINGLE_SYNDICATED_SECONDARY_UPSTREAM",
        }],
    }, now=now)
    # An originally dated target may be outside the stricter valuation TTL
    # even when it remains useful inside the 90-day historical listing.
    if (review["source_count"] not in (0, 1)
            or review["structural_window_complete"] is not False
            or review["window_complete"] is not False
            or review["independent_source_authentication"] is not False
            or review["operational_source_accepted"] is not False
            or review["paper_fill_authorized"] is not False):
        raise ValueError("QD_SECONDARY_RECEIPT_REVIEW_AUTHORITY_CONFLICT")
    return {
        "schema": "ATLAS_QD_SECONDARY_SINGLE_UPSTREAM_REVIEW_V1",
        "symbol": receipt["symbol"],
        "named_firms_in_syndicated_listing": len(firms),
        "independently_authenticated_original_issuers": 0,
        "admissible_independent_valuation_sources": 0,
        "secondary_upstream_review_source_count": 1,
        "fresh_secondary_target_count_for_review": review["source_count"],
        "latest_original_firm_target_date": selected["published_at"],
        "review": review,
        "status": ("RESEARCH_REVIEW_ONLY_ORIGINAL_ISSUER_ATTESTATION_MISSING"
                   if review["source_count"] else
                   "RESEARCH_REVIEW_ONLY_ORIGINAL_TARGET_TOO_OLD"),
        "operational_source_accepted": False,
        "paper_fill_authorized": False,
        "live_order_authorized": False,
    }


if __name__ == "__main__":
    raise SystemExit(main())
