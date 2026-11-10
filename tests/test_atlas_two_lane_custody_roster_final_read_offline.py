"""R14 workspace: end-of-lease writer identity before read-only PAPER cuts.

Exercises REAL UnifiedPortfolioCustody.read_accounts + UnifiedWriterRoster
over TWO inert synthetic writers. No market provider, native paths, accounts,
orders, financial journal mutation, runtime installation or AIP06 bypass.
"""
from __future__ import annotations

import copy
from types import SimpleNamespace

import pytest

from app.services.paper_financial_replay import digest
from app.services.unified_portfolio_custody import UnifiedPortfolioCustody
from app.services.unified_writer_roster import ROLES, EXCLUSIONS, UnifiedWriterRoster


class InertWriter:
    def __init__(self, lane):
        self.manifest = {
            "epoch":"DISPOSABLE_"+lane,
            "strategy":lane,
            "currency":"USD" if lane=="QUALITY_DIPS" else "USDC",
            "opening_cash":"1000",
        }
        self.cut = {
            "manifest":copy.deepcopy(self.manifest),
            "head":"SYNTHETIC_"+lane+"_READ_ONLY_HEAD",
            "root":[7,8,9],
            "state":{
                "revision":0, "cash":"1000", "available_cash":"1000",
                "gross":"0", "costs":"0", "net":"0",
                "fees":"0", "slippage":"0", "funding":"0",
                "positions":{},
            },
        }
    def _cut(self):
        return copy.deepcopy(self.cut)


class InertQDWriter(InertWriter):
    def attest_no_resting_orders(self, cut):
        return cut == self.cut


def fake_two_lane_custody(*, mutate_after_second_read=None):
    clock=lambda:100
    writers={
        "QUALITY_DIPS":InertQDWriter("QUALITY_DIPS"),
        "HYPERLIQUID":InertWriter("HYPERLIQUID"),
    }
    session="SYNTHETIC_SELECTED_R14_NO_FINANCIAL_AUTHORITY"
    grant={"session_id":session}
    process={"pid":17,"created":1234,"image":"D:/SYNTHETIC-NOT-A-PROCESS.exe"}
    roles={r:{
        "writer_id":r,
        "process":copy.deepcopy(process),
        "resource":[7,8,9],
    } for r in ROLES}
    enrollment={
        "schema":"ATLAS_UNIFIED_WRITER_RESOURCES_V1",
        "session_id":session,
        "account_binding":digest({k:digest(w.manifest) for k,w in writers.items()}),
        "writer_binding":"SYNTHETIC_TWO_LANE_ACCEPTED_FOR_THIS_TEST_ONLY",
        "roles":copy.deepcopy(roles),
        "exclusions":{k:"SYNTHETIC_ONLY_NO_EXTERNAL_PROOF" for k in EXCLUSIONS},
    }
    observed={
        "schema":"ATLAS_UNIFIED_WRITER_OBSERVATION_V1",
        "observed_at":100,
        "roles":copy.deepcopy(roles),
        "unknown_writers":[],
        "active_operations":dict.fromkeys(ROLES,0),
        "unknown_operations":False,
    }
    count={"read_cuts":0,"roster_reads":0}
    def roster_read(_):
        count["roster_reads"]+=1
        return copy.deepcopy(observed)
    roster_authority=SimpleNamespace(
        verify_enrollment=lambda *_:True,
        verify_observation=lambda *_:True,
        verify_drain=lambda *_:True,
    )
    roster=UnifiedWriterRoster(
        enrollment=enrollment,
        writers=writers,
        observer=SimpleNamespace(read=roster_read),
        authority=roster_authority, clock=clock,
    )
    policy={"schema":"SYNTHETIC_RISK_POLICY_ONLY"}
    journal_state={"state":{"operations":{}}}
    journal=SimpleNamespace(
        manifest={
            "accounts":{k:digest(w.manifest) for k,w in writers.items()},
            "policy_digest":digest(policy),
        },
        snapshot=lambda:copy.deepcopy(journal_state),
    )
    def verify_read_cuts(*_):
        count["read_cuts"]+=1
        if count["read_cuts"]==2 and mutate_after_second_read is not None:
            mutate_after_second_read(observed,roster_authority,writers)
        return True
    portfolio_authority=SimpleNamespace(
        verify_components=lambda *_:True,
        verify_read_cuts=verify_read_cuts,
    )
    custody=UnifiedPortfolioCustody(
        writers=writers, journal=journal, policy=policy,
        risk=object(), ownership=roster,
        authority=portfolio_authority,clock=clock,
    )
    return SimpleNamespace(
        custody=custody,grant=grant, observed=observed, count=count,
        writers=writers, roster_authority=roster_authority,
        journal_state=journal_state,
    )


def test_clean_two_lane_read_rechecks_writer_roster_after_financial_cut():
    s=fake_two_lane_custody()
    out=s.custody.read_accounts(s.grant)
    assert out["schema"]=="ATLAS_UNIFIED_ACCOUNT_CUTS_V1"
    assert out["state"]=="ACKNOWLEDGED"
    assert set(out["accounts"])=={"QUALITY_DIPS","HYPERLIQUID"}
    assert out["startup_authorized"] is False
    assert s.count["read_cuts"]==2
    assert s.count["roster_reads"]>=4
    assert out["accounts"]["QUALITY_DIPS"]["cash"]=="1000"
    assert out["accounts"]["HYPERLIQUID"]["currency"]=="USDC"


@pytest.mark.parametrize("damage",[
    "foreign_process",
    "unknown_operations",
    "process_incarnation",
    "changed_native_resource",
    "authority_revoked",
    "stale_native_observation",
])
def test_two_lane_account_read_must_refuse_after_final_internal_read(damage):
    def late_mutation(observed,authority,writers):
        if damage=="foreign_process":
            observed["unknown_writers"]=["UNENROLLED_POST_READ"]
        elif damage=="unknown_operations":
            observed["unknown_operations"]=True
        elif damage=="process_incarnation":
            observed["roles"]["GLOBAL_CUSTODY"]["process"]["created"]+=1
        elif damage=="changed_native_resource":
            observed["roles"]["PERP_SOURCE"]["resource"]=[1,3,5]
        elif damage=="authority_revoked":
            authority.verify_observation=lambda *_:False
        else:
            observed["observed_at"]=89
    s=fake_two_lane_custody(mutate_after_second_read=late_mutation)
    initial=copy.deepcopy(s.journal_state)
    before={k:copy.deepcopy(w.cut) for k,w in s.writers.items()}
    with pytest.raises(ValueError,match="NATIVE_WRITER_RESOURCE_OR_QUIESCENCE_UNVERIFIED|ROSTER_COMPONENT_OR_SESSION_CHANGED|WRITER_OBSERVATION_CLOCK_OR_FRESHNESS_CHANGED"):
        s.custody.read_accounts(s.grant)
    # The rejected observation did not place or retry even disposable orders.
    assert s.count["read_cuts"]==2
    assert s.count["roster_reads"]>=4
    assert s.journal_state==initial
    assert {k:w.cut for k,w in s.writers.items()}==before


def test_unexpected_financial_read_failure_is_not_hidden_by_lease_exit():
    s=fake_two_lane_custody()
    def invalid_read_cuts(*_):
        raise OSError("SYNTHETIC_ACCOUNT_CUT_UNKNOWN")
    s.custody.authority.verify_read_cuts=invalid_read_cuts
    result=s.custody.read_accounts(s.grant)
    assert result["state"]=="UNKNOWN"
    assert result["accounts"] is None
    assert result["startup_authorized"] is False
    assert s.count["roster_reads"]>=2
