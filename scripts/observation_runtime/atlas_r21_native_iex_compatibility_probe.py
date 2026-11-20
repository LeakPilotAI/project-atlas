"""Reveal only a safe original R21 read-only boundary error code.

Executed with exact selected R21 interpreter + installed modules. Does not
connect a trading account, grant finance, or change native roots.
"""
from __future__ import annotations

import json
import re

from scripts.observation_runtime.atlas_selected_original_selfjob_structural_readonly import (
    run_isolated_readonly,
)


def main():
    try:
        row = run_isolated_readonly(
            check_independent_ntp=True,
            check_alpaca_iex_rest=True,
        )
        rest = row["alpaca_iex_rest_source_only"] or {}
        output = {
            "status": "REAL_R21_DATA_ONLY_OBSERVATION_VERIFIED",
            "http_get_count": rest.get("http_get_count"),
            "fresh_quote_count": rest.get("fresh_quote_count"),
            "quote_precision_seconds": [
                item["utc_clock_sample_quantization_seconds"]
                for item in rest.get("quotes", [])
            ],
            "paper_start_authorized": False,
            "live_trading_authorized": False,
        }
        code = 0
    except (ValueError, KeyError, TypeError, OSError, RuntimeError, AttributeError) as exc:
        value = str(exc)
        safe = (
            value if type(exc) is ValueError
            and re.fullmatch(r"[A-Z][A-Z0-9_]{7,109}", value)
            else "UNCLASSIFIED_REAL_NATIVE_DATA_ONLY_REFUSAL"
        )
        output = {
            "status": "REAL_R21_DATA_ONLY_REFUSED",
            "safe_reason": safe,
            "exception_class": type(exc).__name__,
            "paper_start_authorized": False,
            "live_trading_authorized": False,
        }
        code = 2
    print(json.dumps(output, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
