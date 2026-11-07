"""Review independently supplied valuation estimates without issuing source authority.

This is a read-only offline research intake. An analyst's explicit values and
URLs are review material, not authenticated trading evidence or PAPER approval.
"""
import argparse
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "backend"))
from app.investment.quality_dips_v2_valuation import build_normalization_window


def review_estimates(document, *, now):
    if (type(document) is not dict or set(document) != {"schema", "symbol", "estimates"}
            or document["schema"] != "QD_EXPLICIT_VALUATION_REVIEW_V1"
            or type(document["symbol"]) is not str
            or re.fullmatch(r"[A-Z]{1,8}", document["symbol"]) is None
            or type(document["estimates"]) is not list
            or not 1 <= len(document["estimates"]) <= 10):
        raise ValueError("QD_VALUATION_REVIEW_SHAPE_REFUSED")
    estimates = document["estimates"]
    identities = set()
    families = set()
    for item in estimates:
        if (type(item) is not dict or
                set(item) not in ({"value", "provenance", "as_of", "source_url", "source_name"},
                                 {"value", "provenance", "as_of", "source_url", "source_name", "issuer_family"})):
            raise ValueError("QD_VALUATION_REVIEW_EVIDENCE_REQUIRED")
        url = item["source_url"]
        if type(url) is not str or len(url) > 2048:
            raise ValueError("QD_VALUATION_REVIEW_SOURCE_URL_REFUSED")
        parsed = urlsplit(url)
        if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
                or parsed.port or parsed.fragment or parsed.hostname in ("localhost", "127.0.0.1")
                or type(item["source_name"]) is not str or not item["source_name"].strip()):
            raise ValueError("QD_VALUATION_REVIEW_SOURCE_URL_REFUSED")
        identity = parsed.hostname.lower()
        if identity in identities:
            raise ValueError("QD_VALUATION_REVIEW_DUPLICATE_ISSUER")
        identities.add(identity)
        family = item.get("issuer_family")
        if family is not None and (type(family) is not str or not family.strip() or len(family) > 128):
            raise ValueError("QD_VALUATION_REVIEW_ISSUER_FAMILY_REFUSED")
        # An aggregator is not an independently authenticated originating analyst.
        # Missing family attribution cannot be treated as proof of independence.
        families.add(family.strip().casefold() if family is not None else None)
    window = build_normalization_window(estimates, now=now)
    independently_distinct = (None not in families and len(families) >= 3)
    # Structural completeness does not imply three distinct originating issuers.
    usable = bool(window["complete"] and independently_distinct)
    return {"schema": "ATLAS_QD_VALUATION_REVIEW_V1", "symbol": document["symbol"],
            "source_count": window["source_count"], "window_complete": usable,
            "structural_window_complete": window["complete"],
            "distinct_declared_issuer_families": len(families - {None}),
            "issuer_independence_declared": independently_distinct,
            "conservative": window["conservative"], "base": window["base"],
            "optimistic": window["optimistic"],
            "independent_source_authentication": False,
            "operational_source_accepted": False, "paper_fill_authorized": False,
            "live_order_authorized": False}


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        if not args.input.is_file() or args.input.stat().st_size > 16384:
            raise ValueError("QD_VALUATION_REVIEW_FILE_REFUSED")
        result = review_estimates(json.loads(args.input.read_text(encoding="utf-8")),
                                  now=datetime.now(UTC))
    except (ValueError, TypeError, KeyError, OSError):
        print(json.dumps({"status": "REFUSED", "operational_source_accepted": False,
                          "paper_fill_authorized": False, "live_order_authorized": False}))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
