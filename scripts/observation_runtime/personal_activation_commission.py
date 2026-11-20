"""Explicit one-shot native PAPER activation entrypoint; no default authorization.

The caller must supply an existing complete operator-signed-in-session record,
release digest, account bindings and the exact installed clock source. Nothing
is inferred from commissioning scope or diagnostic data.
"""
import argparse
import json
import math
import ntpath
import os
import stat
from contextlib import contextmanager
from pathlib import Path

from scripts.observation_runtime.atlas_independent_ntp_clock import SOURCE
from scripts.observation_runtime.atlas_v7_commissioning_ntp_probe import V7_ARTIFACT
from scripts.observation_runtime.personal_activation_publisher import (
    publish_personal_activation,
)
from scripts.observation_runtime.personal_v7_operator_clock import (
    PROFILE as V7_NTP_PROFILE,
)
from scripts.observation_runtime.personal_v7_operator_clock import (
    NativeV7PaperOperatorClock,
)
from scripts.observation_runtime.personal_v8_operator_clock import (
    ARTIFACT as V8_ARTIFACT,
)
from scripts.observation_runtime.personal_v8_operator_clock import (
    PROFILE as V8_NTP_PROFILE,
)
from scripts.observation_runtime.personal_v8_operator_clock import (
    NativeV8PaperOperatorClock,
)
from scripts.observation_runtime.personal_version_safe_release_clock import (
    PROFILE as VERSION_SAFE_NTP_PROFILE,
)
from scripts.observation_runtime.personal_version_safe_release_clock import (
    NativeVersionSafePaperOperatorClock,
    require_version_safe_release_digest,
)
from scripts.observation_runtime.personal_windows_clock import LocalWindowsClock
from scripts.volume_inspector.windows_output import current_sid

# File bounds apply before JSON parsing, native process retention, NTP sampling
# or create-only operator activation. These are untrusted *input* files, never
# native file-identity authority or a replacement for signed operator approval.
INPUT_MAX_BYTES = {
    'record': 65536,
    'policy': 131072,
    'accounts': 65536,
    'quality_dips_enrollment': 131072,
    'hyperliquid_enrollment': 131072,
}


def _unique_json_fields(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('ACTIVATION_DUPLICATE_JSON_INPUT_FIELD')
        result[key] = value
    return result


def _finite_json_float(raw):
    number = float(raw)
    if not math.isfinite(number):
        raise ValueError('ACTIVATION_NONFINITE_JSON_NUMBER')
    return number


def _limit_json_nesting(text, maximum=64):
    # Avoid letting deeply nested but small JSON exhaust the interpreter.
    # Brackets inside quoted strings, including escaped quotes, are not nodes.
    depth = 0
    quoted = escaped = False
    for char in text:
        if quoted:
            if escaped:
                escaped = False
            elif char == '\\':
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
        elif char in '{[':
            depth += 1
            if depth > maximum:
                raise ValueError('ACTIVATION_JSON_INPUT_NESTING_LIMIT')
        elif char in '}]':
            depth -= 1
            if depth < 0:
                raise ValueError('ACTIVATION_JSON_INPUT_NESTING_MALFORMED')


def read_bounded_activation_input(path, *, role):
    """Ordinary existing JSON only, bounded and exact; never reads credentials.

    No input JSON may manufacture native file identity, finance acceptance,
    account enrollment or provider rights. Caller must still verify all those.
    """
    if (type(role) is not str or role not in INPUT_MAX_BYTES
            or type(path) is not str or not path or '\x00' in path):
        raise ValueError('ACTIVATION_EXPLICIT_JSON_INPUT_PATH_REQUIRED')
    item = Path(path)
    if (not item.is_file() or item.is_symlink() or item.is_junction()):
        raise ValueError('ACTIVATION_ORDINARY_JSON_INPUT_REQUIRED:' + role)
    limit = INPUT_MAX_BYTES[role]
    try:
        # Reading through a single opened handle limits TOCTOU path retargets.
        # This is NOT a signed native readback, authorization or anti-admin ACL.
        with item.open('rb') as stream:
            before = os.fstat(stream.fileno())
            if not stat.S_ISREG(before.st_mode) or not 0 < before.st_size <= limit:
                raise ValueError('ACTIVATION_BOUNDED_JSON_INPUT_REQUIRED:' + role)
            raw = stream.read(limit + 1)
            after = os.fstat(stream.fileno())
            if (not 0 < len(raw) <= limit or len(raw) != before.st_size
                    or after.st_size != before.st_size
                    or after.st_mtime_ns != before.st_mtime_ns):
                raise ValueError('ACTIVATION_JSON_INPUT_CHANGED_DURING_READ:' + role)
    except (OSError, OverflowError) as exc:
        raise ValueError('ACTIVATION_JSON_INPUT_UNAVAILABLE:' + role) from exc
    try:
        decoded = raw.decode('utf-8-sig')
        _limit_json_nesting(decoded)
        value = json.loads(
            decoded,
            object_pairs_hook=_unique_json_fields,
            parse_float=_finite_json_float,
            parse_constant=lambda bad: (_ for _ in ()).throw(
                ValueError('ACTIVATION_NONFINITE_JSON_CONSTANT')),
        )
    except (UnicodeError, ValueError, TypeError, RecursionError) as exc:
        raise ValueError('ACTIVATION_STRICT_JSON_INPUT_REFUSED:' + role) from exc
    if type(value) is not dict:
        raise ValueError('ACTIVATION_JSON_OBJECT_REQUIRED:' + role)
    return value


def verify_enrollment_native_roots(enrollment):
    """Existing-only Windows handle verification; JSON identities never suffice."""
    from scripts.observation_runtime.personal_paper_inception import native_primitives
    native = native_primitives()
    for role, resource in enrollment['resources'].items():
        try:
            with native.w.WindowsOutput(resource['path']) as output:
                observed = native.native.file_identity(output.root_handle)
        except (OSError, ValueError) as exc:
            raise ValueError('ACTIVATION_NATIVE_RESOURCE_UNVERIFIED:' + role) from exc
        if observed != resource['native_id']:
            raise ValueError('ACTIVATION_NATIVE_RESOURCE_IDENTITY_MISMATCH:' + role)


@contextmanager
def retain_r16_nonfinancial_original_job(*, qd, perp, owned_job):
    """Guard real R16 structural rosters under original held Windows handles.

    In-process observation ONLY, never an accepted financial writer lease,
    issuer, operational clock, financial inception or activation permission.
    Recheck in finally so an exception in the observed action cannot skip
    the original process incarnation, Job and twelve-root verification.
    """
    from scripts.observation_runtime.personal_r16_owned_job_activation import (
        RetainedSelectedR16OwnerJob,
    )
    if type(owned_job) is not RetainedSelectedR16OwnerJob:
        raise ValueError('R16_NONFINANCIAL_EXACT_RETAINED_ORIGINAL_JOB_REQUIRED')
    owned_job.require_exact_roster(qd=qd, perp=perp)
    try:
        yield owned_job
    finally:
        owned_job.require_exact_roster(qd=qd, perp=perp)


@contextmanager
def retain_activation_writer_guard(*, qd, perp, release_digest, owned_job=None,
                                   actions=None):
    """Use the original R15 Job+PROCESS HANDLE; never reopen its PID.

    R15 ownership is necessarily *in-process*, holding the exact child
    handles and native-root identities. A synthetic roster or standalone
    observed PID cannot be adopted into an operator activation. Earlier
    releases keep the independent native writer-HANDLE retention path.
    This context does NOT confer a financial ownership lease.
    """
    from scripts.observation_runtime.atlas_r15_paper_offline_commissioning import (
        ARTIFACT as R15_ARTIFACT,
    )
    from scripts.observation_runtime.atlas_r16_selected_code_readback import (
        ARTIFACT_DIGEST as R16_ARTIFACT,
    )
    # The R16 structural owner guard checks an ORIGINAL live Job+PROCESS
    # without reopening an enrolled PID. Even a genuine retained Job is NOT
    # independently accepted financial lease/issuer/operator authority.
    # There must be NO yield to the financial activation publisher here.
    if release_digest == R16_ARTIFACT:
        from scripts.observation_runtime.personal_r16_owned_job_activation import (
            RetainedSelectedR16OwnerJob,
        )
        if type(owned_job) is not RetainedSelectedR16OwnerJob:
            raise ValueError('ACTIVATION_R16_RETAINED_FINANCIAL_OWNER_JOB_NOT_YET_ACCEPTED')
        with retain_r16_nonfinancial_original_job(
                qd=qd, perp=perp, owned_job=owned_job):
            raise ValueError('ACTIVATION_R16_INDEPENDENT_FINANCIAL_LEASE_NOT_ACCEPTED')
    # A later selected release must implement a separately audited native
    # Job-backed financial writer issuer. Do NOT route an unknown successor
    # into the old PID-only historical adapter by default.
    if release_digest not in (R15_ARTIFACT, V7_ARTIFACT, V8_ARTIFACT):
        from scripts.observation_runtime.personal_owner_continuity_v2 import NativeReadOnlyRecoveryActivationGuard
        if type(owned_job) is NativeReadOnlyRecoveryActivationGuard:
            if owned_job.release_digest!=release_digest or actions!=['READ_ONLY']:
                raise ValueError('ACTIVATION_RECOVERY_BOOTSTRAP_STRICTLY_READ_ONLY')
            owned_job.require_exact_roster(qd=qd,perp=perp)
            try:yield owned_job
            finally:owned_job.require_exact_roster(qd=qd,perp=perp)
            return
        from scripts.observation_runtime.personal_writer_generation import NativeRecoveredFinancialWriterOwner
        if type(owned_job) is NativeRecoveredFinancialWriterOwner:
            if (owned_job.release_digest!=release_digest
                    or type(actions) is not list or not actions or len(set(actions))!=len(actions)
                    or 'INITIALIZE_SIMULATED_ACCOUNTS' in actions):
                raise ValueError('ACTIVATION_RECOVERED_WRITER_NO_INITIALIZATION_OR_IMPLICIT_SCOPE')
            owned_job.require_exact_roster(qd=qd,perp=perp)
            owned_job.require_financial_fence()
            # The distinct native operator record is still verified/published
            # by the ORIGINAL activation publisher; this guard grants nothing.
            # Publishing an explicitly approved activation RECORD is not a
            # financial operation. Do not place clock acquisition/deep native
            # publication inside the <=5s financial-effect lease. No trading
            # can be active: require the native flat/drained recovery cut.
            with owned_job.generation.journal.exclusive():
                owned_job.generation.recovery.capture()
                try:yield owned_job
                finally:
                    owned_job.require_exact_roster(qd=qd,perp=perp)
                    owned_job.require_financial_fence()
            return
        from scripts.observation_runtime.personal_native_selected_owned_job_preflight import (
            RetainedSelectedNativeOwnerPreflight,
        )
        if (type(owned_job) is not RetainedSelectedNativeOwnerPreflight
                or owned_job.release_digest != release_digest):
            raise ValueError('ACTIVATION_FUTURE_NATIVE_FINANCIAL_JOB_ISSUER_MISSING')
        # The original Job-backed activation RECORD is needed BEFORE the first
        # once-only native PAPER account publisher. Only after independent
        # native readback of the TWO initial coordination journals (ten other
        # account roots still EMPTY) may read+initialize activation proceed.
        # Never AUTO_PAPER or external orders. A distinct post-inception
        # operator activation is required for any later PAPER operation.
        phase = getattr(owned_job, '_phase', None)
        if phase == 'PREINCEPTION_COORDINATION_READY':
            # NativePersonalTechnicalChecks always obtains a native READ_ONLY
            # lease before a once-only simulated account opening. A record
            # granting INITIALIZE alone would pass this guard but fail during
            # actual technical/financial readback. Admit exactly both actions.
            if (type(actions) is not list
                    or len(actions) != 2
                    or set(actions) != {'READ_ONLY', 'INITIALIZE_SIMULATED_ACCOUNTS'}):
                raise ValueError('ACTIVATION_FUTURE_PREINCEPTION_INIT_AND_READ_REQUIRED')
            origin = getattr(owned_job, 'origin', None)
            if (type(origin) is not dict
                    or origin.get('selected_artifact_digest_bound') is not True
                    or any(origin.get(flag) is not False for flag in (
                        'financial_writer_lease_issued',
                        'financial_activation_published',
                        'paper_start_authorized',
                        'live_trading_authorized'))):
                raise ValueError('ACTIVATION_FUTURE_PREINCEPTION_SELECTED_ORIGIN_REQUIRED')
            owned_job.require_exact_roster(qd=qd, perp=perp)
            try:
                yield owned_job  # Activation RECORD only; no publisher run here.
            finally:
                owned_job.require_exact_roster(qd=qd, perp=perp)
                if getattr(owned_job, '_phase', None) != 'PREINCEPTION_COORDINATION_READY':
                    raise ValueError('ACTIVATION_FUTURE_PREINCEPTION_OWNER_PHASE_CHANGED')
            return
        # Any other successor activation requires two ACKNOWLEDGED native
        # FS1/FS3 inceptions. No partial or unknown account may proceed.
        # If a scoped operator record is provided, it MUST NOT grant another
        # account initializer once financial entry can later be admitted.
        if (actions is not None
                and (type(actions) is not list
                     or len(actions) != len(set(actions))
                     or 'INITIALIZE_SIMULATED_ACCOUNTS' in actions)):
            raise ValueError('ACTIVATION_FUTURE_POSTINCEPTION_INIT_REUSE_REFUSED')
        accepted_phase = getattr(owned_job, '_phase', None)
        if (accepted_phase not in ('INITIAL_READBACK_ONLY', 'CURRENT_READBACK_ONLY')
                or type(getattr(owned_job, '_initial_cuts', None)) is not tuple
                or len(owned_job._initial_cuts) != 2
                or type(getattr(owned_job, '_initial_bootstraps', None)) is not tuple
                or len(owned_job._initial_bootstraps) != 2):
            raise ValueError('ACTIVATION_FUTURE_TWO_GENUINE_INITIAL_ACCOUNTS_REQUIRED')
        origin = getattr(owned_job, 'origin', None)
        if (type(origin) is not dict
                or origin.get('selected_artifact_digest_bound') is not True
                or origin.get('financial_writer_lease_issued') is not False
                or origin.get('financial_activation_published') is not False
                or origin.get('paper_start_authorized') is not False
                or origin.get('live_trading_authorized') is not False):
            raise ValueError('ACTIVATION_FUTURE_ORIGINAL_SELECTED_SOURCE_PROOF_REQUIRED')
        owned_job.require_exact_roster(qd=qd, perp=perp)
        try:
            # The activation publisher separately validates the native
            # installed release, approved LOCAL_OPERATOR input record,
            # independent clock and create-only activation output. This
            # borrowed original owner handle does NOT issue a PAPER lease.
            yield owned_job
        finally:
            # Even on publisher exceptions, a disappearing process, changed
            # account root or revoked initial ACK is terminal, never success.
            owned_job.require_exact_roster(qd=qd, perp=perp)
            if getattr(owned_job, '_phase', None) != accepted_phase:
                raise ValueError('ACTIVATION_FUTURE_INITIAL_OWNER_PHASE_CHANGED')
        # A verified successor activation-only context is complete. Never
        # fall through to an obsolete R15 or PID-only legacy writer adapter.
        return
    if release_digest == R15_ARTIFACT:
        from scripts.observation_runtime.personal_r15_owned_job_activation import (
            RetainedSelectedR15OwnerJob,
        )
        if type(owned_job) is not RetainedSelectedR15OwnerJob:
            raise ValueError('ACTIVATION_R15_RETAINED_NATIVE_JOB_REQUIRED')
        owned_job.require_exact_roster(qd=qd, perp=perp)
        yield owned_job
        owned_job.require_exact_roster(qd=qd, perp=perp)
    else:
        if owned_job is not None:
            raise ValueError('ACTIVATION_FOREIGN_JOB_OR_RELEASE_REFUSED')
        from scripts.observation_runtime.personal_native_writer_lifetime import (
            retain_live_enrollment_writers,
        )
        with retain_live_enrollment_writers(qd, perp, release_digest=release_digest) as writers:
            yield writers


def commission(*, root, record_path, policy_path, release_digest, accounts_path,
               expected_clock_source, runtime_id, qd_enrollment_path=None,
               perp_enrollment_path=None, clock_profile="WINDOWS_TIME_OPERATOR_CLOCK_V4",
               owned_job=None, prequalified_clock=None):
    if not all(type(v) is str and v for v in (root, record_path, policy_path,
                                              release_digest, accounts_path,
                                              expected_clock_source, runtime_id)):
        raise ValueError('EXPLICIT_ACTIVATION_INPUTS_REQUIRED')
    if len(release_digest) != 64 or any(c not in '0123456789abcdef' for c in release_digest):
        raise ValueError('EXPLICIT_RELEASE_DIGEST_REQUIRED')
    if (ntpath.normpath(root) != root
            or not ntpath.normcase(root).startswith('d:\\atlascustody\\personalpaper\\')
            or any(c in root[3:] for c in (':', '%', '\x00', '/'))
            or any(part in ('', '.', '..') for part in root[3:].split('\\'))):
        raise ValueError('EXPLICIT_NATIVE_ACTIVATION_ROOT_REQUIRED')
    if not (type(qd_enrollment_path) is str and qd_enrollment_path
            and type(perp_enrollment_path) is str and perp_enrollment_path):
        raise ValueError('BOTH_NATIVE_ACCOUNT_ENROLLMENTS_REQUIRED')
    if clock_profile == V7_NTP_PROFILE:
        if release_digest != V7_ARTIFACT or expected_clock_source != SOURCE:
            raise ValueError('EXACT_V7_NATIVE_RELEASE_AND_NTP_SOURCE_REQUIRED')
    elif clock_profile == V8_NTP_PROFILE:
        if release_digest != V8_ARTIFACT or expected_clock_source != SOURCE:
            raise ValueError('EXACT_V8_NATIVE_RELEASE_AND_NTP_SOURCE_REQUIRED')
    elif clock_profile == VERSION_SAFE_NTP_PROFILE:
        if expected_clock_source != SOURCE:
            raise ValueError('EXACT_VERSION_SAFE_NATIVE_NTP_SOURCE_REQUIRED')
    elif clock_profile != "WINDOWS_TIME_OPERATOR_CLOCK_V4":
        raise ValueError('UNREVIEWED_ACTIVATION_CLOCK_PROFILE')
    # Native issuer candidate MUST originate from the exact selected and
    # original-handle verified installed release and its own Python process.
    # Workspace copies, stale release digests and historical native code must
    # fail before reading untrusted operator JSON or opening any native root.
    from scripts.observation_runtime.personal_native_financial_release_origin import (
        require_selected_native_origin,
    )
    from scripts.observation_runtime.personal_native_original_self_job import NativeFinancialReleaseAdmission
    from scripts.observation_runtime.personal_native_selected_owned_job_preflight import RetainedSelectedNativeOwnerPreflight
    from scripts.observation_runtime.personal_owner_continuity_v2 import NativeReadOnlyRecoveryActivationGuard
    from scripts.observation_runtime.personal_writer_generation import NativeRecoveredFinancialWriterOwner
    admission=None
    if type(owned_job) in (RetainedSelectedNativeOwnerPreflight,NativeReadOnlyRecoveryActivationGuard):
        admission=getattr(owned_job,'_release_admission',None)
    elif type(owned_job) is NativeRecoveredFinancialWriterOwner:
        admission=getattr(owned_job.generation.recovery.readback,'_release_admission',None)
    if admission is not None:
        if type(admission) is not NativeFinancialReleaseAdmission:
            raise ValueError('ACTIVATION_RETAINED_NATIVE_RELEASE_ADMISSION_REQUIRED')
        admission.verify(release_digest=release_digest)
    else:
        if prequalified_clock is not None:
            raise ValueError('ACTIVATION_PREQUALIFIED_CLOCK_REQUIRES_RETAINED_FULL_RELEASE')
        require_selected_native_origin(release_digest=release_digest)
    record = read_bounded_activation_input(record_path, role='record')
    policy = read_bounded_activation_input(policy_path, role='policy')
    accounts = read_bounded_activation_input(accounts_path, role='accounts')
    if (type(record) is not dict or type(accounts) is not dict
            or set(accounts) != {'HYPERLIQUID', 'QUALITY_DIPS'}
            or any(type(v) is not str or len(v) != 64
                   or any(c not in '0123456789abcdef' for c in v)
                   for v in accounts.values())
            or record.get('accounts') != accounts
            or record.get('release_digest') != release_digest):
        raise ValueError('ACTIVATION_ACCOUNTS_OR_RELEASE_MISMATCH')
    # Enrollment JSON alone is not native proof. Require exact structural and
    # digest binding if independently supplied; never mint account digests here.
    from app.services.paper_financial_replay import digest as enrollment_digest
    from app.services.perp_operational_contract import (
        validate_enrollment as perp_validate,
    )
    from app.services.quality_dips_autonomous_enrollment import (
        validate_enrollment as qd_validate,
    )
    qd = qd_validate(read_bounded_activation_input(
        qd_enrollment_path, role='quality_dips_enrollment'))
    perp = perp_validate(read_bounded_activation_input(
        perp_enrollment_path, role='hyperliquid_enrollment'))
    if (accounts != {'QUALITY_DIPS': enrollment_digest(qd),
                     'HYPERLIQUID': enrollment_digest(perp)}
            or qd['release_digest'] != release_digest
            or perp['release_digest'] != release_digest
            or qd['account_id'] == perp['account_id']):
        raise ValueError('ACTIVATION_ENROLLMENT_DIGEST_OR_RELEASE_CONFLICT')
    verify_enrollment_native_roots(qd)
    verify_enrollment_native_roots(perp)
    # Check the full static activation contract before acquiring a short-lived
    # trusted-clock capability or entering native create-only custody.
    from app.services.paper_financial_replay import digest
    from app.services.personal_paper_runtime import validate_policy
    validated_policy = validate_policy(policy)
    if (record.get('policy_digest') != digest(validated_policy)
            or record.get('origin') != 'LOCAL_OPERATOR'
            or record.get('schema') != 'ATLAS_PERSONAL_ACTIVATION_V1'
            or not isinstance(record.get('actions'), list)
            or not record['actions']):
        raise ValueError('ACTIVATION_POLICY_OR_ACTION_BINDING_REQUIRED')
    # R15 must use the ORIGINAL owned Windows Job+PROCESS HANDLE in this
    # trusted process. Never reopen a PID taken from enrollment JSON. The
    # guarded context re-verifies exact 5+7 rosters and all 12 original
    # empty native roots on entry and exit. No financial writer lease exists.
    from scripts.observation_runtime.atlas_r15_paper_offline_commissioning import (
        ARTIFACT as R15_ARTIFACT,
    )
    with retain_activation_writer_guard(qd=qd, perp=perp,
            release_digest=release_digest, owned_job=owned_job,
            actions=record['actions']) as writers:
        writers.verify_still_running()
        if prequalified_clock is not None:
            if (clock_profile!=VERSION_SAFE_NTP_PROFILE
                    or type(prequalified_clock) is not NativeVersionSafePaperOperatorClock):
                raise ValueError('ACTIVATION_EXACT_PREQUALIFIED_VERSION_SAFE_CLOCK_REQUIRED')
            prequalified_clock.require_operational(runtime_id)
            clock=prequalified_clock
        elif clock_profile == V7_NTP_PROFILE:
            clock = NativeV7PaperOperatorClock(runtime_id=runtime_id)
        elif clock_profile == V8_NTP_PROFILE:
            clock = NativeV8PaperOperatorClock(runtime_id=runtime_id)
        elif clock_profile == VERSION_SAFE_NTP_PROFILE:
            clock = NativeVersionSafePaperOperatorClock(runtime_id=runtime_id)
        else:
            clock = LocalWindowsClock(expected_source=expected_clock_source, runtime_id=runtime_id)
        published=False
        try:
            if clock_profile == VERSION_SAFE_NTP_PROFILE:
                require_version_safe_release_digest(clock=clock, runtime_id=runtime_id,
                                                    release_digest=release_digest)
            writers.verify_still_running()
            if release_digest == R15_ARTIFACT:
                owned_job.require_exact_roster(qd=qd, perp=perp)
            result = publish_personal_activation(root=root, record=record, policy=policy,
                operator_id=current_sid(), release_digest=release_digest,
                accounts=accounts, clock=clock, runtime_id=runtime_id,
                clock_profile=clock_profile)
            # A disappearing owned process during the create-only publisher
            # is UNKNOWN, never successful financial commissioning.
            if release_digest == R15_ARTIFACT:
                owned_job.require_exact_roster(qd=qd, perp=perp)
            published=True
            return result
        finally:
            # An explicitly borrowed original cohort clock must remain live
            # for the once-only account ACKs. Its owner revokes it in finally.
            # Locally constructed clocks retain the original revoke behavior.
            if prequalified_clock is None or not published:clock.revoke()


def main(argv=None):
    parser = argparse.ArgumentParser(description='Explicit native PAPER activation; no account inception')
    for name in ('root', 'record-path', 'policy-path', 'release-digest',
                 'accounts-path', 'expected-clock-source', 'runtime-id'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--qd-enrollment-path', required=True)
    parser.add_argument('--perp-enrollment-path', required=True)
    parser.add_argument('--clock-profile', default='WINDOWS_TIME_OPERATOR_CLOCK_V4',
                        choices=['WINDOWS_TIME_OPERATOR_CLOCK_V4', V7_NTP_PROFILE, V8_NTP_PROFILE, VERSION_SAFE_NTP_PROFILE])
    args = vars(parser.parse_args(argv))
    result = commission(**{k.replace('-', '_'): v for k, v in args.items()})
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
