"""Offline release-clock admission; no selector, provider, or financial writes.

A candidate with an embedded operator clock must bind to that candidate's own
release identity. This check deliberately refuses current V8's hardcoded clock
when that source is repackaged under another immutable release commit.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

CLOCK_PATH = "scripts/observation_runtime/personal_v8_operator_clock.py"
HEX40 = re.compile(r"[0-9a-f]{40}\Z")
HEX64 = re.compile(r"[0-9a-f]{64}\Z")


def clock_constants(source: str) -> dict[str, str]:
    tree = ast.parse(source)
    values = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if isinstance(target, ast.Name) and target.id in {"APP", "ARTIFACT", "APP_RECEIPT", "PROFILE"}:
                if not isinstance(node.value, ast.Constant) or type(node.value.value) is not str:
                    raise ValueError("CLOCK_ADMISSION_DYNAMIC_IDENTITY_REFUSED")
                values[target.id] = node.value.value
    if set(values) != {"APP", "ARTIFACT", "APP_RECEIPT", "PROFILE"}:
        raise ValueError("CLOCK_ADMISSION_MISSING_IDENTITY")
    if (not HEX40.fullmatch(values["APP"]) or not HEX64.fullmatch(values["ARTIFACT"])
            or not HEX64.fullmatch(values["APP_RECEIPT"])):
        raise ValueError("CLOCK_ADMISSION_MALFORMED_IDENTITY")
    return values


def require_candidate_clock_identity(*, source: str, candidate_commit: str,
                                     artifact_digest: str, receipt_sha256: str) -> dict[str, str]:
    """Refuse cross-version clock bindings before installation or selection.

    This is necessary, not sufficient, for native release authorization: full
    manifest hashes, source inventory, receipt and clock ownership must also pass.
    """
    if (type(candidate_commit) is not str or not HEX40.fullmatch(candidate_commit)
            or type(artifact_digest) is not str or not HEX64.fullmatch(artifact_digest)
            or type(receipt_sha256) is not str or not HEX64.fullmatch(receipt_sha256)):
        raise ValueError("CLOCK_ADMISSION_INVALID_CANDIDATE")
    values = clock_constants(source)
    if (values["APP"] != candidate_commit or values["ARTIFACT"] != artifact_digest
            or values["APP_RECEIPT"] != receipt_sha256):
        raise ValueError("CLOCK_ADMISSION_RELEASE_IDENTITY_MISMATCH")
    return values


def verify_source_file(*, path: Path, candidate_commit: str,
                       artifact_digest: str, receipt_sha256: str) -> dict[str, str]:
    return require_candidate_clock_identity(
        source=path.read_text(encoding="utf-8"), candidate_commit=candidate_commit,
        artifact_digest=artifact_digest, receipt_sha256=receipt_sha256)
