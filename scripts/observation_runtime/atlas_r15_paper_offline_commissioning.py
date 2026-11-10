"""R15 selected native PAPER offline commissioning, read-only and NO-GO.

The exact selected R15 code can be verified without creating a new financial
activation or trusting the obsolete R14-only release/readiness inspector.
Every provider, account and executable financial gate stays false until
independent, accepted operating evidence exists. No network or NTP acquisition.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

from scripts import release_selection as sel
from scripts.release_selection_store import NativeSelectionStore
from scripts.observation_runtime.personal_version_safe_release_clock import (
    admit_version_safe_clock_source,
)
from scripts.observation_runtime.personal_native_commissioning_inventory import (
    inspect as personal_inventory,
)
from scripts.observation_runtime.quality_dips_source_inventory import (
    inspect as qd_inventory,
)
from scripts.observation_runtime.hyperliquid_native_preflight import (
    inspect as hl_inventory,
)
from scripts.observation_runtime.atlas_r12_alpaca_source_admission import (
    inventory as alpaca_inventory, CATALOG,
)
from scripts.windows import atlas_paper_readiness_check as desktop
from app.prediction.policy import policy_snapshot

ROOT = Path("D:/Work/Project Atlas")
SELECTION = Path("D:/AtlasRuntime/selection")
RELEASE = Path("D:/AtlasRuntime/releases/2c79a8d846d6b33669008114732ae5896153812a")
RECEIPT = ROOT / "logs/diagnostics/qd-unselected-release-2c79a8d846d6b33669008114732ae5896153812a.json"
SELECTOR_NATIVE_ID = [4004218753,65536,1532785]
PREDECESSOR_SHA = "6b1e04b8f733d46421c81a5d158dbafbecf052e6f3a8e8289d175caca96d4e31"
PREDECESSOR_HEAD = "3fd8e1972b559a5de90627a303fc663b11928f8b43e84621a6796e9f3dbe9383"
SELECTED_SHA = "b729ff718fc41d90942400db15fc17e1bcf0cac6ae9ccf18e0492e9c6c4f2eb2"
SELECTED_HEAD = "274f5b00ee0e2f6271c6dd1dc5316f7d9124e932483038a6d93ef62ddbd2cd25"
RECEIPT_SHA = "b313a20f0a747c4a2ac81a2c1ae11b50901786008ce75f84202bf2f2435e741c"
ARTIFACT = "6db8cae881cd0f331b3f0aae78c92f27dbff860c658bb67ab1cfe91a6b8465e6"
CODE_PINS = {
    "backend/app/services/unified_writer_roster.py":
        "d26f821afee33855c8543f649f40f9f2fe25529043770dce59ecb8105945f697",
    "scripts/observation_runtime/personal_version_safe_release_clock.py":
        "7357b0d537a2e4b7728b896337bfee48f8856ced5b6e2410c56c623191ea17c5",
}
PORTS = (
    "backend/app/services/quality_dips_unified_writer.py",
    "backend/app/services/hyperliquid_current_producer.py",
    "backend/app/services/personal_paper_iex_provider.py",
    "backend/app/services/personal_hyperliquid_public_data.py",
)
GATES = (
    "B1_HISTORICAL_COMPLETENESS_OR_EPOCH",
    "C1_OWNERSHIP_AND_FINANCIAL_DRAIN",
    "D1_TRUSTED_STORAGE_AUTHORITY_CLOCK",
    "E1_PROVIDER_RIGHTS_AND_SUPERVISED_SESSION",
    "DESKTOP_OWNED_START_STOP",
    "MARKET_AND_ACCOUNT_COVERAGE",
    "RESTART_AND_RECONCILIATION",
    "SUPERVISED_END_TO_END",
    "EXTENDED_SOAK_ACCEPTANCE",
)


def sha_file(path: Path, *, max_bytes=4*1024*1024):
    if (not path.is_file() or path.is_symlink() or path.is_junction()
            or not 0 < path.stat().st_size <= max_bytes):
        raise ValueError("R15_OFFLINE_NATIVE_FILE_EVIDENCE_REQUIRED")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def selected_code():
    if os.name != "nt":
        raise ValueError("R15_OFFLINE_SELECTED_WINDOWS_REQUIRED")
    store=NativeSelectionStore(root=str(SELECTION),native_root=SELECTOR_NATIVE_ID)
    try:
        with store.locked():
            rows=store.records()
            if (len(rows)!=14 or sel.digest(rows[12])!=PREDECESSOR_HEAD
                    or sel.digest(rows[13])!=SELECTED_HEAD
                    or rows[13].get("revision")!=14
                    or rows[13].get("action")!="SELECT"
                    or rows[13].get("previous")!=PREDECESSOR_HEAD
                    or rows[13].get("restores") is not None):
                raise ValueError("R15_OFFLINE_EXACT_SELECTED_14_RECORD_CHAIN_REQUIRED")
            spec=sel.validate_spec(rows[-1].get("selected"),"WINDOWS_LOCAL")
            if (spec["release"]!=RELEASE.name
                    or spec["root"]!=str(RELEASE)
                    or spec["receipt_sha256"]!=RECEIPT_SHA
                    or spec["artifact_digest"]!=ARTIFACT):
                raise ValueError("R15_OFFLINE_SELECTED_NATIVE_SPEC_REFUSED")
            clock_head,clock_spec=admit_version_safe_clock_source(
                source_file=RELEASE/CODE_PINS_CLOCK_PATH,records=rows)
            if clock_head!=SELECTED_HEAD or clock_spec!=spec:
                raise ValueError("R15_OFFLINE_FINANCIAL_CLOCK_SOURCE_UNBOUND")
    finally:
        store.close()
    if (sha_file(SELECTION/"r0013.json",max_bytes=65536)!=PREDECESSOR_SHA
            or sha_file(SELECTION/"r0014.json",max_bytes=65536)!=SELECTED_SHA
            or sha_file(SELECTION/"r0014.pending",max_bytes=65536)!=SELECTED_SHA
            or sha_file(RECEIPT,max_bytes=4*1024*1024)!=RECEIPT_SHA):
        raise ValueError("R15_OFFLINE_SELECTED_NATIVE_RECEIPT_CHANGED")
    if (not RELEASE.is_dir() or RELEASE.is_symlink() or RELEASE.is_junction()
            or not (RELEASE/"python/python.exe").is_file()):
        raise ValueError("R15_OFFLINE_INSTALLED_PYTHON_MISSING")
    return {
        "revision":14,"selected_release":RELEASE.name,
        "selected_native_head":SELECTED_HEAD,
        "selected_native_record_sha256":SELECTED_SHA,
        "installed_receipt_sha256":RECEIPT_SHA,
        "native_clock_own_release_source_admitted":True,
        "independent_live_financial_clock_lease_accepted":False,
        "financial_authority":False,
    }


CODE_PINS_CLOCK_PATH = "scripts/observation_runtime/personal_version_safe_release_clock.py"


def selected_ports():
    codes={}
    for name in (*CODE_PINS,*PORTS):
        native=RELEASE/name
        actual=sha_file(native,max_bytes=131072)
        if name in CODE_PINS:
            if actual!=CODE_PINS[name]:
                raise ValueError("R15_OFFLINE_REQUIRED_FINANCIAL_SOURCE_HASH_CHANGED")
        else:
            workspace=ROOT/name
            if actual!=sha_file(workspace,max_bytes=131072):
                raise ValueError("R15_OFFLINE_SELECTED_MARKET_PORT_SOURCE_DRIFT")
        codes[name]={"native_sha256":actual,"native_installed_source_present":True}
    return codes


def evaluate(*, selected, codes, personal, qd, hl, alpaca, ui, kalshi):
    """Refuse contradictory or falsely promoted operational evidence."""
    if (type(selected) is not dict or selected.get("revision")!=14
            or selected.get("selected_native_head")!=SELECTED_HEAD
            or selected.get("native_clock_own_release_source_admitted") is not True
            or selected.get("financial_authority") is not False
            or selected.get("independent_live_financial_clock_lease_accepted") is not False):
        raise ValueError("R15_OFFLINE_CODE_OR_CLOCK_AUTHORITY_INVALID")
    if (type(codes) is not dict or set(codes)!=set(CODE_PINS)|set(PORTS)
            or any(type(item) is not dict
                   or item.get("native_installed_source_present") is not True
                   or type(item.get("native_sha256")) is not str
                   or len(item["native_sha256"])!=64
                   for item in codes.values())):
        raise ValueError("R15_OFFLINE_NATIVE_FINANCIAL_PORTS_INVALID")
    if (personal.get("schema")!="ATLAS_PERSONAL_NATIVE_COMMISSIONING_INVENTORY_V1"
            or personal.get("personal_parent_present") is not True
            or personal.get("native_activation_verified") is not False
            or personal.get("account_enrollment_verified") is not False
            or personal.get("paper_start_authorized") is not False):
        raise ValueError("R15_OFFLINE_PERSONAL_ACCOUNT_SCOPE_INVALID")
    if (qd.get("schema")!="ATLAS_QD_NATIVE_SOURCE_INVENTORY_V1"
            or qd.get("operational_publication_verified") is not False
            or hl.get("schema")!="ATLAS_HYPERLIQUID_NATIVE_PREFLIGHT_V1"
            or hl.get("native_writer_ownership")!="NOT_INDEPENDENTLY_VERIFIED"
            or hl.get("provider_rights_and_current_market_data")!="NOT_INDEPENDENTLY_VERIFIED"
            or hl.get("paper_startup_authorized") is not False
            or hl.get("live_trading_authorized") is not False):
        raise ValueError("R15_OFFLINE_TWO_LANE_FINANCIAL_SOURCE_SCOPE_INVALID")
    if (alpaca.get("provider_research_inventory_verified") is not True
            or alpaca.get("paper_execution_eligible_from_catalog") is not False
            or alpaca.get("robinhood_brokerage_coverage_verified") is not False
            or type(alpaca.get("research_symbol_count")) is not int
            or alpaca["research_symbol_count"]<=0
            or type(alpaca.get("required_nonoverlapping_30_symbol_rosters")) is not int):
        raise ValueError("R15_OFFLINE_ALPACA_RESEARCH_NOT_EXECUTION")
    if (ui.get("schema")!="ATLAS_PAPER_DESKTOP_READINESS_V1"
            or ui.get("decision")!="NO_GO"
            or ui.get("paper_startup_authorized") is not False
            or ui.get("live_trading_authorized") is not False
            or kalshi.get("target_paper_strategy")!="NEWLY_LISTED_SINGLE_YES_NO_PRICE_DISCOVERY_V1"
            or kalshi.get("target_new_listing_paper_entry_commissioned") is not False
            or kalshi.get("legacy_repricing_paper_entry_enabled") is not False
            or kalshi.get("live_execution") is not False):
        raise ValueError("R15_OFFLINE_DESKTOP_OR_KALSHI_SCOPE_INVALID")
    return {
        "schema":"ATLAS_SELECTED_R15_OFFLINE_FINANCIAL_COMMISSIONING_V1",
        "decision":"NO_GO",
        "selected_native_release":"R15",
        "selected_native_revision":14,
        "selected_code_verified":True,
        "selected_code_identity":selected,
        "selected_native_financial_port_sources":codes,
        "installed_financial_clock_source_binding_verified":True,
        "continuous_operational_financial_clock_lease_accepted":False,
        "native_personal_activation_children":personal["personal_child_count"],
        "native_personal_activation_verified":False,
        "native_qd_forward_writer_enrolled":False,
        "native_hyperliquid_forward_writer_enrolled":False,
        "native_financial_ledger_accepted":False,
        "native_financial_stop_and_flat_accepted":False,
        "quality_dips_research_catalog_symbols":alpaca["research_symbol_count"],
        "quality_dips_sequential_iex_rosters":alpaca[
            "required_nonoverlapping_30_symbol_rosters"],
        "current_iex_equity_quotes_verified":False,
        "robinhood_equity_etf_universe_verified":False,
        "current_hyperliquid_public_book_verified":False,
        "kalshi_newly_listed_yes_no_only":True,
        "kalshi_new_listing_paper_engine_commissioned":False,
        "desktop_start_stop_financial_ready":False,
        "financial_operating_gates_independently_accepted":0,
        "financial_operating_gates_total":9,
        "gates":[{"gate":name,"accepted":False,
                  "status":"NOT_INDEPENDENTLY_ACCEPTED"} for name in GATES],
        "external_authorizations_required":[
            "Actual local PersonalPaper operator/account activation and native writer/ledger enrollment",
            "Continuous trusted financial UTC and two-lane owned Stop, flat and restart acceptance",
            "Permitted live Alpaca IEX and Hyperliquid current data/provider rights",
            "Supervised financial PAPER account session and extended reconciled soak",
        ],
        "provider_connection_opened":False,
        "credential_bytes_read":False,
        "paper_orders_sent":False,
        "live_orders_sent":False,
        "paper_start_authorized":False,
        "live_trading_authorized":False,
    }


def inspect():
    return evaluate(
        selected=selected_code(),codes=selected_ports(),
        personal=personal_inventory(),qd=qd_inventory(),
        hl=hl_inventory(),alpaca=alpaca_inventory(CATALOG),
        ui=desktop.inspect(root=ROOT),kalshi=policy_snapshot(),
    )


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inspect",action="store_true",required=True)
    parser.parse_args(argv)
    print(json.dumps(inspect(),sort_keys=True,indent=2))
    return 2


if __name__=="__main__":
    raise SystemExit(main())
