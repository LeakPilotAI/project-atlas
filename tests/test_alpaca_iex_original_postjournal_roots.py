"""Atlas bounded IEX data-only postjournal original-root admission.

Never uses Alpaca credentials, provider sockets or financial writer.
The original R26 2-journal state must be independently pinned; current
release accounts (R29/R30) are not adopted, amended or initialized.
"""
import copy
import hashlib
from pathlib import Path

import pytest

from scripts.observation_runtime import alpaca_iex_probe as probe
from scripts.observation_runtime import (
    personal_existing_native_resource_evidence as original_roots,
)

ROLES=("source","projection","report","control","coordination","custody")
LANES=("QUALITY_DIPS","HYPERLIQUID")


def synthetic_original_postjournal_roots():
    lanes={}
    for i,lane in enumerate(LANES):
        roots={}
        for j,role in enumerate(ROLES):
            roots[role]={
                "path":f"D:/AtlasPaper/{lane}/original/{role}",
                "native_identity_verified":True,
                "existing_empty_namespace_verified":role!="coordination",
                "native_id":[110+i,220+i,330+i*6+j],
            }
        lanes[lane]={"roots":roots}
    return {
        "native_root_total":12,"native_root_ids_verified":12,
        "existing_empty_root_namespaces":10,
        "all_twelve_distinct_and_empty":False,"lanes":lanes,
    }


def test_real_R26_original_postjournal_roots_allow_only_data_observation():
    roots=original_roots.inspect_two_lane_native_roots()
    assert roots["native_root_total"]==12
    assert roots["native_root_ids_verified"]==12
    assert roots["existing_empty_root_namespaces"]==10
    assert probe.admit_original_roots_for_data_only(
        roots,selected_revision=30) is True
    assert probe.SCOPE=="ALPACA_IEX_QUOTE_OBSERVATION_ONLY_NO_TRADING"


def test_exact_synthetic_R26_history_with_original_pinned_receipt_is_data_only():
    assert probe.admit_original_roots_for_data_only(
        synthetic_original_postjournal_roots(),selected_revision=30) is True


@pytest.mark.parametrize("damage",[
    "historic_pre26","unknown_revision","missing_role","extra_source",
    "missing_coordination","duplicate_native_id","native_identity_refused",
    "missing_lane","missing_root","invalid_native_id",
    "wrong_empty_count","total_count","native_id_count",
])
def test_postjournal_probe_refuses_untrusted_or_aliased_roots(damage):
    roots=synthetic_original_postjournal_roots()
    revision=30
    if damage=="historic_pre26":
        revision=25
    elif damage=="unknown_revision":
        revision="30"
    elif damage=="missing_role":
        del roots["lanes"]["QUALITY_DIPS"]["roots"]["control"]
    elif damage=="extra_source":
        roots["lanes"]["QUALITY_DIPS"]["roots"]["source"][
            "existing_empty_namespace_verified"]=False
    elif damage=="missing_coordination":
        roots["lanes"]["QUALITY_DIPS"]["roots"]["coordination"][
            "existing_empty_namespace_verified"]=True
    elif damage=="duplicate_native_id":
        roots["lanes"]["HYPERLIQUID"]["roots"]["custody"]["native_id"]=copy.deepcopy(
            roots["lanes"]["QUALITY_DIPS"]["roots"]["custody"]["native_id"]
        )
    elif damage=="native_identity_refused":
        roots["lanes"]["QUALITY_DIPS"]["roots"]["coordination"][
            "native_identity_verified"]=False
    elif damage=="missing_lane":
        del roots["lanes"]["HYPERLIQUID"]
    elif damage=="missing_root":
        roots["lanes"]["QUALITY_DIPS"]["roots"]["source"]["native_id"]=[]
    elif damage=="invalid_native_id":
        roots["lanes"]["QUALITY_DIPS"]["roots"]["source"]["native_id"]=[1,2,True]
    elif damage=="wrong_empty_count":
        roots["existing_empty_root_namespaces"]=9
    elif damage=="total_count":
        roots["native_root_total"]=11
    elif damage=="native_id_count":
        roots["native_root_ids_verified"]=11
    with pytest.raises(probe.IEXRefused):
        probe.admit_original_roots_for_data_only(roots,selected_revision=revision)


def test_postjournal_admission_refuses_tampered_historical_reconciliation(
        monkeypatch,tmp_path):
    raw=b'{"schema":"forged","status":"PAPER_RUNNING"}'
    altered=tmp_path/"altered-r26.json"
    altered.write_bytes(raw)
    monkeypatch.setattr(probe,"R26_ORIGINAL_FINANCIAL_RECEIPT",altered)
    assert hashlib.sha256(raw).hexdigest()!=probe.R26_ORIGINAL_FINANCIAL_RECEIPT_SHA256
    with pytest.raises(probe.IEXRefused):
        probe.admit_original_roots_for_data_only(
            synthetic_original_postjournal_roots(),selected_revision=30)


def test_postjournal_admission_refuses_signed_wrong_financial_status(
        monkeypatch,tmp_path):
    import json
    observed=json.loads(probe.R26_ORIGINAL_FINANCIAL_RECEIPT.read_bytes())
    observed["paper_start_authorized"]=True
    altered=tmp_path/"invalid-paper-approved-history.json"
    raw=json.dumps(observed,sort_keys=True).encode()
    altered.write_bytes(raw)
    monkeypatch.setattr(probe,"R26_ORIGINAL_FINANCIAL_RECEIPT",altered)
    monkeypatch.setattr(
        probe,"R26_ORIGINAL_FINANCIAL_RECEIPT_SHA256",
        hashlib.sha256(raw).hexdigest())
    with pytest.raises(probe.IEXRefused):
        probe.admit_original_roots_for_data_only(
            synthetic_original_postjournal_roots(),selected_revision=30)


def test_preinception_empty_original_roots_remain_accepted_data_only():
    roots=synthetic_original_postjournal_roots()
    for lane in LANES:
        roots["lanes"][lane]["roots"]["coordination"][
            "existing_empty_namespace_verified"]=True
    roots["existing_empty_root_namespaces"]=12
    roots["all_twelve_distinct_and_empty"]=True
    assert probe.admit_original_roots_for_data_only(
        roots,selected_revision=23) is True
