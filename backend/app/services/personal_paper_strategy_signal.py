"""Recompute V3 from validated quote and research; no caller eligibility flags.

Research inputs still require independent source provenance before PAPER fills.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.investment.quality_dips_v3 import build_v3_entry_plan
from app.services.personal_paper_price_evidence import validate_stock_iex_quote


def evaluate_iex_quality_dips_signal(
    *, quote: dict[str, Any], symbol: str, now: datetime,
    research: dict[str, Any],
) -> dict[str, Any]:
    """Pure strategy decision from ask price, never from a claimed signal."""
    evidence = validate_stock_iex_quote(quote, symbol=symbol, now=now)
    if type(research) is not dict or research.get("symbol") != symbol:
        raise ValueError("QUALITY_DIPS_RESEARCH_IDENTITY_REQUIRED")
    if research.get("source_verified") is not True:
        raise ValueError("QUALITY_DIPS_RESEARCH_PROVENANCE_UNVERIFIED")
    from app.services.personal_paper_observations import _aware
    stamp = _aware(research.get("timestamp"), "Quality Dips research")
    age = (now - stamp).total_seconds()
    if not 0 <= age <= 86400:
        raise ValueError("QUALITY_DIPS_RESEARCH_STALE_OR_FUTURE")
    normalization = research.get("normalization_value")
    if type(normalization) is not dict:
        raise ValueError("QUALITY_DIPS_NORMALIZATION_REQUIRED")
    plan = build_v3_entry_plan(
        symbol=symbol, current_price=evidence["ask"], normalization=normalization,
        quality_score=research.get("quality_score"),
        fundamentals_score=research.get("fundamentals_score"),
        valuation_score=research.get("valuation_score"),
        drawdown_percentile=research.get("drawdown_percentile"),
        evidence_quality=research.get("evidence_quality", "UNKNOWN"),
        thesis_intact=research.get("thesis") in ("STRONG", "INTACT"),
        value_trap=research.get("value_trap") is True,
    )
    levels = [row["level"] for row in plan["entry_ladder"]["levels"] if row["reached"]]
    eligible = not plan["blockers"] and plan["patient_state"] in (
        "ACCUMULATION", "DEEP_VALUE", "GENERATIONAL") and bool(levels)
    return {"schema": "ATLAS_PERSONAL_PAPER_RECOMPUTED_IEX_V3_SIGNAL_V1",
            "symbol": symbol, "plan": plan, "reached_levels": levels,
            "candidate": bool(eligible), "research_provenance_attested": False,
            "paper_fill_authorized": False, "live_order_authorized": False,
            "quote_evidence": evidence}


def inspect_leased_iex_v3_candidate(
    *, installation: Any, request: dict[str, Any], components: Any,
    provider: Any, symbol: str, now: datetime, research: dict[str, Any],
) -> dict[str, Any]:
    """Recompute a V3 candidate from the installed feed under one operator lease.

    This does not attest caller-provided research or authorize journal mutation.
    """
    from app.services.personal_paper_iex_provider import PersonalPaperIEXProvider
    from app.services.personal_paper_runtime import checked_personal_installation

    if (installation is None or type(request) is not dict
            or request.get("action") != "AUTO_PAPER"
            or type(provider) is not PersonalPaperIEXProvider):
        raise ValueError("LEASED_IEX_V3_DEPENDENCIES_REQUIRED")
    try:
        with installation.lease(request) as lease:
            proof = checked_personal_installation(lease, request)
            if lease.check_components(components) is not True:
                raise ValueError("LEASED_IEX_V3_COMPONENTS_CHANGED")
            quote = provider.read_iex_quote(symbol)
            candidate = evaluate_iex_quality_dips_signal(
                quote=quote, symbol=symbol, now=now, research=research)
            if lease.check(proof) is not True or lease.check_components(components) is not True:
                raise ValueError("LEASED_IEX_V3_LEASE_CHANGED")
            return {**candidate, "operator_lease_checked": True,
                    "research_provenance_attested": False,
                    "paper_fill_authorized": False, "live_order_authorized": False}
    except (AttributeError, TypeError, OSError) as exc:
        raise ValueError("LEASED_IEX_V3_ADMISSION_REFUSED") from exc
