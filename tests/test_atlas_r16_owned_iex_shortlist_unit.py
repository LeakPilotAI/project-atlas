"""Pure no-I/O tests for the position-safe IEX roster under a synthetic cut.

Financial writer instances are deliberately uninitialized TEST-ONLY
objects so no native V5 fixture session, financial directory, actual account,
credentials or provider can be created. Never claim native enrollment.
The separate confined real-writer tests stay skipped absent their guard.
"""
from __future__ import annotations

import copy
import json

import pytest

from app.investment.alpaca_iex import IEXFeed
from app.services.quality_dips_unified_writer import EnrolledQualityDipsWriter
from scripts.observation_runtime import atlas_r16_owned_iex_shortlist as shortlist
from scripts.observation_runtime.alpaca_equity_catalog import inventory_snapshot


class FixtureRankingSigner:
    __test__ = False
    def verify_ranking(self, row):
        return row["source"] == "DISPOSABLE_SIGNER_NOT_A_PROVIDER"


def dummy_writer():
    # Create only the exact Python TYPE for dependency identity tests.
    # Deliberately no __init__, native files, V5 operational authority,
    # financial runtime, or actual _cut I/O. Never pass outside tests.
    writer = object.__new__(EnrolledQualityDipsWriter)
    writer.runtime, writer.authority, writer.store = object(), object(), object()
    writer.manifest = {"epoch": "PURE_TEST_NO_NATIVE_ACCOUNT"}
    cut = {
        "manifest":copy.deepcopy(writer.manifest),
        "head":"a"*64,"acknowledged_operations":{},
        "state":{"revision":0,"positions":{}},
    }
    writer._cut = lambda:copy.deepcopy(cut)
    return writer,cut


def owner_and_feed(*,entries=None):
    writer,cut=dummy_writer()
    if entries:
        cut["state"]["positions"]=copy.deepcopy(entries)
    owner=shortlist.NativeQDPositionPins(writer=writer)
    feed=IEXFeed(["S000"],position_symbols=owner.current)
    return owner,feed,writer,cut


def ranking(*,n=70,ts=1000):
    return [{"symbol":f"S{i:03d}","score":str(n-i),
             "revision":1,"at":ts,"source":"DISPOSABLE_SIGNER_NOT_A_PROVIDER"}
            for i in range(n)]


def catalog():
    return inventory_snapshot([
        {"class":"us_equity","symbol":f"S{i:03d}",
         "status":"active","tradable":True,
         "exchange":"NASDAQ","id":str(i)}
        for i in range(65)],captured_at="2026-11-11T10:00:00+00:00")


def open_position(symbol="S050",remaining="1"):
    return {"A":{"symbol":symbol,"remaining":remaining}}


def test_uninitialized_test_double_not_confused_with_default_financial_authority():
    with pytest.raises(ValueError,match="ACTUAL_ENROLLED_QD_WRITER_REQUIRED"):
        shortlist.NativeQDPositionPins(writer=object())


def test_synthetic_zero_position_ranked_shortlist_really_uses_iexfeed_rotation():
    owner,feed,w,cut=owner_and_feed()
    result=shortlist.apply_ranked_shortlist(
        feed=feed,owner=owner,ranked=list(reversed(ranking())),
        ranking_authority=FixtureRankingSigner(),now=1000)
    assert result["schema"]==shortlist.SCHEMA
    assert result["financial_position_pins_from_real_native_cut"]==[]
    # The *source method* would read an actual FS1 cut in live code; this
    # particular test object is intentionally synthetic and writes nothing.
    assert result["requested_symbols"]==[f"S{i:03d}" for i in range(30)]
    assert result["remaining_slots_for_research"]==30
    assert tuple(feed.symbols)==tuple(result["requested_symbols"])
    assert feed.roster_revision==1
    assert feed.connection=="DISCONNECTED"
    assert result["financial_execution_authorized"] is False
    assert result["source_entitlement_accepted"] is False
    assert result["paper_start_authorized"] is False
    assert result["native_financial_accounts_created"] is False
    assert shortlist.require_current_pins(feed=feed,owner=owner)==()


def test_open_position_pin_preempts_all_thirty_research_candidates():
    owner,feed,w,cut=owner_and_feed(entries=open_position())
    output=shortlist.apply_ranked_shortlist(
        feed=feed,owner=owner,ranked=ranking(),
        ranking_authority=FixtureRankingSigner(),now=1000)
    assert owner.current()==["S050"]
    assert output["requested_symbols"][0]=="S050"
    assert len(output["requested_symbols"])==30
    assert "S029" not in output["requested_symbols"]
    assert output["remaining_slots_for_research"]==29
    assert shortlist.require_current_pins(feed=feed,owner=owner)==("S050",)
    assert output["orders_created"]==0


def test_catalog_rotation_protects_held_position_across_all_research_buckets():
    owner,feed,w,cut=owner_and_feed(entries=open_position())
    source=catalog()
    one=shortlist.apply_catalog_research(
        feed=feed,owner=owner,catalog=source,offset=0)
    two=shortlist.apply_catalog_research(
        feed=feed,owner=owner,catalog=source,
        offset=one["research_cursor_next_not_committed"])
    three=shortlist.apply_catalog_research(
        feed=feed,owner=owner,catalog=source,
        offset=two["research_cursor_next_not_committed"])
    assert [x["requested_symbols"][0] for x in (one,two,three)]==["S050"]*3
    assert [len(x["requested_symbols"]) for x in (one,two,three)]==[30,30,7]
    visited=sum([x["requested_symbols"][1:] for x in (one,two,three)],[])
    assert len(visited)==len(set(visited))==64
    assert set(visited)=={f"S{i:03d}" for i in range(65)}-{"S050"}
    assert [x["feed_roster_revision"] for x in (one,two,three)]==[1,2,3]
    assert feed.connection=="DISCONNECTED"
    assert all(x["source_entitlement_accepted"] is False for x in (one,two,three))
    assert all(x["paper_start_authorized"] is False for x in (one,two,three))


def test_position_opened_after_plan_revokes_feed_and_invalidates_price_cache():
    owner,feed,w,cut=owner_and_feed()
    shortlist.apply_ranked_shortlist(
        feed=feed,owner=owner,ranked=ranking(),
        ranking_authority=FixtureRankingSigner(),now=1000)
    assert "S050" not in feed.symbols
    cut["state"]["revision"]=1
    cut["state"]["positions"]=open_position()
    cut["head"]="b"*64
    feed.connection="CONNECTED"
    feed.authenticated=feed.subscribed=True
    feed.quotes["S000"]={"symbol":"S000","state":"FRESH"}
    with pytest.raises(ValueError,match="POSITION_NOT_SUBSCRIBED"):
        shortlist.require_current_pins(feed=feed,owner=owner)
    assert feed.connection=="DISCONNECTED"
    assert feed.authenticated is feed.subscribed is False
    assert feed.quotes=={}


def test_wrong_position_reader_implementation_cannot_replace_authenticated_method():
    owner,feed,w,cut=owner_and_feed(entries=open_position())
    feed.position_symbols=lambda:["S000"]
    feed.connection="CONNECTED"
    feed.authenticated=feed.subscribed=True
    feed.quotes["S000"]={"symbol":"S000","state":"FRESH"}
    with pytest.raises(ValueError,match="RETAIN_EXACT_ENROLLED_POSITION_READER"):
        shortlist.apply_ranked_shortlist(
            feed=feed,owner=owner,ranked=ranking(),
            ranking_authority=FixtureRankingSigner(),now=1000)
    assert feed.connection=="DISCONNECTED" and feed.quotes=={}
    assert feed.authenticated is feed.subscribed is False


@pytest.mark.parametrize("fault",[
    "negative","nan","infinity","bad_symbol","duplicate_symbol",
    "too_many_positions","missing_remaining","missing_position","revision_bool",
    "revision_negative","head_missing","foreign_manifest","no_receipts",
    "cut_string","cut_rollback","same_revision_forgery","writer_component",
])
def test_corrupt_financial_cut_fails_closed_in_read_only_pin_reader(fault):
    owner,feed,w,cut=owner_and_feed()
    if fault=="negative":cut["state"]["positions"]=open_position(remaining="-1")
    elif fault=="nan":cut["state"]["positions"]=open_position(remaining="NaN")
    elif fault=="infinity":cut["state"]["positions"]=open_position(remaining="Infinity")
    elif fault=="bad_symbol":cut["state"]["positions"]=open_position(symbol="BTC/USD")
    elif fault=="duplicate_symbol":
        cut["state"]["positions"]={"A":{"symbol":"MSFT","remaining":"1"},
                                   "B":{"symbol":"MSFT","remaining":"2"}}
    elif fault=="too_many_positions":
        cut["state"]["positions"]={"A":{"symbol":"MSFT","remaining":"1"},
                                   "B":{"symbol":"SPY","remaining":"2"}}
    elif fault=="missing_remaining":cut["state"]["positions"]={"A":{"symbol":"MSFT"}}
    elif fault=="missing_position":cut["state"].pop("positions")
    elif fault=="revision_bool":cut["state"]["revision"]=True
    elif fault=="revision_negative":cut["state"]["revision"]=-1
    elif fault=="head_missing":cut.pop("head")
    elif fault=="foreign_manifest":cut["manifest"]={"epoch":"OTHER"}
    elif fault=="no_receipts":cut.pop("acknowledged_operations")
    elif fault=="cut_string":w._cut=lambda:"FORGED"
    elif fault=="cut_rollback":
        cut["state"]["revision"]=-1
    elif fault=="same_revision_forgery":cut["head"]="f"*64
    elif fault=="writer_component":w.runtime=object()
    with pytest.raises(ValueError):
        owner.current()


@pytest.mark.parametrize("damage",[
    "age","future","issuer","rank_duplicate","nan_score",
    "unknown_candidate","bad_symbol","capacity",
])
def test_unverified_research_candidates_cannot_renew_subscription(damage):
    owner,feed,w,cut=owner_and_feed(entries=open_position())
    rows=ranking()
    if damage=="age":rows[0]["at"]=900
    elif damage=="future":rows[0]["at"]=2000
    elif damage=="issuer":rows[0]["source"]="NOT_ACCEPTED"
    elif damage=="rank_duplicate":rows.append(copy.deepcopy(rows[0]))
    elif damage=="nan_score":rows[0]["score"]="NaN"
    elif damage=="unknown_candidate":rows[0]["revision"]=True
    elif damage=="bad_symbol":rows[0]["symbol"]="A/B"
    elif damage=="capacity":rows[0]["score"]="Infinity"
    with pytest.raises((ValueError,TypeError)):
        shortlist.apply_ranked_shortlist(
            feed=feed,owner=owner,ranked=rows,
            ranking_authority=FixtureRankingSigner(),now=1000)
    assert feed.roster_revision==0
    assert feed.connection=="DISCONNECTED"
    assert feed.snapshot()["paper_startup_authorized"] is False


def test_native_provider_remains_no_go_until_real_writer_exists():
    from scripts.observation_runtime.atlas_r16_nine_gate_evidence_inventory import inspect
    from scripts.observation_runtime.personal_existing_native_resource_evidence import inspect_two_lane_native_roots
    g=inspect()
    roots=inspect_two_lane_native_roots()
    assert g["source_release"]=="R16"
    assert g["independently_accepted_gate_count"]==0
    assert roots["all_twelve_distinct_and_empty"] is True
    assert roots["native_root_total"]==12


def test_broken_financial_owner_during_shortlist_refresh_disconnects_existing_feed():
    owner,feed,w,cut=owner_and_feed()
    feed.connection="CONNECTED"
    feed.authenticated=feed.subscribed=True
    feed.quotes["S000"]={"symbol":"S000","state":"FRESH"}
    cut["state"]["revision"]=-1
    with pytest.raises(ValueError,match="REVISION_REQUIRED"):
        shortlist.apply_ranked_shortlist(
            feed=feed,owner=owner,ranked=ranking(),
            ranking_authority=FixtureRankingSigner(),now=1000)
    assert feed.connection=="DISCONNECTED" and not feed.quotes
    assert feed.authenticated is feed.subscribed is False


def test_financial_position_changes_inside_roster_rotation_clears_old_quote_cache(monkeypatch):
    owner,feed,w,cut=owner_and_feed()
    original=feed.request_roster
    def switch_after_request(row):
        original(row)
        cut["state"]["revision"]=1
        cut["state"]["positions"]=open_position()
        cut["head"]="b"*64
    monkeypatch.setattr(feed,"request_roster",switch_after_request)
    feed.quotes["S000"]={"symbol":"S000","state":"FRESH"}
    with pytest.raises(ValueError,match="POSITIONS_CHANGED_DURING_ROTATION"):
        shortlist.apply_ranked_shortlist(
            feed=feed,owner=owner,ranked=ranking(),
            ranking_authority=FixtureRankingSigner(),now=1000)
    assert feed.connection=="DISCONNECTED" and feed.quotes=={}
    assert feed.authenticated is feed.subscribed is False


def test_position_owner_cannot_be_swapped_between_planning_and_final_feed_readback(monkeypatch):
    owner,feed,w,cut=owner_and_feed(entries=open_position())
    original=owner.current
    calls=[0]
    def changing():
        calls[0]+=1
        if calls[0]>=3:
            cut["state"]["revision"]=1
            cut["state"]["positions"]=open_position("S051")
            cut["head"]="c"*64
        return original()
    monkeypatch.setattr(owner,"current",changing)
    # Rebound owner observation changes midway through native-feed handoff;
    # the retained class-method callback catches a mismatch and disconnects.
    with pytest.raises(ValueError,match="POSITIONS_CHANGED_DURING_ROTATION"):
        shortlist.apply_ranked_shortlist(
            feed=feed,owner=owner,ranked=ranking(),
            ranking_authority=FixtureRankingSigner(),now=1000)
    assert feed.roster_revision==1
    assert feed.connection=="DISCONNECTED" and feed.quotes=={}
