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
    clock_profile="WINDOWS_TIME_OPERATOR_CLOCK_V4",
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

    # Caller-supplied identity/time never authorize native publication.
    # V7 requires its own exact selected native release and two-peer NTP port.
    # Existing Windows-time path retains its original default.
    from scripts.observation_runtime.personal_windows_clock import LocalWindowsClock
    from scripts.observation_runtime.personal_v7_operator_clock import (
        NativeV7PaperOperatorClock, PROFILE as V7_NTP_PROFILE,
    )
    from scripts.observation_runtime.atlas_v7_commissioning_ntp_probe import (
        V7_ARTIFACT,
    )
    from scripts.observation_runtime.personal_v8_operator_clock import (
        NativeV8PaperOperatorClock, PROFILE as V8_NTP_PROFILE,
        ARTIFACT as V8_ARTIFACT,
    )
    from scripts.observation_runtime.personal_version_safe_release_clock import (
        NativeVersionSafePaperOperatorClock, PROFILE as VERSION_SAFE_NTP_PROFILE,
        require_version_safe_release_digest,
    )
    from scripts.observation_runtime.atlas_independent_ntp_clock import SOURCE
    from scripts.volume_inspector.windows_output import current_sid

    if operator_id != current_sid():
        raise PersonalActivationPublicationRefused(
            "Windows operator identity mismatch"
        )

    if clock_profile == "WINDOWS_TIME_OPERATOR_CLOCK_V4":
        if type(clock) is not LocalWindowsClock:
            raise PersonalActivationPublicationRefused(
                "Operational Windows clock required"
            )
    elif clock_profile == V7_NTP_PROFILE:
        if type(clock) is not NativeV7PaperOperatorClock or release_digest != V7_ARTIFACT:
            raise PersonalActivationPublicationRefused(
                "Selected V7 native release and independent clock required"
            )
    elif clock_profile == V8_NTP_PROFILE:
        if type(clock) is not NativeV8PaperOperatorClock or release_digest != V8_ARTIFACT:
            raise PersonalActivationPublicationRefused(
                "Selected V8 native release and independent clock required"
            )
    elif clock_profile == VERSION_SAFE_NTP_PROFILE:
        if type(clock) is not NativeVersionSafePaperOperatorClock:
            raise PersonalActivationPublicationRefused("Exact version-safe native clock required")
        try:
            require_version_safe_release_digest(clock=clock, runtime_id=runtime_id,
                                                release_digest=release_digest)
        except (ValueError, TypeError, OSError) as exc:
            raise PersonalActivationPublicationRefused("Selected version-safe native release binding required") from exc
    else:
        raise PersonalActivationPublicationRefused(
            "Unreviewed activation clock profile"
        )

    clock.require_operational(runtime_id)

    sample = clock.runtime_sample()

    if not clock.verify_runtime_sample(sample):
        raise PersonalActivationPublicationRefused(
            "Trusted selected clock verification failed"
        )
    if clock_profile in (V7_NTP_PROFILE, V8_NTP_PROFILE, VERSION_SAFE_NTP_PROFILE) and (
        type(sample) is not dict or sample.get("source_id") != SOURCE
        or type(sample.get("uncertainty_ms")) is not int
        or not 0 <= sample["uncertainty_ms"] <= 1000
    ):
        raise PersonalActivationPublicationRefused(
            "Selected V7 two-peer UTC evidence required"
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

    # Validate serialized size before create-only custody publication. A refused
    # oversized record must never consume a once-only native activation root.
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

    native = _native_store()
    with native.w.WindowsOutput.create_root(root) as output:
        native_root = native.native.file_identity(output.root_handle)

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
