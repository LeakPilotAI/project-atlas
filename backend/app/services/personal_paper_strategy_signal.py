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


def inspect_published_quality_dips_research(
    *, publication: Any, symbol: str, research: dict[str, Any],
) -> dict[str, Any]:
    """Compare research to the existing custody-verified scanner publication.

    A matching board row is provenance evidence, not permission to execute.
    """
    from app.services.paper_financial_replay import body, digest
    from app.services.paper_source_publication import QualityDipsSourcePublication

    if (type(publication) is not QualityDipsSourcePublication
            or type(symbol) is not str or not symbol
            or type(research) is not dict or research.get("symbol") != symbol):
        raise ValueError("QD_PUBLISHED_RESEARCH_DEPENDENCIES_REQUIRED")
    packet = publication.read_current()  # Existing authority, archive and clock checks.
    if (packet.get("schema") != "QD_SCANNER_PUBLICATION_V1"
            or type(packet.get("bundles")) is not list):
        raise ValueError("QD_PUBLISHED_RESEARCH_SOURCE_REFUSED")
    matches = []
    for bundle in packet["bundles"]:
        if type(bundle) is not dict or type(bundle.get("board")) is not list:
            raise ValueError("QD_PUBLISHED_RESEARCH_BOARD_INVALID")
        instrument = bundle.get("instrument")
        if type(instrument) is not dict or instrument.get("symbol") != symbol:
            continue
        observation = bundle.get("observation")
        if (type(observation) is not dict or observation.get("symbol") != symbol
                or observation.get("strategy_version") != "QUALITY_DIPS_V3"
                or observation.get("evidence_class") != "FORWARD_COLLECTION"):
            raise ValueError("QD_PUBLISHED_RESEARCH_OBSERVATION_MISMATCH")
        rows = [row for row in bundle["board"]
                if type(row) is dict and row.get("symbol") == symbol]
        if len(rows) != 1:
            raise ValueError("QD_PUBLISHED_RESEARCH_BOARD_INVALID")
        matches.extend(rows)
    # The original scanner repeats the same complete board in each instrument
    # bundle. Accept identical copies; refuse divergent revisions.
    if not matches or any(body(row) != body(research) for row in matches):
        raise ValueError("QD_PUBLISHED_RESEARCH_CONTENT_NOT_BOUND")
    return {"schema": "ATLAS_PERSONAL_PAPER_PUBLISHED_RESEARCH_MATCH_V1",
            "symbol": symbol, "source_id": packet["source_id"],
            "revision": packet["revision"], "research_digest": digest(research),
            "publication_read_verified": True, "paper_fill_authorized": False,
            "live_order_authorized": False}


def evaluate_published_iex_v3_candidate(
    *, publication: Any, provider: Any, symbol: str, now: datetime,
) -> dict[str, Any]:
    """Read accepted QD board, recompute V3 using current IEX ask; no fills.

    This deliberately does not start providers, lease an operator or mutate cash.
    """
    from app.services.personal_paper_iex_provider import PersonalPaperIEXProvider
    from app.services.paper_source_publication import QualityDipsSourcePublication
    from app.services.personal_paper_observations import _aware
    from app.services.paper_financial_replay import body

    if (type(publication) is not QualityDipsSourcePublication
            or type(provider) is not PersonalPaperIEXProvider
            or type(symbol) is not str or not symbol):
        raise ValueError("QD_PUBLISHED_IEX_BOUND_PORTS_REQUIRED")
    packet = publication.read_current()
    # Freeze the first read: a mutable provider object must not hide a revision
    # change by returning the same dictionary instance on the second read.
    from app.services.paper_financial_replay import strict
    packet = strict(body(packet))
    if packet.get("schema") != "QD_SCANNER_PUBLICATION_V1" or type(packet.get("bundles")) is not list:
        raise ValueError("QD_PUBLISHED_IEX_PACKET_INVALID")
    rows = []
    observation_stamps = []
    for bundle in packet["bundles"]:
        if type(bundle) is not dict or type(bundle.get("instrument")) is not dict:
            raise ValueError("QD_PUBLISHED_IEX_BUNDLE_INVALID")
        if bundle["instrument"].get("symbol") != symbol:
            continue
        observation = bundle.get("observation")
        if (type(observation) is not dict or observation.get("symbol") != symbol
                or observation.get("strategy_version") != "QUALITY_DIPS_V3"
                or observation.get("evidence_class") != "FORWARD_COLLECTION"):
            raise ValueError("QD_PUBLISHED_IEX_OBSERVATION_INVALID")
        observation_stamps.append(observation.get("timestamp"))
        board = bundle.get("board")
        if type(board) is not list:
            raise ValueError("QD_PUBLISHED_IEX_BOARD_INVALID")
        rows.extend(row for row in board if type(row) is dict and row.get("symbol") == symbol)
    if not rows or any(body(row) != body(rows[0]) for row in rows):
        raise ValueError("QD_PUBLISHED_IEX_RESEARCH_MISSING_OR_CONFLICTING")
    row = rows[0]
    if row.get("blockers") != [] or row.get("missing_critical") != []:
        raise ValueError("QD_PUBLISHED_IEX_RESEARCH_BLOCKED")
    projection = row.get("quality_dips_v2")
    if type(projection) is not dict or projection.get("missing_v2_evidence") != []:
        raise ValueError("QD_PUBLISHED_IEX_V3_EVIDENCE_INCOMPLETE")
    inputs = projection.get("decision_inputs")
    if type(inputs) is not dict or inputs.get("symbol") != symbol:
        raise ValueError("QD_PUBLISHED_IEX_DECISION_INPUTS_REQUIRED")
    # The accepted observation supplies the point-in-time source stamp.
    if len(set(observation_stamps)) != 1:
        raise ValueError("QD_PUBLISHED_IEX_OBSERVATION_TIMES_CONFLICT")
    stamp = _aware(observation_stamps[0], "published observation")
    if row.get("timestamp") is not None and _aware(row["timestamp"], "published board") != stamp:
        raise ValueError("QD_PUBLISHED_IEX_BOARD_OBSERVATION_TIME_MISMATCH")
    if not 0 <= (now - stamp).total_seconds() <= 600:
        raise ValueError("QD_PUBLISHED_IEX_RESEARCH_NOT_CURRENT")
    research = {"symbol": symbol, "source_verified": True,
                "timestamp": stamp.isoformat(),
                "normalization_value": inputs.get("normalization_value"),
                "quality_score": inputs.get("quality_score"),
                "fundamentals_score": inputs.get("fundamentals_score"),
                "valuation_score": inputs.get("valuation_score"),
                "drawdown_percentile": inputs.get("drawdown_percentile"),
                "evidence_quality": inputs.get("evidence_quality"),
                "thesis": "INTACT" if inputs.get("thesis_intact") is True else "BLOCKED",
                "value_trap": inputs.get("value_trap") is True}
    candidate = evaluate_iex_quality_dips_signal(
        quote=provider.read_iex_quote(symbol), symbol=symbol, now=now, research=research)
    if strict(body(publication.read_current())) != packet:
        raise ValueError("QD_PUBLISHED_IEX_SOURCE_CHANGED")
    return {**candidate, "published_source_id": packet["source_id"],
            "published_revision": packet["revision"],
            "publication_read_verified": True,
            "research_provenance_attested": False,
            "paper_fill_authorized": False, "live_order_authorized": False}


def inspect_leased_published_iex_v3_candidate(
    *, installation: Any, request: dict[str, Any], components: Any,
    publication: Any, provider: Any, symbol: str, now: datetime,
) -> dict[str, Any]:
    """One operator lease for verified source read and fresh IEX candidate.

    No account initialization, simulated fill, startup or broker route.
    """
    from app.services.personal_paper_runtime import checked_personal_installation
    from app.services.personal_paper_iex_provider import PersonalPaperIEXProvider
    from app.services.paper_source_publication import QualityDipsSourcePublication

    if (installation is None or type(request) is not dict
            or request.get("action") != "AUTO_PAPER"
            or type(provider) is not PersonalPaperIEXProvider
            or type(publication) is not QualityDipsSourcePublication):
        raise ValueError("LEASED_PUBLISHED_IEX_DEPENDENCIES_REQUIRED")
    with installation.lease(request) as lease:
        proof = checked_personal_installation(lease, request)
        if lease.check_components(components) is not True:
            raise ValueError("LEASED_PUBLISHED_IEX_COMPONENTS_CHANGED")
        candidate = evaluate_published_iex_v3_candidate(
            publication=publication, provider=provider, symbol=symbol, now=now)
        if lease.check(proof) is not True or lease.check_components(components) is not True:
            raise ValueError("LEASED_PUBLISHED_IEX_LEASE_CHANGED")
        return {**candidate, "operator_lease_checked": True,
                "paper_fill_authorized": False, "live_order_authorized": False}


def inspect_leased_published_iex_journal_candidate(
    *, installation: Any, request: dict[str, Any], components: Any,
    publication: Any, provider: Any, symbol: str, now: datetime,
    journal_path: Any, account_id: str,
) -> dict[str, Any]:
    """Lease-held source, quote, and disk-replayed PAPER capacity; read only.

    A positive result is NOT an entry permit or a journal writer grant.
    """
    from pathlib import Path
    from app.investment.quality_dips_paper import (
        accounting_snapshot, journal_mutation_transaction, read_events, open_lots,
    )
    from app.services.personal_paper_runtime import checked_personal_installation
    from app.services.personal_paper_iex_provider import PersonalPaperIEXProvider
    from app.services.paper_source_publication import QualityDipsSourcePublication

    if (installation is None or type(request) is not dict
            or request.get("action") != "AUTO_PAPER"
            or type(publication) is not QualityDipsSourcePublication
            or type(provider) is not PersonalPaperIEXProvider
            or not isinstance(journal_path, (str, Path))
            or type(account_id) is not str or not account_id):
        raise ValueError("LEASED_PUBLISHED_JOURNAL_DEPENDENCIES_REQUIRED")
    path = Path(journal_path)
    if not path.is_file():
        raise ValueError("LEASED_PUBLISHED_JOURNAL_NOT_INITIALIZED")
    with installation.lease(request) as lease:
        proof = checked_personal_installation(lease, request)
        if lease.check_components(components) is not True:
            raise ValueError("LEASED_PUBLISHED_JOURNAL_COMPONENTS_CHANGED")
        # Lock only the existing journal; do not open any simulated position.
        with journal_mutation_transaction(path):
            candidate = evaluate_published_iex_v3_candidate(
                publication=publication, provider=provider, symbol=symbol, now=now)
            events = read_events(path)
            snapshot = accounting_snapshot(events, account_id=account_id)
            positions = open_lots(events)
            if any(lot.get("account_id") != account_id for lot in positions):
                raise ValueError("LEASED_PUBLISHED_JOURNAL_FOREIGN_ACCOUNT_POSITION")
            if (snapshot is None or snapshot.get("data_provenance") != "FORWARD_COLLECTION"
                    or snapshot.get("cash_reconciled") is not True):
                raise ValueError("LEASED_PUBLISHED_JOURNAL_ACCOUNT_INVALID")
            if snapshot["open_positions"] != len(positions):
                raise ValueError("LEASED_PUBLISHED_JOURNAL_POSITION_COUNT_MISMATCH")
            from decimal import Decimal
            marks = []
            for lot in positions:
                if lot.get("symbol") != symbol:
                    raise ValueError("LEASED_PUBLISHED_JOURNAL_OTHER_SYMBOL_POSITION")
                bid = Decimal(candidate["quote_evidence"]["bid"])
                quantity = Decimal(str(lot["quantity_shares"]))
                entry = Decimal(str(lot["fill_price"]))
                entry_fee = Decimal(str(lot["entry_fee"]))
                exit_fee = bid * quantity * Decimal(str(snapshot["fee_bps_per_side"])) / Decimal(10000)
                marks.append({"lot_id": lot["lot_id"], "bid": str(bid),
                              "unrealized_net_pnl_estimate": float(round(
                                  (bid - entry) * quantity - entry_fee - exit_fee, 8))})
            cash = Decimal(str(snapshot["available_cash"]))
            liquidation_proceeds = sum(
                (Decimal(str(mark["bid"])) * Decimal(str(lot["quantity_shares"]))
                 * (Decimal(1) - Decimal(str(snapshot["fee_bps_per_side"])) / Decimal(10000)))
                for mark, lot in zip(marks, positions, strict=True)
            )
            estimated_equity = round(cash + liquidation_proceeds, 8)
            if not estimated_equity.is_finite() or estimated_equity < 0:
                raise ValueError("LEASED_PUBLISHED_JOURNAL_EQUITY_INVALID")
            if lease.check(proof) is not True or lease.check_components(components) is not True:
                raise ValueError("LEASED_PUBLISHED_JOURNAL_LEASE_CHANGED")
            return {**candidate, "account_id": account_id,
                    "journal_cash_reconciled": True,
                    "journal_open_positions": snapshot["open_positions"],
                    "journal_open_lots": len(positions),
                    "journal_position_marks": marks,
                    "journal_available_cash": snapshot["available_cash"],
                    "journal_estimated_liquidation_equity": float(estimated_equity),
                    "journal_estimated_total_return": float(round(
                        estimated_equity - Decimal(str(snapshot["opening_cash"])), 8)),
                    "journal_writer_lock_checked": True,
                    "operator_lease_checked": True,
                    "paper_fill_authorized": False, "live_order_authorized": False}


def plan_leased_published_iex_paper_tick(
    *, installation: Any, request: dict[str, Any], components: Any,
    publication: Any, provider: Any, symbol: str, now: datetime,
    journal_path: Any, account_id: str,
) -> dict[str, Any]:
    """Bounded, read-only forward tick planner. Never grants fill authority.

    Replays account under the original operator/source/quote lease and returns
    a deterministic WAIT, BLOCKED, or CANDIDATE state for an eventual writer.
    No startup, broker route, or journal mutation is possible here.
    """
    from app.services.paper_financial_replay import strict, body, digest

    inspection = inspect_leased_published_iex_journal_candidate(
        installation=installation, request=request, components=components,
        publication=publication, provider=provider, symbol=symbol, now=now,
        journal_path=journal_path, account_id=account_id,
    )
    # The inspection already checks journal reconciliation and operator lease.
    # Never expose a trade-ready state while custody attestation is absent.
    if inspection.get("paper_fill_authorized") is not False:
        raise ValueError("PAPER_TICK_UNEXPECTED_FILL_AUTHORITY")
    positions = inspection["journal_open_lots"]
    state = ("WAIT_EXISTING_POSITION" if positions else
             "CANDIDATE_UNAUTHORIZED" if inspection["candidate"] else
             "WAIT_NO_SIGNAL")
    # A traceable decision identity is useful for later independent forward
    # audit, but a digest is NOT proof of quote/provider authenticity.
    evidence = {"account_id": account_id, "symbol": symbol,
                "published_source_id": inspection["published_source_id"],
                "published_revision": inspection["published_revision"],
                "provider_timestamp": inspection["quote_evidence"]["provider_timestamp"],
                "bid": inspection["quote_evidence"]["bid"],
                "ask": inspection["quote_evidence"]["ask"],
                "state": state, "candidate": inspection["candidate"],
                "position_marks": inspection["journal_position_marks"],
                "available_cash": inspection["journal_available_cash"],
                "estimated_liquidation_equity": inspection["journal_estimated_liquidation_equity"]}
    return strict(body({"schema": "ATLAS_PERSONAL_PAPER_TICK_PLAN_V1",
                        "symbol": symbol, "account_id": account_id,
                        "decision_evidence_digest": digest(evidence),
                        "provider_timestamp": evidence["provider_timestamp"],
                        "published_revision": evidence["published_revision"],
                        "state": state, "candidate": inspection["candidate"],
                        "open_positions": positions,
                        "position_marks": inspection["journal_position_marks"],
                        "available_cash": inspection["journal_available_cash"],
                        "estimated_liquidation_equity": inspection["journal_estimated_liquidation_equity"],
                        "estimated_total_return": inspection["journal_estimated_total_return"],
                        "paper_fill_authorized": False,
                        "live_order_authorized": False}))
