"""Native create-only publication of a local PAPER activation record.

No default operator authorization, financial inception, or runtime startup.
"""

import hashlib
import importlib.util
import json
from pathlib import Path


class PersonalActivationPublicationRefused(ValueError):
    pass


def _native_store():
    path = (
        Path(__file__).resolve().parents[1]
        / "volume_inspector"
        / "snapshot_store.py"
    )
    spec = importlib.util.spec_from_file_location(
        "atlas_personal_activation_native_store",
        path,
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def publish_personal_activation(
    *,
    root,
    record,
    policy,
    operator_id,
    release_digest,
    accounts,
    clock,
    runtime_id,
):
    """Create and independently verify one native-bound activation record.

    The parent directories must already exist under the installed operator's
    authorized custody hierarchy. The final root must not exist.
    """
    from backend.app.services.personal_paper_runtime import (
        validate_activation_record,
    )
    from scripts.observation_runtime.personal_paper_activation import (
        NativePersonalActivationReader,
    )

    if not isinstance(root, str):
        raise PersonalActivationPublicationRefused(
            "Explicit native activation root required"
        )

    # Match the installed native reader's custody-root restrictions.
    import ntpath

    if (
        ntpath.normpath(root) != root
        or not ntpath.normcase(root).startswith(
            "d:\\atlascustody\\personalpaper\\"
        )
        or any(c in root[3:] for c in (":", "%", "\x00", "/"))
        or any(
            component in ("", ".", "..")
            for component in root[3:].split("\\")
        )
    ):
        raise PersonalActivationPublicationRefused(
            "Invalid personal PAPER custody root"
        )

    if not isinstance(record, dict):
        raise PersonalActivationPublicationRefused(
            "Explicit operator activation record required"
        )

    if record.get("actions") is None:
        raise PersonalActivationPublicationRefused(
            "Explicit action authorization required"
        )

    # Caller-supplied identity and time are insufficient authorization.
    # Verify against the actual Windows operator and installed local clock.
    from scripts.observation_runtime.personal_windows_clock import LocalWindowsClock
    from scripts.volume_inspector.windows_output import current_sid

    if operator_id != current_sid():
        raise PersonalActivationPublicationRefused(
            "Windows operator identity mismatch"
        )

    if type(clock) is not LocalWindowsClock:
        raise PersonalActivationPublicationRefused(
            "Operational Windows clock required"
        )

    clock.require_operational(runtime_id)

    sample = clock.runtime_sample()

    if not clock.verify_runtime_sample(sample):
        raise PersonalActivationPublicationRefused(
            "Trusted Windows clock verification failed"
        )

    now = sample["utc"]

    if type(now) is not int:
        raise PersonalActivationPublicationRefused(
            "Invalid trusted UTC timestamp"
        )

    for action in record["actions"]:
        validate_activation_record(
            record,
            policy=policy,
            operator_id=operator_id,
            release=release_digest,
            accounts=accounts,
            now=now,
            action=action,
        )

    if not record["actions"]:
        raise PersonalActivationPublicationRefused(
            "Empty activation authorization refused"
        )

    native = _native_store()

    # Native WindowsOutput.create_root() must enforce exclusive creation.
    # No Python mkdir(), overwrite, or fallback path is permitted.
    with native.w.WindowsOutput.create_root(root) as output:
        native_root = native.native.file_identity(
            output.root_handle
        )

        raw = json.dumps(
            record,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")

        if len(raw) > 65536:
            raise PersonalActivationPublicationRefused(
                "Activation record exceeds native output bound"
            )

        binding = output.write_bound(
            "activation.json",
            raw,
        )

        reader = NativePersonalActivationReader(
            root=root,
            native_root=native_root,
            binding=binding,
        )

        verified = reader.read()

        if verified != record:
            raise PersonalActivationPublicationRefused(
                "Native activation readback mismatch"
            )

        if hashlib.sha256(raw).hexdigest() != binding["sha256"]:
            raise PersonalActivationPublicationRefused(
                "Activation commitment mismatch"
            )

        return {
            "schema": "ATLAS_PERSONAL_ACTIVATION_PUBLICATION_V1",
            "root": root,
            "native_root": native_root,
            "binding": binding,
            "status": "NATIVE_VERIFIED",
        }



if __name__ == "__main__":
    raise SystemExit(
        "This module is an import-only activation publisher. "
        "No automatic activation is permitted."
    )
