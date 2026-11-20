"""R14 selected code: cross-lane PAPER source + writer readiness, read-only.

Reuses the preexisting Alpaca IEX research catalog, QD source inventory, and
Hyperliquid native preflight, but never inherits the R12-only admission claim.
Neither code release selection nor directory presence grants PAPER authority.
No private config read, socket, orders, ledger writes, or real session start.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from scripts.observation_runtime.atlas_r14_selected_paper_readiness import (
    collect_selected_reference,
)
from scripts.observation_runtime.atlas_r12_alpaca_source_admission import (
    inventory as alpaca_catalog_inventory,
    CATALOG,
    ALPACA_CONFIG,
    IEX_MAX_SYMBOLS_PER_CONNECTION,
)
from scripts.observation_runtime.quality_dips_source_inventory import (
    inspect as qd_source_inventory,
)
from scripts.observation_runtime.hyperliquid_native_preflight import (
    inspect as hyperliquid_native_inventory,
)

ROOT = Path("D:/Work/Project Atlas")
RELEASE = Path("D:/AtlasRuntime/releases/7ff9d3dba2eabe110f843c13efac49464805de2a")
SOURCES = {
    "backend/app/services/quality_dips_unified_writer.py": None,
    "backend/app/services/hyperliquid_current_producer.py": None,
    "backend/app/services/personal_paper_iex_provider.py": None,
    "backend/app/services/personal_hyperliquid_public_data.py": None,
}


def selected_contracts():
    """Ensure selected native R14 contains the exact existing port source."""
    found = {}
    for name in SOURCES:
        native, workspace = RELEASE / name, ROOT / name
        if (not native.is_file() or native.is_symlink()
                or not workspace.is_file() or workspace.is_symlink()
                or native.stat().st_size > 128*1024
                or workspace.stat().st_size > 128*1024):
            raise ValueError("R14_FINANCIAL_PAPER_PORT_SOURCE_UNAVAILABLE")
        installed_sha = hashlib.sha256(native.read_bytes()).hexdigest()
        workspace_sha = hashlib.sha256(workspace.read_bytes()).hexdigest()
        if installed_sha != workspace_sha:
            raise ValueError("R14_FINANCIAL_PAPER_PORT_SOURCE_IDENTITY_CHANGED")
        found[name] = {"native_source_sha256":installed_sha,
                       "selected_release_source_matches_workspace":True}
    return found


def evaluate(*, selected, alpaca, quality_dips, hyperliquid, source_contracts, config_present):
    """Pure gate: never convert installed code or observation to financial grant."""
    if (type(selected) is not dict
            or selected.get("revision") != 13
            or selected.get("selected_release") != RELEASE.name
            or selected.get("native_selection_record_verified") is not True
            or selected.get("financial_authority") is not False):
        raise ValueError("R14_FINANCIAL_PAPER_EXACT_SELECTED_CODE_REQUIRED")
    if (type(alpaca) is not dict
            or alpaca.get("provider_research_inventory_verified") is not True
            or alpaca.get("paper_execution_eligible_from_catalog") is not False
            or alpaca.get("robinhood_brokerage_coverage_verified") is not False
            or type(alpaca.get("research_symbol_count")) is not int
            or not 0 < alpaca["research_symbol_count"] <= 20000
            or type(alpaca.get("required_nonoverlapping_30_symbol_rosters")) is not int
            or alpaca["required_nonoverlapping_30_symbol_rosters"] < 1):
        raise ValueError("R14_FINANCIAL_PAPER_RESEARCH_EVIDENCE_SCOPE_REFUSED")
    if (type(quality_dips) is not dict
            or quality_dips.get("schema") != "ATLAS_QD_NATIVE_SOURCE_INVENTORY_V1"
            or quality_dips.get("operational_publication_verified") is not False):
        raise ValueError("R14_FINANCIAL_PAPER_QD_SOURCE_PUBLICATION_UNPROVEN_REQUIRED")
    if (type(hyperliquid) is not dict
            or hyperliquid.get("schema") != "ATLAS_HYPERLIQUID_NATIVE_PREFLIGHT_V1"
            or hyperliquid.get("paper_startup_authorized") is not False
            or hyperliquid.get("live_trading_authorized") is not False
            or hyperliquid.get("hyperliquid_native_account_inception") != "NOT_INDEPENDENTLY_VERIFIED"
            or hyperliquid.get("native_writer_ownership") != "NOT_INDEPENDENTLY_VERIFIED"
            or hyperliquid.get("provider_rights_and_current_market_data") != "NOT_INDEPENDENTLY_VERIFIED"):
        raise ValueError("R14_FINANCIAL_PAPER_HL_SCOPE_AND_EVIDENCE_REFUSED")
    if (type(source_contracts) is not dict or set(source_contracts) != set(SOURCES)
            or any(type(row) is not dict
                   or row.get("selected_release_source_matches_workspace") is not True
                   or type(row.get("native_source_sha256")) is not str
                   or len(row["native_source_sha256"]) != 64
                   for row in source_contracts.values())
            or type(config_present) is not bool):
        raise ValueError("R14_FINANCIAL_PAPER_INSTALLED_PORT_CONTRACTS_REQUIRED")
    return {
        "schema":"ATLAS_R14_TWO_LANE_FINANCIAL_SOURCE_PREFLIGHT_V1",
        "decision":"NO_GO",
        "selected_code_revision":13,
        "selected_code_release":RELEASE.name,
        "installed_provider_writer_code_verified":True,
        "quality_dips":{
            "provider":"ALPACA",
            "market":"US_STOCKS_ETFS",
            "data_feed":"IEX_SINGLE_EXCHANGE_NOT_NBBO",
            "catalog_symbols":alpaca["research_symbol_count"],
            "minimum_sequential_30_symbol_rosters":alpaca[
                "required_nonoverlapping_30_symbol_rosters"],
            "research_inventory_verified":True,
            "research_catalog_sha256":alpaca["catalog_file_sha256"],
            "alpaca_config_file_present":config_present,
            "credential_bytes_opened":False,
            "robinhood_equity_etf_universe_verified":False,
            "authenticated_current_quotes_verified":False,
            "operational_source_publication_verified":False,
            "native_writer_enrolled":False,
            "paper_execution_authorized":False,
        },
        "hyperliquid":{
            "provider":"HYPERLIQUID",
            "market":"PERPETUALS_ONLY",
            "native_custody_parent_present":hyperliquid["custody_parent_present"],
            "native_custody_direct_child_count":len(hyperliquid["custody_child_names"]),
            "account_inception_verified":False,
            "current_market_data_rights_verified":False,
            "native_financial_writer_verified":False,
            "paper_execution_authorized":False,
        },
        "selected_installed_source_contracts":source_contracts,
        "source_rights_independently_accepted":False,
        "continuous_financial_clock_authorized":False,
        "native_financial_ledger_and_owner_accepted":False,
        "owned_financial_stop_verified":False,
        "financial_operating_gates_accepted":0,
        "financial_operating_gates_total":9,
        "provider_connections_opened":False,
        "paper_accounts_created":False,
        "orders_submitted":False,
        "paper_startup_authorized":False,
        "live_trading_authorized":False,
        "next_required_evidence":[
            "Current allowed IEX entitlement plus continuously fresh subscribed quotes across bounded rotating rosters; validate eligible stocks/ETFs and avoid claiming Robinhood coverage from Alpaca listings",
            "QD operational source-publication and independently enrolled native writer/ledger",
            "Hyperliquid accepted public data and genuine native PAPER account/writer ownership",
            "Continuous operational financial UTC authority, global custody, risk and two-lane Stop/readback",
        ],
    }


def inspect():
    selected=collect_selected_reference()
    catalog=alpaca_catalog_inventory(CATALOG)
    qd=qd_source_inventory()
    hl=hyperliquid_native_inventory()
    config=Path(ALPACA_CONFIG)
    exists=config.is_file() and not config.is_symlink()
    return evaluate(
        selected=selected, alpaca=catalog, quality_dips=qd,
        hyperliquid=hl, source_contracts=selected_contracts(),
        config_present=exists,
    )


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inspect",action="store_true",required=True)
    parser.parse_args(argv)
    print(json.dumps(inspect(),sort_keys=True,indent=2))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
