"""Real unified QD writer financial-cut position pins -> real IEXFeed roster.

Uses the actual V5 financial writer / FS1/FS3 / coordination implementation
from disposable test fixtures, never installed Atlas account roots. Rankings
and operator authority are synthetic and are NOT real PAPER enrollment.
"""
from __future__ import annotations

import copy

import pytest

from app.investment.alpaca_iex import IEXFeed, IEXRefused
from app.services.paper_financial_replay import digest
from scripts.observation_runtime.alpaca_equity_catalog import inventory_snapshot
from scripts.observation_runtime import atlas_r16_owned_iex_shortlist as short
from test_qd_unified_writer_native import system, writer, proposed, capture


class TestRankingIssuer:
    __test__ = False
    def verify_ranking(self, row):
        return row["source"] == "SYNTHETIC_RANKING_ONLY"


def candidates(*,count=45,stamp=1000):
    return [
        {"symbol":f"S{i:03d}","score":str(100-i),"revision":1,
         "at":stamp,"source":"SYNTHETIC_RANKING_ONLY"}
        for i in range(count)
    ]


def catalog(*,position=None):
    symbols=[f"S{i:03d}" for i in range(75)]+([position] if position else [])
    return inventory_snapshot([
        {"class":"us_equity","symbol":symbol,"status":"active",
         "tradable":True,"exchange":"NASDAQ","id":symbol}
        for symbol in symbols],
        captured_at="2026-11-11T09:00:00+00:00")


def opened(s,w,authority):
    p, observation = proposed(s,w)
    authority.reserved={"state":"RESERVED","binding":digest(p)}
    receipt=w.dispatch(p,authority.reserved)
    assert receipt["source_revision"]==1
    state=w._cut()["state"]
    symbols=[p["symbol"] for p in state["positions"].values()
             if p["remaining"]!="0"]
    assert len(symbols)==1
    return symbols[0]


def feed_for(owner, *, symbols=("S000",)):
    return IEXFeed(list(symbols), position_symbols=owner.current)


def test_missing_or_foreign_position_reader_is_not_adopted_by_feed(system):
    w,a=writer(system)
    with pytest.raises(ValueError,match="ACTUAL_ENROLLED_QD_WRITER_REQUIRED"):
        short.NativeQDPositionPins(writer=object())
    own=short.NativeQDPositionPins(writer=w)
    assert own.current()==[]
    with pytest.raises(ValueError,match="RETAIN_EXACT_ENROLLED_POSITION_READER"):
        short.apply_ranked_shortlist(
            feed=IEXFeed(["S000"],position_symbols=lambda:[]),
            owner=own,ranked=candidates(),
            ranking_authority=TestRankingIssuer(),now=1000)
    with pytest.raises(ValueError,match="RETAIN_EXACT_ENROLLED_POSITION_READER"):
        short.apply_catalog_research(
            feed=IEXFeed(["S000"]),
            owner=own,catalog=catalog())


def test_actual_native_financial_writer_empty_read_only_then_top_30_shortlist(system):
    w,a=writer(system)
    owner=short.NativeQDPositionPins(writer=w)
    feed=feed_for(owner)
    before=capture(system)
    output=short.apply_ranked_shortlist(
        feed=feed,owner=owner,ranked=list(reversed(candidates())),
        ranking_authority=TestRankingIssuer(),now=1000)
    assert output["financial_position_pins_from_real_native_cut"]==[]
    assert len(output["requested_symbols"])==30
    assert output["requested_symbols"]==[f"S{i:03d}" for i in range(30)]
    assert output["remaining_slots_for_research"]==30
    assert feed.symbols==tuple(output["requested_symbols"])
    assert feed.connection=="DISCONNECTED"
    assert feed.snapshot()["paper_startup_authorized"] is False
    assert output["financial_execution_authorized"] is False
    assert output["paper_start_authorized"] is False
    assert output["source_entitlement_accepted"] is False
    assert short.require_current_pins(feed=feed,owner=owner)==()
    assert capture(system)==before  # This is NO native financial publication.


def test_actual_native_v5_held_position_always_pins_before_ranking(system):
    w,a=writer(system)
    owner=short.NativeQDPositionPins(writer=w)
    feed=feed_for(owner)
    held=opened(system,w,a)
    assert owner.current()==[held]
    output=short.apply_ranked_shortlist(
        feed=feed,owner=owner,ranked=candidates(),
        ranking_authority=TestRankingIssuer(),now=1000)
    assert output["requested_symbols"][0]==held
    assert held in feed.symbols
    assert len(feed.symbols)==30
    assert output["remaining_slots_for_research"]==29
    assert output["financial_position_pins_from_real_native_cut"]==[held]
    assert short.require_current_pins(feed=feed,owner=owner)==(held,)
    assert output["feed_requires_new_authorization_and_subscription_ack"] is True
    assert feed.snapshot()["connection"]=="DISCONNECTED"
    assert output["orders_created"]==0


def test_actual_open_position_is_preserved_through_research_catalog_rotation(system):
    w,a=writer(system)
    owner=short.NativeQDPositionPins(writer=w)
    held=opened(system,w,a)
    feed=feed_for(owner)
    snap=catalog(position=held)
    x=short.apply_catalog_research(feed=feed,owner=owner,catalog=snap,offset=0)
    y=short.apply_catalog_research(
        feed=feed,owner=owner,catalog=snap,
        offset=x["research_cursor_next_not_committed"])
    assert x["requested_symbols"][0]==y["requested_symbols"][0]==held
    assert len(x["requested_symbols"])==len(y["requested_symbols"])==30
    assert x["requested_symbols"]!=y["requested_symbols"]
    assert set(x["requested_symbols"][1:]).isdisjoint(y["requested_symbols"][1:])
    assert y["feed_roster_revision"]==x["feed_roster_revision"]+1
    assert y["candidate_source"]=="CATALOG_RESEARCH_NOT_ELIGIBILITY"
    assert y["source_entitlement_accepted"] is False
    assert y["paper_start_authorized"] is False
    assert feed.connection=="DISCONNECTED"


def test_late_real_financial_position_change_invalidates_old_roster_and_cache(system):
    w,a=writer(system)
    owner=short.NativeQDPositionPins(writer=w)
    feed=feed_for(owner)
    short.apply_ranked_shortlist(
        feed=feed,owner=owner,ranked=candidates(),now=1000,
        ranking_authority=TestRankingIssuer())
    held=opened(system,w,a)
    assert held not in feed.symbols  # Different symbol, not fake research pins.
    feed.connection="CONNECTED"
    feed.authenticated=feed.subscribed=True
    feed.quotes["S000"]={"state":"FRESH","generation":feed.generation}
    with pytest.raises(ValueError,match="POSITION_NOT_SUBSCRIBED"):
        short.require_current_pins(feed=feed,owner=owner)
    assert feed.connection=="DISCONNECTED" and not feed.quotes
    assert feed.authenticated is feed.subscribed is False


def test_bad_open_position_cannot_be_dropped_under_capacity_pressure(system,monkeypatch):
    w,a=writer(system)
    owner=short.NativeQDPositionPins(writer=w)
    held=opened(system,w,a)
    feed=feed_for(owner)
    # A caller-supplied 30-slot roster that omits the native position is
    # rejected before IEXFeed.request_roster could publish new subscriptions.
    with pytest.raises(ValueError,match="POSITION_SAFE_ROSTER_SCOPE_REQUIRED"):
        short._apply(feed=feed,owner=owner,symbols=[f"S{i:03d}" for i in range(30)],
                     expected=[held],metadata="NO_OWNED_POSITION")
    assert feed.roster_revision==0 and feed.symbols==("S000",)


@pytest.mark.parametrize("kind",[
    "writer_identity","financial_cut_missing","negative_remaining",
    "nan_remaining","malformed_symbol","too_many_active",
    "rollback_revision","same_revision_changed_cut",
])
def test_original_writer_cut_corruption_never_becomes_a_pinned_roster(system,monkeypatch,kind):
    w,a=writer(system)
    owner=short.NativeQDPositionPins(writer=w)
    real_cut=w._cut()
    mutated=copy.deepcopy(real_cut)
    if kind=="writer_identity":
        w.authority=object()
    elif kind=="financial_cut_missing":
        del mutated["state"]
    elif kind in ("negative_remaining","nan_remaining","malformed_symbol","too_many_active"):
        position={"symbol":"MSFT","remaining":"1"}
        if kind=="negative_remaining":position["remaining"]="-1"
        if kind=="nan_remaining":position["remaining"]="NaN"
        if kind=="malformed_symbol":position["symbol"]="btc/usd"
        mutated["state"]["positions"]["a"]=position
        if kind=="too_many_active":
            mutated["state"]["positions"]["b"]={"symbol":"SPY","remaining":"1"}
    elif kind=="rollback_revision":
        mutated["state"]["revision"]=-1
    elif kind=="same_revision_changed_cut":
        mutated["head"]="f"*64
    if kind!="writer_identity":
        monkeypatch.setattr(w,"_cut",lambda:copy.deepcopy(mutated))
    with pytest.raises(ValueError):
        owner.current()


def test_financial_position_reader_cannot_be_replaced_by_injected_list(system):
    w,a=writer(system)
    owner=short.NativeQDPositionPins(writer=w)
    feed=feed_for(owner)
    copied=copy.deepcopy(candidates())
    bogus=["S001"]
    # Neither caller pins nor a new position callback can replace the
    # reader's exact bound method and native-cut source.
    feed.position_symbols=lambda:list(bogus)
    with pytest.raises(ValueError,match="RETAIN_EXACT_ENROLLED_POSITION_READER"):
        short.apply_ranked_shortlist(
            feed=feed,owner=owner,ranked=copied,
            ranking_authority=TestRankingIssuer(),now=1000)


@pytest.mark.parametrize("damage",[
    {"at":980},{"at":1001},{"source":"unverified-scanner"},
    {"revision":True},{"score":"NaN"},
])
def test_stale_forged_or_nonfinite_rankings_refuse_native_owned_shortlist(system,damage):
    w,a=writer(system)
    owner=short.NativeQDPositionPins(writer=w)
    feed=feed_for(owner)
    rows=candidates()
    rows[0].update(damage)
    with pytest.raises(ValueError,match="ROSTER_UNVERIFIED_OR_STALE_RANKING"):
        short.apply_ranked_shortlist(
            feed=feed,owner=owner,ranked=rows,
            ranking_authority=TestRankingIssuer(),now=1000)
    assert feed.roster_revision==0


def test_original_native_release_is_still_read_only_no_operating_authority():
    from scripts.observation_runtime.atlas_r16_nine_gate_evidence_inventory import inspect
    from scripts.observation_runtime.personal_existing_native_resource_evidence import inspect_two_lane_native_roots
    g=inspect()
    roots=inspect_two_lane_native_roots()
    assert g["source_release"]=="R16"
    assert g["independently_accepted_gate_count"]==0
    assert roots["native_root_total"]==12
    assert roots["all_twelve_distinct_and_empty"] is True
