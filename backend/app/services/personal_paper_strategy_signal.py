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


def run_bounded_readonly_paper_session(*, ticks: int, clock: Any, **dependencies: Any) -> dict[str, Any]:
    """Explicitly invoked, bounded forward diagnostic; never starts a service.

    Stops on the first technical/provider/operator error. The caller must
    supply the clock and live installed ports; this does not create them.
    """
    from app.services.paper_financial_replay import strict, body

    if type(ticks) is not int or not 1 <= ticks <= 30 or not callable(clock):
        raise ValueError("PAPER_SESSION_BOUNDED_EXPLICIT_CLOCK_REQUIRED")
    # A caller resuming a supervised diagnostic can supply the previously
    # accepted provider event. Refuse stale/replayed events across invocations.
    from app.services.personal_paper_observations import _aware
    previous_event = dependencies.pop("previous_provider_timestamp", None)
    if previous_event is not None:
        previous_event = _aware(previous_event, "previous PAPER provider event")
    records = []
    for index in range(ticks):
        now = clock()
        if type(now) is not datetime or now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("PAPER_SESSION_AWARE_CLOCK_REQUIRED")
        if records and now <= records[-1]["_clock"]:
            raise ValueError("PAPER_SESSION_NONMONOTONIC_CLOCK")
        plan = plan_leased_published_iex_paper_tick(now=now, **dependencies)
        if plan["paper_fill_authorized"] is not False or plan["live_order_authorized"] is not False:
            raise ValueError("PAPER_SESSION_UNEXPECTED_AUTHORITY")
        # A bounded run is not forward market observation if every iteration
        # reuses the same quote event. Refuse duplicate or regressing stamps.
        if type(plan.get("provider_timestamp")) is not str:
            raise ValueError("PAPER_SESSION_PROVIDER_TIMESTAMP_REQUIRED")
        from app.services.personal_paper_observations import _aware
        provider_stamp = _aware(plan["provider_timestamp"], "PAPER session provider event")
        if provider_stamp > now or (now - provider_stamp).total_seconds() > 15:
            raise ValueError("PAPER_SESSION_PROVIDER_EVENT_NOT_FRESH")
        if ((records and provider_stamp <= records[-1]["_provider_stamp"])
                or (previous_event is not None and provider_stamp <= previous_event)):
            raise ValueError("PAPER_SESSION_PROVIDER_EVENT_NOT_ADVANCING")
        # Proposals are advisory only. Recompute them from the inspected tick
        # rather than allowing a caller to supply an action or authorization.
        proposal = propose_forward_paper_action(plan=plan)
        if proposal["paper_fill_authorized"] is not False:
            raise ValueError("PAPER_SESSION_UNEXPECTED_PROPOSAL_AUTHORITY")
        records.append({"_clock": now, "_provider_stamp": provider_stamp,
                        "tick": index, "plan": plan, "proposal": proposal})
    return strict(body({"schema": "ATLAS_BOUNDED_READONLY_PAPER_SESSION_V1",
                        "ticks": [{"timestamp": r["_clock"].isoformat(),
                                   "index": r["tick"], "plan": r["plan"],
                                   "proposal": r["proposal"]} for r in records],
                        "completed": len(records),
                        "last_provider_timestamp": records[-1]["_provider_stamp"].isoformat(),
                        "paper_fill_authorized": False,
                        "live_order_authorized": False}))


def propose_forward_paper_action(*, plan: dict[str, Any],
                                 max_notional: float = 100.0) -> dict[str, Any]:
    """Pure next-action proposal, NEVER a fill or financial-write permit.

    Requires an internally generated read-only tick schema, conservative
    account capacity and a reproducible decision digest. Caller-provided
    dictionaries are not authentic provider/operator attestations.
    """
    from decimal import Decimal, InvalidOperation
    from app.services.paper_financial_replay import strict, body
    if (type(plan) is not dict or plan.get("schema") != "ATLAS_PERSONAL_PAPER_TICK_PLAN_V1"
            or plan.get("paper_fill_authorized") is not False
            or plan.get("live_order_authorized") is not False
            or type(plan.get("decision_evidence_digest")) is not str
            or len(plan["decision_evidence_digest"]) != 64):
        raise ValueError("PAPER_ACTION_PROPOSAL_VERIFIED_READONLY_TICK_REQUIRED")
    try:
        cash = Decimal(str(plan["available_cash"]))
        ceiling = Decimal(str(max_notional))
    except (KeyError, ValueError, InvalidOperation) as exc:
        raise ValueError("PAPER_ACTION_PROPOSAL_CAPACITY_INVALID") from exc
    if not cash.is_finite() or cash < 0 or not ceiling.is_finite() or not 0 < ceiling <= 100:
        raise ValueError("PAPER_ACTION_PROPOSAL_CAPACITY_INVALID")
    state = plan.get("state")
    positions = plan.get("open_positions")
    if (type(positions) is not int or positions < 0
            or state not in ("WAIT_EXISTING_POSITION", "WAIT_NO_SIGNAL", "CANDIDATE_UNAUTHORIZED")
            or (state == "WAIT_EXISTING_POSITION") != (positions > 0)
            or (state == "CANDIDATE_UNAUTHORIZED" and plan.get("candidate") is not True)):
        raise ValueError("PAPER_ACTION_PROPOSAL_STATE_CONFLICT")
    proposed = min(ceiling, cash / Decimal("1.001")) if state == "CANDIDATE_UNAUTHORIZED" else Decimal(0)
    return strict(body({"schema": "ATLAS_FORWARD_PAPER_UNAUTHORIZED_ACTION_PROPOSAL_V1",
                        "symbol": plan.get("symbol"), "account_id": plan.get("account_id"),
                        "decision_evidence_digest": plan["decision_evidence_digest"],
                        "action": "PROPOSE_ENTRY" if proposed > 0 else "WAIT",
                        "reason": state if proposed > 0 or state != "CANDIDATE_UNAUTHORIZED" else "INSUFFICIENT_CASH",
                        "max_simulated_notional": float(round(proposed, 8)),
                        "paper_fill_authorized": False,
                        "live_order_authorized": False}))


def assess_forward_paper_activation_readiness(*, installation: Any,
                                              publication: Any,
                                              provider: Any,
                                              journal_path: Any,
                                              account_id: str) -> dict[str, Any]:
    """Non-mutating readiness inventory, not an activation or login attempt.

    Refuses to infer provider authentication from mutable feed flags or
    operator authorization from an installation object's mere existence.
    """
    from pathlib import Path
    from app.investment.quality_dips_paper import accounting_snapshot, read_events
    from app.services.paper_financial_replay import body, strict
    from app.services.personal_paper_runtime import PersonalOperatorInstallation
    from app.services.personal_paper_iex_provider import PersonalPaperIEXProvider
    from app.services.quality_dips_current_producer import QualityDipsSourcePublication
    if (type(account_id) is not str or not account_id
            or not isinstance(journal_path, Path)):
        raise ValueError("PAPER_ACTIVATION_PREFLIGHT_INPUT_INVALID")
    blockers = []
    if type(installation) is not PersonalOperatorInstallation:
        blockers.append("LOCAL_OPERATOR_INSTALLATION_NOT_VERIFIED")
    if type(publication) is not QualityDipsSourcePublication:
        blockers.append("NATIVE_SOURCE_PUBLICATION_NOT_VERIFIED")
    if type(provider) is not PersonalPaperIEXProvider:
        blockers.append("IEX_PROVIDER_PORT_NOT_VERIFIED")
    if not journal_path.is_file():
        blockers.append("PAPER_JOURNAL_NOT_INITIALIZED")
    else:
        try:
            snapshot = accounting_snapshot(read_events(journal_path), account_id=account_id)
            if (snapshot is None or snapshot.get("data_provenance") != "FORWARD_COLLECTION"
                    or snapshot.get("cash_reconciled") is not True):
                blockers.append("FORWARD_JOURNAL_RECONCILIATION_REQUIRED")
        except (OSError, ValueError, KeyError, TypeError):
            blockers.append("FORWARD_JOURNAL_REPLAY_REFUSED")
    # These conditions must be proven by a supervised session and trusted
    # custody path; a structural preflight must never mark them complete.
    blockers.extend(("SUPERVISED_OPERATOR_LEASE_NOT_PROVEN",
                     "AUTHENTICATED_IEX_SESSION_NOT_PROVEN",
                     "NATIVE_FORWARD_PROVENANCE_NOT_ATTESTED",
                     "FORWARD_FINANCIAL_WRITE_AUTHORITY_NOT_GRANTED"))
    return strict(body({"schema": "ATLAS_FORWARD_PAPER_ACTIVATION_PREFLIGHT_V1",
                        "account_id": account_id, "blockers": blockers,
                        "ready": False, "paper_fill_authorized": False,
                        "live_order_authorized": False}))


def check_local_iex_config_readiness(*, config_path: Any) -> dict[str, Any]:
    """Validate local data-only Alpaca config without connecting or leaking keys.

    This checks format and trading-disabled policy, not authentication,
    operator approval, provider rights or permission to simulate fills.
    """
    from pathlib import Path
    from app.investment.alpaca_iex import Credentials, IEXRefused
    from app.services.paper_financial_replay import strict, body
    if not isinstance(config_path, Path):
        raise ValueError("IEX_PREFLIGHT_EXPLICIT_PATH_REQUIRED")
    try:
        Credentials.load(config_path)
        status = "VALID_FORMAT_ONLY"
    except IEXRefused:
        status = "CONFIG_REJECTED"
    return strict(body({"schema": "ATLAS_LOCAL_IEX_CONFIG_PREFLIGHT_V1",
                        "status": status, "data_only_policy_checked": status == "VALID_FORMAT_ONLY",
                        "provider_authenticated": False,
                        "provider_activation_authorized": False,
                        "paper_fill_authorized": False,
                        "live_order_authorized": False}))
