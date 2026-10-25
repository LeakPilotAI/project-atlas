"""Bounded directory-to-research and research-to-IEX routing, without network I/O.

Nasdaq reference listings are not broker eligibility, corporate-action clearance,
rankings or executable prices. Permission/authenticity is independently injected.
No token catalog is treated as Robinhood's U.S. brokerage universe.
"""

import csv
import hashlib
import io
import re
from datetime import datetime
from urllib.request import Request, urlopen

from app.services.paper_financial_replay import digest, number, text

SOURCES = {"nasdaqlisted.txt", "otherlisted.txt"}
EXCHANGES = {"N": "XNYS", "A": "XASE", "P": "ARCX", "Z": "BATS", "V": "IEXG"}
SYMBOL = re.compile(r"[A-Z][A-Z0-9.\-]{0,14}\Z")


class NasdaqDirectorySource:
    """Explicit bounded public-reference download; never invoked on import/GET.

    TLS authenticates the transport, not financial authority or complete corporate
    actions. Internal research use/terms must be reviewed separately for deployment.
    No credentials, brokerage SDK, scanner startup or financial path is present.
    """

    def __init__(self, *, opener=urlopen):
        self.opener, self.downloads = opener, {}

    def download(self, source):
        if source not in SOURCES:
            raise ValueError("UNIVERSE_FIXED_PUBLIC_SOURCE_REQUIRED")
        url = "https://www.nasdaqtrader.com/dynamic/SymDir/" + source
        req = Request(url, headers={"User-Agent": "ProjectAtlas/read-only-reference-research"})
        with self.opener(req, timeout=8) as response:  # Fixed HTTPS source allowlist.
            if response.geturl() != url:
                raise ValueError("UNIVERSE_FOREIGN_REDIRECT_REFUSED")
            raw = response.read(8_000_001)
        if not 1 <= len(raw) <= 8_000_000:
            raise ValueError("UNIVERSE_DIRECTORY_CAPACITY")
        self.downloads[source] = raw
        return directory_snapshot(raw, source=source, authority=self)

    def verify_directory(self, source, raw):
        return source in self.downloads and self.downloads[source] == raw


def directory_snapshot(raw, *, source, authority):
    if (source not in SOURCES or type(raw) is not bytes or not 1 <= len(raw) <= 8_000_000
            or not raw.endswith(b"\n") or authority is None
            or authority.verify_directory(source, raw) is not True):
        raise ValueError("UNIVERSE_COMPLETE_AUTHENTICATED_DIRECTORY_REQUIRED")
    lines = raw.decode("utf-8-sig").splitlines()
    if not 3 <= len(lines) <= 30002 or not lines[-1].startswith("File Creation Time: "):
        raise ValueError("UNIVERSE_MISSING_SOURCE_CUT")
    creation = lines[-1].split("|", 1)[0].removeprefix("File Creation Time: ")
    datetime.strptime(creation, "%m%d%Y%H:%M")  # noqa: DTZ007 - validate provider local text only; never invent UTC
    reader = csv.DictReader(io.StringIO("\n".join(lines[:-1])), delimiter="|")
    expected = ({"Symbol", "Security Name", "Market Category", "Test Issue", "Financial Status",
                 "Round Lot Size", "ETF", "NextShares"} if source == "nasdaqlisted.txt" else
                {"ACT Symbol", "Security Name", "Exchange", "CQS Symbol", "ETF", "Round Lot Size", "Test Issue", "NASDAQ Symbol"})
    if set(reader.fieldnames or []) != expected or len(reader.fieldnames) != len(expected):
        raise ValueError("UNIVERSE_UNSUPPORTED_DIRECTORY_SCHEMA")
    rows, excluded, seen = [], [], set()
    for row in reader:
        if set(row) != expected or any(v is None for v in row.values()):
            raise ValueError("UNIVERSE_TRUNCATED_OR_EXTRA_FIELDS")
        symbol = row["Symbol"] if source == "nasdaqlisted.txt" else row["NASDAQ Symbol"]
        if symbol in seen:
            raise ValueError("UNIVERSE_DUPLICATE_SOURCE_IDENTITY")
        seen.add(symbol)
        if row["ETF"] not in ("Y", "N") or row["Test Issue"] not in ("Y", "N"):
            raise ValueError("UNIVERSE_UNKNOWN_FLAGS")
        exchange = "XNAS" if source == "nasdaqlisted.txt" else EXCHANGES.get(row["Exchange"])
        if (row["Test Issue"] != "N" or not SYMBOL.fullmatch(symbol) or exchange is None
                or source == "nasdaqlisted.txt" and (row["Financial Status"] != "N" or row["NextShares"] != "N")):
            excluded.append({"symbol": symbol, "reason": "UNSUPPORTED_OR_NONNORMAL_LISTING"})
            continue
        if not row["Round Lot Size"].isdigit() or not 0 < int(row["Round Lot Size"]) <= 10000:
            raise ValueError("UNIVERSE_INVALID_LOT_MAPPING")
        rows.append({"symbol": symbol, "name": row["Security Name"], "exchange": exchange,
                     "instrument_type": "ETF" if row["ETF"] == "Y" else "EQUITY_REFERENCE",
                     "source_symbols": {k: row[k] for k in ("Symbol", "ACT Symbol", "CQS Symbol", "NASDAQ Symbol") if k in row},
                     "round_lot_shares": int(row["Round Lot Size"]), "execution_eligible": False,
                     "corporate_actions": "UNVERIFIED", "halt_state": "UNVERIFIED"})
    return {"schema": "QD_REFERENCE_DIRECTORY_V1", "source": source, "source_cut_local": creation,
            "source_digest": hashlib.sha256(raw).hexdigest(), "rows": rows, "excluded": excluded,
            "source_records": len(seen), "startup_authorized": False}


def research_batch(snapshot, *, offset, budget):
    """Stable bounded pages for the existing research engine, not new rankings."""
    if (snapshot.get("schema") != "QD_REFERENCE_DIRECTORY_V1" or type(offset) is not int
            or offset < 0 or type(budget) is not int or not 1 <= budget <= 100):
        raise ValueError("UNIVERSE_BOUNDED_RESEARCH_BUDGET_REQUIRED")
    ordered = sorted(snapshot["rows"], key=lambda r: (r["exchange"], r["symbol"]))
    return {"source_digest": snapshot["source_digest"], "rows": ordered[offset:offset + budget],
            "next_offset": min(len(ordered), offset + budget), "remaining": max(0, len(ordered) - offset - budget)}


def research_universe(batch, *, metadata, instrument_authority):
    """Use the actual InvestmentScanner's injected InvestmentUniverse interface.

    Missing metadata stays explicitly excluded, never guessed from a ticker/name.
    No load_universe/bootstrap, provider fetch, legacy PaperBook or scanner start.
    The caller must separately inject safe research ingest/budget and disable
    financial mirrors/notifications; this function supplies research identity only.
    """
    from app.investment.enums import AssetType
    from app.investment.universe import InvestmentUniverse, UniverseEntry

    if instrument_authority is None or type(metadata) is not dict or type(batch.get("rows")) is not list:
        raise ValueError("UNIVERSE_INSTRUMENT_METADATA_AUTHORITY_REQUIRED")
    entries, excluded = [], []
    for reference in batch["rows"]:
        item = metadata.get(reference["symbol"])
        if (type(item) is not dict or set(item) != {"symbol", "instrument_id", "asset_class", "exchange", "currency", "status", "revision"}
                or item["symbol"] != reference["symbol"] or item["exchange"] != reference["exchange"]
                or item["currency"] != "USD" or item["status"] != "ACTIVE"
                or item["asset_class"] not in ("STOCK", "ETF")
                or reference["instrument_type"] == "ETF" and item["asset_class"] != "ETF"
                or type(item["revision"]) is not int or item["revision"] < 1
                or instrument_authority.verify_instrument(item, reference, batch["source_digest"]) is not True):
            excluded.append({"symbol": reference["symbol"], "reason": "INSTRUMENT_IDENTITY_UNVERIFIED_OR_UNSUPPORTED"})
            continue
        text(item["instrument_id"])
        entries.append(UniverseEntry(symbol=item["symbol"], name=reference["name"],
                                    asset_type=AssetType(item["asset_class"]), exchange=item["exchange"],
                                    groups=["VERIFIED_REFERENCE_RESEARCH_ONLY"]))
    return {"universe": InvestmentUniverse(entries), "excluded": excluded, "execution_authorized": False}


def live_roster(ranked, *, required_symbols, capacity, now, max_age, ranking_authority):
    """Pin every open-position symbol, then deterministic verified rank order.

    Capacity must come from the accepted subscription entitlement, not the size
    of the directory or a claim of unlimited IEX coverage. No tie randomness.
    """
    if (type(capacity) is not int or not 1 <= capacity <= 30 or type(now) is not int
            or type(max_age) is not int or not 0 < max_age <= 3600
            or type(required_symbols) is not list or len(set(required_symbols)) != len(required_symbols)
            or any(type(s) is not str or not SYMBOL.fullmatch(s) for s in required_symbols)
            or len(required_symbols) > capacity or type(ranked) is not list or len(ranked) > 30000
            or ranking_authority is None):
        raise ValueError("ROSTER_PINNED_EXPLICIT_CAPACITY_REQUIRED")
    seen, candidates = set(), []
    for row in ranked:
        if (type(row) is not dict or set(row) != {"symbol", "score", "revision", "at", "source"}
                or type(row["symbol"]) is not str or not SYMBOL.fullmatch(row["symbol"])
                or row["symbol"] in seen or type(row["revision"]) is not int or row["revision"] < 1
                or type(row["at"]) is not int or not 0 <= now - row["at"] <= max_age
                or ranking_authority.verify_ranking(row) is not True):
            raise ValueError("ROSTER_UNVERIFIED_OR_STALE_RANKING")
        text(row["source"])
        score = number(row["score"])
        seen.add(row["symbol"])
        candidates.append((-score, row["symbol"]))
    selected = sorted(required_symbols)
    for _, symbol in sorted(candidates):
        if symbol not in selected and len(selected) < capacity:
            selected.append(symbol)
    return {"schema": "QD_IEX_ROSTER_V1", "symbols": selected, "required_symbols": sorted(required_symbols),
            "capacity": capacity, "ranking_digest": digest(ranked), "execution_authorized": False}
