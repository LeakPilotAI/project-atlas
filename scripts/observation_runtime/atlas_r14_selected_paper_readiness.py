"""Read-only readiness of selected R14 native code versus PAPER Start/Stop.

No independent NTP acquisition, child interpreter, provider, account, order,
service start, Stop signal, desktop shortcut mutation, or native release write.
This is NOT a financial acceptance grant.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

from scripts import release_selection as sel
from scripts.release_selection_store import NativeSelectionStore
from scripts.windows import atlas_paper_readiness_check as desktop

ROOT = Path("D:/Work/Project Atlas")
SELECTION_ROOT = Path("D:/AtlasRuntime/selection")
NATIVE_ROOT_ID = [4004218753, 65536, 1532785]
R12_SHA = "f685ff5c5d55ab87c4ee47b651afb823faa8d3696da4db120624bfac67c7c0c7"
R13_SHA = "6b1e04b8f733d46421c81a5d158dbafbecf052e6f3a8e8289d175caca96d4e31"
R14_SHA = "4cbf4f78c4da879f0e7d35f7ab1c3e119b4e0e7fc04640f0984ad4c8ce912ba7"
R14_HEAD = "3fd8e1972b559a5de90627a303fc663b11928f8b43e84621a6796e9f3dbe9383"
R12_HEAD = "f4cf83bb1e98ecb7cfa3be37fe27e80a79b339dc26f73358a1702349b47958fd"
R14 = Path("D:/AtlasRuntime/releases") / sel.R14_CODE_RELEASE
INSTALLED_RECEIPT = ROOT / "logs/diagnostics" / (
    "qd-unselected-release-" + sel.R14_CODE_RELEASE + ".json")

# Existing independent acceptance vocabulary; no gate promotion by this probe.
GATE_NEXT = {
    "B1_HISTORICAL_COMPLETENESS_OR_EPOCH":
        "Independently prove source-history completeness or an explicitly accepted new epoch",
    "C1_OWNERSHIP_AND_FINANCIAL_DRAIN":
        "Prove the same owned PAPER session can stop/flatten both QD and Hyperliquid and reconcile",
    "D1_TRUSTED_STORAGE_AUTHORITY_CLOCK":
        "Qualify a separate continuously valid financial clock, protected ledger and writer custody",
    "E1_PROVIDER_RIGHTS_AND_SUPERVISED_SESSION":
        "Verify free data entitlements/provider terms and supervised provider/PAPER session",
    "DESKTOP_OWNED_START_STOP":
        "Replace blocked legacy batch targets only after accepted installed owned Start and verified Stop",
    "MARKET_AND_ACCOUNT_COVERAGE":
        "Qualify Robinhood-listed equity/ETF universe via permitted Alpaca data and Hyperliquid perps",
    "RESTART_AND_RECONCILIATION":
        "Demonstrate recovery of durable PAPER positions and Stop receipts across a process restart",
    "SUPERVISED_END_TO_END":
        "Run supervised PAPER-only order, risk, flatten and durable ledger acceptance",
    "EXTENDED_SOAK_ACCEPTANCE":
        "Observe continuous PAPER operation and reconcile independent multi-session performance evidence",
}


def sha_small(path: Path, limit=65536):
    if not path.is_file() or path.is_symlink() or path.stat().st_size > limit:
        raise ValueError("R14_READINESS_EXACT_SMALL_NATIVE_EVIDENCE_REQUIRED")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def collect_selected_reference():
    """Native read-only identity checks; only 13 tiny selection records."""
    if os.name != "nt":
        raise ValueError("R14_READINESS_WINDOWS_NATIVE_REQUIRED")
    store = NativeSelectionStore(root=str(SELECTION_ROOT), native_root=list(NATIVE_ROOT_ID))
    try:
        with store.locked():
            rows = store.records()
            if len(rows) != 13:
                raise ValueError("R14_READINESS_EXACT_REV13_NATIVE_HEAD_REQUIRED")
            if (sel.digest(rows[11]) != R12_HEAD
                    or sel.digest(rows[12]) != R14_HEAD
                    or rows[12].get("revision") != 13
                    or rows[12].get("action") != "SELECT"
                    or rows[12].get("previous") != R12_HEAD):
                raise ValueError("R14_READINESS_NATIVE_SELECTION_HEAD_CHANGED")
            if sha_small(SELECTION_ROOT/"r0012.json") != R12_SHA:
                raise ValueError("R14_READINESS_R12_PREDECESSOR_CHANGED")
            if (sha_small(SELECTION_ROOT/"r0013.json") != R13_SHA
                    or sha_small(SELECTION_ROOT/"r0013.pending") != R13_SHA):
                raise ValueError("R14_READINESS_PUBLISHED_REV13_BYTES_CHANGED")
            selected = sel.validate_spec(rows[12]["selected"], "WINDOWS_LOCAL")
            if (selected["release"] != sel.R14_CODE_RELEASE
                    or selected["root"] != str(R14)
                    or selected["receipt_sha256"] != R14_SHA
                    or selected["artifact_digest"] != sel.R14_ARTIFACT_DIGEST):
                raise ValueError("R14_READINESS_R14_NATIVE_REFERENCE_CHANGED")
    finally:
        store.close()
    # Small installed files only: existing installation/select verification
    # already performed the expensive 10,519-file native handle readback.
    if (R14.is_symlink() or R14.is_junction()
            or not R14.is_dir()
            or not (R14 / "python/python.exe").is_file()):
        raise ValueError("R14_READINESS_SELECTED_RUNTIME_PATH_UNAVAILABLE")
    if (not INSTALLED_RECEIPT.is_file() or INSTALLED_RECEIPT.is_symlink()
            or INSTALLED_RECEIPT.stat().st_size > 3*1024*1024
            or hashlib.sha256(INSTALLED_RECEIPT.read_bytes()).hexdigest() != R14_SHA):
        raise ValueError("R14_READINESS_INSTALLED_RECEIPT_CHANGED")
    return {
        "revision":13, "selected_release":sel.R14_CODE_RELEASE,
        "native_selection_head":R14_HEAD,
        "native_r13_envelope_sha256":R13_SHA,
        "native_original_r12_sha256":R12_SHA,
        "native_installed_receipt_sha256":R14_SHA,
        "selected_runtime_directory":str(R14),
        "native_selection_record_verified":True,
        "financial_authority":False,
    }


def collect_lifecycle():
    results = desktop.inspect(root=ROOT)
    if (results.get("schema") != "ATLAS_PAPER_DESKTOP_READINESS_V1"
            or results.get("decision") != "NO_GO"
            or results.get("paper_startup_authorized") is not False
            or results.get("live_trading_authorized") is not False):
        raise ValueError("R14_READINESS_DESKTOP_AUDIT_INVALID")
    native = {}
    for name in ("Atlas-Launch.ps1","Atlas-Stop.ps1",
                 "Atlas-Paper-Stop-Request.ps1"):
        file = R14/"scripts/windows"/name
        if not file.is_file() or file.is_symlink() or file.stat().st_size > 65536:
            native[name] = "UNVERIFIED_SELECTED_RUNTIME_SCRIPT"
            continue
        contents = file.read_text(encoding="utf-8-sig")
        if name in ("Atlas-Launch.ps1","Atlas-Stop.ps1"):
            native[name] = ("BLOCKED_LEGACY"
                            if desktop.ACTIVE_GUARD.search(contents)
                            else "UNVERIFIED_NOT_CERTIFIED")
        else:
            native[name] = ("SOURCE_ONLY_STOP_SIGNAL_NOT_FLATNESS_RECEIPT"
                            if "REQUESTED_NOT_VERIFIED" in contents
                            and "financial_flatness_verified" in contents
                            else "UNVERIFIED_NOT_CERTIFIED")
    return {"workspace_desktop":results["desktop"],
            "selected_runtime_script_checks":native,
            "stop_requires_owned_session_and_durable_flat_receipt":True}


def evaluate(selected, lifecycle):
    """Refuse foreign/missing selection; do not turn code into PAPER authority."""
    if (type(selected) is not dict or
            selected.get("selected_release") != sel.R14_CODE_RELEASE
            or selected.get("revision") != 13
            or selected.get("native_selection_head") != R14_HEAD
            or selected.get("native_selection_record_verified") is not True
            or selected.get("financial_authority") is not False):
        raise ValueError("R14_READINESS_SELECTED_CODE_IDENTITY_REQUIRED")
    if (type(lifecycle) is not dict or
            type(lifecycle.get("workspace_desktop")) is not dict or
            type(lifecycle.get("selected_runtime_script_checks")) is not dict):
        raise ValueError("R14_READINESS_LIFECYCLE_EVIDENCE_REQUIRED")
    checks = lifecycle["workspace_desktop"]
    native = lifecycle["selected_runtime_script_checks"]
    if (set(checks) != {"desktop_start","desktop_stop"}
            or any(value not in ("BLOCKED_LEGACY","UNVERIFIED")
                   for value in checks.values())
            or set(native) != {
                "Atlas-Launch.ps1","Atlas-Stop.ps1","Atlas-Paper-Stop-Request.ps1"
            } or lifecycle.get("stop_requires_owned_session_and_durable_flat_receipt") is not True):
        raise ValueError("R14_READINESS_LIFECYCLE_EVIDENCE_REFUSED")
    rows = [{
        "gate": gate, "status":"NOT_INDEPENDENTLY_ACCEPTED",
        "accepted":False, "next_evidence": next_evidence
    } for gate,next_evidence in GATE_NEXT.items()]
    if set(GATE_NEXT) != set(desktop.ACCEPTANCE_GATES):
        raise ValueError("R14_READINESS_NINE_GATE_DRIFT")
    return {
        "schema":"ATLAS_SELECTED_R14_PAPER_READINESS_V1",
        "decision":"NO_GO",
        "selected_code_identity":selected,
        "selected_code_verified":True,
        "selected_code_is_financial_authority":False,
        "lifecycle":lifecycle,
        "accepted_financial_operating_gates":0,
        "total_financial_operating_gates":len(rows),
        "gates":rows,
        "desktop_one_click_paper_ready":False,
        "paper_start_authorized":False,
        "paper_orders_authorized":False,
        "live_orders_authorized":False,
        "provider_access_authorized":False,
        "financial_ledger_mutation":False,
        "automatic_startup":False,
        "note":"Verified R14 code selection does not establish operating provider/source, owned Stop flatten, financial custody or continuous PAPER profitability.",
    }


def inspect():
    return evaluate(collect_selected_reference(), collect_lifecycle())


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inspect", action="store_true", required=True)
    args=parser.parse_args(argv)
    print(json.dumps(inspect(),sort_keys=True,indent=2))
    return 2  # Explicit NO_GO, not a launch-ready exit.


if __name__ == "__main__":
    raise SystemExit(main())
