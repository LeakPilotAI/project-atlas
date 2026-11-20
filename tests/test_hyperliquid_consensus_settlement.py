"""Funding-rate history is not the historical settlement oracle.

Use original HyperCore event identity/order in *operational* source claims.
All examples are synthetic and must still be checked by independent source
authorities; no public requests, wallets, trades or financial mutation.
"""
import copy
import pytest

from app.adapters.hyperliquid import _paper_funding_observation
from app.services.hyperliquid_consensus_settlement import (
    require_consensus_settlement_oracle,
)
from test_hyperliquid_current_producer import STAMP, fixture

AT=7200
RATE="-0.001"


def history(at=AT, rate=RATE):
    atms=at*1000
    return _paper_funding_observation(
        "BTC",
        [{"coin":"BTC","fundingRate":rate,"premium":"0.01","time":atms+76}],
        atms,atms+3600000,atms+1000,atms+1000,
    )["records"][0]


def proof(at=AT, rate=RATE):
    return {
        "schema":"HL_CONSENSUS_SETTLEMENT_ORACLE_V1",
        "venue":"HYPERCORE_NATIVE_PERPS",
        "symbol":"BTC",
        "settlement_at":at,
        "price":"100.3",
        "source_id":"SYNTHETIC_NOT_A_REAL_CONSENSUS_RECORD",
        "revision":1,
        "price_block":10000,
        "settlement_block":10007,
        "price_event_at_ms":at*1000-3000,
        "settlement_event_at_ms":at*1000+23,
        "funding_rate":rate,
        "oracle_action_digest":"a"*64,
        "funding_action_digest":"b"*64,
    }


def test_valid_original_consensus_shape_is_not_trading_authorization():
    oracle=proof()
    frozen=copy.deepcopy(oracle)
    assert require_consensus_settlement_oracle(
        oracle,symbol="BTC",at=AT,funding_record=history()) is None
    assert oracle==frozen


@pytest.mark.parametrize("damage", [
    "legacy", "current_live_oracle", "schema", "wrong_coin", "wrong_hour",
    "future_oracle_block", "future_oracle_event", "stale_oracle_event",
    "before_hour_settlement", "late_settlement", "boolean_revision",
    "missing_funding_digest", "bad_oracle_digest", "wrong_rate",
    "negative_price", "unset_source", "unknown_venue", "missing_proof_field",
])
def test_invalid_or_nonhistorical_oracle_source_never_admitted(damage):
    oracle=proof()
    if damage=="legacy":
        oracle={k:oracle[k] for k in
                ("symbol","settlement_at","price","source_id","revision")}
    elif damage=="current_live_oracle":
        oracle={"symbol":"BTC","oraclePx":"100.3","markPx":"101"}
    elif damage=="schema":
        oracle["schema"]="LIVE_MARK_CONTEXT"
    elif damage=="wrong_coin":
        oracle["symbol"]="ETH"
    elif damage=="wrong_hour":
        oracle["settlement_at"]=AT+3600
    elif damage=="future_oracle_block":
        oracle["price_block"]=oracle["settlement_block"]+1
    elif damage=="future_oracle_event":
        oracle["price_event_at_ms"]=oracle["settlement_event_at_ms"]+1
    elif damage=="stale_oracle_event":
        oracle["price_event_at_ms"]=AT*1000-60001
    elif damage=="before_hour_settlement":
        oracle["settlement_event_at_ms"]=AT*1000-1
    elif damage=="late_settlement":
        oracle["settlement_event_at_ms"]=AT*1000+30001
    elif damage=="boolean_revision":
        oracle["revision"]=True
    elif damage=="missing_funding_digest":
        del oracle["funding_action_digest"]
    elif damage=="bad_oracle_digest":
        oracle["oracle_action_digest"]="unverified"
    elif damage=="wrong_rate":
        oracle["funding_rate"]="0"
    elif damage=="negative_price":
        oracle["price"]="-100"
    elif damage=="unset_source":
        oracle["source_id"]=""
    elif damage=="unknown_venue":
        oracle["venue"]="SPOT_MARKET"
    else:
        oracle["extra"]="UNTRUSTED"
    with pytest.raises(ValueError):
        require_consensus_settlement_oracle(
            oracle,symbol="BTC",at=AT,funding_record=history())


@pytest.mark.parametrize("bad_record", [
    {"settlement_at_ms":AT*1000+1000},
    {"provider_event_at_ms":AT*1000+30001},
    {"settlement_oracle":"CURRENT_LIVE_QUOTE"},
    {"hourly_rate":"0.02"},
])
def test_incomplete_or_mismatched_funding_rate_cannot_backdoor_oracle(bad_record):
    h=history()
    h.update(bad_record)
    with pytest.raises(ValueError):
        require_consensus_settlement_oracle(
            proof(),symbol="BTC",at=AT,funding_record=h)


def _funding_fixture(monkeypatch):
    f=fixture(monkeypatch)
    at=(STAMP//3600-1)*3600
    start=at*1000
    raw=[{"coin":"BTC","fundingRate":RATE,"premium":"0.01","time":start+76}]
    parsed=_paper_funding_observation("BTC",raw,start,start+3600000,
                                      STAMP*1000,STAMP*1000)
    f.adapter._cache_paper("funding","BTC",{
        "rows":raw,"started_ms":STAMP*1000,"parsed":parsed})
    f.cut["settlements"][f"BTC:{at}"]=proof(at=at)
    f.sync()
    # Directly exercising the original publication parser: the owner normally
    # pins this port only inside _prepare()/readback under its bounded lock.
    f.owner._evidence.cut=f.cut
    return f,at


def test_operational_publication_refuses_old_unproven_historical_oracle(monkeypatch):
    f,at=_funding_fixture(monkeypatch)
    # The original disposable harness must remain readable, while the
    # operational source *must* enforce stronger event provenance.
    old={k:f.cut["settlements"][f"BTC:{at}"][k] for k in
         ("symbol","settlement_at","price","source_id","revision")}
    f.cut["settlements"][f"BTC:{at}"]=old
    f.orders.manifest["schema"]="PAPER_EPOCH_PERP_OPERATIONAL_V1"
    with pytest.raises(ValueError,match="ORIGINAL_CONSENSUS"):
        f.owner.publication.prepare_capture()


def test_operational_publication_requires_separate_authority_and_rate_binding(monkeypatch):
    f,at=_funding_fixture(monkeypatch)
    f.orders.manifest["schema"]="PAPER_EPOCH_PERP_OPERATIONAL_V1"
    original=f.cut["settlements"][f"BTC:{at}"]
    original["funding_rate"]="0"
    with pytest.raises(ValueError,match="RATE_OR_PRICE"):
        f.owner.publication.prepare_capture()
    original["funding_rate"]=RATE
    f.auth.verify_settlement=lambda *_: False
    with pytest.raises(ValueError,match="AUTHENTICATED_HISTORICAL_ORACLE"):
        f.owner.publication.prepare_capture()


def test_disposable_old_settlement_shape_preserves_historical_fixture_replay(monkeypatch):
    f,at=_funding_fixture(monkeypatch)
    old={k:f.cut["settlements"][f"BTC:{at}"][k] for k in
         ("symbol","settlement_at","price","source_id","revision")}
    f.cut["settlements"][f"BTC:{at}"]=old
    packet,_=f.owner.publication.prepare_capture()
    assert packet["oracles"][f"BTC:{at}"]==old
    assert packet["funding"]["BTC"]["settlement_evidence_complete"] is False

@pytest.mark.asyncio
@pytest.mark.parametrize("kind",[
    "old_five_fields", "live_oracle_context", "wrong_rate",
    "wrong_settlement_block", "approved_shape",
])
async def test_operational_paper_planner_refuses_unproven_oracle_even_if_verifier_claims_yes(kind):
    """Calls the original next_proposal method with isolated in-memory ports.

    All authority approvals here are synthetic. No RestingPerpWriter, native
    storage, network, account or actual PAPER operation is created.
    """
    from types import SimpleNamespace
    from app.services.perp_source_planner import PerpSourcePlanner

    at=AT
    data=proof()
    if kind=="old_five_fields":
        data={k:data[k] for k in
              ("symbol","settlement_at","price","source_id","revision")}
    elif kind=="live_oracle_context":
        data={"symbol":"BTC","settlement_at":AT,"price":"100.3",
              "source_id":"LIVE_ORACLE_QUOTE_NOT_HISTORICAL","revision":1}
    elif kind=="wrong_rate":
        data["funding_rate"]="0"
    elif kind=="wrong_settlement_block":
        data["price_block"]=data["settlement_block"]+1
    record=history()
    rates={"schema":"ATLAS_HYPERLIQUID_FUNDING_HISTORY_V1",
           "symbol":"BTC","rate_history_complete":True,"records":[record]}
    packet={"funding":{"BTC":rates},"oracles":{f"BTC:{at}":data}}
    cut={"state":{"positions":{"synthetic-position":{
        "remaining":"0.5","next_funding":at,"symbol":"BTC","revision":1}},
        "revision":2}}
    authority_calls=[]
    def verify_settlement(*args):
        authority_calls.append(True)
        return True
    writer=SimpleNamespace(
        manifest={"schema":"PAPER_EPOCH_PERP_OPERATIONAL_V1",
                  "epoch":"SYNTHETIC_ONLY","perp_policy":{"funding_source":"synthetic-funding"}},
        authority=SimpleNamespace(verify_settlement_source=verify_settlement),
        binding={"SYNTHETIC_ONLY":True},
        _control=lambda:{"state":{"orders":{}}})
    dummy=SimpleNamespace(
        writer=writer,
        clock=lambda:at+1,
        _source=lambda observation,cut:packet,
        _proposal=lambda command,source_cut,source_packet:{
            "kind":command["kind"],"evidence":command["evidence"]})
    if kind != "approved_shape":
        with pytest.raises(ValueError):
            await PerpSourcePlanner.next_proposal(dummy,None,cut)
        assert authority_calls==[]  # invalid evidence never reaches issuer
    else:
        proposed=await PerpSourcePlanner.next_proposal(dummy,None,cut)
        assert authority_calls==[True]
        assert proposed["kind"]=="FUNDING"
        assert proposed["evidence"]["rate"]==RATE
        assert proposed["evidence"]["oracle"]=="100.3"
