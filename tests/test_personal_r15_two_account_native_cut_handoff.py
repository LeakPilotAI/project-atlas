"""R15 two-account post-inception handoff: synthetic tests, NO native publication.

Uses real source validators and in-memory once-only publication receipts.
Synthetic Windows output/coordination adapters exercise the integration only;
they are NEVER accepted financial authority or native commissioning evidence.
"""
import copy
from pathlib import Path as RealPath
from types import SimpleNamespace

import pytest

from app.services.paper_financial_replay import (
    body, digest, initial_state,
)
from app.services.personal_native_coordination import PersonalNativeCoordination
from app.services.personal_paper_runtime import PersonalOperatorInstallation
from scripts.observation_runtime import personal_paper_inception as inception
from scripts.observation_runtime import personal_r15_owned_job_activation as gate
from scripts.observation_runtime.personal_coordination_store import NativePersonalCoordinationImages

from test_personal_paper_inception_memory import system


def synthetic_pair(monkeypatch):
    q, h = system("QUALITY_DIPS"), system("HYPERLIQUID")
    # Both independent simulated lanes use unique identities and account IDs.
    for lane, test in (("QUALITY_DIPS", q), ("HYPERLIQUID", h)):
        e = test.b.enrollment
        n = e["native_enrollment"]
        n["account_id"] = "SYNTHETIC-R15-" + lane
        e["report_scope"]["account_id"] = n["account_id"]
        n["epoch"] = test.m["epoch"]
        for idx, role in enumerate(gate.ROLES):
            resource = n["resources"][role]
            resource["path"] = rf"D:\SyntheticOnly\{lane}\{role}"
            resource["native_id"] = [123, 1000 + (0 if lane=="QUALITY_DIPS" else 100) + idx, 0]
    # The prepublication manifests/contract must still be independently valid.
    for test in (q, h):
        inception.validate_personal_inception(test.b.enrollment)
        test.pub.publish()
    original_qd = copy.deepcopy(q.b.enrollment["native_enrollment"])
    original_hl = copy.deepcopy(h.b.enrollment["native_enrollment"])
    accounts={"QUALITY_DIPS": original_qd, "HYPERLIQUID": original_hl}

    def evidence(empty):
        lanes={}
        for lane, account in accounts.items():
            roots={}
            for role, resource in account["resources"].items():
                roots[role]={
                    "path": resource["path"],
                    "native_id": list(resource["native_id"]),
                    "native_identity_verified": True,
                    "existing_empty_namespace_verified": empty,
                }
            lanes[lane]={"epoch": account["epoch"], "roots": roots}
        return {
            "schema": "ATLAS_TWO_LANE_EXISTING_NATIVE_ROOT_PRE_ENROLLMENT_V1",
            "lanes": lanes,
            "native_root_total": 12,
            "native_root_ids_verified": 12,
            "existing_empty_root_namespaces": 12 if empty else 0,
            "all_twelve_distinct_and_empty": empty,
            "operator_account_enrollment_verified": False,
            "writer_ownership_verified": False,
            "financial_inception_verified": False,
            "paper_start_authorized": False,
            "live_trading_authorized": False,
            "filesystem_writes": 0,
            "network_requests": 0,
        }
    binding=gate.require_exact_r15_preinception_roots(
        original_qd, original_hl, evidence(True))
    owner=object.__new__(gate.RetainedSelectedR15OwnerJob)
    owner._qd=digest(original_qd)
    owner._perp=digest(original_hl)
    owner._original_qd=copy.deepcopy(original_qd)
    owner._original_perp=copy.deepcopy(original_hl)
    owner._native_root_binding=binding
    checked=[]
    def check_worker(self):
        checked.append(True)
        return True
    monkeypatch.setattr(gate.RetainedSelectedR15OwnerJob,"_verify_owned_worker",check_worker)
    monkeypatch.setattr(gate, "inspect_two_lane_native_roots",lambda:copy.deepcopy(evidence(False)))
    monkeypatch.setattr(gate, "ARTIFACT", original_qd["release_digest"])

    # Test-only fake factory around the genuine FS1/FS3 source verifier.
    lookup={}
    for lane, test in (("QUALITY_DIPS",q),("HYPERLIQUID",h)):
        for role, resource in test.b.enrollment["native_enrollment"]["resources"].items():
            lookup[resource["path"]] = (test, role)
    closed=[]
    class Output:
        def __init__(self,path):
            self.root=path
            self.root_handle=path
        def _verify(self):
            return True
        def close(self):
            closed.append(self.root)
    def file_id(path):
        test, role=lookup[path]
        return test.b.enrollment["native_enrollment"]["resources"][role]["native_id"]
    def read_bound(out,name,binding):
        test, role=lookup[out.root]
        value=test.files.values[(role,name)]
        if digest(value)!=binding["sha256"]:
            raise ValueError("SYNTHETIC_BOUND_HASH_MISMATCH")
        return body(value).encode(), binding["id"]
    native=SimpleNamespace(
        w=SimpleNamespace(WindowsOutput=Output),
        native=SimpleNamespace(file_identity=file_id),
        read_bound=read_bound,
    )
    monkeypatch.setattr(inception, "native_primitives", lambda:native)
    def path(value):
        if str(value) in lookup:
            test, role=lookup[str(value)]
            return SimpleNamespace(iterdir=lambda:iter(
                SimpleNamespace(name=name)
                for (r,name) in test.files.values if r==role))
        return RealPath(value)
    monkeypatch.setattr(inception,"Path",path)

    installation=object.__new__(PersonalOperatorInstallation)
    installation.accounts={lane:digest(n) for lane,n in accounts.items()}
    installation.release=original_qd["release_digest"]
    issuer=inception.PersonalPublicationIssuer(installation=installation)

    for test in (q,h):
        test.b.readback=inception.NativePersonalInitialReadback()
        test.b.issuer=issuer
        test.ledger.db.execute("CREATE TABLE projections (receipt TEXT)")
        test.ledger.db.commit()
        fake_images=object.__new__(NativePersonalCoordinationImages)
        enrolled=test.b.enrollment["native_enrollment"]
        root=enrolled["resources"]["coordination"]
        fake_images.root=root["path"]
        fake_images.root_id=list(root["native_id"])
        fake_images.enrollment=digest(enrolled)
        ledger=object.__new__(PersonalNativeCoordination)
        ledger.images=fake_images
        ledger.manifest=test.b.enrollment["parameters"]
        ledger.connect=test.ledger.connect
        m=ledger.manifest
        ledger._load=lambda db,m=m:(initial_state(m),digest(m),[])
        test.b.publication.ledger=ledger
    return SimpleNamespace(
        q=q,h=h, owner=owner,qd=original_qd,perp=original_hl,
        checked=checked,closed=closed, issuer=issuer,
    )


def close_pair(s):
    for test in (s.q,s.h):
        test.ledger.db.close()


def inspect(s):
    return s.owner.inspect_both_committed_initial_cuts(
        qd=s.qd,perp=s.perp,
        qd_bootstrap=s.q.b,perp_bootstrap=s.h.b)


def test_two_lane_synthetic_receipt_reader_wiring_never_issues_financial_grant(monkeypatch):
    s=synthetic_pair(monkeypatch)
    try:
        result=inspect(s)
        assert result["schema"]=="ATLAS_R15_TWO_LANE_INITIAL_NATIVE_CUT_TECHNICAL_READBACK_V1"
        assert set(result["lanes"])=={"QUALITY_DIPS","HYPERLIQUID"}
        assert all(item["initial_cash_simulated"]=="1000" and item["initial_position_count"]==0
                   for item in result["lanes"].values())
        assert result["acknowledged_native_initial_cuts_reverified"] is True
        assert result["financial_operating_authority_granted"] is False
        assert result["persistent_financial_writer_lease_issued"] is False
        assert result["financial_startup_authorized"] is False
        assert result["live_trading_authorized"] is False
        assert len(s.checked)==3
        assert len(s.closed)==12
    finally:
        close_pair(s)


@pytest.mark.parametrize("failure", [
    "no_perp_bootstrap", "one_fake_issuer", "foreign_job_enrollment",
    "wrong_release", "missing_native_ledger", "wrong_native_images",
    "unacknowledged_receipt", "pending_projection",
    "nonzero_position", "wrong_cash", "bad_fs3_receipt",
])
def test_two_lane_initial_cut_fails_closed_for_missing_native_or_ack(failure,monkeypatch):
    s=synthetic_pair(monkeypatch)
    try:
        q,h=s.q,s.h
        kwargs=dict(qd=s.qd,perp=s.perp,
                    qd_bootstrap=q.b,perp_bootstrap=h.b)
        if failure=="no_perp_bootstrap":
            kwargs["perp_bootstrap"]=None
        elif failure=="one_fake_issuer":
            h.b.issuer=object()
        elif failure=="foreign_job_enrollment":
            kwargs["qd"]=copy.deepcopy(s.qd)
            kwargs["qd"]["account_id"]+="FOREIGN"
        elif failure=="wrong_release":
            monkeypatch.setattr(gate,"ARTIFACT","f"*64)
        elif failure=="missing_native_ledger":
            q.b.publication.ledger=object()
        elif failure=="wrong_native_images":
            h.b.publication.ledger.images.root_id=[1,2,3]
        elif failure=="unacknowledged_receipt":
            h.ledger.db.execute("UPDATE personal_publications SET state='PENDING'")
            h.ledger.db.commit()
        elif failure=="pending_projection":
            q.ledger.db.execute("INSERT INTO projections VALUES(NULL)")
            q.ledger.db.commit()
        elif failure=="nonzero_position":
            h.b.publication.ledger._load=lambda db:(dict(initial_state(h.m),positions={"BTC":"SYNTHETIC"}),digest(h.m),[])
        elif failure=="wrong_cash":
            q.b.publication.ledger._load=lambda db:(dict(initial_state(q.m),cash="2000"),digest(q.m),[])
        elif failure=="bad_fs3_receipt":
            h.files.values["report","0001-report.json"]["report_id"]="f"*64
        with pytest.raises((ValueError,TypeError,KeyError,AttributeError)):
            s.owner.inspect_both_committed_initial_cuts(**kwargs)
    finally:
        close_pair(s)
