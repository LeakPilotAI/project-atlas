"""Exact V5 package pins and grant arguments. No native effect on import."""

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(r"D:\Work\Project Atlas")
ROOT = Path(__file__).parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

sys.path[:0] = [str(REPO / "backend"), str(REPO / "backend/.venv/Lib/site-packages")]
from scripts.observation_runtime.installed_acceptance_package_v5 import (
    validate_scope as review_scope,
)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def verify_sources(manifest, repo=REPO):
    paths = [row["path"] for row in manifest["files"]]
    if len(paths) != len(set(paths)):
        raise ValueError("DUPLICATE_SOURCE_PIN")
    for row in manifest["files"]:
        file = repo / row["path"]
        if not file.resolve().is_relative_to(repo.resolve()):
            raise ValueError("SOURCE_SCOPE_ESCAPE")
        if any(p.is_symlink() or p.is_junction() for p in [file, *file.parents]):
            raise ValueError("SOURCE_REPARSE_REFUSAL")
        raw = file.read_bytes()
        if len(raw) != row["bytes"] or hashlib.sha256(raw).hexdigest() != row["sha256"]:
            raise ValueError("SOURCE_PIN_DRIFT")


def validate_scope(scope_sha256, approved_checkpoint):
    if not re.fullmatch("[0-9a-f]{64}", scope_sha256) or not re.fullmatch(
        "[0-9a-f]{40}", approved_checkpoint
    ):
        raise ValueError("EXACT_EXPLICIT_APPROVAL_ARGUMENTS_REQUIRED")
    proposal = json.loads((ROOT / "proposal.json").read_bytes())
    if hashlib.sha256(canonical(proposal)).hexdigest() != scope_sha256:
        raise ValueError("APPROVED_SCOPE_HASH_MISMATCH")
    public = json.loads((REPO / proposal["public_scope_document"]).read_bytes())
    if canonical(public) != canonical(proposal):
        raise ValueError("PUBLIC_SCOPE_MISMATCH")
    review_scope(proposal)
    if proposal["evidence_root"] != str(ROOT):
        raise ValueError("EXACT_EVIDENCE_ROOT_REQUIRED")
    if (
        subprocess.check_output(["git", "branch", "--show-current"], cwd=REPO)
        .decode()
        .strip()
        != proposal["branch"]
    ):
        raise ValueError("APPROVED_BRANCH_REQUIRED")
    if (
        subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO).decode().strip()
        != approved_checkpoint
    ):
        raise ValueError("APPROVED_CHECKPOINT_MISMATCH")
    subprocess.run(
        [
            "git",
            "merge-base",
            "--is-ancestor",
            proposal["starting_checkpoint"],
            approved_checkpoint,
        ],
        cwd=REPO,
        check=True,
    )
    raw = (ROOT / "source-manifest.json").read_bytes()
    if hashlib.sha256(raw).hexdigest() != proposal["source_manifest_sha256"]:
        raise ValueError("SOURCE_MANIFEST_HASH_MISMATCH")
    manifest = json.loads(raw)
    if (
        len(manifest["files"]) != proposal["source_files"]
        or manifest["schema"] != "QD_FINAL_INSTALLED_ACCEPTANCE_SOURCE_MANIFEST_V5"
    ):
        raise ValueError("EXACT_V5_MANIFEST_COUNT_REQUIRED")
    verify_sources(manifest)
    return proposal


if __name__ == "__main__":
    if len(sys.argv) != 4 or sys.argv[1] != "--verify-only":
        raise SystemExit("V5_REVIEW_ONLY_NO_NATIVE_ACTION")
    sys.stdout = (ROOT / "gate-stdout.log").open("x", buffering=1)
    sys.stderr = (ROOT / "gate-stderr.log").open("x", buffering=1)
    validate_scope(sys.argv[2], sys.argv[3])
    print("V5_EXACT_SCOPE_SOURCE_AND_GIT_VERIFIED_NO_EXECUTION_AUTHORITY")
