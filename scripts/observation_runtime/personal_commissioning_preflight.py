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
    parser.add_argument("--check-native-clock", action="store_true",
                        help="Perform a bounded read-only native clock probe; never grants runtime authority")
    parser.add_argument("--expected-source", help="Explicit reviewed 40-character source commit")
    parser.add_argument("--activation-root", help="Explicit existing personal activation child; never created")
    parser.add_argument("--activation-native-root", nargs=3, type=int, metavar=("VOL", "HIGH", "LOW"),
                        help="Independently recorded native root identity (3 integers)")
    parser.add_argument("--activation-binding-id", nargs=3, type=int, metavar=("VOL", "HIGH", "LOW"),
                        help="Independently recorded activation.json native file identity")
    parser.add_argument("--activation-binding-sha256",
                        help="Independently recorded SHA256 of bound activation.json")
    args = parser.parse_args()
    if args.expected_source is not None and not re.fullmatch('[0-9a-f]{40}', args.expected_source):
        parser.error('Expected source must be an explicit full commit SHA')
    if args.activation_root is not None and (
            ntpath.normpath(args.activation_root) != args.activation_root
            or not ntpath.normcase(args.activation_root).startswith('d:\\atlascustody\\personalpaper\\')
            or any(c in args.activation_root[3:] for c in (':', '%', '\x00', '/'))):
        parser.error('Activation root must be an exact D: personal custody child')

    supplied_binding = (args.activation_root, args.activation_native_root,
                        args.activation_binding_id, args.activation_binding_sha256)
    if any(value is not None for value in supplied_binding) and not all(
            value is not None for value in supplied_binding):
        parser.error("Native activation verification requires complete independent binding")

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

    # A pre-existing source directory is only a custody location, never an
    # accepted operational QD source publication. Native archive admission
    # requires the independently accepted enrollment/issuer/clock ports.
    source_parent = Path("D:/AtlasCustody/QualityDips")
    source_children = []
    if source_parent.is_dir() and not source_parent.is_symlink() and not source_parent.is_junction():
        source_children = [p.name for p in source_parent.iterdir()
                           if p.is_dir() and not p.is_symlink() and not p.is_junction()]
    results.append(check(
        "OPERATIONAL_QD_SOURCE_PUBLICATION",
        False,
        "Native Quality Dips custody alone is not an enrolled and independently "
        "authenticated current FORWARD_COLLECTION source publication",
    ))

    activation_root = Path("D:/AtlasCustody/PersonalPaper")

    # Inventory the actual installed roots, without treating a directory,
    # metadata flag, or unbound JSON file as operator authorization.
    from scripts.observation_runtime.personal_installation_preflight import (
        inspect_native_personal_installation,
    )
    native = inspect_native_personal_installation()
    results.append(check(
        "NATIVE_CUSTODY_PARENTS",
        native["custody_parent_exists"] and native["personal_parent_exists"],
        "Existing ordinary native custody directories required; no approval implied",
    ))

    results.append(check(
        "ACTIVATION_ROOT",
        activation_root.is_dir(),
        str(activation_root),
    ))

    activation_child = Path(args.activation_root) if args.activation_root else None
    activation_record = activation_child / 'activation.json' if activation_child else None
    # Presence must not follow a junction/symlink masquerading as a native
    # activation child or record. Native bound readback is still required.
    activation_child_ordinary = (activation_child is not None
                                 and activation_child.is_dir()
                                 and not activation_child.is_symlink()
                                 and not activation_child.is_junction())
    activation_record_ordinary = (activation_child_ordinary
                                  and activation_record.is_file()
                                  and not activation_record.is_symlink()
                                  and not activation_record.is_junction())
    results.append(check(
        "ACTIVATION_RECORD_PRESENT",
        activation_record_ordinary,
        "Existing ordinary native activation child and file required; "
        "presence is not verification",
    ))

    native_activation_verified = False
    activation_verification_reason = (
        "Requires independently supplied native root/file identities and SHA256; "
        "no fallback authorization")
    if activation_record_ordinary and all(value is not None for value in supplied_binding):
        from scripts.observation_runtime.personal_paper_activation import NativePersonalActivationReader
        try:
            reader = NativePersonalActivationReader(
                root=args.activation_root, native_root=args.activation_native_root,
                binding={"id": args.activation_binding_id,
                         "sha256": args.activation_binding_sha256})
            record = reader.read()  # Existing-only bound Windows read; no publication.
            # This verifies bound bytes only, not the separate operator SID,
            # policy, expiry, release, account and technical lease requirements.
            expected_fields = {"schema", "profile", "origin", "activation_id",
                               "operator_id", "policy_digest", "release_digest",
                               "accounts", "issued_at", "expires_at", "actions"}
            native_activation_verified = (
                type(record) is dict and set(record) == expected_fields
                and record["schema"] == "ATLAS_PERSONAL_ACTIVATION_V1"
                and record["profile"] == "PERSONAL_PAPER_ONLY_V1"
                and record["origin"] == "LOCAL_OPERATOR"
                and type(record["issued_at"]) is int
                and type(record["expires_at"]) is int
                and 0 < record["expires_at"] - record["issued_at"] <= 1800
                and type(record["actions"]) is list
                and "READ_ONLY" in record["actions"])
            activation_verification_reason = (
                "Native-bound record structure read back; operator, policy, expiry "
                "and technical lease not independently accepted" if native_activation_verified
                else "Native-bound record structure invalid")
        except (ValueError, OSError, KeyError, TypeError):
            activation_verification_reason = "Native-bound activation readback refused"
    results.append(check(
        "ACTIVATION_NATIVE_VERIFIED",
        native_activation_verified,
        activation_verification_reason,
    ))

    results.append(check(
        "FINANCIAL_INCEPTION",
        False,
        "Attempted/publication flags are not native financial readback; "
        "requires independently verified native account state",
    ))

    results.append(check(
        "RUNTIME_AUTHORIZATION",
        False,
        "Scope metadata is not an accepted runtime lease; "
        "requires verified installed runtime dependencies and native grant",
    ))

    clock_probe = None
    if args.check_native_clock:
        from scripts.observation_runtime.personal_clock_gate_probe import (
            inspect_personal_clock_gate,
        )
        clock_probe = inspect_personal_clock_gate()
        results.append(check(
            "NATIVE_CLOCK_PROBE",
            clock_probe["trusted_clock_verified_for_probe"] is True,
            "One-time native Windows clock evidence only; does not authorize a lease",
        ))

    passed = all(item["status"] == "PASS" for item in results)
    # Dependencies are explanatory, never synthetic PASS states or permissions.
    next_actions = {
        "OPERATIONAL_QD_SOURCE_PUBLICATION":
            "Independently enroll and authenticate current FORWARD_COLLECTION QD publication, including issuer, durable custody, writer ownership and accepted Stop controls",
        "ACTIVATION_RECORD_PRESENT":
            "Obtain operator-approved installed activation record under existing native PersonalPaper custody; do not generate from preflight",
        "ACTIVATION_NATIVE_VERIFIED":
            "Independently bind native activation root/file identities and SHA256; verify operator, policy, release, expiry and technical lease separately",
        "FINANCIAL_INCEPTION":
            "Only after source and activation acceptance, verify authorized once-only simulated $1000 account inception through native financial readback",
        "RUNTIME_AUTHORIZATION":
            "Verify accepted native runtime grant, market inputs, financial ownership, Control Center Stop and bounded 60-second pilot scope",
    }
    blocked = [item["check"] for item in results if item["status"] == "BLOCKED"]

    report = {
        "schema": "ATLAS_QD_COMMISSIONING_PREFLIGHT_V1",
        "profile": PROFILE,
        "status": "PASS" if passed else "BLOCKED",
        "checks": results,
        "blocked_dependency_order": [name for name in next_actions if name in blocked],
        "blocked_dependency_actions": {name: next_actions[name] for name in next_actions if name in blocked},
        "source_enrollment_policy_review": {
            "schema": "ATLAS_QD_ENROLLMENT_POLICY_REVIEW_V1",
            "legacy_qd_op_contract_requires_manual_only": True,
            "personal_pilot_uses_distinct_auto_native_enrollment_v4": True,
            "manual_only_conflict_applies_to_personal_pilot": False,
            "autonomous_pilot_native_acceptance_verified": False,
            "next_action": "Verify independently accepted QD_AUTO_NATIVE_ENROLLMENT_V4 source publication, custody, issuer, Stop and native activation; never translate legacy QD_OP_ENROLLMENT_V1 into autonomous authority",
            "grants_authority": False,
        },
        "financial_mutations": False,
        "live_orders": False,
        "pilot_started": False,
        "native_custody_inventory": native,
        "quality_dips_custody_inventory": {
            "native_parent_present": source_parent.is_dir()
            and not source_parent.is_symlink() and not source_parent.is_junction(),
            "ordinary_child_count": len(source_children),
            "operational_publication_verified": False,
        },
        "native_clock_probe": clock_probe,
        "operator_action_required": (
            "Review source checkpoint and explicitly authorize native activation "
            "only after independently accepted research, financial custody, "
            "writer ownership, and Stop controls are verified"
        ),
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
