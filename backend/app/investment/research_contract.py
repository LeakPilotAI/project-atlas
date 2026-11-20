"""Pure offline presentation contract; no API route registration or state writes."""
from __future__ import annotations

from math import isfinite

from app.investment.offline_research import (
    ResearchInputRefused,
    aware,
    equity_session,
    number,
    symbol_identity,
)

SCHEMA = "ATLAS_OFFLINE_EQUITY_RESEARCH_V1"


def public_research(signal, *, now, max_age_seconds=180):
    if not isinstance(signal, dict):
        raise ResearchInputRefused("Research mapping required")
    if signal.get("research_only") is not True or signal.get("trading_enabled") is not False or signal.get("network_authorized") is not False or signal.get("execution_authority") is not False:
        raise ResearchInputRefused("Research authority contract refused")
    if type(max_age_seconds) not in (int, float) or not isfinite(max_age_seconds) or max_age_seconds <= 0:
        raise ResearchInputRefused("Invalid presentation freshness bound")
    timestamp = aware(signal.get("timestamp"))
    clock = aware(now)
    age = (clock-timestamp).total_seconds()
    session = equity_session(timestamp)
    if not 0 <= age <= max_age_seconds or session == "CLOSED" or signal.get("session") != session:
        raise ResearchInputRefused("Stale or inconsistent research presentation")
    source = signal.get("source")
    if not isinstance(source, str) or not source.strip() or len(source) > 64:
        raise ResearchInputRefused("Explicit research source required")
    price = number(signal.get("price"), "research price")
    status = signal.get("relative_volume_status")
    allowed = {"BASELINE_REQUIRED", "BASELINE_INSUFFICIENT", "CURRENT_WINDOW_INCOMPLETE", "ZERO_BASELINE", "COMPARABLE_HISTORY"}
    ratio = signal.get("relative_volume")
    if status not in allowed or (ratio is None) != (status != "COMPARABLE_HISTORY"):
        raise ResearchInputRefused("Contradictory baseline evidence")
    if ratio is not None:
        ratio = number(ratio, "relative volume", zero=True)
    reference_status = signal.get("previous_close_status")
    if reference_status not in {"DATED_CALLER_REFERENCE", "UNDATED_CALLER_REFERENCE"}:
        raise ResearchInputRefused("Previous close provenance required")
    return {"schema_version": SCHEMA, "symbol": symbol_identity(signal.get("symbol")),
            "timestamp": timestamp.isoformat(), "source": source, "session": session,
            "price": price, "relative_volume": ratio, "relative_volume_status": status,
            "previous_close_status": reference_status,
            "freshness": {"state": "FRESH", "age_seconds": age},
            "capabilities": {"research_only": True, "live_orders": False, "paper_orders": False,
                             "discord": False, "network_authorized": False},
            "provider_rights_status": "NOT_VERIFIED", "wire_request_count": None,
            "scope": "OFFLINE_CALLER_SUPPLIED"}
