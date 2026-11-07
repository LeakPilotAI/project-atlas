import json
import os
import time
from pathlib import Path

_live_root = Path(__file__).parent
if (
    not os.environ.get("ATLAS_AUTH_SCOPE_SHA256")
    or not (_live_root / "single-use-claim.json").exists()
):
    raise SystemExit("NO_LIVE_EXPLICITLY_APPROVED_ACCEPTANCE_SESSION")
_live = json.loads((_live_root / "single-use-claim.json").read_bytes())
assert (
    _live["scope_sha256"] == os.environ["ATLAS_AUTH_SCOPE_SHA256"]
    and time.perf_counter_ns() < _live["deadline_ns"]
)
import ctypes as C
import json
import os
import shutil
import sys
import time
import zipfile
from pathlib import Path

r = Path(r"D:\Work\Project Atlas")
e = Path(__file__).parent
sys.path[:0] = [str(r / "backend"), str(r / "backend/.venv/Lib/site-packages"), str(r)]
from scripts.observation_runtime.personal_release_identity import (
    NativePersonalReleaseIdentity,
)
from scripts.observation_runtime.personal_windows_clock import LocalWindowsClock
from scripts.release_selection import NativeInstalledReleaseVerifier, ReleaseSelector
from scripts.release_selection_store import NativeSelectionStore
from scripts.support_deployment import (
    held,
    identity,
    prepare,
    safe_read,
    sha,
    verify_deployment,
)
from scripts.volume_inspector import windows_output as w

assert not C.windll.shell32.IsUserAnAdmin(), "ORDINARY_PROCESS_REQUIRED"
started = time.perf_counter()
result = {
    "accepted": False,
    "checks": [],
    "administrator": False,
    "operational_mutations": 0,
}


def passed(name, **details):
    result["checks"].append({"name": name, "passed": True, **details})
    (e / "native-preflight-progress.json").write_text(json.dumps(result, indent=2))
    print(name, flush=True)


try:
    mpath = r / "docs/QD_SUPPORT_DEPLOYMENT_MANIFEST_V1_2026-11-02.json"
    m = json.loads(safe_read(mpath, 65536))
    archive = (
        r
        / "logs/diagnostics/qd-support-deployment-reviewed-source-20261101/readiness-image-repair/support-source.zip"
    )
    m, files = prepare(
        m, archive, "7947f54e82d74079b378ad14c238dadb4259671ee7ed5c9d03e952d5d8327cd3"
    )
    package = json.loads(files["support-manifest.json"])
    assert (
        sha(files["support-manifest.json"])
        == m["support_manifest_sha256"]
        == "5b027d7dc0853975ee751c2c83145a9820a95da28041263b3585b56a4312eccc"
    )
    for row in m["files"]:
        if row["path"] != "support-manifest.json":
            assert (
                safe_read(r / row["path"], 262144).replace(b"\r\n", b"\n")
                == files[row["path"]]
            )
    passed(
        "EXACT_SUPPORT_ARCHIVE_MANIFEST_AND_NINE_CURRENT_SOURCES",
        archive_bytes=archive.stat().st_size,
        files=len(files),
        payload_bytes=sum(map(len, files.values())),
    )
    assert m["limits"] == {"seconds": 600, "entries": 8192, "bytes": 67108864}
    paths = [
        *[Path(x) for x in m["new_parents"]],
        Path(m["selection"]),
        Path(m["destination"]),
        Path(m["control"]),
    ]
    existing_receipt = verify_deployment(
        m,
        expected_receipt_sha256="01bb0f6efb04c706e594acb8c63759ee682e4bce2f2062882015edff36d6ce91",
    )
    result["existing_verified_operational_paths"] = [str(p) for p in paths]
    with held(w.WindowsOutput(r"D:\AtlasRuntime")) as parent:
        result["private_parent_native_identity"] = identity(w, parent.root_handle)
        result["private_owner_sid"] = parent.sid
        parent._verify()
    assert parent.handles == []
    passed(
        "EXACT_EXISTING_RECEIPT_ACK_NATIVE_NTFS_OWNER_SYSTEM_ACL_AND_NAMESPACES",
        parent_handles_after_close=0,
    )

    reference = {
        "schema": "QD_INSTALLED_RELEASE_REFERENCE_V1",
        "domain": "WINDOWS_LOCAL",
        **m["application"],
    }
    t = time.perf_counter()
    with NativeInstalledReleaseVerifier().open(reference) as receipt:
        assert receipt["source_commit"] == "2c039af29dfefd1df77e0caa3db3fdf5ed188118"
        assert len(receipt["files"]) == 10204 and len(receipt["directories"]) == 903
        actual = {row["path"].replace("\\", "/"): row for row in receipt["files"]}
        for row in package["required_installed_application_sources"]:
            assert actual[row["path"]]["sha256"] == row["sha256"]
        result["application"] = {
            "release": receipt["source_commit"],
            "root": receipt["release_path"],
            "artifact_digest": receipt["artifact_digest"],
            "files": len(actual),
            "directories": len(receipt["directories"]),
            "bytes": sum(row["bytes"] for row in receipt["files"]),
            "verified_required_dependencies": len(
                package["required_installed_application_sources"]
            ),
        }
    passed(
        "ACTUAL_APPLICATION_NATIVE_INVENTORY_HASHES_IDENTITIES_ACLS_NAMESPACE_AND_INSTALLED_ONLY_READBACK",
        seconds=time.perf_counter() - t,
        **result["application"],
    )

    receipt_path = Path(reference["receipt"])
    journal = safe_read(
        receipt_path.with_suffix(".pending.jsonl"), 128 * 1024**2
    ).splitlines()
    assert json.loads(journal[-1]) == {
        "stage": "UNSELECTED_CODE_INSTALL_VERIFIED",
        "receipt_sha256": reference["receipt_sha256"],
    }
    assert sha(safe_read(receipt_path, 8 * 1024**2)) == reference["receipt_sha256"]
    assert (
        sha(safe_read(receipt_path.with_suffix(".pending.jsonl"), 128 * 1024**2))
        == "27940d77ef60d5389581213f6334910fdc84677c85639aeb20c50bc10d644f13"
    )
    control_pins = {
        "intent.json": "270ebc37107734a845e9bb9c4ef831152e43f8069a1328570b27597418b16a79",
        "receipt.json": "01bb0f6efb04c706e594acb8c63759ee682e4bce2f2062882015edff36d6ce91",
        "ack.json": "2d87da5b5b9959d5e0933d730e26b2a425f7bddd1b80d089fec98536a3b62851",
    }
    for name, pin in control_pins.items():
        assert sha(safe_read(Path(m["control"]) / name, 8 * 1024**2)) == pin
    passed(
        "ORIGINAL_DURABLE_APPLICATION_RECEIPT_AND_FINAL_ACK",
        journal_records=len(journal),
    )

    app_archive = (
        r
        / "logs/diagnostics/qd-evidence-promotion-package-d08ba9cbba2c405c/archive/atlas-source.zip"
    )
    assert (
        sha(safe_read(app_archive, 64 * 1024**2))
        == package["application_archive_sha256"]
        == receipt["archive_sha256"]
    )
    with zipfile.ZipFile(app_archive) as z:
        source_manifest = json.loads(z.read("release-manifest.json"))
        assert (
            source_manifest["head"] == receipt["source_commit"]
            and source_manifest["activation_approved"] is False
        )
        assert len(source_manifest["files"]) == 638
        for row in source_manifest["files"]:
            raw = z.read(row["path"])
            assert sha(raw) == row["sha256"] == actual[row["path"]]["sha256"]
            assert len(raw) == row["bytes"] == actual[row["path"]]["bytes"]
    passed("FROZEN_638_SOURCE_MANIFEST_ARCHIVE_TO_NATIVE_INSTALLED_INVENTORY_PARITY")

    previous_path = (
        r / "logs/diagnostics/qd-d-runtime-coordination-installation-20261028.json"
    )
    previous_raw = safe_read(previous_path, 8 * 1024**2)
    previous = json.loads(previous_raw)
    old_owner = NativePersonalReleaseIdentity(
        receipt=previous,
        artifact_digest="93e52e897fd2f2f3cc4b17bd3e804e8c598a1a3a8938c2b5c47d386890310c91",
    )
    try:
        assert len(old_owner.files) == 10182 and len(old_owner.outputs) == 903
    finally:
        old_owner.close()
    assert old_owner.closed and not old_owner.handles and not old_owner.outputs
    result["previous_release"] = {
        "release": previous["source_commit"],
        "files": 10182,
        "directories": 903,
        "receipt_sha256": sha(previous_raw),
        "selected_status": "NOT_INFERRED_FROM_EXISTENCE",
        "owned_handles_after_close": 0,
    }
    passed(
        "OLDER_RETAINED_RELEASE_FULL_NATIVE_INVENTORY_PRESERVED_NOT_ASSUMED_SELECTED",
        **result["previous_release"],
    )

    # Existing-only selector readback. Never create, reset or publish in preflight.
    clock = store = None
    try:
        store = NativeSelectionStore(
            root=m["selection"], native_root=existing_receipt["selection_id"]
        )
        clock = LocalWindowsClock(
            expected_source="time.windows.com,0x9", runtime_id="qd-acceptance-preflight"
        )
        current = ReleaseSelector(
            store=store, verifier=NativeInstalledReleaseVerifier(), clock=clock
        ).current()
        with store.locked():
            rows = store.records()
        assert len(rows) == 6 and current == {
            "head": "c9bc240c11c148cd6c6f6dda7c6760aa2d2ac9547ee8c44847bf239b6382ffbc",
            "selected": None,
        }
    finally:
        if store is not None:
            store.close()
        if clock is not None:
            clock.revoke()
    result["selection_baseline"] = {
        "resource_exists": True,
        "records": 6,
        "head": current["head"],
        "selected": None,
        "rollback_target_head": current["head"],
    }
    result["reused_support_receipt_sha256"] = (
        "01bb0f6efb04c706e594acb8c63759ee682e4bce2f2062882015edff36d6ce91"
    )
    assert existing_receipt["parent_id"] == result["private_parent_native_identity"]
    passed(
        "EXACT_CURRENT_R6_UNSELECTED_BASELINE_AND_VERIFIED_KNOWN_HEAD_ROLLBACK_READINESS",
        **result["selection_baseline"],
    )

    assert (
        m["runtime"]["providers"] is False
        and m["runtime"]["financial_writers"] is False
    )
    assert m["runtime"]["workspace_fallback"] is False
    assert (
        package["financial_startup_authorized"] is False
        and package["providers_authorized"] is False
    )
    assert package["limits"] == {
        "application_seconds": 120,
        "complete_stop_seconds": 8,
        "readiness_seconds": 180,
        "record_bytes": 65536,
        "selection_records": 128,
        "total_attempted_requests": 96,
    }
    result["resource_plan"] = {
        "maximum_seconds": 600,
        "maximum_entries": 8192,
        "maximum_bytes": 67108864,
        "existing_support_entries": 20,
        "selector_records_budgeted": 2,
        "selector_alias_entries": 4,
        "planned_new_entry_upper_bound": 4,
        "planned_accounted_byte_upper_bound": 4 * 65536 + 4 * 4096,
        "free_bytes": shutil.disk_usage(r"D:\AtlasRuntime").free,
        "global_execution_deadline_required": True,
    }
    assert (
        result["resource_plan"]["planned_accounted_byte_upper_bound"]
        < m["limits"]["bytes"]
    )
    assert result["resource_plan"]["free_bytes"] > m["limits"]["bytes"]
    passed(
        "EXACT_RESOURCE_LIMITS_STORAGE_HEADROOM_AND_PROVIDER_FINANCIAL_DISABLED_CONTRACTS",
        **result["resource_plan"],
    )

    # Existence/identity recheck only; never repair, adopt or select anything.
    existing_receipt = verify_deployment(
        m,
        expected_receipt_sha256="01bb0f6efb04c706e594acb8c63759ee682e4bce2f2062882015edff36d6ce91",
    )
    with held(w.WindowsOutput(r"D:\AtlasRuntime")) as again:
        assert (
            identity(w, again.root_handle) == result["private_parent_native_identity"]
        )
    assert not again.handles
    result.update(accepted=True, operational_mutations=0)
except Exception as exc:  # noqa: BLE001 - preserve refusal evidence and run exact owned cleanup.
    result.update(error_type=type(exc).__name__, error=str(exc))
    print("REFUSED", type(exc).__name__, str(exc), flush=True)
finally:
    result["elapsed_seconds"] = time.perf_counter() - started
    (e / "native-preflight-result.json").write_text(json.dumps(result, indent=2))
    print(
        json.dumps(
            {
                "accepted": result["accepted"],
                "checks_passed": len(result["checks"]),
                "elapsed_seconds": result["elapsed_seconds"],
                "error": result.get("error"),
            }
        ),
        flush=True,
    )
sys.exit(0 if result["accepted"] else 2)
