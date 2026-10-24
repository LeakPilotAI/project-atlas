"""Explicitly confined disposable D1 runner; never an operational authority."""
import argparse
import hashlib
import json
import os
import platform
import stat
import sys
from pathlib import Path


def confined_root(value, financial=False):
    root = Path(value)
    parent = Path(__file__).resolve().parents[2] / "logs" / "diagnostics"
    if not root.is_absolute() or root.parent != parent or not root.name.startswith("qd-d1-financial-records-" if financial else "qd-d1-native-acceptance-"):
        raise ValueError("Exact authorized disposable run root required")
    if any(part in (".", "..") for part in root.parts):
        raise ValueError("No traversal")
    for p in [*reversed(root.parents), root]:
        info = p.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise ValueError("Reparse ancestor refused")
    if not root.is_dir():
        raise ValueError("Pre-created exclusive directory required")
    return root


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", required=True)
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--financial", action="store_true")
    args = parser.parse_args()
    root = confined_root(args.run_root, args.financial)
    if not args.attempt.isalnum():
        raise ValueError("Opaque attempt identity required")
    identity = [root.stat().st_dev, root.stat().st_ino]
    marker = root / "root-identity.json"
    if marker.exists():
        if marker.is_symlink() or marker.stat().st_nlink != 1 or json.loads(marker.read_text(encoding="utf-8")) != identity:
            raise ValueError("Run root substitution refused")
    else:
        with marker.open("x", encoding="utf-8") as handle:
            json.dump(identity, handle)
    attempt = root / args.attempt
    attempt.mkdir()  # Never overwrite prior failure evidence.
    for name in ("TEMP", "TMP", "TMPDIR"):
        os.environ[name] = str(attempt)
    os.environ["ATLAS_D1_RUN_ROOT"] = str(root)
    os.environ["ATLAS_D1_ATTEMPT"] = str(attempt)
    os.environ["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    sys.dont_write_bytecode = True
    import pytest

    class Evidence:
        def __init__(self):
            self.cases = {}
            self.details = {}

        def pytest_runtest_logreport(self, report):
            if report.when == "call" or report.failed or report.skipped:
                self.cases[report.nodeid] = "FAIL" if report.failed else "NOT_EXECUTED" if report.skipped else "PASS"
                if report.failed or report.skipped:
                    self.details[report.nodeid] = str(report.longrepr)

    evidence = Evidence()
    repo = Path(__file__).resolve().parents[2]
    sources = [Path(__file__), repo / "tests/test_qd_d1_native_acceptance.py",
               repo / "tests/test_r7e47f_snapshot_store.py", repo / "scripts/volume_inspector/snapshot_store.py",
               repo / "scripts/volume_inspector/windows_output.py", repo / "scripts/volume_inspector/shared_fence.py",
               repo / "backend/app/services/paper_writer_fixture.py"]
    source_hashes = {str(p.relative_to(repo)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
    (attempt / "source-hashes.json").write_text(json.dumps(source_hashes, indent=2), encoding="utf-8")
    test_file = "tests/test_quality_dips_financial_records_native.py" if args.financial else "tests/test_qd_d1_native_acceptance.py"
    if args.financial:
        for relative in (test_file, "scripts/volume_inspector/financial_record_store.py",
                         "backend/app/services/paper_financial_replay.py", "backend/app/services/paper_financial_audit.py"):
            source_hashes[relative] = hashlib.sha256((repo / relative).read_bytes()).hexdigest()
        (attempt / "source-hashes.json").write_text(json.dumps(source_hashes, indent=2), encoding="utf-8")
    result = pytest.main([str(repo / test_file), "-q", "-p", "no:cacheprovider",
                          "--basetemp=" + str(attempt / "cases")], plugins=[evidence])
    observations = attempt / "observations.jsonl"
    helpers = [x for x in (json.loads(line) for line in observations.read_text(encoding="utf-8").splitlines()) if x["case"] == "helper"] if observations.exists() else []
    summary = {"plan_version": "FS2_NATIVE_V1" if args.financial else "QD_D1_NATIVE_V1", "platform": platform.platform(), "python": sys.version,
               "root_identity": identity, "source_hashes": source_hashes,
               "cases": evidence.cases, "details": evidence.details, "pytest_exit": int(result),
               "counts": {s: list(evidence.cases.values()).count(s) for s in ("PASS", "FAIL", "BLOCKED", "NOT_EXECUTED")},
               "helpers": helpers, "cleanup": "Test artifacts retained; no deletion or forced process termination; helper outcomes individually recorded",
               "operational_acceptance": False}
    (attempt / "evidence.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    if confined_root(str(root), args.financial).stat().st_ino != identity[1]:
        raise ValueError("Run identity changed")
    return result


if __name__ == "__main__":
    raise SystemExit(main())
