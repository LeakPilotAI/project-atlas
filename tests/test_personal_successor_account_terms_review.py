"""Pure finance-terms review of new R26 successor epoch, no grants/files."""
import copy
import pytest
from app.services.paper_financial_replay import digest
import scripts.observation_runtime.personal_successor_account_terms_review as target
from scripts.observation_runtime.personal_successor_native_root_scope import successor_root_plan

RELEASE="d"*40
DIGEST="c"*64
NONCE="0123456789abcdef01234567"


def fixture(monkeypatch):
    p=successor_root_plan(successor_release=RELEASE,epoch_nonce=NONCE)
    terms={
        "QUALITY_DIPS":{"schema":"PAPER_EPOCH_AUTONOMOUS_QD_V1",
                        "strategy":"QUALITY_DIPS","currency":"USD",
                        "opening_cash":"1000","opened_at":1795104014,
                        "cost_policy":"SIDE_NOTIONAL_FEE_SLIPPAGE_V1",
                        "fees_bps":"2","slippage_bps":"2",
                        "autonomous_policy":{"schema":"SIMULATED_POLICY"},
                        "timezone":"America/New_York","initial_net_r":"0",
                        "provenance":"ACCEPTED_AUTONOMOUS_PAPER_PARAMETERS_V1"},
        "HYPERLIQUID":{"schema":"PAPER_EPOCH_PERP_OPERATIONAL_V1",
                       "strategy":"HYPERLIQUID_PAPER","currency":"USDC",
                       "opening_cash":"1000","opened_at":1795104014,
                       "cost_policy":"PERP_QUOTE_PLUS_CASH_COST_V2",
                       "perp_policy":{"schema":"SIMULATED_PERP","symbols":["BTC","ETH","SOL"],
                                      "taker_bps":"10","slippage_bps":"5"},
                       "timezone":"UTC","initial_net_r":"0",
                       "provenance":"ACCEPTED_PERP_PAPER_PARAMETERS_V1"},
    }
    originals={}
    for lane in target.LANES:
        m=terms[lane]
        m["epoch"]=target.ORIGINAL_EPOCHS[lane]
        m["release"]=target.R26_DIGEST
        originals[lane]={
            "schema":"SYNTHETIC_R26_"+lane,
            "release_digest":target.R26_DIGEST,
            "epoch":m["epoch"],"account_id":target.ORIGINAL_ACCOUNTS[lane],
            "inception_digest":digest(m),
            "policy_digest":digest(m.get("autonomous_policy",m.get("perp_policy"))),
        }
    def fake_validate_enrollment(obj):
        assert obj["inception_digest"] in (digest(terms[lane]) for lane in target.LANES)
        return copy.deepcopy(obj)
    monkeypatch.setattr(target,"ORIGINAL_ENROLLMENT_DIGESTS",
                        {lane:digest(originals[lane]) for lane in target.LANES})
    monkeypatch.setattr(target,"ORIGINAL_MANIFEST_DIGESTS",
                        {lane:digest(terms[lane]) for lane in target.LANES})
    monkeypatch.setattr(target,"ORIGINAL_ECONOMIC_DIGESTS",
                        {lane:digest(target.economic_terms(terms[lane]))
                         for lane in target.LANES})
    monkeypatch.setattr(target,"validate_qd",fake_validate_enrollment)
    monkeypatch.setattr(target,"validate_hl",fake_validate_enrollment)
    monkeypatch.setattr(target,"validate_manifest",lambda m:None)
    monkeypatch.setattr(target,"validate_personal_inception",
                        lambda obj:(obj["lane"],obj["native_enrollment"],obj["parameters"]))
    from app.services import personal_paper_runtime
    monkeypatch.setattr(personal_paper_runtime,"validate_policy",lambda p:copy.deepcopy(p))
    args={"plan":p,"old_enrollments":originals,"old_manifests":terms,
          "personal_policy":{"simulation_only":True},
          "successor_artifact_digest":DIGEST}
    return args


def test_review_packet_preserves_all_economic_terms_and_forbids_authority(monkeypatch):
    args=fixture(monkeypatch)
    before=copy.deepcopy(args)
    out=target.derive_reviewable_successor_terms(**args)
    assert args==before
    assert out["schema"]==target.SCHEMA
    assert out["status"]=="EXACT_NEW_EPOCH_TERMS_FOR_OPERATOR_REVIEW_ONLY"
    assert out["new_operator_approval_issued"] is False
    assert out["old_approval_transferred"] is False
    assert out["new_journal_or_account_created"] is False
    assert out["paper_start_authorized"] is False
    assert out["live_money_trading_authorized"] is False
    assert len(out["accounts"])==2
    for lane,entry in out["accounts"].items():
        assert entry["new_epoch"]==args["plan"]["lanes"][lane]["epoch"]
        assert entry["new_epoch"]!=target.ORIGINAL_EPOCHS[lane]
        assert entry["new_account_id"]!=target.ORIGINAL_ACCOUNTS[lane]
        assert entry["economic_terms_digest"]==digest(
            target.economic_terms(args["old_manifests"][lane]))
        assert entry["opening_timestamp_pending_independent_native_UTC"] is True
        assert entry["new_native_resource_ids_pending"] is True
        assert entry["new_windows_process_writer_roster_pending"] is True
        assert entry["new_local_operator_financial_review_required"] is True
        assert entry["account_initialized"] is False


@pytest.mark.parametrize("damage",[
    "old_account_id","old_epoch","old_release","manifest_release",
    "manifest_epoch","prior_inception_digest","prior_policy_digest",
    "zero_opened_at","forged_cash","one_lane_missing",
    "foreign_successor_plan","reused_old_release","invalid_digest",
    "successor_path_override","old_manifest_source_change",
])
def test_exact_original_history_and_new_epoch_terms_required(monkeypatch,damage):
    args=fixture(monkeypatch)
    q=args["old_enrollments"]["QUALITY_DIPS"]
    m=args["old_manifests"]["QUALITY_DIPS"]
    if damage=="old_account_id":q["account_id"]="ACCOUNT_ALREADY_CHANGED"
    elif damage=="old_epoch":q["epoch"]="OLD_OTHER_EPOCH"
    elif damage=="old_release":q["release_digest"]="e"*64
    elif damage=="manifest_release":m["release"]="e"*64
    elif damage=="manifest_epoch":m["epoch"]="OTHER"
    elif damage=="prior_inception_digest":q["inception_digest"]="f"*64
    elif damage=="prior_policy_digest":q["policy_digest"]="f"*64
    elif damage=="zero_opened_at":m["opened_at"]=0
    elif damage=="forged_cash":m["opening_cash"]="2000"
    elif damage=="one_lane_missing":args["old_manifests"].pop("HYPERLIQUID")
    elif damage=="foreign_successor_plan":args["plan"]["successor_release"]=target.ORIGINAL_RELEASE if hasattr(target,"ORIGINAL_RELEASE") else "a746d99240f91609825b015b369020a4035d6501"
    elif damage=="reused_old_release":args["successor_artifact_digest"]=target.R26_DIGEST
    elif damage=="invalid_digest":args["successor_artifact_digest"]="F"*64
    elif damage=="successor_path_override":args["plan"]["lanes"]["QUALITY_DIPS"]["roots"]["source"]=r"D:\AtlasPaper\QualityDips\OLD_R26"
    elif damage=="old_manifest_source_change":m["strategy"]="CHANGED"
    with pytest.raises((ValueError,AssertionError,KeyError)):
        target.derive_reviewable_successor_terms(**args)


def test_economic_hash_excludes_only_three_identity_fields_not_fees():
    old={"release":target.R26_DIGEST,"epoch":"original","opened_at":1,
         "currency":"USD","fees_bps":"2","opening_cash":"1000"}
    newer={**old,"release":"f"*64,"epoch":"successor","opened_at":2}
    assert digest(target.economic_terms(old))==digest(target.economic_terms(newer))
    newer["fees_bps"]="3"
    assert digest(target.economic_terms(old))!=digest(target.economic_terms(newer))
    newer["fees_bps"]="2"
    newer["opening_cash"]="900"
    assert digest(target.economic_terms(old))!=digest(target.economic_terms(newer))


def test_hash_pinned_original_refuses_self_consistent_rewritten_financial_history(monkeypatch):
    args=fixture(monkeypatch)
    original=args["old_enrollments"]["QUALITY_DIPS"]
    manifest=args["old_manifests"]["QUALITY_DIPS"]
    manifest["fees_bps"]="3"
    original["inception_digest"]=digest(manifest)
    # All locally recomputed digests agree, but they are not the immutable
    # native R26 journal and operator-reviewed account originally admitted.
    with pytest.raises(ValueError,match="SUCCESSOR_REVIEW_ORIGINAL"):
        target.derive_reviewable_successor_terms(**args)
