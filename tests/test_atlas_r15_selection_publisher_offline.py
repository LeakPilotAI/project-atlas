"""R15 future selection publisher is source-complete but NEVER preapproved."""
import hashlib
import json
from pathlib import Path

import pytest

from scripts import atlas_r15_code_only_selection_publisher as pub
from scripts import release_selection


def fake_proposal():
    row={
        "schema":"QD_RELEASE_SELECTION_RECEIPT_V1",
        "domain":"WINDOWS_LOCAL",
        "revision":14,
        "action":"SELECT",
        "operation":"b"*32,
        "previous":pub.handoff.R14_HEAD,
        "selected":{
            "schema":"QD_INSTALLED_RELEASE_REFERENCE_V1",
            "domain":"WINDOWS_LOCAL",
            "release":pub.handoff.SOURCE_COMMIT,
            "root":str(pub.handoff.TARGET),
            "receipt":str(pub.handoff.RECEIPT),
            "receipt_sha256":"c"*64,
            "artifact_digest":"d"*64,
        },
        "restores":None,
    }
    return {
        "schema":"ATLAS_R15_CODE_SELECTION_HANDOFF_V1",
        "status":"SOURCE_ONLY_CANDIDATE_REQUIRES_NATIVE_HANDLE_VERIFIER_AND_ONE_SHOT_SELECTION_APPROVAL",
        "proposed_row":row,
        "proposed_row_digest":release_selection.digest(row),
    }


def approval(proposal):
    row=proposal["proposed_row"]
    return {
        "schema":"ATLAS_R15_NATIVE_CODE_SELECTION_APPROVAL_V1",
        "decision":pub.OPERATION,
        "scope":pub.SCOPE,
        "operator_sid":"S-1-5-21-1-2-3-1001",
        "source_commit":pub.handoff.SOURCE_COMMIT,
        "predecessor_r14_head":pub.handoff.R14_HEAD,
        "native_selection_revision":14,
        "proposed_head":proposal["proposed_row_digest"],
        "installed_receipt_sha256":row["selected"]["receipt_sha256"],
        "operation":row["operation"],
        "publisher_source_sha256":hashlib.sha256(Path(pub.__file__).read_bytes()).hexdigest(),
        "one_shot":True,
        "selection_allowed":True,
        "financial_authority":False,
        "paper_accounts":False,
        "provider_access":False,
        "paper_start_authorized":False,
        "live_orders_authorized":False,
    }


def test_native_selection_waits_for_separate_installed_receipt():
    row=pub.inspect()
    assert row["status"]=="WAITING_FOR_SEPARATELY_AUTHORIZED_R15_CODE_ONLY_INSTALL"
    assert row["target_revision"]==14
    assert row["exact_one_shot_operator_approval_pinned"] is False
    assert row["native_installed_child_readback_completed"] is False
    assert row["native_selection_published"] is False
    assert row["paper_start_authorized"] is False
    assert pub.APPROVAL_SHA256 is None
    assert not pub.APPROVAL.exists()
    assert not (pub.handoff.SELECTION_ROOT/"r0014.json").exists()


def test_pure_operator_decision_requires_exact_installed_receipt_and_sid():
    proposal=fake_proposal()
    row=approval(proposal)
    out=pub.validate_operator_decision(
        row,sid="S-1-5-21-1-2-3-1001",proposal=proposal)
    assert out["selection_allowed"] is True
    assert out["financial_authority"] is False
    assert out["provider_access"] is False


@pytest.mark.parametrize("key,value",[
    ("one_shot",False),("financial_authority",True),
    ("paper_accounts",True),("provider_access",True),
    ("paper_start_authorized",True),("live_orders_authorized",True),
    ("source_commit","f"*40),
    ("predecessor_r14_head","f"*64),
    ("native_selection_revision",13),
    ("proposed_head","0"*64),
    ("installed_receipt_sha256","0"*64),
    ("publisher_source_sha256","0"*64),
    ("operation","0"*32),
])
def test_forged_grant_or_altered_code_selection_refused(key,value):
    proposal=fake_proposal()
    row=approval(proposal)
    row[key]=value
    with pytest.raises(ValueError,match="EXACT_SID_BOUND_ONE_SHOT"):
        pub.validate_operator_decision(
            row,sid="S-1-5-21-1-2-3-1001",proposal=proposal)


def test_duplicate_or_foreign_operator_grants_refused():
    proposal=fake_proposal()
    row=approval(proposal)
    with pytest.raises(ValueError,match="EXACT_SID_BOUND_ONE_SHOT"):
        pub.validate_operator_decision(
            row,sid="S-1-5-21-9-8-7-1001",proposal=proposal)
    row["PROVIDER_UNRESTRICTED"]=True
    with pytest.raises(ValueError,match="EXACT_SID_BOUND_ONE_SHOT"):
        pub.validate_operator_decision(
            row,sid="S-1-5-21-1-2-3-1001",proposal=proposal)


def test_no_foreign_readonly_proposal_can_activate_install_or_selection():
    proposal=fake_proposal()
    for changed in ({"status":"GO"},
                    {"proposed_row_digest":"f"*64}):
        bad={**proposal,**changed}
        with pytest.raises(ValueError,match="EXACT_SID_BOUND_ONE_SHOT"):
            pub.validate_operator_decision(
                approval(proposal),sid="S-1-5-21-1-2-3-1001",proposal=bad)


def test_unapproved_publish_exits_before_selection_or_network(monkeypatch):
    with pytest.raises(ValueError,match="APPROVAL_NOT_PINNED"):
        pub.require_operator_approval(fake_proposal())
    with pytest.raises(ValueError,match="APPROVAL_NOT_PINNED"):
        pub.publish(clock=object(),proof={"elapsed_seconds":180,"samples":37})


def test_cli_cannot_create_clock_or_publish_without_synthetic_install(monkeypatch):
    from scripts.observation_runtime import atlas_independent_ntp_clock as ntp
    monkeypatch.setattr(ntp,"IndependentNtpClock",
                        lambda **_:pytest.fail("NTP_MUST_NOT_START"))
    with pytest.raises(ValueError,match="APPROVAL_NOT_PINNED"):
        pub.main(["--execute-one-shot-code-selection",
                  "--confirm-scope",pub.SCOPE])
    with pytest.raises(ValueError,match="EXACT_CODE_ONLY_SCOPE_REQUIRED"):
        pub.main(["--execute-one-shot-code-selection",
                  "--confirm-scope","LIVE_ORDERS"])
    with pytest.raises(SystemExit):
        pub.main(["--paper-live"])
    assert pub.main(["--inspect"])["native_selection_published"] is False


def test_publisher_does_not_acquire_same_native_selector_mutex_recursively():
    import inspect
    source=inspect.getsource(pub.publish)
    # Handoff.inspection acquires the selector's mutex itself; only outside
    # the publishing lock is this permissible.
    assert source.count("proposal=handoff.inspect()")==1
    locked=source.split("with store.locked():",1)[1]
    assert "=handoff.inspect()" not in "\n".join(
        line for line in locked.splitlines() if not line.lstrip().startswith("#"))
    assert "refreshed=handoff.candidate_from_receipt" in source
    assert "store.publish(row)" in source
