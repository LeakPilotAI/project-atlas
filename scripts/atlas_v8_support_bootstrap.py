"""One-shot V8 nonfinancial support bootstrap; never selects or starts PAPER.

Only the reviewed support_deployment.py adapter is loaded from workspace.
All application imports come from the already verified installed V8 Python.
No workspace application import fallback; no Windows Time UTC fallback.
"""
import argparse
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path

REPO = Path(r"D:\Work\Project Atlas")
V8 = "c8cc4846508b29483d10a0b4c4353f8a26f1fc9c"
V7 = "af96bec0484a8e43f9965610e071a907a0d316bf"
APP = Path(r"D:\AtlasRuntime\releases") / V8
PROPOSAL = REPO / "docs/ATLAS_V8_NONFINANCIAL_SUPPORT_INSTALL_R2_2026-11-08.json"
SOURCE = REPO / "scripts/support_deployment.py"
MANIFEST = REPO / "logs/diagnostics/atlas-v8-ntp-support-offline-proposal-20261108-r11/deployment.json"
ARCHIVE = MANIFEST.parent / "support-source.zip"
RECEIPT = REPO / "logs/diagnostics" / ("qd-unselected-release-" + V8 + ".json")
SELECTOR = Path(r"D:\AtlasRuntime\selection")
HEAD = "933482b46a31af43270a193a94a83353e945fbecc4eb4661e8b7f8e9c8262997"
NTP_ORIGIN = "230a35d8b293be0d38ded533bb964d36bc5bf3c80d432a85656bc4c22650979c"
OPERATOR_SOURCE = "ded15bde4e2b3ce845b2eaf95818b6c81fb3b759daf2b9375a68533710599e8d"
MANIFEST_SHA = "13fbcf6b90cf1c2e6f5aa74aa60a057f6865d52097916db4d6e03669275eab86"
ARCHIVE_SHA = "77ed856d98f0fec39cc45280c35299c38147014aae933adbf6e5f7f3e0dae76d"
SUPPORT_SHA = "808a7994ec644f596aa7214c281c557862d10b1ad571a6632d3c0c67d426ede8"
RECEIPT_SHA = "ecb94e00e262e371caea494b1cc552352c892fa437a3b5f4946b54f7f863ae34"
ARTIFACT = "65c4b4661ec6aef7359e9dae716a416327379f5082a5b309ccdb5a148a569c95"
PARENTS = {
    r"D:\AtlasRuntime\launchers": [4004218753, 327680, 1532783],
    r"D:\AtlasRuntime\support-installations": [4004218753, 327680, 1532784],
    r"D:\AtlasRuntime\selection": [4004218753, 65536, 1532785],
}
BASE_ID = [4004218753, 65536, 1113770]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def require(condition, code):
    if not condition:
        raise ValueError(code)


def admit_proposal(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review-proposal", required=True)
    parser.add_argument("--proposal-sha256", required=True)
    parser.add_argument("--execute-code-only", action="store_true")
    a = parser.parse_args(argv)
    require(Path(a.review_proposal).absolute() == PROPOSAL,
            "V8_EXACT_BOOTSTRAP_PROPOSAL_REQUIRED")
    raw = PROPOSAL.read_bytes()
    require(sha(raw.replace(b"\r\n", b"\n")) == a.proposal_sha256,
            "V8_BOOTSTRAP_PROPOSAL_HASH_MISMATCH")
    p = json.loads(raw)
    require(type(p) is dict and set(p) == {
        "schema", "bootstrap_sha256", "support_source_sha256",
        "manifest_sha256", "archive_sha256", "application_receipt_sha256",
        "application_artifact_digest", "native_base_id", "native_parents",
        "selected_head", "selected_release", "target_release",
        "selected", "paper_startup", "financial_authority",
        "provider_connections", "allow_install", "allow_selection"
    }, "V8_BOOTSTRAP_EXACT_PROPOSAL_SCHEMA_REQUIRED")
    require(p["schema"] == "ATLAS_V8_NONFINANCIAL_SUPPORT_BOOTSTRAP_R1"
            and p["target_release"] == V8 and p["selected_release"] == V7
            and p["selected_head"] == HEAD
            and p["bootstrap_sha256"] == sha(Path(__file__).read_bytes().replace(b"\r\n", b"\n"))
            and p["manifest_sha256"] == MANIFEST_SHA
            and p["support_source_sha256"] == SUPPORT_SHA
            and p["archive_sha256"] == ARCHIVE_SHA
            and p["application_receipt_sha256"] == RECEIPT_SHA
            and p["application_artifact_digest"] == ARTIFACT
            and p["native_base_id"] == BASE_ID and p["native_parents"] == PARENTS
            and p["selected"] is False and p["paper_startup"] is False
            and p["financial_authority"] is False and p["provider_connections"] is False
            and p["allow_install"] is True and p["allow_selection"] is False,
            "V8_BOOTSTRAP_EXACT_NONFINANCIAL_SCOPE_REQUIRED")
    return a, p


def require_installed_interpreter():
    require(sys.flags.isolated and sys.flags.no_site
            and sys.flags.dont_write_bytecode and sys.dont_write_bytecode
            and Path(sys.executable) == APP / "python/python.exe"
            and Path(sys.base_prefix) == APP / "python",
            "V8_INSTALLED_ISOLATED_PYTHON_REQUIRED")
    require(all(Path(x).is_absolute() and Path(x).resolve().is_relative_to(APP)
                for x in sys.path if x), "V8_FOREIGN_PYTHON_IMPORT_PATH_REFUSED")
    sys.path[:0] = [str(APP / "backend"), str(APP), str(APP / "python/Lib/site-packages")]


def load_reviewed_support(p, manifest):
    # Deliberate single trusted adapter exception: no other workspace import.
    raw = SOURCE.read_bytes()
    require(sha(raw.replace(b"\r\n", b"\n")) == p["support_source_sha256"],
            "V8_BOOTSTRAP_REVIEWED_ADAPTER_CHANGED")
    with zipfile.ZipFile(ARCHIVE) as z:
        row = next(x for x in manifest["files"]
                   if x["path"] == "scripts/support_deployment.py")
        require(sha(z.read(row["path"])) == p["support_source_sha256"]
                and sha(raw.replace(b"\r\n", b"\n")) == row["sha256"],
                "V8_BOOTSTRAP_ARCHIVED_ADAPTER_MISMATCH")
    spec = importlib.util.spec_from_file_location("scripts.support_deployment", SOURCE)
    require(spec is not None and spec.loader is not None,
            "V8_BOOTSTRAP_ADAPTER_LOADER_UNAVAILABLE")
    loaded = importlib.util.module_from_spec(spec)
    sys.modules["scripts.support_deployment"] = loaded
    spec.loader.exec_module(loaded)
    require(Path(loaded.__file__).absolute() == SOURCE,
            "V8_BOOTSTRAP_ADAPTER_SOURCE_CHANGED")
    return loaded


def verify_native_roots(support):
    from scripts.volume_inspector import windows_output as win
    from scripts.release_selection import digest
    from scripts.release_selection_store import NativeSelectionStore
    with support.held(win.WindowsOutput(r"D:\AtlasRuntime")) as out:
        require(support.identity(win, out.root_handle) == BASE_ID,
                "V8_NATIVE_PARENT_IDENTITY_CHANGED")
    for path, expected in PARENTS.items():
        with support.held(win.WindowsOutput(path)) as out:
            require(support.identity(win, out.root_handle) == expected,
                    "V8_SUPPORT_PARENT_IDENTITY_CHANGED")
    store = NativeSelectionStore(root=str(SELECTOR),
                                 native_root=PARENTS[str(SELECTOR)])
    try:
        with store.locked():
            history = store.records()
            require(len(history) == 11 and history[-1]["revision"] == 11
                    and digest(history[-1]) == HEAD
                    and history[-1]["selected"]["release"] == V7,
                    "V8_V7_NATIVE_SELECTION_HISTORY_CHANGED")
    finally:
        store.close()
    require(not os.path.lexists(SELECTOR / "r0012.json"),
            "V8_SELECTION_R12_ALREADY_EXISTS")


def preflight(p):
    require_installed_interpreter()
    require(sha(RECEIPT.read_bytes()) == RECEIPT_SHA,
            "V8_INSTALLED_APP_RECEIPT_CHANGED")
    receipt = json.loads(RECEIPT.read_bytes())
    require(receipt["source_commit"] == V8
            and receipt["artifact_digest"] == ARTIFACT
            and all(receipt[key] is False for key in (
                "selected", "financial_effects", "provider_connections",
                "operational_acceptance")),
            "V8_INSTALLED_APPLICATION_FINANCIAL_BOUNDARY_REFUSED")
    require(sha(MANIFEST.read_bytes().replace(b"\r\n", b"\n")) == MANIFEST_SHA,
            "V8_SUPPORT_MANIFEST_CHANGED")
    require(sha(ARCHIVE.read_bytes()) == ARCHIVE_SHA,
            "V8_SUPPORT_ARCHIVE_CHANGED")
    import scripts
    from scripts.release_selection import encoded
    manifest = json.loads(MANIFEST.read_bytes())
    require(sha(encoded(manifest)) == MANIFEST_SHA
            and manifest["application"]["release"] == V8
            and manifest["application"]["artifact_digest"] == ARTIFACT
            and manifest["application"]["receipt_sha256"] == RECEIPT_SHA
            and manifest["accepted_parents"] == PARENTS
            and manifest["runtime"]["python"] == str(APP / "python/python.exe")
            and manifest["runtime"]["providers"] is False
            and manifest["runtime"]["financial_writers"] is False,
            "V8_SUPPORT_MANIFEST_APP_BINDING_REFUSED")
    require(all(not os.path.lexists(Path(manifest[key]))
                for key in ("destination", "control")),
            "V8_SUPPORT_ALREADY_INSTALLED_OR_PARTIAL_NO_RETRY")
    support = load_reviewed_support(p, manifest)
    require(support.support_clock_profile(manifest) == support.V7_NTP_CLOCK_PROFILE,
            "V8_SUPPORT_OLD_WINDOWS_CLOCK_REJECTED")
    support.prepare(manifest, ARCHIVE, MANIFEST_SHA)
    verify_native_roots(support)
    return support, manifest


def main(argv=None):
    a, p = admit_proposal(argv)
    support, manifest = preflight(p)
    if not a.execute_code_only:
        print(json.dumps({"status": "V8_REVIEW_ONLY_PASS", "installed": False,
                          "selected": False, "financial_authority": False}))
        return
    require(subprocess.check_output(["git", "status", "--porcelain",
                                     "--untracked-files=no"], cwd=REPO) == b"",
            "V8_SUPPORT_BOOTSTRAP_TRACKED_WORKTREE_NOT_CLEAN")
    from scripts.observation_runtime.atlas_independent_ntp_clock import (
        IndependentNtpClock,
    )
    clock = IndependentNtpClock(runtime_id="qd-support-deployment-" + MANIFEST_SHA)
    try:
        support, manifest = preflight(p)
        result = support.install_operational(
            approved=True, manifest=manifest, archive=ARCHIVE,
            manifest_sha256=MANIFEST_SHA, parent_identity=BASE_ID, clock=clock)
        require(result["handles_after_close"] == 0
                and result["receipt"]["selected"] is False
                and result["receipt"]["financial_actions"] == 0,
                "V8_SUPPORT_INSTALL_FINANCIAL_OR_HANDLE_REFUSED")
        verify_native_roots(support)
        print(json.dumps({
            "status": "V8_NONFINANCIAL_SUPPORT_INSTALLED_UNSELECTED",
            "receipt_sha256": result["receipt_sha256"],
            "support_manifest_sha256": MANIFEST_SHA,
            "source_release": V8, "native_handles_after_close": 0,
            "selected": False, "financial_authority": False,
            "providers": False,
        }, sort_keys=True), flush=True)
    finally:
        clock.revoke()


if __name__ == "__main__":
    main()
