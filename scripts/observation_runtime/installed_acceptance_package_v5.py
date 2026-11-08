"""Exact V5 review constraints; never execution or financial authority."""

from copy import deepcopy

from scripts.observation_runtime.installed_acceptance_package import (
    validate_scope as v4_review,
)

ROOT = r"D:\Work\Project Atlas\logs\diagnostics\qd-final-installed-nonfinancial-acceptance-v5-20261103"
PUBLIC = "docs/QD_FINAL_INSTALLED_NONFINANCIAL_ACCEPTANCE_SCOPE_V5_2026-11-03.json"
CONTRACT = {
    "outer_owner": "PINNED_POWERSHELL_RETAINED_CREATEPROCESS_HANDLE",
    "worker_topology": "DIRECT_DETACHED_NO_UNCLAIMED_REDIRECTOR",
    "parent_and_launch_handles": "DUPLICATED_WHILE_SUSPENDED_ORIGINAL_OWNER_RETAINS_HANDLES",
    "job_handle": "ONLY_PARENT_RETAINS_JOB_HANDLE_NATIVE_QUERY_REPLIES_BOUND_TO_LIVE_PARENT",
    "role_validation": "EXACT_IMAGE_ID_HASH_COMMAND_PARENT_CREATION_HANDLES_AND_COMPLETE_JOB",
    "query_reply_maximum_age_ms": 500,
    "query_reply_timeout_seconds": 2,
    "failed_observation": "LATCH_REFUSAL_NO_AUTOMATIC_ADOPTION_OR_RETRY",
    "console_terminal_code": 109,
    "unknown_processes": "REFUSE_NEVER_COMMAND_SUBSTRING_ALLOWLIST",
    "short_diagnostics": "PINNED_REQUEST_ORIGINAL_POPEN_HANDLE_NATIVE_CREATION_EXIT_AND_EMPTY_JOB_AFTER_RETURN",
}


def validate_scope(scope):
    if (
        type(scope) is not dict
        or scope.get("schema") != "QD_FINAL_INSTALLED_NONFINANCIAL_ACCEPTANCE_SCOPE_V5"
    ):
        raise ValueError("EXACT_V5_SCOPE_REQUIRED")
    if (
        scope.get("evidence_root") != ROOT
        or scope.get("public_scope_document") != PUBLIC
    ):
        raise ValueError("EXACT_V5_PATHS_REQUIRED")
    base = deepcopy(scope)
    base.update(
        schema="QD_FINAL_INSTALLED_NONFINANCIAL_ACCEPTANCE_SCOPE_V4",
        evidence_root=r"D:\Work\Project Atlas\logs\diagnostics\qd-final-installed-nonfinancial-acceptance-v4-20261103",
        public_scope_document="docs/QD_FINAL_INSTALLED_NONFINANCIAL_ACCEPTANCE_SCOPE_V4_2026-11-03.json",
    )
    v4_review(base)
    if scope.get("ownership", {}).get("contract") != CONTRACT:
        raise ValueError("EXACT_V5_RETAINED_OWNERSHIP_CONTRACT_REQUIRED")
    if (
        scope["ownership"].get("console_command")
        != r"\??\C:\WINDOWS\system32\conhost.exe 0x4"
    ):
        raise ValueError("EXACT_CONSOLE_COMMAND_REQUIRED")
    diagnostics = scope["ownership"].get("diagnostic_images", {})
    if (
        set(diagnostics) != {"netstat"}
        or diagnostics["netstat"].get("path") != r"C:\Windows\System32\netstat.exe"
    ):
        raise ValueError("EXACT_DIAGNOSTIC_BINARY_REQUIRED")
    images = scope["ownership"].get("images", {})
    if set(images) != {"observer", "powershell", "installed_python", "console"}:
        raise ValueError("COMPLETE_V5_IMAGE_PINS_REQUIRED")
    import re

    for row in [*images.values(), *diagnostics.values()]:
        if (
            set(row) != {"path", "id", "sha256"}
            or type(row["id"]) is not list
            or len(row["id"]) != 3
            or any(type(n) is not int or not 0 <= n <= 0xFFFFFFFF for n in row["id"])
            or not re.fullmatch("[0-9a-f]{64}", row["sha256"])
        ):
            raise ValueError("EXACT_NATIVE_IMAGE_PIN_REQUIRED")
    if (
        images["observer"]["path"]
        != r"C:\Users\renal\AppData\Local\Programs\Python\Python312\python.exe"
        or images["powershell"]["path"]
        != r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
        or images["installed_python"]["path"]
        != scope["application"]["root"] + r"\python\python.exe"
        or images["console"]["path"] != r"C:\Windows\System32\conhost.exe"
    ):
        raise ValueError("EXACT_OWNER_AND_INSTALLED_IMAGE_PATHS_REQUIRED")
    expected = [
        ROOT
        + r"\<exact-owned diagnostics, temp/cache, logs, browser/Stop receipts, launch and Job-query packets>",
        *[
            rf"D:\AtlasRuntime\selection\r{n:04d}.{suffix}"
            for n in (7, 8)
            for suffix in ("pending", "json")
        ],
        "Repository checkpoint/report updates and non-force Git commit/push",
    ]
    if scope.get("allowed_mutations") != expected:
        raise ValueError("EXACT_FOUR_SELECTOR_NAMES_AND_OWNED_EVIDENCE_ONLY")
    return scope
