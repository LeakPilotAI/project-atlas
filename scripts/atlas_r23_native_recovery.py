"""One-shot, separately audited R23 original-native PARTIAL-RELEASE RECOVERY.

NEVER reruns failed original R23 installer or overwrites one original file.
Reopens all 7,910 originally copied native files and revalidates exact SID/ACL,
Windows identities, hardlinks, source hashes and sequential source manifest.
Only then creates the 2,853 missing native files using original NTFS relative
exclusive-create handles, revalidates each, and independently reads back the
whole new code-only release under its OWN isolated installed Python.

Original REFUSED journal remains unchanged until all native verification is
complete, and then retains its original refusal as line 2; a real new native
recovery result/one-shot approved action becomes line 3 final ACK, never a
synthetic substitution. Separate recovery intent prevents ambiguous retries.
No source switching, financial accounts, provider, PAPER or LIVE permission.
"""
from __future__ import annotations

import argparse
import ctypes as C
import hashlib
import io
import json
import os
import re
import time
import zipfile
from contextlib import ExitStack
from pathlib import Path

from scripts.atlas_r13_low_impact_installer import LowImpactEnvelope, _exact_bytes
from scripts.atlas_r23_code_only_install import (
    ARCHIVE_SHA,
    EXPECTED_DIRECTORIES,
    EXPECTED_FILES,
    INVENTORY_SHA,
    JOURNAL,
    RECEIPT,
    SOURCE,
    TARGET,
    original_accounts,
    original_selected_r21,
)
from scripts.atlas_r23_partial_native_readonly import (
    AUDIT,
    native_audit,
    source_plan,
)
from scripts.atlas_r23_partial_native_readonly import (
    SCHEMA as READONLY_SCHEMA,
)
from scripts.atlas_r23_source_review import ROOT
from scripts.install_verified_release import installed_readback, write_new_json
from scripts.observation_runtime.atlas_independent_ntp_clock import IndependentNtpClock
from scripts.observation_runtime.atlas_r17_cpu_budget import NativeR17CpuBudget
from scripts.observation_runtime.native_install_host_admission import (
    require_code_install_host_ready,
)
from scripts.observation_runtime.personal_paper_inception import native_primitives
from scripts.observation_runtime.personal_version_safe_release_clock import (
    SELECTOR_NATIVE,
)
from scripts.release_selection_store import NativeSelectionStore

SCHEMA = "ATLAS_R23_ORIGINAL_NATIVE_PARTIAL_RELEASE_RECOVERY_V1"
AUDIT_SHA = "30d4a475a56d40527fc9478595dc84de26ffeb7a32f299575f111d6139008096"
APPROVAL = ROOT / "logs/diagnostics/atlas-r23-partial-recovery-approved-20261116.json"
APPROVAL_PIN = None  # Distinct source/SDDL/partial audit-bound recovery approval.
RECOVERY_JOURNAL = ROOT / "logs/diagnostics/atlas-r23-original-partial-recovery-20261116.pending.jsonl"
RECOVERY_RECEIPT = ROOT / "logs/diagnostics/atlas-r23-original-partial-recovery-20261116.json"
SCOPE = "APPROVE_ONE_R23_ORIGINAL_NATIVE_PARTIAL_CODE_RECOVERY_NO_FINANCE"
CLOCK_IDENTITY = "atlas-r23-original-recovery-" + SOURCE
MAX_RECOVERY_SECONDS = 575
MIN_PREFIX = 7910
MAX_PREFIX = 7910
RECOVERED_ACK_STAGE = "UNSELECTED_CODE_INSTALL_VERIFIED"


def source_hash():
    data = Path(__file__).read_bytes()
    changed, count = re.subn(
        rb'(?m)^APPROVAL_PIN = (?:None|"[0-9a-f]{64}")'
        rb"  # Distinct source/SDDL/partial audit-bound recovery approval\.",
        b"APPROVAL_PIN = None  # Distinct source/SDDL/partial audit-bound recovery approval.",
        data,
    )
    if count != 1:
        raise ValueError("R23_RECOVERY_SOURCE_SHA_CANONICAL_REFUSED")
    return hashlib.sha256(changed).hexdigest()


def _audit():
    raw = _exact_bytes(AUDIT, AUDIT_SHA, max_bytes=4*1024*1024)
    prior = json.loads(raw)
    if (
        type(prior) is not dict or prior.get("schema") != READONLY_SCHEMA
        or prior.get("source_commit") != SOURCE
        or prior.get("archive_sha256") != ARCHIVE_SHA
        or prior.get("source_inventory_sha256") != INVENTORY_SHA
        or prior.get("native_root") != str(TARGET)
        or prior.get("expected_file_count") != EXPECTED_FILES
        or not MIN_PREFIX <= prior.get("existing_native_verified_prefix_files", 0)
        <= MAX_PREFIX
        or len(prior.get("native_prefix_files", []))
        != prior["existing_native_verified_prefix_files"]
        or len(prior.get("native_directories", [])) != EXPECTED_DIRECTORIES
        or prior.get("original_partial_refusal_preserved") is not True
        or prior.get("native_original_acl_identity_hash_readback") is not True
        or any(prior.get(k) is not False for k in (
            "code_only_recovery_write_authorized",
            "new_native_release_selected", "financial_accounts_created",
            "paper_start_authorized", "live_trading_authorized",
        ))
    ):
        raise ValueError("R23_RECOVERY_ORIGINAL_EXACT_NATIVE_AUDIT_REQUIRED")
    return prior


def approval_digest():
    if (
        type(APPROVAL_PIN) is not str
        or re.fullmatch(r"[0-9a-f]{64}", APPROVAL_PIN) is None
    ):
        raise ValueError("R23_RECOVERY_DISTINCT_APPROVAL_REQUIRED")
    from scripts.volume_inspector.windows_output import current_sid

    decision = json.loads(_exact_bytes(APPROVAL, APPROVAL_PIN, max_bytes=4096))
    audit = _audit()
    fields = {
        "schema", "scope", "action", "operator_sid", "installer_source_sha256",
        "release_source_commit", "original_native_refusal_sha256",
        "read_only_native_audit_sha256", "native_prefix_files",
        "remaining_create_only_files", "selected_predecessor_release",
        "selected_predecessor_artifact_digest", "target_native_root",
        "original_pending_journal", "final_release_receipt",
        "separate_recovery_journal", "separate_recovery_receipt",
        "one_shot", "financial_authority", "provider_access",
        "simulated_accounts", "paper_start_authorized",
        "live_trading_authorized",
    }
    old = original_selected_r21()
    if (
        type(decision) is not dict or set(decision) != fields
        or decision["schema"] != "ATLAS_R23_NATIVE_PARTIAL_CODE_RECOVERY_APPROVAL_V1"
        or decision["scope"] != SCOPE
        or decision["action"] != "ONE_SHOT_VERIFY_EXISTING_AND_CREATE_MISSING"
        or decision["operator_sid"] != current_sid()
        or decision["installer_source_sha256"] != source_hash()
        or decision["release_source_commit"] != SOURCE
        or decision["original_native_refusal_sha256"]
        != audit["original_refused_journal_sha256"]
        or decision["read_only_native_audit_sha256"] != AUDIT_SHA
        or decision["native_prefix_files"] != audit["existing_native_verified_prefix_files"]
        or decision["remaining_create_only_files"] != audit["remaining_create_only_files"]
        or decision["selected_predecessor_release"] != old["release"]
        or decision["selected_predecessor_artifact_digest"]
        != old["artifact_digest"]
        or decision["target_native_root"] != str(TARGET)
        or decision["original_pending_journal"] != str(JOURNAL)
        or decision["final_release_receipt"] != str(RECEIPT)
        or decision["separate_recovery_journal"] != str(RECOVERY_JOURNAL)
        or decision["separate_recovery_receipt"] != str(RECOVERY_RECEIPT)
        or decision["one_shot"] is not True
        or any(decision[k] is not False for k in (
            "financial_authority", "provider_access",
            "simulated_accounts", "paper_start_authorized",
            "live_trading_authorized",
        ))
    ):
        raise ValueError("R23_RECOVERY_APPROVAL_SCOPE_SID_OR_SOURCE_REFUSED")
    return APPROVAL_PIN


def _readonly_preflight():
    if (
        os.path.lexists(RECOVERY_JOURNAL)
        or os.path.lexists(RECOVERY_RECEIPT)
        or os.path.lexists(RECEIPT)
        or os.path.lexists(Path("D:/AtlasRuntime/selection/r0021.json"))
        or os.path.lexists(Path("D:/AtlasRuntime/selection/r0021.pending"))
    ):
        raise ValueError("R23_RECOVERY_CREATE_ONLY_NO_RETRY_REQUIRED")
    require_code_install_host_ready(TARGET.parent)
    original_accounts()
    prepared, refused_sha = source_plan(for_verified_recovery=True)
    original = _audit()
    if refused_sha != original["original_refused_journal_sha256"]:
        raise ValueError("R23_RECOVERY_ORIGINAL_REFUSAL_DRIFT")
    return prepared, original


def _no_selector_change(expected):
    selector = NativeSelectionStore(
        root=r"D:\AtlasRuntime\selection", native_root=list(SELECTOR_NATIVE),
    )
    try:
        with selector.locked():
            rows = selector.records()
            if (
                len(rows) != 20 or rows[-1]["revision"] != 20
                or rows[-1]["selected"] != expected
            ):
                raise ValueError("R23_RECOVERY_ORIGINAL_SELECTED_R21_CHANGED")
    finally:
        selector.close()
    return True


def _copy_missing_native(*, prepared, existing, tick):
    """ONLY missing files, create-exclusive; original files never opened WRITE."""
    native = native_primitives()
    w = native.w
    names = prepared["names"]
    if (
        [row["path"] for row in existing["native_prefix_files"]]
        != names[:len(existing["native_prefix_files"])]
    ):
        raise ValueError("R23_RECOVERY_ORIGINAL_FILE_PREFIX_CHANGED")
    prior = existing["native_prefix_files"]
    rows = list(prior)
    known_ids = {tuple(row["id"]) for row in existing["native_directories"]+prior}
    if len(known_ids) != len(existing["native_directories"])+len(prior):
        raise ValueError("R23_RECOVERY_ORIGINAL_NATIVE_ID_ALIAS")
    with ExitStack() as stack:
        outputs = {}
        for row in existing["native_directories"]:
            tick()
            p = TARGET if row["path"] == "." else TARGET / row["path"]
            out = stack.enter_context(w.WindowsOutput(str(p)))
            info = w.info(out.root_handle)
            actual_id = [info.volume, info.index_hi, info.index_lo]
            if actual_id != row["id"]:
                raise ValueError("R23_RECOVERY_ORIGINAL_NATIVE_DIR_CHANGED")
            outputs[row["path"]] = out
        readers = {}
        bundle = stack.enter_context(zipfile.ZipFile(io.BytesIO(prepared["raw"])))
        for name in names[len(prior):]:
            tick()
            row = (prepared["dependencies"] if
                   name in prepared["dependencies"] else prepared["runtime"])[name]
            relative = Path(name)
            directory = relative.parent.as_posix()
            out = outputs[directory]
            if os.path.lexists(TARGET/relative):
                raise ValueError("R23_RECOVERY_ONLY_NEW_NATIVE_FILES_ALLOWED")
            if name in prepared["dependencies"]:
                if directory not in readers:
                    src = stack.enter_context(
                        w.WindowsOutput(str(prepared["source"]/directory))
                    )
                    info = w.info(src.root_handle)
                    if [info.volume, info.index_hi, info.index_lo] != (
                        prepared["old_dirs"][directory]["id"]
                    ):
                        raise ValueError("R23_RECOVERY_ORIGINAL_DEPENDENCY_DIR_CHANGED")
                    readers[directory] = src
                src = readers[directory]
                inp = w.relative_open(
                    src.root_handle, relative.name, src.sid, False,
                    access=w.READ | w.READ_CONTROL,
                )
                try:
                    w.validate_acl(inp, src.sid)
                    info = w.info(inp)
                    if (
                        [info.volume, info.index_hi, info.index_lo] != row["id"]
                        or info.links != 1
                        or ((info.size_hi << 32) | info.size_lo) != row["bytes"]
                    ):
                        raise ValueError("R23_RECOVERY_DEPENDENCY_NATIVE_ID_CHANGED")
                    chunks, total = [], 0
                    while True:
                        tick()
                        buf, count = C.create_string_buffer(65536), w.W.DWORD()
                        w.check(w.read_file(inp, buf, 65536, C.byref(count), None))
                        if not count.value:
                            break
                        total += count.value
                        if total > row["bytes"]:
                            raise ValueError("R23_RECOVERY_DEPENDENCY_GROWTH")
                        chunks.append(buf.raw[:count.value])
                    data = b"".join(chunks)
                finally:
                    if not w.close_handle(inp):
                        raise OSError("R23_RECOVERY_ORIGINAL_INPUT_CLOSE_FAILED")
            else:
                data = bundle.read(name)
            if len(data) != row["bytes"] or hashlib.sha256(data).hexdigest() != row["sha256"]:
                raise ValueError("R23_RECOVERY_PINNED_SOURCE_CHANGED")
            out._verify()
            handle = w.relative_open(
                out.root_handle, relative.name, out.sid, False,
                create=True,
                access=w.READ | w.WRITE | w.READ_CONTROL,
            )
            try:
                w.validate_acl(handle, out.sid)
                info = w.info(handle)
                ident = (info.volume, info.index_hi, info.index_lo)
                if ident in known_ids or info.links != 1:
                    raise ValueError("R23_RECOVERY_NEW_NATIVE_ID_INVALID")
                for offset in range(0, len(data), 65536):
                    tick()
                    part = data[offset:offset+65536]
                    count = w.W.DWORD()
                    w.check(w.write_file(handle, part, len(part), C.byref(count), None))
                    if count.value != len(part):
                        raise OSError("R23_RECOVERY_NATIVE_FILE_PARTIAL_WRITE")
                w.check(w.flush(handle))
                info = w.info(handle)
                if (
                    (info.volume, info.index_hi, info.index_lo) != ident
                    or info.links != 1
                    or ((info.size_hi << 32) | info.size_lo) != len(data)
                ):
                    raise ValueError("R23_RECOVERY_NEW_NATIVE_FILE_CHANGED")
            finally:
                if not w.close_handle(handle):
                    raise OSError("R23_RECOVERY_NEW_NATIVE_HANDLE_CLOSE")
            # Distinct handle readback of new file, not trusting write counts.
            fresh = w.relative_open(
                out.root_handle, relative.name, out.sid, False,
                access=w.READ | w.READ_CONTROL,
            )
            try:
                w.validate_acl(fresh, out.sid)
                info = w.info(fresh)
                if [info.volume, info.index_hi, info.index_lo] != list(ident):
                    raise ValueError("R23_RECOVERY_NEW_NATIVE_READBACK_ID")
                sha, count = hashlib.sha256(), 0
                while True:
                    tick()
                    buf, n = C.create_string_buffer(65536), w.W.DWORD()
                    w.check(w.read_file(fresh, buf, 65536, C.byref(n), None))
                    if not n.value:
                        break
                    count += n.value
                    if count > len(data):
                        raise ValueError("R23_RECOVERY_NEW_NATIVE_GROWTH")
                    sha.update(buf.raw[:n.value])
                if count != len(data) or sha.hexdigest() != row["sha256"]:
                    raise ValueError("R23_RECOVERY_NEW_NATIVE_DIGEST_CHANGED")
            finally:
                if not w.close_handle(fresh):
                    raise OSError("R23_RECOVERY_NEW_NATIVE_READBACK_CLOSE")
            known_ids.add(ident)
            rows.append({
                "path": name, "bytes": len(data), "sha256": row["sha256"],
                "id": list(ident),
            })
    if len(rows) != EXPECTED_FILES:
        raise ValueError("R23_RECOVERY_NOT_FULL_RELEASE")
    return rows, existing["native_directories"]


def recover(*, clock, approved=False):
    if approved is not True:
        raise ValueError("R23_RECOVERY_SEPARATE_ONE_SHOT_APPROVAL_REQUIRED")
    approval_digest()
    prepared, old = _readonly_preflight()
    clock_required_as_recovery(clock)
    from scripts.install_version_safe_candidate import _qualify_native_clock_180s
    _qualify_native_clock_180s(clock, CLOCK_IDENTITY)
    approval_digest()
    prior_r21 = original_selected_r21()
    with NativeR17CpuBudget() as cpu, LowImpactEnvelope(
        check_every=64, pace_every=128, pause_seconds=0.01,
        max_seconds=MAX_RECOVERY_SECONDS,
    ) as envelope:
        last = None

        def admission():
            nonlocal last
            cpu.pulse()
            envelope.tick()
            now = time.monotonic()
            if last is None or now - last >= 30:
                _no_selector_change(prior_r21)
                clock_required_as_recovery(clock)
                original_accounts()
                last = now
            return True

        admission()
        fresh = native_audit(
            prepared=prepared,
            journal_digest=old["original_refused_journal_sha256"],
            tick=admission,
        )
        if fresh != old:
            raise ValueError("R23_RECOVERY_ORIGINAL_NATIVE_AUDIT_DRIFT")
        approval_digest()
        admission()
        write_new_json(RECOVERY_JOURNAL, {
            "schema": SCHEMA,
            "stage": "RECOVERY_INTENT_VERIFY_EXISTING_CREATE_MISSING_ONLY",
            "original_audit_sha256": AUDIT_SHA,
            "original_refusal_sha256": old["original_refused_journal_sha256"],
            "new_original_root_allowed": False,
            "financial_authority": False,
            "selection_allowed": False,
        })

        def event(value):
            with RECOVERY_JOURNAL.open("ab") as file:
                file.write(b"\n"+json.dumps(
                    value, sort_keys=True, allow_nan=False,
                ).encode())
                file.flush()
                os.fsync(file.fileno())

        try:
            created, dirs = _copy_missing_native(
                prepared=prepared, existing=fresh, tick=admission,
            )
            receipt = {
                "schema": "ATLAS_QD_D_RUNTIME_INSTALLATION_V1",
                "stage": "D_RUNTIME_LAYOUT_VERIFIED",
                "release_path": str(TARGET),
                "source_commit": SOURCE,
                "files": created,
                "directories": dirs,
                "archive_sha256": ARCHIVE_SHA,
                "inventory_sha256": INVENTORY_SHA,
                "selected": False,
                "financial_effects": False,
                "provider_connections": False,
                "operational_acceptance": False,
            }
            artifact = hashlib.sha256(json.dumps(
                receipt["files"], sort_keys=True,
                separators=(",", ":"), allow_nan=False,
            ).encode()).hexdigest()
            deadline = MAX_RECOVERY_SECONDS - (
                time.monotonic() - envelope.started
            )
            if deadline < 185:
                raise ValueError("R23_RECOVERY_INDEPENDENT_180S_READBACK_DEADLINE")
            readback = installed_readback(
                TARGET, receipt, artifact, timeout=min(180, deadline-5),
            )
            receipt.update(layout=readback["layout"], artifact_digest=artifact)
            admission()
            original_selected_r21()
            original_accounts()
            approval_digest()
            result = {
                "schema": SCHEMA,
                "stage": "RECOVERY_FULL_NATIVE_ORIGINAL_READBACK_ACCEPTED",
                "source_commit": SOURCE,
                "source_archive_sha256": ARCHIVE_SHA,
                "original_partial_native_files_rechecked":
                    fresh["existing_native_verified_prefix_files"],
                "new_native_create_only_files":
                    len(created)-len(fresh["native_prefix_files"]),
                "final_original_native_files": len(created),
                "final_original_native_directories": len(dirs),
                "original_refusal_journal_sha256":
                    old["original_refused_journal_sha256"],
                "independent_original_native_installed_readback": True,
                "source_release_artifact_digest": artifact,
                "code_only_release_selected": False,
                "financial_authority": False,
                "paper_start_authorized": False,
                "live_trading_authorized": False,
            }
            # Create-only recovery evidence; original stage-2 refusal remains
            # byte-for-byte preserved in the earlier journal lines.
            write_new_json(RECOVERY_RECEIPT, result)
            write_new_json(RECEIPT, receipt)
            sha = hashlib.sha256(RECEIPT.read_bytes()).hexdigest()
            ack = {"stage": RECOVERED_ACK_STAGE, "receipt_sha256": sha}
            with JOURNAL.open("ab") as file:
                file.write(b"\n"+json.dumps(ack, sort_keys=True).encode())
                file.flush()
                os.fsync(file.fileno())
            event({"stage": "RECOVERED_FULL_CODE_ONLY_NATIVE_ACK",
                   "receipt_sha256": sha})
            return {
                "status": "R23_ORIGINAL_NATIVE_RECOVERY_FULL_CODE_ONLY_VERIFIED_UNSELECTED",
                "native_installed_files": len(created),
                "original_native_files_revalidated":
                    old["existing_native_verified_prefix_files"],
                "new_native_create_only_files": len(created)-len(old["native_prefix_files"]),
                "artifact_digest": artifact,
                "installed_receipt_sha256": sha,
                "financial_authority": False,
                "code_only_release_selected": False,
                "paper_start_authorized": False,
                "live_trading_authorized": False,
            }
        except BaseException:
            event({"stage": "RECOVERY_REFUSED_PRESERVE_PARTIAL_NO_RETRY"})
            raise


def clock_required_as_recovery(clock):
    if type(clock) is not IndependentNtpClock:
        raise ValueError("R23_RECOVERY_ORIGINAL_TWO_PEER_NTP_REQUIRED")
    clock.require_operational(CLOCK_IDENTITY)
    e = clock.evidence
    if (
        type(e.get("bound_ms")) is not int
        or not 0 <= e["bound_ms"] <= 1000
        or e.get("domain") != "TWO_PUBLIC_UNAUTHENTICATED_NTP_PEERS"
        or e.get("financial_authority") is not False
    ):
        raise ValueError("R23_RECOVERY_INDEPENDENT_NTP_REFUSED")
    return True


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--inspect", action="store_true")
    modes.add_argument("--execute-approved-recovery", action="store_true")
    parser.add_argument("--confirm-scope", default=None)
    args = parser.parse_args(argv)
    if args.inspect:
        prepared, prior = _readonly_preflight()
        return {
            "status": "ORIGINAL_PARTIAL_NATIVE_AUDIT_READY_FOR_SEPARATE_RECONCILIATION",
            "old_native_verified_files": prior["existing_native_verified_prefix_files"],
            "only_new_files_planned": len(prepared["names"])-len(
                prior["native_prefix_files"]),
            "original_code_release_selected": False,
            "approval_pin_present": type(APPROVAL_PIN) is str,
            "financial_authority": False,
            "paper_start_authorized": False,
        }
    if args.confirm_scope != SCOPE:
        raise ValueError("R23_RECOVERY_EXACT_APPROVAL_SCOPE_REQUIRED")
    approval_digest()
    clock = IndependentNtpClock(runtime_id=CLOCK_IDENTITY)
    try:
        return recover(clock=clock, approved=True)
    finally:
        clock.revoke()


if __name__ == "__main__":
    print(json.dumps(main(), sort_keys=True))
