"""Independent READ-ONLY original-Windows-native partial R21 release reconciliation.

Runs on original selected R20 Python and uses exact pinned source/dependency
manifest. Opens every existing directory/file by original native Windows NTFS
handle, checks SID+SYSTEM protected ACL, unique file IDs, 1 link, size and
SHA256. Rejects unlisted paths or anything other than an exact PREFIX of the
old immutable code-only copier's sorted file order.

NEVER writes the original partial root, never deletes evidence, never emits a
financial or source/installation/selection acceptance, and never edits the
original REFUSED journal. Its original file proof is independently reverified
before any separately authorized recovery write.
"""
from __future__ import annotations

import argparse
import ctypes as C
import hashlib
import json
import os
import time
from contextlib import ExitStack
from pathlib import Path

from scripts.atlas_r13_low_impact_installer import LowImpactEnvelope
from scripts.atlas_r14_low_impact_installer import (
    DEPENDENCY,
    DEPENDENCY_INVENTORY_SHA256,
    DEPENDENCY_RECEIPT_SHA256,
)
from scripts.atlas_r21_code_only_install import (
    ARCHIVE,
    ARCHIVE_SHA,
    EXPECTED_DIRECTORIES,
    EXPECTED_FILES,
    INVENTORY_SHA,
    JOURNAL,
    RECEIPT,
    SOURCE,
    TARGET,
    original_accounts,
    original_selected_r20,
)
from scripts.atlas_r21_source_review import ROOT
from scripts.native_install_plan import prepare_install_inputs
from scripts.observation_runtime.personal_paper_inception import native_primitives

SCHEMA = "ATLAS_R21_ORIGINAL_PARTIAL_NATIVE_FILE_RECONCILIATION_READONLY_V1"
AUDIT = ROOT / "logs/diagnostics/atlas-r21-native-partial-readonly-audit-20261113.json"
MAX_AUDIT_SECONDS = 570
OLD_REFUSAL = {"stage": "REFUSED_PRESERVE_PARTIAL_NO_RETRY"}


def source_plan(*, for_verified_recovery=False):
    original_selected_r20()
    original_accounts()
    if (
        not TARGET.is_dir()
        or TARGET.is_symlink() or TARGET.is_junction()
        or RECEIPT.exists()
        or (AUDIT.exists() and not for_verified_recovery)
    ):
        raise ValueError("R21_RECOVERY_EXACT_PRESERVED_PARTIAL_REQUIRED")
    if (
        not JOURNAL.is_file() or JOURNAL.is_symlink()
        or JOURNAL.is_junction() or JOURNAL.stat().st_size > 4096
    ):
        raise ValueError("R21_RECOVERY_ORIGINAL_REFUSAL_REQUIRED")
    raw = JOURNAL.read_bytes()
    lines = raw.splitlines()
    if (
        len(lines) != 2
        or json.loads(lines[0]) != {
            "schema": "ATLAS_R21_UNSELECTED_CODE_INSTALL_INTENT_V1",
            "source_commit": SOURCE, "archive_sha256": ARCHIVE_SHA,
            "target": str(TARGET), "financial_authority": False,
            "selection_allowed": False, "paper_start_authorized": False,
        }
        or json.loads(lines[1]) != OLD_REFUSAL
    ):
        raise ValueError("R21_RECOVERY_EXACT_NATIVE_REFUSAL_JOURNAL_REQUIRED")
    from scripts.atlas_r14_low_impact_installer import _exact_bytes
    dep = _exact_bytes(DEPENDENCY, DEPENDENCY_RECEIPT_SHA256, max_bytes=16*1024*1024)
    prepared = prepare_install_inputs(
        archive=ARCHIVE, archive_sha256=ARCHIVE_SHA, source_commit=SOURCE,
        inventory_digest=INVENTORY_SHA, dependency_receipt=json.loads(dep),
        dependency_digest=DEPENDENCY_INVENTORY_SHA256, require_tracked=True,
    )
    if (
        len(prepared["names"]) != EXPECTED_FILES
        or len(prepared["directories"])+1 != EXPECTED_DIRECTORIES
    ):
        raise ValueError("R21_RECOVERY_FROZEN_SOURCE_INVENTORY_REQUIRED")
    return prepared, hashlib.sha256(raw).hexdigest()


def native_audit(*, prepared, journal_digest, tick, include_rows=True):
    """All originally written files must be a strict, native-verified prefix."""
    native = native_primitives()
    w = native.w
    start = time.monotonic()
    expected_dirs = {".", *prepared["directories"]}
    expected_names = prepared["names"]
    actual_names, actual_dirs = set(), {"."}
    for current, dirs, files in os.walk(TARGET, followlinks=False):
        tick()
        base = Path(current).relative_to(TARGET)
        for leaf in dirs:
            path = Path(current) / leaf
            if path.is_symlink() or path.is_junction():
                raise ValueError("R21_PARTIAL_UNTRUSTED_REPARSE_DIRECTORY")
            actual_dirs.add((base / leaf).as_posix())
        for leaf in files:
            path = Path(current) / leaf
            if path.is_symlink() or path.is_junction():
                raise ValueError("R21_PARTIAL_UNTRUSTED_REPARSE_FILE")
            actual_names.add((base / leaf).as_posix())
    if (
        actual_dirs != expected_dirs
        or not 1 <= len(actual_names) < len(expected_names)
        or actual_names != set(expected_names[:len(actual_names)])
    ):
        raise ValueError("R21_PARTIAL_ORIGINAL_SEQUENTIAL_COPY_NOT_PROVEN")
    # The physical directory identities and ACLs are read through Windows
    # native handles; os.walk is only a secondary namespace completeness check.
    rows, directory_rows, seen_ids, total = [], [], set(), 0
    with ExitStack() as stack:
        outputs = {}
        for relative in [".", *prepared["directories"]]:
            tick()
            path = TARGET if relative == "." else TARGET / relative
            out = stack.enter_context(w.WindowsOutput(str(path)))
            out._verify()
            info = w.info(out.root_handle)
            ident = (info.volume, info.index_hi, info.index_lo)
            if ident in seen_ids:
                raise ValueError("R21_PARTIAL_NATIVE_DIR_ID_ALIAS")
            seen_ids.add(ident)
            outputs[relative] = out
            directory_rows.append({"path": relative, "id": list(ident)})
        for name in expected_names[:len(actual_names)]:
            tick()
            template = (prepared["dependencies"] if
                        name in prepared["dependencies"] else prepared["runtime"])[name]
            relative = Path(name)
            out = outputs[relative.parent.as_posix()]
            handle = w.relative_open(
                out.root_handle, relative.name, out.sid, False,
                access=w.READ | w.READ_CONTROL,
            )
            try:
                w.validate_acl(handle, out.sid)
                info = w.info(handle)
                ident = (info.volume, info.index_hi, info.index_lo)
                if (
                    ident in seen_ids or info.links != 1
                    or ((info.size_hi << 32) | info.size_lo) != template["bytes"]
                ):
                    raise ValueError("R21_PARTIAL_NATIVE_ID_SIZE_OR_HARDLINK_REFUSED")
                sha = hashlib.sha256()
                count = 0
                while True:
                    tick()
                    chunk, n = C.create_string_buffer(65536), w.W.DWORD()
                    w.check(w.read_file(handle, chunk, 65536, C.byref(n), None))
                    if not n.value:
                        break
                    count += n.value
                    if count > template["bytes"]:
                        raise ValueError("R21_PARTIAL_NATIVE_FILE_GROWTH_REFUSED")
                    sha.update(chunk.raw[:n.value])
                if count != template["bytes"] or sha.hexdigest() != template["sha256"]:
                    raise ValueError("R21_PARTIAL_NATIVE_HASH_REFUSED")
                seen_ids.add(ident)
                total += count
                rows.append({
                    "path": name, "bytes": count, "sha256": sha.hexdigest(),
                    "id": list(ident),
                })
            finally:
                if not w.close_handle(handle):
                    raise OSError("R21_PARTIAL_NATIVE_HANDLE_CLOSE_REFUSED")
    if time.monotonic() - start > MAX_AUDIT_SECONDS:
        raise ValueError("R21_PARTIAL_AUDIT_DEADLINE_REFUSED")
    return {
        "schema": SCHEMA,
        "original_refused_journal_sha256": journal_digest,
        "source_commit": SOURCE,
        "archive_sha256": ARCHIVE_SHA,
        "source_inventory_sha256": INVENTORY_SHA,
        "native_root": str(TARGET),
        "expected_file_count": EXPECTED_FILES,
        "existing_native_verified_prefix_files": len(rows),
        "existing_native_verified_prefix_bytes": total,
        "remaining_create_only_files": EXPECTED_FILES-len(rows),
        "native_directories": directory_rows,
        "native_prefix_files": rows if include_rows else [],
        "original_partial_refusal_preserved": True,
        "native_original_acl_identity_hash_readback": True,
        "code_only_recovery_write_authorized": False,
        "new_native_release_selected": False,
        "financial_accounts_created": False,
        "paper_start_authorized": False,
        "live_trading_authorized": False,
    }


def execute_readonly():
    if os.path.lexists(AUDIT):
        raise ValueError("R21_PARTIAL_AUDIT_CREATE_ONLY_REFUSED")
    prepared, sha = source_plan()
    with LowImpactEnvelope(
        check_every=64, pace_every=128, pause_seconds=0.01,
        max_seconds=MAX_AUDIT_SECONDS,
    ) as envelope:
        result = native_audit(
            prepared=prepared, journal_digest=sha,
            tick=envelope.tick,
        )
    # Read-only diagnostic is allowed to create one new project-local report,
    # NEVER original native release or financial files.
    from scripts.install_verified_release import write_new_json
    write_new_json(AUDIT, result)
    return {
        "schema": result["schema"],
        "status": "ORIGINAL_NATIVE_PARTIAL_PREFIX_VERIFIED_NO_WRITE",
        "original_prefix_file_count": result["existing_native_verified_prefix_files"],
        "original_prefix_bytes": result["existing_native_verified_prefix_bytes"],
        "remaining_create_only_files": result["remaining_create_only_files"],
        "readback_audit_sha256": hashlib.sha256(AUDIT.read_bytes()).hexdigest(),
        "original_refusal_preserved": True,
        "financial_authority": False,
        "paper_start_authorized": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute-readonly-native-audit", action="store_true")
    args = parser.parse_args(argv)
    if not args.execute_readonly_native_audit:
        raise ValueError("R21_EXACT_READONLY_AUDIT_SCOPE_REQUIRED")
    print(json.dumps(execute_readonly(), sort_keys=True))


if __name__ == "__main__":
    main()
