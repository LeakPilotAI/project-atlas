"""R14 selected native two-lane source preflight refuses unearned PAPER rights."""
import copy
import json

import pytest

from scripts.observation_runtime import atlas_r14_two_lane_source_preflight as mod


@pytest.fixture(scope="module")
def evidence():
    from scripts.observation_runtime.atlas_r14_selected_paper_readiness import collect_selected_reference
    from scripts.observation_runtime.atlas_r12_alpaca_source_admission import inventory
    from scripts.observation_runtime.quality_dips_source_inventory import inspect as qd
    from scripts.observation_runtime.hyperliquid_native_preflight import inspect as hl
    return {
        "selected":collect_selected_reference(),
        "alpaca":inventory(),
        "quality_dips":qd(),
        "hyperliquid":hl(),
        "source_contracts":mod.selected_contracts(),
        "config_present":False,
    }


def test_actual_selected_r14_source_inventory_read_only_no_authority(evidence):
    report=mod.evaluate(**evidence)
    assert report["schema"]=="ATLAS_R14_TWO_LANE_FINANCIAL_SOURCE_PREFLIGHT_V1"
    assert report["decision"]=="NO_GO"
    assert report["selected_code_revision"]==13
    assert report["selected_code_release"]==mod.RELEASE.name
    assert report["installed_provider_writer_code_verified"] is True
    assert len(report["selected_installed_source_contracts"]) == 4
    assert report["quality_dips"]["catalog_symbols"] == 13487
    assert report["quality_dips"]["minimum_sequential_30_symbol_rosters"] == 450
    assert report["quality_dips"]["robinhood_equity_etf_universe_verified"] is False
    assert report["quality_dips"]["paper_execution_authorized"] is False
    assert report["hyperliquid"]["paper_execution_authorized"] is False
    assert report["financial_operating_gates_accepted"] == 0
    assert report["financial_operating_gates_total"] == 9
    assert len(report["next_required_evidence"]) == 4
    for field in ("source_rights_independently_accepted",
                  "continuous_financial_clock_authorized",
                  "native_financial_ledger_and_owner_accepted",
                  "owned_financial_stop_verified",
                  "provider_connections_opened",
                  "paper_accounts_created",
                  "orders_submitted",
                  "paper_startup_authorized",
                  "live_trading_authorized"):
        assert report[field] is False


@pytest.mark.parametrize("field,value",[
    ("revision",12),("selected_release","2d4879878bf58bea5a3ed0a986b809791f638fec"),
    ("native_selection_record_verified",False),("financial_authority",True),
])
def test_foreign_selected_release_or_fake_finance_refused(evidence,field,value):
    fake=copy.deepcopy(evidence)
    fake["selected"][field]=value
    with pytest.raises(ValueError,match="EXACT_SELECTED_CODE_REQUIRED"):
        mod.evaluate(**fake)


@pytest.mark.parametrize("field,value",[
    ("provider_research_inventory_verified",False),
    ("paper_execution_eligible_from_catalog",True),
    ("robinhood_brokerage_coverage_verified",True),
    ("research_symbol_count",0),
    ("required_nonoverlapping_30_symbol_rosters",0),
])
def test_research_cannot_grant_provider_or_brokerage_scope(evidence,field,value):
    fake=copy.deepcopy(evidence)
    fake["alpaca"][field]=value
    with pytest.raises(ValueError,match="RESEARCH_EVIDENCE_SCOPE_REFUSED"):
        mod.evaluate(**fake)


@pytest.mark.parametrize("field,value",[
    ("operational_publication_verified",True),("schema","FORGED_SOURCE"),
])
def test_fake_qd_source_publication_rejected(evidence,field,value):
    fake=copy.deepcopy(evidence)
    fake["quality_dips"][field]=value
    with pytest.raises(ValueError,match="QD_SOURCE_PUBLICATION_UNPROVEN_REQUIRED"):
        mod.evaluate(**fake)


@pytest.mark.parametrize("field,value",[
    ("hyperliquid_native_account_inception","VERIFIED"),
    ("provider_rights_and_current_market_data","PASS"),
    ("native_writer_ownership","ACCEPTED"),
    ("paper_startup_authorized",True),
    ("live_trading_authorized",True),
])
def test_native_hyperliquid_directory_never_grants_financial_writer_rights(evidence,field,value):
    fake=copy.deepcopy(evidence)
    fake["hyperliquid"][field]=value
    with pytest.raises(ValueError,match="HL_SCOPE_AND_EVIDENCE_REFUSED"):
        mod.evaluate(**fake)


def test_source_contract_source_change_refused(monkeypatch,tmp_path):
    fake=tmp_path/"tampered.py"
    fake.write_text("# not selected installed code")
    changed=dict(mod.SOURCES)
    name=next(iter(changed))
    monkeypatch.setattr(mod,"ROOT",tmp_path)
    (tmp_path/name).parent.mkdir(parents=True)
    (tmp_path/name).write_text("# foreign code")
    with pytest.raises(ValueError,match="PORT_SOURCE_IDENTITY_CHANGED"):
        mod.selected_contracts()


def test_native_contract_claims_must_be_complete(evidence):
    fake=copy.deepcopy(evidence)
    fake["source_contracts"].pop(next(iter(fake["source_contracts"])))
    with pytest.raises(ValueError,match="INSTALLED_PORT_CONTRACTS_REQUIRED"):
        mod.evaluate(**fake)


def test_readonly_cli_refuses_to_grant_trading(capsys):
    assert mod.main(["--inspect"])==2
    packet=json.loads(capsys.readouterr().out)
    assert packet["decision"]=="NO_GO"
    assert packet["orders_submitted"] is False
    assert packet["paper_startup_authorized"] is False
    assert packet["financial_operating_gates_accepted"]==0
    with pytest.raises(SystemExit):
        mod.main(["--start-paper"])
    with pytest.raises(SystemExit):
        mod.main(["--provider-login"])
