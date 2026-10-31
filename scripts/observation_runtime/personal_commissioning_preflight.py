"""Read-only commissioning preflight for the personal Quality Dips PAPER pilot.

This module never creates activation records, financial accounts, sessions,
provider connections, or trading orders.
"""

import argparse
import json
import ntpath
import re
import subprocess
from pathlib import Path

EXPECTED_BRANCH = "chatgpt/atlas-rebuild-v1"
PROFILE = "PERSONAL_PAPER"


def check(name, passed, detail):
    return {
        "check": name,
        "status": "PASS" if passed else "BLOCKED",
        "detail": detail,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--expected-source", help="Explicit reviewed 40-character source commit")
    parser.add_argument("--activation-root", help="Explicit existing personal activation child; never created")
    args = parser.parse_args()
    if args.expected_source is not None and not re.fullmatch('[0-9a-f]{40}', args.expected_source):
        parser.error('Expected source must be an explicit full commit SHA')
    if args.activation_root is not None and (
            ntpath.normpath(args.activation_root) != args.activation_root
            or not ntpath.normcase(args.activation_root).startswith('d:\\atlascustody\\personalpaper\\')
            or any(c in args.activation_root[3:] for c in (':', '%', '\x00', '/'))):
        parser.error('Activation root must be an exact D: personal custody child')

    root = Path(__file__).resolve().parents[2]

    def git(*arguments):
        return subprocess.check_output(
            ["git", *arguments],
            cwd=root,
            text=True,
        ).strip()

    results = []

    branch = git("branch", "--show-current")
    commit = git("rev-parse", "HEAD")

    results.append(check(
        "SOURCE_BRANCH",
        branch == EXPECTED_BRANCH,
        branch,
    ))

    results.append(check(
        "SOURCE_CHECKPOINT",
        args.expected_source is not None and commit == args.expected_source,
        commit if args.expected_source is not None else "Explicit reviewed source identity required",
    ))
    changes = git('status', '--porcelain', '--untracked-files=no')
    results.append(check('TRACKED_SOURCE_UNCHANGED', not changes,
                         'Tracked changes present' if changes else 'Tracked source matches commit'))

    scope_path = (
        root
        / "docs"
        / "QD_COMMISSIONING_OPERATOR_SCOPE_2026-10-27.json"
    )

    scope = json.loads(scope_path.read_text(encoding="utf-8-sig"))

    results.append(check(
        "OPERATOR_SCOPE",
        scope.get("status")
        == "APPROVED_PARTIALLY_EXECUTED_PAUSED_BEFORE_INCEPTION",
        scope.get("status"),
    ))

    release_root = Path(
        "D:/AtlasRuntime/releases/"
        "fca29cfe7760a28d2569b8b4b91ed1ea99804c3c"
    )

    results.append(check(
        "EXISTING_IMMUTABLE_RELEASE",
        release_root.is_dir(),
        str(release_root),
    ))

    activation_root = Path("D:/AtlasCustody/PersonalPaper")

    results.append(check(
        "ACTIVATION_ROOT",
        activation_root.is_dir(),
        str(activation_root),
    ))

    activation_record = Path(args.activation_root)/'activation.json' if args.activation_root else None

    results.append(check(
        "ACTIVATION_RECORD_PRESENT",
        activation_record is not None and activation_record.is_file(),
        "Existing-only activation record; presence is not verification",
    ))

    results.append(check(
        "ACTIVATION_NATIVE_VERIFIED",
        False,
        "Requires NativePersonalActivationReader with verified root identity "
        "and bound file digest; no fallback authorization",
    ))

    results.append(check(
        "FINANCIAL_INCEPTION",
        scope.get("financial_publication_attempted") is True,
        "Requires independent native financial readback",
    ))

    results.append(check(
        "RUNTIME_AUTHORIZATION",
        scope.get("runtime_consumable") is True,
        "Requires accepted installed runtime dependencies",
    ))

    passed = all(item["status"] == "PASS" for item in results)

    report = {
        "schema": "ATLAS_QD_COMMISSIONING_PREFLIGHT_V1",
        "profile": PROFILE,
        "status": "PASS" if passed else "BLOCKED",
        "checks": results,
        "financial_mutations": False,
        "live_orders": False,
        "pilot_started": False,
    }

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print("\n=== ATLAS PERSONAL PAPER PREFLIGHT ===")
        for item in results:
            print(
                f"{item['status']:7} "
                f"{item['check']}: {item['detail']}"
            )
        print(f"\nFINAL STATUS: {report['status']}")

    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
