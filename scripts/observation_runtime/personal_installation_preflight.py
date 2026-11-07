"""Read-only inventory of native Personal PAPER activation prerequisites.

Never creates directories, issues activation records, opens market connections,
reads credentials, or grants authority. Paths are fixed to the installed design.
"""
import json
from pathlib import Path


CUSTODY_PARENT = Path(r"D:\AtlasCustody")
PERSONAL_PARENT = CUSTODY_PARENT / "PersonalPaper"


def inspect_native_personal_installation(*, custody_parent=CUSTODY_PARENT):
    """Report only filesystem prerequisites, never treat them as approval."""
    parent = Path(custody_parent)
    personal = parent / "PersonalPaper"
    custody_present = parent.is_dir() and not parent.is_symlink()
    personal_present = custody_present and personal.is_dir() and not personal.is_symlink()
    return {
        "schema": "ATLAS_NATIVE_PERSONAL_INSTALLATION_PREFLIGHT_V1",
        "custody_parent_exists": custody_present,
        "personal_parent_exists": personal_present,
        "native_activation_record_verified": False,
        "trusted_clock_verified": False,
        "operator_lease_verified": False,
        "forward_financial_write_authorized": False,
        "live_order_authorized": False,
        "blockers": (["CUSTODY_PARENT_MISSING"] if not custody_present else [])
        + (["PERSONAL_PARENT_MISSING"] if not personal_present else [])
        + ["NATIVE_OPERATOR_ACTIVATION_UNVERIFIED",
           "TRUSTED_WINDOWS_CLOCK_UNVERIFIED",
           "PERSONAL_ENROLLMENT_AND_WRITER_OWNERSHIP_UNVERIFIED"],
    }


def main():
    print(json.dumps(inspect_native_personal_installation(), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
