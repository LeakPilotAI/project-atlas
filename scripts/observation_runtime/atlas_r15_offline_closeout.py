"""One-command offline Atlas closeout: actual local evidence, never a GO.

Joins existing R14 native selection, R15 create-only code plan, public research
rights, PersonalPaper native enrollment, desktop guard and Kalshi scope.
Never acquires NTP, creates a financial account, imports credentials, connects
to a provider, writes a ledger, starts a service or launches an order.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from scripts.observation_runtime.atlas_r14_selected_paper_readiness import (
    inspect as selected_inspect,
)
from scripts.observation_runtime.atlas_r14_two_lane_source_preflight import (
    inspect as source_inspect,
)
from scripts.observation_runtime.atlas_r15_code_install_plan_preflight import (
    inspect as code_install_inspect,
)
from scripts.observation_runtime.alpaca_iex_probe import inspect_selected_data_only
from scripts.observation_runtime.atlas_r14_hyperliquid_public_book_probe import (
    inspect as hyperliquid_book_inspect,
)
from scripts.observation_runtime.personal_native_commissioning_inventory import (
    inspect as personal_native_inspect,
)
from app.prediction.policy import policy_snapshot

ROOT = Path("D:/Work/Project Atlas")
NATIVE = Path("D:/AtlasRuntime/releases/7ff9d3dba2eabe110f843c13efac49464805de2a")
CHANGED_SELECTED_RUNTIME = (
    "backend/app/services/unified_writer_roster.py",
    "scripts/observation_runtime/personal_version_safe_release_clock.py",
)


def source_differences():
    result = {}
    for name in CHANGED_SELECTED_RUNTIME:
        old, new = NATIVE/name, ROOT/name
        if (not old.is_file() or not new.is_file()
                or old.is_symlink() or new.is_symlink()
                or old.stat().st_size > 64*1024 or new.stat().st_size > 64*1024):
            raise ValueError("ATLAS_OFFLINE_SELECTED_CODE_DIFF_EVIDENCE_MISSING")
        actual = hashlib.sha256(old.read_bytes()).hexdigest()
        pending = hashlib.sha256(new.read_bytes()).hexdigest()
        if actual == pending:
            raise ValueError("ATLAS_OFFLINE_SELECTED_RELEASE_UNEXPECTEDLY_CHANGED")
        result[name] = {
            "selected_r14_sha256":actual,
            "successor_workspace_sha256":pending,
            "selected_native_contains_successor_fix":False,
        }
    return result


def evaluate(*, selected, install_plan, sources, iex, hl, personal, kalshi, differences):
    """All evidence is read-only; refuse if any dependency claims authority."""
    if (selected.get("decision") != "NO_GO"
            or selected.get("selected_code_verified") is not True
            or selected.get("selected_code_identity", {}).get("revision") != 13
            or selected.get("accepted_financial_operating_gates") != 0
            or selected.get("total_financial_operating_gates") != 9
            or selected.get("desktop_one_click_paper_ready") is not False
            or selected.get("paper_start_authorized") is not False):
        raise ValueError("ATLAS_OFFLINE_SELECTED_PAPER_GATE_INVALID")
    if (install_plan.get("status")
            != "SOURCE_AND_DEPENDENCY_PLAN_VERIFIED_NOT_INSTALL_AUTHORIZATION"
            or install_plan.get("native_installation_authorized") is not False
            or install_plan.get("native_installation_executed") is not False
            or install_plan.get("financial_paper_start_authorized") is not False
            or install_plan.get("planned_native_files") != 10526):
        raise ValueError("ATLAS_OFFLINE_CODE_ONLY_PLAN_CHANGED")
    if (sources.get("decision") != "NO_GO"
            or sources.get("selected_code_revision") != 13
            or sources.get("source_rights_independently_accepted") is not False
            or sources.get("paper_startup_authorized") is not False
            or sources.get("quality_dips", {}).get("operational_source_publication_verified") is not False
            or sources.get("hyperliquid", {}).get("native_financial_writer_verified") is not False):
        raise ValueError("ATLAS_OFFLINE_MARKET_SOURCE_SCOPE_CHANGED")
    if (iex.get("selected_revision") != 13
            or iex.get("provider_connected") is not False
            or iex.get("private_credentials_accessed") is not False
            or iex.get("sample_already_verified") is not False
            or iex.get("trading_authorized") is not False):
        raise ValueError("ATLAS_OFFLINE_IEX_GUARD_CHANGED")
    if (hl.get("selected_code_revision") != 13
            or hl.get("financial_execution_authorized") is not False
            or hl.get("market_book_observed") is not False
            or hl.get("provider_connection_opened") is not False
            or hl.get("paper_startup_authorized") is not False):
        raise ValueError("ATLAS_OFFLINE_HL_GUARD_CHANGED")
    if (personal.get("schema") != "ATLAS_PERSONAL_NATIVE_COMMISSIONING_INVENTORY_V1"
            or personal.get("native_activation_verified") is not False
            or personal.get("account_enrollment_verified") is not False
            or personal.get("paper_start_authorized") is not False):
        raise ValueError("ATLAS_OFFLINE_PERSONAL_ENROLLMENT_SCOPE_CHANGED")
    if (kalshi.get("target_paper_strategy")
            != "NEWLY_LISTED_SINGLE_YES_NO_PRICE_DISCOVERY_V1"
            or kalshi.get("legacy_repricing_paper_entry_enabled") is not False
            or kalshi.get("target_new_listing_paper_entry_commissioned") is not False
            or kalshi.get("yes_no_single_leg_only") is not True
            or kalshi.get("combos_allowed") is not False
            or kalshi.get("parlays_allowed") is not False
            or kalshi.get("live_execution") is not False):
        raise ValueError("ATLAS_OFFLINE_KALSHI_SCOPE_CHANGED")
    if (type(differences) is not dict
            or set(differences) != set(CHANGED_SELECTED_RUNTIME)
            or any(row.get("selected_native_contains_successor_fix") is not False
                   for row in differences.values())):
        raise ValueError("ATLAS_OFFLINE_PENDING_NATIVE_FIX_INVENTORY_INVALID")
    return {
        "schema":"ATLAS_R15_OFFLINE_PREPRODUCTION_CLOSEOUT_V1",
        "decision":"NO_GO",
        "offline_evidence_compiled":True,
        "selected_native_release":"R14",
        "selected_native_revision":13,
        "frozen_successor_source_candidate_verified":True,
        "successor_code_only_install_plan_verified":True,
        "successor_code_only_install_authorized":False,
        "successor_native_installation_executed":False,
        "successor_code_selection_authorized":False,
        "successor_source_commit":install_plan["source_commit"],
        "successor_archive_sha256":install_plan["source_archive_sha256"],
        "successor_native_plan_files":install_plan["planned_native_files"],
        "successor_native_plan_bytes":install_plan["planned_native_bytes"],
        "selected_r14_missing_successor_source_fixes":differences,
        "quality_dips_research_assets":sources["quality_dips"]["catalog_symbols"],
        "quality_dips_current_quotes_verified":False,
        "quality_dips_forward_paper_writer_enrolled":False,
        "hyperliquid_public_request_attempts_remaining":hl[
            "existing_request_budget"]["remaining"],
        "hyperliquid_current_book_verified":False,
        "hyperliquid_forward_paper_writer_enrolled":False,
        "personal_paper_native_activation_candidates":len(
            personal["ordinary_activation_file_candidates"]),
        "personal_paper_native_account_enrollment_verified":False,
        "kalshi_target_strategy":"NEWLY_LISTED_SINGLE_YES_NO_PRICE_DISCOVERY_V1",
        "kalshi_new_listing_paper_engine_commissioned":False,
        "legacy_desktop_launcher_ready":False,
        "live_trading_authorized":False,
        "paper_trading_authorized":False,
        "automated_desktop_start_stop_certified":False,
        "financial_operating_gates_accepted":0,
        "financial_operating_gates_total":9,
        "not_blocked_by_stock_market_hours_but_requires_separate_permission":[
            "Review and independently authorize one exact, low-impact, code-only successor native installation",
            "After verified native readback, separately authorize the successor code-only selection",
            "Independently enroll genuine local QD and Hyperliquid PAPER financial writers, native activation and operator leases",
            "Qualify independent continuous financial clock, native ledger and risk/Stop custody under an accepted owner",
        ],
        "blocked_on_real_provider_data_or_operational_evidence":[
            "Verify Alpaca free IEX data entitlement and current eligible equity/ETF quotes; do not infer Robinhood market coverage",
            "Verify Hyperliquid live public price book and source rights without resetting remaining requests",
            "Qualify Kalshi newly listed single YES/NO market timestamps, public books and future PAPER execution (separate lane)",
            "Supervised first real PAPER simulated entry, mark, risk, durable Stop, restart and operator observation",
            "Sustained multi-session PAPER soak and accounting evidence before months-ready acceptance",
        ],
        "provider_connections_opened":False,
        "credentials_accessed":False,
        "orders_submitted":False,
        "native_installation_modified":False,
        "selected_release_modified":False,
        "financial_gate_override":False,
    }


def inspect():
    return evaluate(
        selected=selected_inspect(),
        install_plan=code_install_inspect(),
        sources=source_inspect(),
        iex=inspect_selected_data_only(),
        hl=hyperliquid_book_inspect(),
        personal=personal_native_inspect(),
        kalshi=policy_snapshot(),
        differences=source_differences(),
    )


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inspect",action="store_true",required=True)
    parser.parse_args(argv)
    print(json.dumps(inspect(),sort_keys=True,indent=2))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
