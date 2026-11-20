"""Current installed-native PAPER activation origin admission; no issuer/grant.

Always verify the code WHICH IS RUNNING, not a caller-selected digest, source
checkout, historical native receipt, HTTP login, or source-only artifact.
This is a prerequisite, never a financial writer lease or account permission.
"""
from __future__ import annotations

import ntpath
import os
import re
import sys
from pathlib import Path

from scripts.observation_runtime.personal_version_safe_release_clock import (
    CLOCK_RELATIVE,
    RELEASE_PARENT,
    SELECTOR_NATIVE,
    admit_version_safe_clock_source,
)

SCHEMA = "ATLAS_NATIVE_SELECTED_FINANCIAL_ACTIVATION_SOURCE_BINDING_V1"


def resolve_installed_activation_module(helper_module):
    """Bind a selected native helper to its exact installed activation sibling.

    Never present the origin-helper .py as the activation entrypoint. Both
    paths are checked against original installed Windows handles later.
    """
    if (not isinstance(helper_module, Path) or not helper_module.is_absolute()
            or helper_module.name != "personal_native_financial_release_origin.py"
            or helper_module.parent.name != "observation_runtime"
            or helper_module.parent.parent.name != "scripts"):
        raise ValueError("FINANCIAL_ACTIVATION_EXACT_ORIGIN_HELPER_REQUIRED")
    module = helper_module.with_name("personal_activation_commission.py")
    if module.parent != helper_module.parent:
        raise ValueError("FINANCIAL_ACTIVATION_ORIGIN_SIBLING_CHANGED")
    return module


def validate_origin(*, module_path, executable, selected, release_digest):
    """Pure fail-closed consistency check AFTER actual original-handle readback."""
    from scripts.release_selection import validate_spec

    if (not isinstance(module_path, Path) or not isinstance(executable, Path)
            or not module_path.is_absolute() or not executable.is_absolute()
            or module_path.name != "personal_activation_commission.py"
            or module_path.parent.name != "observation_runtime"
            or module_path.parent.parent.name != "scripts"
            or type(release_digest) is not str
            or re.fullmatch("[0-9a-f]{64}", release_digest) is None
            or type(selected) is not dict):
        raise ValueError("FINANCIAL_ACTIVATION_EXACT_NATIVE_CODE_ORIGIN_REQUIRED")
    release = module_path.parents[2]
    if (release.parent != RELEASE_PARENT
            or re.fullmatch("[0-9a-f]{40}", release.name) is None
            or module_path != release / "scripts/observation_runtime/personal_activation_commission.py"
            or ntpath.normcase(ntpath.normpath(str(executable))) !=
               ntpath.normcase(ntpath.normpath(str(release / "python/python.exe")))):
        raise ValueError("FINANCIAL_ACTIVATION_INSTALLED_SELECTED_PROCESS_ONLY")
    spec = validate_spec(selected, "WINDOWS_LOCAL")
    if (spec["release"] != release.name
            or Path(spec["root"]) != release
            or spec["artifact_digest"] != release_digest):
        raise ValueError("FINANCIAL_ACTIVATION_STALE_OR_FOREIGN_RELEASE_REFUSED")
    return {
        "schema": SCHEMA,
        "selected_code_release": release.name,
        "installed_source_and_process_path_bound": True,
        "selected_artifact_digest_bound": True,
        "financial_writer_lease_issued": False,
        "financial_activation_published": False,
        "paper_start_authorized": False,
        "live_trading_authorized": False,
    }


def require_selected_native_origin(*, release_digest):
    """Original native selector, installed file handles, running image, same release.

    An unselected host-workspace copy must refuse BEFORE reading operator
    activation files or opening any financial output. There is no network, NTP,
    credential, native account write, or provider call in this method.
    """
    if os.name != "nt":
        raise ValueError("FINANCIAL_ACTIVATION_NATIVE_WINDOWS_REQUIRED")
    helper = Path(__file__).absolute()
    module = resolve_installed_activation_module(helper)
    release = helper.parents[2]
    if (release.parent != RELEASE_PARENT
            or not helper.is_file() or helper.is_symlink()
            or helper.is_junction()
            or not module.is_file() or module.is_symlink()
            or module.is_junction()
            or not (release / CLOCK_RELATIVE).is_file()):
        raise ValueError("FINANCIAL_ACTIVATION_SOURCE_MUST_BE_INSTALLED")
    from scripts.release_selection import NativeInstalledReleaseVerifier
    from scripts.release_selection_store import NativeSelectionStore

    store = NativeSelectionStore(
        root=r"D:\AtlasRuntime\selection", native_root=list(SELECTOR_NATIVE))
    try:
        with store.locked():
            _, spec = admit_version_safe_clock_source(
                source_file=release / CLOCK_RELATIVE,
                records=store.records(),
            )
            readback = validate_origin(
                module_path=module, executable=Path(sys.executable),
                selected=spec, release_digest=release_digest,
            )
            # This native verifier opens original installed Windows handles
            # for ALL declared native-release files; a JSON digest is insufficient.
            with NativeInstalledReleaseVerifier().open(spec) as installed:
                if (installed.get("source_commit") != release.name
                        or installed.get("artifact_digest") != release_digest
                        or installed.get("selected") is not False
                        or installed.get("financial_effects") is not False
                        or installed.get("operational_acceptance") is not False):
                    raise ValueError(
                        "FINANCIAL_ACTIVATION_ORIGINAL_INSTALLED_RELEASE_REFUSED")
        return readback
    finally:
        store.close()
