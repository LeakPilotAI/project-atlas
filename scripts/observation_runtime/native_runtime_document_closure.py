"""Detect the *source-code referenced* runtime documents missing from native code releases.

No publication or permissions. A historical operator-input path that is not
Git-tracked MUST NEVER be manufactured or bundled as consent. Native releases
need their pinned policy/old-account documents on disk for read-only selected
financial draft inspection; the prior R19 code-only selection omitted them.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

from scripts.build_release_candidate import source_bytes, source_path

SCHEMA = "ATLAS_NATIVE_SELECTED_SOURCE_REFERENCED_DOC_CLOSURE_V1"
SOURCE_ROOTS = ("backend/app/", "scripts/", "frontend/offline/")
EXPLICIT_UNAVAILABLE_OPERATOR_INPUT = (
    "docs/PERSONAL_NATIVE_COMPATIBILITY_OPERATOR_APPROVAL_V5.json"
)
REFERENCE = re.compile(rb"docs/[A-Za-z0-9_./-]+(?:\.json|\.md|\.txt)", re.IGNORECASE)
MAX_REFERENCES = 100
MAX_DOC_BYTES = 12 * 1024 * 1024
MAX_SINGLE_DOC = 1024 * 1024


class NativeRuntimeDocumentClosureRefused(ValueError):
    """The selected source contains an unverified runtime document reference."""


def required_runtime_documents(root, *, selected, tracked):
    """Pure inventory: 28 historical tracked docs + missing operator exception.

    The caller independently pins the containing source Git revision, immutable
    archive, exact file identities and original financial activation. This
    output grants no financial permission; it only prevents broken releases.
    """
    root = Path(root)
    if (type(selected) not in (set, list, tuple)
            or type(tracked) not in (set, list, tuple)
            or any(type(x) is not str or not x.startswith(SOURCE_ROOTS)
                   for x in selected)
            or any(type(x) is not str for x in tracked)):
        raise NativeRuntimeDocumentClosureRefused(
            "NATIVE_RUNTIME_DOCUMENT_SELECTED_TRACKED_SCOPE_REQUIRED")
    files = set(selected)
    known = set(tracked)
    found: set[str] = set()
    try:
        for name in sorted(files):
            source_path(root, name)
            if Path(name).suffix.lower() not in (".py", ".js", ".cjs", ".mjs"):
                continue
            content = source_bytes(root, name, maximum_bytes=16*1024*1024)
            found.update(item.decode("ascii") for item in REFERENCE.findall(content))
    except (ValueError, OSError, UnicodeError) as exc:
        raise NativeRuntimeDocumentClosureRefused(
            "NATIVE_RUNTIME_DOCUMENT_SOURCE_UNVERIFIABLE") from exc
    if not 0 < len(found) <= MAX_REFERENCES:
        raise NativeRuntimeDocumentClosureRefused(
            "NATIVE_RUNTIME_DOCUMENT_REFERENCE_BOUND_REFUSED")
    missing = found - known
    if missing - {EXPLICIT_UNAVAILABLE_OPERATOR_INPUT}:
        raise NativeRuntimeDocumentClosureRefused(
            "NATIVE_RUNTIME_DOCUMENT_UNTRACKED_NEW_REQUIRED_INPUT_REFUSED")
    resources = sorted(found & known)
    total = 0
    for name in resources:
        if Path(name).suffix.lower() not in (".json", ".md", ".txt"):
            raise NativeRuntimeDocumentClosureRefused(
                "NATIVE_RUNTIME_DOCUMENT_FILE_TYPE_REFUSED")
        source_path(root, name)
        raw = source_bytes(root, name, maximum_bytes=MAX_SINGLE_DOC)
        total += len(raw)
        if total > MAX_DOC_BYTES:
            raise NativeRuntimeDocumentClosureRefused(
                "NATIVE_RUNTIME_DOCUMENT_TOTAL_BYTES_REFUSED")
    return {
        "schema": SCHEMA,
        "tracked_runtime_document_paths": resources,
        "tracked_runtime_document_count": len(resources),
        "total_runtime_document_bytes": total,
        "missing_independent_operator_approval_input":
            sorted(missing),
        "missing_operator_input_must_not_be_packaged":
            missing == {EXPLICIT_UNAVAILABLE_OPERATOR_INPUT},
        "untrusted_external_issuer_invented": False,
        "financial_accounts_created": False,
        "paper_start_authorized": False,
        "live_orders_authorized": False,
    }


def tracked_selected(root, *, original_source):
    """Git-tracked current source union genuine prior frozen source inventory."""
    root = Path(root)
    def git(*arguments):
        return subprocess.check_output(
            ["git", *arguments], cwd=root, text=True, encoding="utf-8"
        ).splitlines()
    before = set(original_source)
    changed = set(git("diff", "--name-only", "3de954bcfd8533bfaaf32f62745d912a24a71cfc", "HEAD",
                      "--", "backend/app/", "scripts/", "tests/", "frontend/offline/", "docs/"))
    tracked = set(git("ls-files", "--", "backend/app/", "scripts/", "tests/",
                      "frontend/offline/", "docs/"))
    selected = before | changed
    return selected, tracked
