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
        if not (ANALYST.fullmatch(analyst) and FIRM.fullmatch(firm)
                and TARGET.fullmatch(target) and len(by_firm) <= MAX_ROWS):
            continue
        try:
            estimate = Decimal(TARGET.fullmatch(target).group(1))
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


if __name__ == "__main__":
    raise SystemExit(main())
