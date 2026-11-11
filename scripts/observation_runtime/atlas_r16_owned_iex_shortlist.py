"""Position-safe IEX shortlist attached to a genuine enrolled QD financial cut.

This component only updates a provided in-memory IEXFeed subscription roster.
It never reads credentials, opens a socket, starts a writer, creates a native
account, issues a command, or accepts any PAPER/real execution authority.

Unlike historical research-only pins, required symbols MUST be read from the
actual EnrolledQualityDipsWriter._cut(), which checks native V5 FS1 state,
coordination replay and accepted caller-injected cut authority. No synthetic
pin list, stale position cut, or feed callback substitution is accepted.

The local R16 code-only source still has zero genuine enrolled financial
writers; this adapter can be tested with real V5 implementation + disposable
test authority but cannot be activated in PAPER production yet.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation

from app.investment.alpaca_iex import IEXFeed, IEXRefused
from app.investment.quality_dips_market_roster import live_roster
from app.services.paper_financial_replay import body, digest, strict
from app.services.quality_dips_unified_writer import EnrolledQualityDipsWriter
from scripts.observation_runtime.atlas_r12_iex_rotation_plan import (
    SYMBOL, plan as research_plan,
)

SCHEMA = "ATLAS_QD_OWNED_POSITION_PINNED_IEX_SHORTLIST_V1"


class NativeQDPositionPins:
    """Bound read-only source of actually OPEN positions from a verified FS1 cut."""

    def __init__(self, *, writer):
        if type(writer) is not EnrolledQualityDipsWriter:
            raise ValueError("IEX_ACTUAL_ENROLLED_QD_WRITER_REQUIRED")
        self._writer = writer
        self._runtime = writer.runtime
        self._authority = writer.authority
        self._store = writer.store
        self._manifest = strict(body(writer.manifest))
        self._last = None
        self.current()  # Real financial reader must be available at construction.

    def current(self):
        writer = self._writer
        if (type(writer) is not EnrolledQualityDipsWriter
                or writer.runtime is not self._runtime
                or writer.authority is not self._authority
                or writer.store is not self._store
                or body(writer.manifest) != body(self._manifest)):
            raise ValueError("IEX_FINANCIAL_OWNER_COMPONENT_REPLACED")
        # This method independently checks native FS1/FS3 financial state,
        # original authorization, and coordination. It may raise: fail closed.
        cut = writer._cut()
        if (type(cut) is not dict
                or cut.get("manifest") != self._manifest
                or type(cut.get("head")) is not str
                or len(cut["head"]) != 64
                or type(cut.get("acknowledged_operations")) is not dict
                or type(cut.get("state")) is not dict):
            raise ValueError("IEX_NATIVE_FINANCIAL_POSITION_CUT_REQUIRED")
        state = cut["state"]
        if (type(state.get("revision")) is not int
                or state["revision"] < 0
                or type(state.get("positions")) is not dict):
            raise ValueError("IEX_NATIVE_FINANCIAL_POSITION_REVISION_REQUIRED")
        pinned = set()
        for item in state["positions"].values():
            if type(item) is not dict or type(item.get("symbol")) is not str:
                raise ValueError("IEX_NATIVE_POSITION_SHAPE_REQUIRED")
            try:
                remaining = Decimal(item["remaining"])
            except (KeyError, TypeError, InvalidOperation) as exc:
                raise ValueError("IEX_NATIVE_POSITION_QUANTITY_REQUIRED") from exc
            if not remaining.is_finite() or remaining < 0:
                raise ValueError("IEX_NATIVE_POSITION_QUANTITY_INVALID")
            if remaining == 0:
                continue
            symbol = item["symbol"]
            if SYMBOL.fullmatch(symbol) is None or symbol in pinned:
                raise ValueError("IEX_OPEN_POSITION_SYMBOL_UNSUPPORTED_OR_DUPLICATED")
            pinned.add(symbol)
        # The actual QD policy is one open position max. More than one is
        # missing custody/risk acceptance, not a reason to drop some.
        if len(pinned) > 1:
            raise ValueError("IEX_QD_MULTIPLE_ACTIVE_POSITIONS_REFUSED")
        marker = (state["revision"], digest(cut))
        if (self._last is not None
                and (marker[0] < self._last[0]
                     or marker[0] == self._last[0]
                     and marker[1] != self._last[1])):
            raise ValueError("IEX_FINANCIAL_POSITION_CUT_ROLLBACK_OR_CONFLICT")
        self._last = marker
        return sorted(pinned)


def _invalidate_feed(feed, code):
    feed.disconnect(code)
    with feed.lock:
        feed.quotes.clear()


def _owner_pins_or_disconnect(*, feed, owner):
    _require_owned_feed(feed, owner)
    try:
        return owner.current()
    except BaseException:
        _invalidate_feed(feed, "IEX_NATIVE_FINANCIAL_OWNER_READ_FAILED")
        raise


def _require_owned_feed(feed, owner):
    if (type(feed) is not IEXFeed
            or type(owner) is not NativeQDPositionPins
            or getattr(feed.position_symbols, "__self__", None) is not owner
            or getattr(feed.position_symbols, "__func__", None)
                is not NativeQDPositionPins.current):
        if type(feed) is IEXFeed:
            _invalidate_feed(feed, "IEX_POSITION_READER_METHOD_REPLACED")
        raise ValueError("IEX_FEED_MUST_RETAIN_EXACT_ENROLLED_POSITION_READER")


def _apply(*, feed, owner, symbols, expected, metadata):
    _require_owned_feed(feed, owner)
    if (type(symbols) is not list or not symbols or len(symbols) > 30
            or len(set(symbols)) != len(symbols)
            or any(type(s) is not str or SYMBOL.fullmatch(s) is None for s in symbols)
            or type(expected) is not list or not set(expected) <= set(symbols)):
        raise ValueError("IEX_POSITION_SAFE_ROSTER_SCOPE_REQUIRED")
    before = _owner_pins_or_disconnect(feed=feed, owner=owner)
    if before != expected:
        _invalidate_feed(feed, "IEX_POSITION_CUT_CHANGED_BEFORE_ROSTER")
        raise ValueError("IEX_POSITIONS_CHANGED_DURING_SHORTLIST_PLANNING")
    try:
        feed.request_roster({
            "schema": "QD_IEX_ROSTER_V1",
            "symbols": symbols, "required_symbols": before, "capacity": 30,
        })
        after = owner.current()
        if after != before:
            raise ValueError("IEX_FINANCIAL_POSITIONS_CHANGED_DURING_ROTATION")
        view = feed.snapshot()
        if (tuple(feed.symbols) != tuple(symbols)
                or view["connection"] != "DISCONNECTED"
                or view["authenticated"] is not False
                or view["subscribed"] is not False
                or view["paper_startup_authorized"] is not False
                or any(q.get("state") == "FRESH" for q in view["quotes"])):
            raise ValueError("IEX_NEW_ROSTER_NEEDS_NEW_AUTH_ACK_AND_FRESH_QUOTES")
    except BaseException:
        # Fail closed even if the owned position changes on the last read,
        # or the feed rejects the roster during an existing live session.
        _invalidate_feed(feed, "IEX_PINNED_FINANCIAL_POSITION_INCONSISTENT")
        raise
    return {
        "schema": SCHEMA,
        "status": "OWNED_QD_POSITION_ROSTER_PLANNED_NOT_CONNECTED",
        "financial_position_pins_from_real_native_cut": list(before),
        "requested_symbols": list(symbols),
        "remaining_slots_for_research": 30 - len(before),
        "feed_roster_revision": feed.roster_revision,
        "feed_requires_new_authorization_and_subscription_ack": True,
        "previous_cached_quotes_usable": False,
        "candidate_source": metadata,
        "financial_execution_authorized": False,
        "source_entitlement_accepted": False,
        "paper_start_authorized": False,
        "live_trading_authorized": False,
        "native_financial_accounts_created": False,
        "orders_created": 0,
    }


def apply_ranked_shortlist(*, feed, owner, ranked, ranking_authority,
                           now, max_age=30):
    """Use existing verified candidate-ranker; existing position always wins."""
    _require_owned_feed(feed, owner)
    positions = _owner_pins_or_disconnect(feed=feed, owner=owner)
    shortlist = live_roster(
        ranked, required_symbols=positions, capacity=30,
        now=now, max_age=max_age, ranking_authority=ranking_authority)
    if (shortlist.get("schema") != "QD_IEX_ROSTER_V1"
            or shortlist.get("execution_authorized") is not False):
        raise ValueError("IEX_VERIFIED_CANDIDATE_ROSTER_REQUIRED")
    return _apply(
        feed=feed, owner=owner, symbols=shortlist["symbols"],
        expected=positions, metadata="VERIFIED_RANKED_CANDIDATES_NOT_EXECUTABLE")


def apply_catalog_research(*, feed, owner, catalog, offset=0):
    """Research-only rotation; catalog symbols NEVER become financial positions."""
    _require_owned_feed(feed, owner)
    positions = _owner_pins_or_disconnect(feed=feed, owner=owner)
    plan = research_plan(catalog, offset=offset, monitored_symbols=positions)
    if (plan.get("schema") != "ATLAS_R12_IEX_RESEARCH_OBSERVATION_ROSTER_V1"
            or plan.get("startup_authorized") is not False
            or plan.get("paper_execution_authorized") is not False):
        raise ValueError("IEX_UNACCEPTED_RESEARCH_CATALOG_PLAN_REQUIRED")
    result = _apply(
        feed=feed, owner=owner, symbols=plan["requested_symbols"],
        expected=positions, metadata="CATALOG_RESEARCH_NOT_ELIGIBILITY")
    result["research_catalog_digest"] = plan["catalog_sha256"]
    result["research_cursor_next_not_committed"] = plan["next_offset"]
    return result


def require_current_pins(*, feed, owner):
    """Call before reconnect/use: changed custody invalidates old quote cache."""
    _require_owned_feed(feed, owner)
    try:
        pinned = owner.current()
        if not set(pinned) <= set(feed.symbols):
            raise ValueError("IEX_OPEN_FINANCIAL_POSITION_NOT_SUBSCRIBED")
    except BaseException:
        _invalidate_feed(feed, "IEX_FINANCIAL_OWNER_LIVENESS_OR_PIN_CHANGE")
        raise
    return tuple(pinned)
