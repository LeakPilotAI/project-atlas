"""R15 read-only financial commissioning: release and evidence scope.

No private credentials, NTP, provider calls, publication, orders or native
account activation. Filesystem-dependent tests are run on the selected host.
"""
from __future__ import annotations

import copy
import hashlib

import pytest

from scripts.observation_runtime import atlas_r15_paper_offline_commissioning as mod
from scripts.observation_runtime.personal_native_commissioning_inventory import (
    inspect as personal_inspect,
)
from scripts.observation_runtime.quality_dips_source_inventory import (
    inspect as qd_inspect,
)
from scripts.observation_runtime.hyperliquid_native_preflight import (
    inspect as hl_inspect,
)
from scripts.observation_runtime.atlas_r12_alpaca_source_admission import (
    inventory as alpaca_inspect, CATALOG,
)
from scripts.windows.atlas_paper_readiness_check import inspect as desktop_inspect
from app.prediction.policy import policy_snapshot


@pytest.fixture(scope="module")
def evidence():
    return {
        "selected":mod.selected_code(),
        "codes":mod.selected_ports(),
        "personal":personal_inspect(),
        "qd":qd_inspect(),
        "hl":hl_inspect(),
        "alpaca":alpaca_inspect(CATALOG),
        "ui":desktop_inspect(root=mod.ROOT),
        "kalshi":policy_snapshot(),
    }


def test_installed_r15_release_original_selection_chain_is_exact(evidence):
    selected=evidence["selected"]
    assert selected["revision"]==14
    assert selected["selected_native_head"]==mod.SELECTED_HEAD
    assert selected["selected_native_record_sha256"]==mod.SELECTED_SHA
    assert selected["native_clock_own_release_source_admitted"] is True
    assert selected["independent_live_financial_clock_lease_accepted"] is False
    assert hashlib.sha256(
        (mod.SELECTION/"r0014.json").read_bytes()).hexdigest()==mod.SELECTED_SHA
    assert hashlib.sha256(
        mod.RECEIPT.read_bytes()).hexdigest()==mod.RECEIPT_SHA


def test_selected_r15_writer_and_clock_source_matches_verified_native_files(evidence):
    assert set(evidence["codes"])==set(mod.CODE_PINS)|set(mod.PORTS)
    for path, row in evidence["codes"].items():
        assert row["native_installed_source_present"] is True
        if path in mod.CODE_PINS:
            assert row["native_sha256"]==mod.CODE_PINS[path]


def test_combined_r15_commissioning_is_true_financial_no_go(evidence):
    report=mod.evaluate(**evidence)
    assert report["selected_native_release"]=="R15"
    assert report["selected_code_verified"] is True
    assert report["selected_native_revision"]==14
    assert report["installed_financial_clock_source_binding_verified"] is True
    assert report["decision"]=="NO_GO"
    assert report["native_personal_activation_children"]==0
    assert report["financial_operating_gates_independently_accepted"]==0
    assert report["financial_operating_gates_total"]==9
    assert len(report["gates"])==9
    assert {x["gate"] for x in report["gates"]}==set(mod.GATES)
    assert all(x["accepted"] is False for x in report["gates"])
    assert report["quality_dips_research_catalog_symbols"]==13487
    assert report["quality_dips_sequential_iex_rosters"]==450
    assert report["kalshi_newly_listed_yes_no_only"] is True
    for field in (
        "continuous_operational_financial_clock_lease_accepted",
        "native_personal_activation_verified",
        "native_qd_forward_writer_enrolled",
        "native_hyperliquid_forward_writer_enrolled",
        "native_financial_ledger_accepted",
        "native_financial_stop_and_flat_accepted",
        "current_iex_equity_quotes_verified",
        "robinhood_equity_etf_universe_verified",
        "current_hyperliquid_public_book_verified",
        "kalshi_new_listing_paper_engine_commissioned",
        "desktop_start_stop_financial_ready",
        "provider_connection_opened",
        "credential_bytes_read",
        "paper_orders_sent",
        "live_orders_sent",
        "paper_start_authorized",
        "live_trading_authorized",
    ):
        assert report[field] is False


@pytest.mark.parametrize("part,field,value",[
    ("selected","revision",13),
    ("selected","selected_native_head","0"*64),
    ("selected","native_clock_own_release_source_admitted",False),
    ("selected","independent_live_financial_clock_lease_accepted",True),
    ("selected","financial_authority",True),
    ("personal","native_activation_verified",True),
    ("personal","account_enrollment_verified",True),
    ("personal","paper_start_authorized",True),
    ("qd","operational_publication_verified",True),
    ("hl","native_writer_ownership","INDEPENDENTLY_VERIFIED"),
    ("hl","provider_rights_and_current_market_data","INDEPENDENTLY_VERIFIED"),
    ("hl","paper_startup_authorized",True),
    ("hl","live_trading_authorized",True),
    ("alpaca","provider_research_inventory_verified",False),
    ("alpaca","paper_execution_eligible_from_catalog",True),
    ("alpaca","robinhood_brokerage_coverage_verified",True),
    ("ui","decision","GO"),
    ("ui","paper_startup_authorized",True),
    ("kalshi","target_new_listing_paper_entry_commissioned",True),
    ("kalshi","legacy_repricing_paper_entry_enabled",True),
    ("kalshi","live_execution",True),
])
def test_forged_financial_acceptance_never_promotes_r15_offline_gate(
        evidence,part,field,value):
    changed=copy.deepcopy(evidence)
    changed[part][field]=value
    with pytest.raises(ValueError,match="R15_OFFLINE_"):
        mod.evaluate(**changed)


def test_substituted_native_port_or_clock_source_is_refused(evidence):
    changed=copy.deepcopy(evidence)
    changed["codes"]["backend/app/services/unified_writer_roster.py"][
        "native_installed_source_present"]=False
    with pytest.raises(ValueError,match="NATIVE_FINANCIAL_PORTS_INVALID"):
        mod.evaluate(**changed)
    changed=copy.deepcopy(evidence)
    changed["codes"]["backend/app/services/quality_dips_unified_writer.py"][
        "native_sha256"]="bad"
    with pytest.raises(ValueError,match="NATIVE_FINANCIAL_PORTS_INVALID"):
        mod.evaluate(**changed)


def test_readonly_cli_returns_explicit_no_go_without_account_start(capsys):
    assert mod.main(["--inspect"])==2
    data=__import__("json").loads(capsys.readouterr().out)
    assert data["selected_native_revision"]==14
    assert data["financial_operating_gates_independently_accepted"]==0
    assert data["paper_start_authorized"] is False
    with pytest.raises(SystemExit):
        mod.main(["--start"])
