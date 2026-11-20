"""Construct a REAL selected-native two-account PAPER inception issuer.

No default operator, signing, account, source, NTP, Job or ledger creation.
A selected installed Windows worker must provide ALL original native ports:
the SAME living original Job, exact accepted two-lane activation reader, one
version-safe independently qualified clock, verified installed image, two
already-initialized native coordination journals, and non-stale 1000-unit
account enrollments with exact original 12 writer-root identities.

This factory connects genuine production classes for the already-implemented
NativeSelectedTwoAccountSimulatedInception. It never calls publish_both_once;
a separate explicit, one-shot commissioning action is required. If assembly
fails, native writer handles are closed and there is no account file write.
"""
from __future__ import annotations

from app.services.paper_financial_replay import body, digest
from app.services.personal_native_coordination import PersonalNativeCoordination
from app.services.personal_paper_runtime import PersonalOperatorInstallation
from app.services.personal_publication_custody import PersonalPublicationCustody

from scripts.observation_runtime.personal_installation_technical import (
    NativePersonalTechnicalChecks,
)
from scripts.observation_runtime.personal_local_authority import (
    NativePersonalOperatorAuthority,
)
from scripts.observation_runtime.personal_native_selected_owned_job_preflight import (
    RetainedSelectedNativeOwnerPreflight,
)
from scripts.observation_runtime.personal_paper_activation import (
    NativePersonalActivationReader,
)
from scripts.observation_runtime.personal_paper_inception import (
    NativePersonalInceptionFiles,
    NativePersonalInitialReadback,
    PersonalInceptionBootstrap,
    PersonalInceptionPublisher,
    PersonalPublicationIssuer,
    validate_personal_inception,
)
from scripts.observation_runtime.personal_release_identity import (
    NativePersonalReleaseIdentity,
)
from scripts.observation_runtime.personal_selected_two_account_simulated_inception import (
    NativeSelectedTwoAccountSimulatedInception,
)
from scripts.observation_runtime.personal_version_safe_release_clock import (
    PROFILE as VERSION_SAFE_PROFILE,
)
from scripts.observation_runtime.personal_version_safe_release_clock import (
    NativeVersionSafePaperOperatorClock,
    require_version_safe_release_digest,
)
from scripts.observation_runtime.personal_writer_ownership import (
    NativePersonalWriterOwnership,
)
from scripts.observation_runtime.quality_dips_read_service import observe_self

LANES = ("QUALITY_DIPS", "HYPERLIQUID")
ISSUER_SCHEMA = "ATLAS_SELECTED_NATIVE_REAL_TWO_ACCOUNT_PREINCEPTION_FACTORY_V1"
ACTIONS = frozenset(("READ_ONLY", "INITIALIZE_SIMULATED_ACCOUNTS"))


def _origination_requirements(
        *, job, release, clock, reader, operators, ledgers, enrollments,
        runtime_id):
    """Mandatory independent authentic preconditions; no writer object yet."""
    if (type(job) is not RetainedSelectedNativeOwnerPreflight
            or type(release) is not NativePersonalReleaseIdentity
            or type(clock) is not NativeVersionSafePaperOperatorClock
            or type(reader) is not NativePersonalActivationReader
            or type(operators) is not dict or set(operators) != set(LANES)
            or type(ledgers) is not dict or set(ledgers) != set(LANES)
            or type(enrollments) is not dict or set(enrollments) != set(LANES)
            or type(runtime_id) is not str or not runtime_id
            or job._phase != "PREINCEPTION_COORDINATION_READY"):
        raise ValueError("SELECTED_ISSUER_EXACT_GENUINE_NATIVE_PORTS_REQUIRED")
    job.verify_still_running()
    selected = job.release_digest
    if release.artifact_digest != selected or not selected:
        raise ValueError("SELECTED_ISSUER_NATIVE_RELEASE_MISMATCH")
    if require_version_safe_release_digest(
            clock=clock, runtime_id=runtime_id,
            release_digest=selected) is not True:
        raise ValueError("SELECTED_ISSUER_SAME_VERSION_SAFE_NATIVE_UTC_REQUIRED")
    from scripts.observation_runtime.personal_existing_native_resource_evidence import (
        inspect_two_lane_native_roots,
    )
    native_roots = job._inspect_roots()
    if (native_roots["native_root_total"] != 12
            or native_roots["existing_empty_root_namespaces"] != 10
            or native_roots["all_twelve_distinct_and_empty"] is not False):
        raise ValueError("SELECTED_ISSUER_TWO_INITIAL_COORDINATION_JOURNALS_REQUIRED")
    observer = {"schema": "QD_OP_PROCESS_ID_V1", **observe_self()}
    if (type(job._identity) is not dict
            or observer != {"schema": "QD_OP_PROCESS_ID_V1", **job._identity}):
        raise ValueError("SELECTED_ISSUER_MUST_RUN_IN_ORIGINAL_JOB_PROCESS")
    native_enrollments = {}
    digests = {}
    accounts = {}
    record = None
    for lane in LANES:
        e = enrollments[lane]
        true_lane, native, manifest = validate_personal_inception(e)
        operator, ledger = operators[lane], ledgers[lane]
        if (true_lane != lane
                or type(operator) is not NativePersonalOperatorAuthority
                or type(ledger) is not PersonalNativeCoordination
                or operator._lane != lane
                or operator.reader is not reader
                or operator.clock is not clock
                or operator.runtime_id != runtime_id
                or operator.clock_profile != VERSION_SAFE_PROFILE
                or operator.enrollment != native
                or ledger.manifest != manifest
                or ledger.images.enrollment != digest(native)
                or ledger.images.root_id !=
                   native["resources"]["coordination"]["native_id"]
                or native["release_digest"] != selected
                or manifest["opening_cash"] != "1000"
                or any(native["writers"].get(role) != observer
                       for role in native["writers"])):
            raise ValueError("SELECTED_ISSUER_ORIGINAL_ACCOUNT_OR_OPERATOR_MISMATCH")
        approval = operator.activation("INITIALIZE_SIMULATED_ACCOUNTS")
        if (set(approval["actions"]) != ACTIONS
                or approval["release_digest"] != selected
                or approval["origin"] != "LOCAL_OPERATOR"
                or approval["accounts"] != operator.accounts):
            raise ValueError("SELECTED_ISSUER_BOTH_ACTIONS_AND_ONE_OPERATOR_REQUIRED")
        if record is not None and body(approval) != record:
            raise ValueError("SELECTED_ISSUER_ONE_IMMUTABLE_APPROVAL_REQUIRED")
        record = body(approval)
        native_enrollments[lane] = native
        digests[lane] = digest(native)
        accounts[lane] = operator.accounts
    if (accounts[LANES[0]] != accounts[LANES[1]]
            or accounts[LANES[0]] != digests
            or job.release_digest != selected):
        raise ValueError("SELECTED_ISSUER_BOTH_ACCOUNT_DIGESTS_IN_ONE_APPROVAL")
    job.require_exact_roster(
        qd=native_enrollments[LANES[0]],
        perp=native_enrollments[LANES[1]])
    return selected


def assemble_selected_two_account_inception(
        *, job, release, clock, reader, operators, ledgers,
        enrollments, runtime_id):
    """Return the authentic once-only issuer and exact closeable owners.

    The caller MUST close owners in finally after the scoped commissioning
    attempt. No returned port can grant live trading or financial orders.
    """
    selected = _origination_requirements(
        job=job, release=release, clock=clock, reader=reader,
        operators=operators, ledgers=ledgers,
        enrollments=enrollments, runtime_id=runtime_id,
    )
    publishers, owners = {}, {}
    try:
        for lane in LANES:
            enrollment = enrollments[lane]
            ledger = ledgers[lane]
            operator = operators[lane]
            custody = PersonalPublicationCustody(ledger)
            issuer = PersonalPublicationIssuer()
            files = NativePersonalInceptionFiles()
            bootstrap = PersonalInceptionBootstrap(
                enrollment=enrollment, publication=custody, issuer=issuer,
                clock=clock, readback=NativePersonalInitialReadback())
            owner = NativePersonalWriterOwnership(
                enrollment=enrollment["native_enrollment"],
                authority=operator, inception_intent=bootstrap.scope(),
                ledger=ledger, read_only=False)
            owners[lane] = owner
            technical = NativePersonalTechnicalChecks(
                bootstrap=bootstrap, release=release,
                clock=clock, runtime_id=runtime_id,
                ownership=owner, ledger=ledger, files=files,
                current=None, engine=None, clock_profile=VERSION_SAFE_PROFILE)
            installation = PersonalOperatorInstallation(
                policy=enrollment["personal_policy"],
                reader=reader, identity=operator, technical=technical,
                clock=clock, components=(bootstrap, owner, ledger, files),
                release_digest=selected, accounts=operator.accounts)
            issuer.bind_installation(installation)
            publishers[lane] = PersonalInceptionPublisher(
                bootstrap=bootstrap, custody=custody, ownership=owner,
                observer=lambda: {"schema": "QD_OP_PROCESS_ID_V1", **observe_self()},
                files=files)
        bound = NativeSelectedTwoAccountSimulatedInception(
            original_job=job, quality_dips=publishers[LANES[0]],
            hyperliquid=publishers[LANES[1]])
        return bound, owners
    except BaseException:
        for owner in reversed(list(owners.values())):
            owner.close()
        raise
