"""Real existing and synthetic scored-research -> native source gap contracts.

All tests read local files or create tmp synthetic examples. Never invoke
Alpaca, the SEC, financial writers, or any PAPER trading endpoints.
"""
import copy
import hashlib
import json
from pathlib import Path

import pytest

from scripts.observation_runtime import atlas_qd_scored_research_intake as audit


def fake_report():
    return {
        "schema":"ATLAS_BROAD_SCORED_RESEARCH_V1",
        "batch":{
            "schema":"ATLAS_ALPACA_RESEARCH_BATCH_V1",
            "symbols":["MSFT"],
            "offset":0,
            "inventory_sha256":"a"*64,
            "hyperliquid_perpetuals_included":False,
            "paper_execution_authorized":False,
            "live_order_authorized":False,
        },
        "results":[{
            "symbol":"MSFT",
            "status":"RESEARCH_SCORED",
            "provider_receipt_count":4,
            "research_lane":"QUALITY_DIPS",
            "evidence_quality":"HIGH",
            "opportunity_score":99,
            "paper_eligible":False,
            "live_order_authorized":False,
        }],
        "scoring_complete":True,
        "cursor_advanced":False,
        "paper_execution_authorized":False,
        "live_order_authorized":False,
    }


def store(tmp_path,report):
    raw=json.dumps(report,sort_keys=True,separators=(",",":"),allow_nan=False).encode("utf-8")
    h=hashlib.sha256(raw).hexdigest()
    p=tmp_path/("alpaca-scored-"+h+".json")
    p.write_bytes(raw)
    return p


def test_valid_scored_research_is_not_valid_forward_input(tmp_path):
    p=store(tmp_path,fake_report())
    original=p.read_bytes()
    row=audit.inspect_receipt(p,root=tmp_path)
    assert row["symbols"]==["MSFT"]
    assert row["recorded_research_lanes"]==["QUALITY_DIPS"]
    assert row["scored_research_count"]==1
    assert row["status"]=="RESEARCH_RECEIPT_VALID_NATIVE_FORWARD_INPUT_INCOMPLETE"
    assert "accepted_native_scanner_publication" in row["missing_native_intake_fields"]
    assert "research_rows_with_original_provenance" in row["missing_native_intake_fields"]
    for name in ("native_forward_input_complete","native_scanner_issuer_accepted",
                 "source_rights_accepted","financial_clock_accepted",
                 "paper_orders_authorized","live_orders_authorized","startup_authorized",
                 "three_fresh_independent_valuation_estimates_verified"):
        assert row[name] is False
    assert p.read_bytes()==original


def test_missing_operational_native_source_is_not_fixed_by_optimistic_scores(tmp_path):
    r=fake_report()
    r["results"][0]["opportunity_score"]=100
    r["results"][0]["evidence_quality"]="HIGH"
    row=audit.inspect_receipt(store(tmp_path,r),root=tmp_path)
    assert row["native_forward_input_complete"] is False
    assert row["paper_orders_authorized"] is False


@pytest.mark.parametrize("mutate",[
    lambda r:r.update(paper_execution_authorized=True),
    lambda r:r.update(cursor_advanced=True),
    lambda r:r["batch"].update(hyperliquid_perpetuals_included=True),
    lambda r:r["results"][0].update(paper_eligible=True),
    lambda r:r["results"][0].update(live_order_authorized=True),
    lambda r:r["results"][0].update(symbol="SPY"),
    lambda r:r["results"][0].update(status="INCOMPLETE"),
    lambda r:r["results"][0].update(provider_receipt_count=0),
    lambda r:r["batch"].update(symbols=["MSFT","MSFT"]),
])
def test_invalid_or_promoted_research_receipt_refuses(tmp_path,mutate):
    packet=fake_report()
    mutate(packet)
    path=store(tmp_path,packet)
    with pytest.raises(ValueError):
        audit.inspect_receipt(path,root=tmp_path)


def test_rewritten_receipt_without_rehash_refuses(tmp_path):
    p=store(tmp_path,fake_report())
    p.write_bytes(p.read_bytes()+b"\n")
    with pytest.raises(ValueError,match="DIGEST_MISMATCH"):
        audit.inspect_receipt(p,root=tmp_path)


def test_wrong_path_and_symlink_refuse(tmp_path):
    p=store(tmp_path,fake_report())
    with pytest.raises(ValueError,match="EXACT_READONLY_RECEIPT_REQUIRED"):
        audit.inspect_receipt(p,root=tmp_path/"other")
    with pytest.raises(ValueError,match="EXACT_READONLY_RECEIPT_REQUIRED"):
        audit.inspect_receipt(tmp_path/"other.json",root=tmp_path)


def test_duplicate_object_keys_refuse_even_with_matching_digest(tmp_path):
    raw=b'{"schema":"X","schema":"Y"}'
    path=tmp_path/("alpaca-scored-"+hashlib.sha256(raw).hexdigest()+".json")
    path.write_bytes(raw)
    with pytest.raises(ValueError):
        audit.inspect_receipt(path,root=tmp_path)


def test_bounded_actual_readonly_receipt_inventory_when_present():
    if not audit.RESEARCH.is_dir():
        pytest.skip("No existing local scored-research receipts")
    before={p.name:p.read_bytes() for p in audit.RESEARCH.glob("alpaca-scored-*.json")}
    if len(before)>8:
        pytest.skip("More historical receipts than read-only fixture limit")
    report=audit.inspect_existing()
    assert report["source_authority_verified"] is False
    assert report["native_forward_publication_created"] is False
    assert report["paper_orders_authorized"] is False
    assert len(report["reports"])==len(before)
    assert before=={p.name:p.read_bytes() for p in audit.RESEARCH.glob("alpaca-scored-*.json")}


def test_exact_catalog_origin_must_match_scored_batch(tmp_path):
    report=fake_report()
    rows=[{"symbol":"MSFT"},{"symbol":"SPY"}]
    payload=json.dumps(rows,sort_keys=True,separators=(",",":")).encode()
    digest=hashlib.sha256(payload).hexdigest()
    catalog={"schema":"ATLAS_ALPACA_EQUITY_RESEARCH_INVENTORY_V1",
             "rows":rows,"sha256":digest,"paper_execution_authorized":False,
             "robinhood_brokerage_verified":False}
    report["batch"]["inventory_sha256"]=digest
    path=store(tmp_path,report)
    result=audit.inspect_receipt(path,root=tmp_path,catalog=catalog)
    assert result["symbols"]==["MSFT"]
    assert result["native_forward_input_complete"] is False
    catalog["sha256"]="b"*64
    with pytest.raises(ValueError,match="RESEARCH_INVENTORY_MISMATCH"):
        audit.inspect_receipt(path,root=tmp_path,catalog=catalog)
    catalog["sha256"]=digest
    report["batch"]["offset"]=1
    path=store(tmp_path,report)
    with pytest.raises(ValueError,match="RESEARCH_BATCH_MISMATCH"):
        audit.inspect_receipt(path,root=tmp_path,catalog=catalog)


def test_real_scored_receipts_match_existing_unpromoted_research_inventory():
    catalog_path=audit.RESEARCH/"alpaca_equity_inventory.json"
    if not catalog_path.is_file():
        pytest.skip("Existing research catalog not available")
    catalog=json.loads(catalog_path.read_text(encoding="utf-8"))
    files=sorted(audit.RESEARCH.glob("alpaca-scored-*.json"))
    assert files, "Expected retained scored-research receipts from premarket work"
    for path in files:
        row=audit.inspect_receipt(path,root=audit.RESEARCH,catalog=catalog)
        assert row["native_forward_input_complete"] is False
        assert row["native_scanner_issuer_accepted"] is False
        assert row["three_fresh_independent_valuation_estimates_verified"] is False
