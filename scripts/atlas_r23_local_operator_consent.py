"""Human-local R23 code-only installer consent, never a financial grant.

Intended for a visible, interactive Windows console deliberately launched by
the signed-in operator. Remote/tool stdin and headless sessions refuse.
R23 itself retains final native selector/roots/clock/identity safety checks.
"""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import importlib
import json
import os
import sys
import tempfile
from pathlib import Path

from scripts import atlas_r23_code_only_install as inst

EXPECTED_HASH = "c227afa1fd71980e3d294c03a0f50f0a3bc8bd31f99cd4f96988ad054684742a"
SCOPE = "APPROVE_ONE_R23_CODE_ONLY_NATIVE_INSTALL_NO_FINANCIAL_START"
SOURCE_ROOT = Path("D:/Work/Project Atlas")


def preflight():
    if os.name != "nt" or Path(inst.__file__).resolve() != SOURCE_ROOT / "scripts/atlas_r23_code_only_install.py":
        raise ValueError("R23_LOCAL_ORIGINAL_WINDOWS_INSTALLER_REQUIRED")
    if inst.APPROVAL_PIN is not None or inst.source_hash() != EXPECTED_HASH:
        raise ValueError("R23_ORIGINAL_UNAPPROVED_INSTALLER_HASH_REQUIRED")
    if any(os.path.lexists(p) for p in (inst.APPROVAL, inst.TARGET, inst.RECEIPT, inst.JOURNAL)):
        raise ValueError("R23_LOCAL_ONE_SHOT_ORIGINAL_CREATE_ONLY_STATE_REQUIRED")
    prepared = inst.frozen_prepared()
    if len(prepared["names"]) != inst.EXPECTED_FILES:
        raise ValueError("R23_LOCAL_ORIGINAL_FROZEN_INVENTORY_CHANGED")
    return {
        "status": "PREPARED_LOCAL_OPERATOR_DECISION_NOT_APPROVED",
        "code_only_scope": SCOPE,
        "installer_source_sha256": EXPECTED_HASH,
        "source_release": inst.SOURCE,
        "native_target": str(inst.TARGET),
        "native_files": inst.EXPECTED_FILES,
        "simulated_accounts_authorized": False,
        "paper_start_authorized": False,
        "live_trading_authorized": False,
    }


def require_visible_local_console():
    if os.name != "nt" or not sys.stdin.isatty():
        raise ValueError("R23_VISIBLE_LOCAL_WINDOWS_OPERATOR_CONSOLE_REQUIRED")
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetConsoleWindow.restype = ctypes.c_void_p
    hwnd = kernel.GetConsoleWindow()
    if not hwnd:
        raise ValueError("R23_VISIBLE_LOCAL_WINDOWS_OPERATOR_CONSOLE_REQUIRED")
    user = ctypes.WinDLL("user32", use_last_error=True)
    user.IsWindowVisible.argtypes = [ctypes.c_void_p]
    user.IsWindowVisible.restype = ctypes.c_int
    if not user.IsWindowVisible(hwnd):
        raise ValueError("R23_VISIBLE_LOCAL_WINDOWS_OPERATOR_CONSOLE_REQUIRED")
    return True


def approval_record():
    from scripts.volume_inspector.windows_output import current_sid

    original = inst.original_selected_r21()
    return {
        "schema": inst.DECISION_SCHEMA,
        "scope": SCOPE,
        "action": "ONE_SHOT_R23_NATIVE_CODE_ONLY_INSTALL",
        "operator_sid": current_sid(),
        "source_commit": inst.SOURCE,
        "source_archive_sha256": inst.ARCHIVE_SHA,
        "source_inventory_sha256": inst.INVENTORY_SHA,
        "dependency_inventory_sha256": inst.DEPENDENCY_INVENTORY_SHA256,
        "native_predecessor": inst.R21_SOURCE,
        "native_predecessor_artifact_digest": original["artifact_digest"],
        "installer_source_sha256": EXPECTED_HASH,
        "destination": str(inst.TARGET),
        "receipt": str(inst.RECEIPT),
        "one_shot": True,
        "financial_authority": False,
        "provider_access": False,
        "paper_accounts": False,
        "paper_start_authorized": False,
        "live_trading_authorized": False,
    }


def pin_after_human_action():
    require_visible_local_console()
    preflight()
    decision = approval_record()
    raw = json.dumps(decision, sort_keys=True, allow_nan=False).encode("utf-8")
    sha = hashlib.sha256(raw).hexdigest()
    marker = b"APPROVAL_PIN = None  # Original distinct R23 operator approval; canonical source hash."
    updated = (b'APPROVAL_PIN = "' + sha.encode("ascii")
               + b'"  # Original distinct R23 operator approval; canonical source hash.')
    path = Path(inst.__file__)
    original = path.read_bytes()
    if original.count(marker) != 1:
        raise ValueError("R23_LOCAL_CANONICAL_SOURCE_PIN_MARKER_CHANGED")
    # Create-only decision first; any interrupted stage fails the installer closed.
    with inst.APPROVAL.open("xb") as f:
        f.write(raw)
        f.flush()
        os.fsync(f.fileno())
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(mode="wb", prefix=".atlas-r23-consent-",
                                         suffix=".tmp", dir=path.parent, delete=False) as out:
            tmp = Path(out.name)
            out.write(original.replace(marker, updated))
            out.flush()
            os.fsync(out.fileno())
        if path.read_bytes() != original:
            raise ValueError("R23_LOCAL_INSTALLER_CHANGED_DURING_APPROVAL")
        os.replace(tmp, path)
    finally:
        if tmp is not None and tmp.exists():
            tmp.unlink()
    importlib.reload(inst)
    if inst.source_hash() != EXPECTED_HASH or inst.approval_digest() != sha:
        raise ValueError("R23_LOCAL_OPERATOR_DECISION_READBACK_REFUSED")
    return sha


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--review", action="store_true")
    mode.add_argument("--approve-and-install", action="store_true")
    args = parser.parse_args(argv)

    if args.review:
        print(json.dumps(preflight(), sort_keys=True, indent=2))
        return 0

    require_visible_local_console()
    review = preflight()
    print(json.dumps(review, sort_keys=True, indent=2), flush=True)
    print("\nThis is ONLY the once-only R23 CODE INSTALL, leaving selected R21 unchanged.")
    print("NO paper accounts, NO PAPER operation, NO trading permission, NO live money.")
    typed = input("\nType the EXACT code-only scope shown above and press Enter: ")
    if typed != SCOPE:
        print("REFUSED: distinct local operator approval not provided.")
        return 2
    require_visible_local_console()
    sha = pin_after_human_action()
    print("LOCAL_OPERATOR_DECISION_PINNED_SHA256=" + sha, flush=True)
    result = inst.main(["--execute-approved-code-only", "--confirm-scope", SCOPE])
    print(json.dumps(result, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
