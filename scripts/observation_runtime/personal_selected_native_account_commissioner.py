"""Original selected personal PAPER account commissioning, stages C-G.

One SAME selected native Windows process retains the original installation
inventory, Windows Job, genuine original financial writer-roster identities
and independent operational UTC through the existing original:
  C: explicitly reviewed fresh original account candidates in memory
  D: two coordination journals (separate exact operator scope)
  E: preinception READ_ONLY + INITIALIZE_SIMULATED_ACCOUNTS activation record
  F: two real PAPER-only $1,000-account initial durable native publications
  G: distinct postinception READ_ONLY + CONNECT_APPROVED_DATA activation

This is the missing composition, NOT another financial issuer, order route,
source-terms grant, wallet connection or PAPER startup. No defaults, no
provisioning of financial parent directories, no fixture/JSON-only authority.
Any uncertain partial publication is terminal and must be reconciled manually.
"""
from __future__ import annotations

from app.services.paper_financial_replay import body, digest, strict
from app.services.personal_native_coordination import PersonalNativeCoordination

from scripts.observation_runtime.atlas_independent_ntp_clock import SOURCE
from scripts.observation_runtime.personal_activation_commission import (
    commission as commission_native_activation,
)
from scripts.observation_runtime.personal_native_original_self_job import (
    NativeFinancialReleaseAdmission,
    NativeOriginalSelfJob,
)
from scripts.observation_runtime.personal_native_selected_owned_job_preflight import (
    RetainedSelectedNativeOwnerPreflight,
)
from scripts.observation_runtime.personal_original_preinception_journal_permit import (
    NativeOriginalTwoJournalPreinceptionPermit,
)
from scripts.observation_runtime.personal_paper_activation import (
    NativePersonalActivationReader,
)
from scripts.observation_runtime.personal_release_identity import (
    NativePersonalReleaseIdentity,
)
from scripts.observation_runtime.personal_selected_two_account_issuer_factory import (
    assemble_selected_two_account_inception,
)
from scripts.observation_runtime.personal_version_safe_release_clock import (
    PROFILE as CLOCK_PROFILE,
    NativeVersionSafePaperOperatorClock,
    require_version_safe_release_digest,
)

LANES = ("QUALITY_DIPS", "HYPERLIQUID")
# Stable LOCAL source names from the documented public Hyperliquid /info
# request families. These are labels for a future independently accepted
# publisher, not source permissions, a settlement oracle or executable proof.
HL_ORIGINAL_PUBLIC_SOURCE_REVIEW = {
    "schema": "ATLAS_HL_PUBLIC_INFO_SOURCE_IDENTIFIERS_REVIEW_V1",
    "provider_url": "https://api.hyperliquid.xyz/info",
    "market_source": "HL_ORIGINAL_INFO_META_AND_L2BOOK_V1",
    "instrument_cut": "HL_ORIGINAL_INFO_META_ASSET_CTX_V1",
    "funding_source": "HL_ORIGINAL_INFO_FUNDING_HISTORY_V1",
}
STATES = (
    "PREINCEPTION_READY",
    "JOURNALS_UNKNOWN",
    "TWO_JOURNALS_ACKNOWLEDGED",
    "ACTIVATION_UNKNOWN",
    "INITIALIZE_ACTIVATION_ACKNOWLEDGED",
    "TWO_ACCOUNTS_UNKNOWN",
    "TWO_ACCOUNTS_ACKNOWLEDGED",
    "DATA_ACTIVATION_UNKNOWN",
    "POSTINCEPTION_DATA_ACTIVATION_ACKNOWLEDGED",
)


def prepare_original_fresh_two_account_inceptions(
        *, self_job, release, clock, runtime_id, personal_policy,
        operator_acceptance_ids, approved_unstamped_manifest_digests,
        hl_cost_amendment=None, hl_source_identifiers=None):
    """Stage C: create fresh IN-MEMORY original-manifest candidates.

    The source is the real selected original release + 12 genuine original
    empty root identities, NOT caller-chosen arbitrary finance templates.
    The local operator must already have reviewed the exact unstamped
    financial terms, fees, cash, source labels and policies and supplied
    both digests. Source labels are NOT provider authorization or a genuine
    trading-source issuer. No journal, activation, account, or trade starts.
    The returned opening time expires in five seconds by the ORIGINAL issuer;
    caller must retain the same original self-Job and initialize journals
    immediately under an independent exact one-shot operator scope.
    """
    from copy import deepcopy
    from app.services.hyperliquid_forward_flat_paper_policy import (
        CONSERVATIVE_LOCAL_FEE_POLICY_ID,
        derive_reviewable_conservative_hl_manifest,
    )
    from app.services.personal_paper_runtime import validate_policy
    from app.services.paper_financial_replay import validate_manifest
    from app.services.quality_dips_autonomous_enrollment import (
        WRITERS as QD_WRITERS,
    )
    from app.services.perp_operational_contract import WRITERS as HL_WRITERS
    from scripts.observation_runtime.personal_current_selected_dual_account_draft import (
        inspect as inspect_selected_draft,
    )
    from scripts.observation_runtime.personal_paper_inception import (
        validate_personal_inception,
    )
    from scripts.observation_runtime.personal_existing_native_resource_evidence import (
        inspect_two_lane_native_roots,
    )
    if (type(self_job) is not NativeOriginalSelfJob
            or type(release) is not NativePersonalReleaseIdentity
            or type(clock) is not NativeVersionSafePaperOperatorClock
            or type(runtime_id) is not str or not runtime_id
            or type(operator_acceptance_ids) is not dict
            or set(operator_acceptance_ids) != set(LANES)
            or hl_cost_amendment not in (
                None, CONSERVATIVE_LOCAL_FEE_POLICY_ID,
            )
            or (hl_source_identifiers is not None
                and (type(hl_source_identifiers) is not dict
                     or hl_source_identifiers
                     != HL_ORIGINAL_PUBLIC_SOURCE_REVIEW))
            or type(approved_unstamped_manifest_digests) is not dict
            or set(approved_unstamped_manifest_digests) != set(LANES)
            or any(type(operator_acceptance_ids[k]) is not str
                   or not operator_acceptance_ids[k]
                   or operator_acceptance_ids[k].startswith("UNACCEPTED")
                   for k in LANES)
            or len(set(operator_acceptance_ids.values())) != 2
            or any(type(approved_unstamped_manifest_digests[k]) is not str
                   or len(approved_unstamped_manifest_digests[k]) != 64
                   or any(c not in "0123456789abcdef"
                          for c in approved_unstamped_manifest_digests[k])
                   for k in LANES)):
        raise ValueError("PERSONAL_C_REVIEWED_ORIGINAL_ACCOUNT_INPUTS_REQUIRED")
    if self_job.verify() is not True:
        raise ValueError("PERSONAL_C_ORIGINAL_WINDOWS_SELF_JOB_GONE")
    admission = NativeFinancialReleaseAdmission(release=release)
    if admission.verify(release_digest=release.artifact_digest) is None:
        raise ValueError("PERSONAL_C_SELECTED_ORIGINAL_SOURCE_REQUIRED")
    if require_version_safe_release_digest(
            clock=clock, runtime_id=runtime_id,
            release_digest=release.artifact_digest) is not True:
        raise ValueError("PERSONAL_C_SELECTED_ONE_NTP_REQUIRED")
    approved_policy = validate_policy(personal_policy)
    roots_before = inspect_two_lane_native_roots()
    if (roots_before["native_root_total"] != 12
            or roots_before["existing_empty_root_namespaces"] != 12
            or roots_before["all_twelve_distinct_and_empty"] is not True):
        raise ValueError("PERSONAL_C_TWELVE_EMPTY_ORIGINAL_ROOTS_REQUIRED")
    selected = inspect_selected_draft()
    if (selected.get("status")
            != "TWO_CURRENT_RELEASE_ACCOUNT_DRAFTS_UNACCEPTED_NO_FINANCE"
            or selected.get("selected_artifact_digest")
            != release.artifact_digest
            or selected.get("original_native_root_count") != 12
            or selected.get("native_account_inceptions_published") != 0
            or selected.get("operator_financial_approval_accepted") is not False
            or selected.get("paper_start_authorized") is not False
            or selected.get("live_trading_authorized") is not False
            or set(selected.get("accounts", {})) != set(LANES)):
        raise ValueError("PERSONAL_C_UNACCEPTED_SELECTED_ORIGINAL_DRAFT_REQUIRED")
    # Finish expensive original release/draft verification BEFORE establishing
    # the new five-second issuer-sensitive opening timestamp.
    self_job.verify()
    clock.require_operational(runtime_id)
    opening = clock()
    if type(opening) is not int:
        raise ValueError("PERSONAL_C_INTEGER_ORIGINAL_UTC_REQUIRED")
    process = {"schema": "QD_OP_PROCESS_ID_V1", **self_job.identity}
    result = {}
    for lane, roles in (
        ("QUALITY_DIPS", QD_WRITERS),
        ("HYPERLIQUID", HL_WRITERS),
    ):
        old = selected["accounts"][lane]
        if (old.get("opening_timestamp_historical_stale") is not True
                or old.get("operator_approval_unissued") is not True
                or old.get("fee_rights_unreviewed") is not True
                or old.get("fs1_fs3_not_published") is not True
                or old.get("operational_market_rights_unaccepted") is not True):
            raise ValueError("PERSONAL_C_ORIGINAL_DRAFT_ALREADY_PROMOTED_REFUSED")
        manifest = deepcopy(old["unaccepted_historical_parameters"])
        enrollment = deepcopy(old["unaccepted_historical_enrollment"])
        scope = deepcopy(old["unaccepted_historical_report_scope"])
        validate_manifest(manifest)
        if (lane == "HYPERLIQUID" and
                manifest.get("schema") == "PAPER_EPOCH_PERP_OPERATIONAL_V1"):
            # The original R15 fee draft is immutable but incompatible with
            # today's conservative PAPER pilot. Never accept its 4.5/2 bps or
            # PENDING fee ID as financially approved.
            if hl_cost_amendment != CONSERVATIVE_LOCAL_FEE_POLICY_ID:
                raise ValueError(
                    "PERSONAL_C_CONSERVATIVE_HL_TERMS_REVIEW_REQUIRED"
                )
            manifest = derive_reviewable_conservative_hl_manifest(manifest)
            bindings = ("market_source", "instrument_cut", "funding_source")
            if any(manifest["perp_policy"][key].startswith("PENDING_")
                   for key in bindings):
                # Stage C must not permanently open an account whose immutable
                # manifest can only match placeholder public-source IDs.
                # The exact reviewed namespace will still need independent
                # source authentication at the later PAPER publication gate.
                if hl_source_identifiers != HL_ORIGINAL_PUBLIC_SOURCE_REVIEW:
                    raise ValueError(
                        "PERSONAL_C_HL_PENDING_SOURCE_IDS_MUST_BE_REVIEWED")
                for key in bindings:
                    manifest["perp_policy"][key] = hl_source_identifiers[key]
            elif hl_source_identifiers is not None and any(
                    manifest["perp_policy"][key]
                    != hl_source_identifiers[key] for key in bindings):
                raise ValueError("PERSONAL_C_HL_SOURCE_REVIEW_BINDING_CONFLICT")
            if any(
                    manifest["perp_policy"][key].startswith("PENDING_")
                    for key in bindings):
                raise ValueError("PERSONAL_C_HL_SOURCE_PLACEHOLDER_REFUSED")
            enrollment["policy_digest"] = digest(manifest["perp_policy"])
        # Approval binds ALL original finance terms except a fresh UTC
        # inception second that could not have been approved in advance.
        financial_terms = {k: v for k, v in manifest.items() if k != "opened_at"}
        if digest(financial_terms) != approved_unstamped_manifest_digests[lane]:
            raise ValueError("PERSONAL_C_FEES_RISK_AND_MANIFEST_TERMS_NOT_APPROVED")
        manifest["opened_at"] = opening
        validate_manifest(manifest)
        enrollment["writers"] = {
            role: deepcopy(process) for role in roles
        }
        enrollment["acceptance_id"] = operator_acceptance_ids[lane]
        enrollment["clock_source"] = SOURCE
        enrollment["inception_digest"] = digest(manifest)
        scope["policy_digest"] = digest(manifest)
        inception = {
            "profile": "PERSONAL_PAPER_ONLY_V1",
            "personal_policy": deepcopy(approved_policy),
            "lane": lane,
            "native_enrollment": enrollment,
            "parameters": manifest,
            "report_scope": scope,
        }
        verified_lane, verified_native, verified_manifest = (
            validate_personal_inception(inception)
        )
        if (verified_lane != lane
                or verified_native != enrollment
                or verified_manifest != manifest
                or manifest["release"] != release.artifact_digest
                or enrollment["release_digest"] != release.artifact_digest
                or manifest["opening_cash"] != "1000"
                or manifest["currency"] != (
                    "USD" if lane == "QUALITY_DIPS" else "USDC")
                or any(
                    enrollment["resources"][role]["native_id"]
                    != roots_before["lanes"][lane]["roots"][role]["native_id"]
                    for role in roots_before["lanes"][lane]["roots"]
                )):
            raise ValueError("PERSONAL_C_FINANCIAL_MANIFEST_OR_NATIVE_ROOT_CONFLICT")
        result[lane] = inception
    if (clock() - opening > 2
            or inspect_two_lane_native_roots() != roots_before
            or self_job.verify() is not True):
        raise ValueError("PERSONAL_C_FRESH_ORIGINAL_SELECTED_COHORT_EXPIRED")
    # Keep the SAME full selected native release handles alive through the
    # immediately following owner and journal admission; never reopen them.
    return strict(body(result)), admission


def bind_original_native_two_account_commissioner(
        *, self_job, release, clock, runtime_id, inceptions, admission,
        successor_root_scope=None):
    """Stage C->D handoff: bind two REAL native stores without writing either.

    Caller owns release/clock/self-Job and must close returned image handles.
    Requires separately reviewed fresh C results and retained native admission.
    No default account, local approval, journal image, provider or PAPER grant.
    """
    from pathlib import Path
    from scripts.observation_runtime.personal_coordination_store import (
        NativePersonalCoordinationImages,
    )
    from scripts.observation_runtime.personal_paper_inception import (
        validate_personal_inception,
    )
    from scripts.observation_runtime.personal_original_preinception_journal_permit import (
        MAX_MANIFEST_OPENING_AGE_SECONDS,
    )
    if (type(self_job) is not NativeOriginalSelfJob
            or type(release) is not NativePersonalReleaseIdentity
            or type(clock) is not NativeVersionSafePaperOperatorClock
            or type(admission) is not NativeFinancialReleaseAdmission
            or admission.release is not release
            or type(runtime_id) is not str or not runtime_id
            or type(inceptions) is not dict or set(inceptions) != set(LANES)):
        raise ValueError("PERSONAL_C_D_EXACT_RETAINED_NATIVE_INPUTS_REQUIRED")
    if successor_root_scope is not None:
        from scripts.observation_runtime.personal_successor_native_root_scope import (
            NativeSelectedSuccessorEpochRoots,
        )
        if (type(successor_root_scope) is not NativeSelectedSuccessorEpochRoots
                or successor_root_scope.exact_selected_release_bound(
                    release.root.name,release.artifact_digest) is not True):
            raise ValueError('PERSONAL_C_D_GENUINE_SUCCESSOR_ROOT_SCOPE_REQUIRED')
    self_job.verify()
    admission.verify(release_digest=release.artifact_digest)
    require_version_safe_release_digest(
        clock=clock, runtime_id=runtime_id,
        release_digest=release.artifact_digest,
    )
    enrollments, manifests = {}, {}
    for lane in LANES:
        entry = inceptions[lane]
        actual_lane, enrollment, manifest = validate_personal_inception(entry)
        if (actual_lane != lane
                or manifest["release"] != release.artifact_digest
                or enrollment["release_digest"] != release.artifact_digest
                or enrollment["inception_digest"] != digest(manifest)
                or manifest["opening_cash"] != "1000"
                or manifest["currency"] != (
                    "USD" if lane == "QUALITY_DIPS" else "USDC")
                or manifest["opened_at"] != inceptions[LANES[0]]["parameters"]["opened_at"]):
            raise ValueError("PERSONAL_C_D_FRESH_TWO_ACCOUNT_MANIFESTS_REQUIRED")
        if successor_root_scope is not None:
            scoped=successor_root_scope.plan['lanes'][lane]
            if (enrollment['epoch'] != scoped['epoch']
                    or any(enrollment['resources'][role]['path'] != path
                           for role,path in scoped['roots'].items())):
                raise ValueError('PERSONAL_C_D_SUCCESSOR_NEW_EPOCH_BINDING_REQUIRED')
        enrollments[lane] = enrollment
        manifests[lane] = manifest
    owner_args={'qd':enrollments[LANES[0]], 'perp':enrollments[LANES[1]],
                'release_digest':release.artifact_digest,
                'release_admission':admission}
    if successor_root_scope is not None:
        owner_args['successor_root_scope']=successor_root_scope
    owner = self_job.selected_two_account_owner(**owner_args)
    if (type(owner) is not RetainedSelectedNativeOwnerPreflight
            or owner._phase != "PREINCEPTION"
            or owner._release_admission is not admission
            or owner.verify_still_running() is not True):
        raise ValueError("PERSONAL_C_D_ONE_RETAINED_ORIGINAL_OWNER_REQUIRED")
    images = {}
    try:
        ledgers = {}
        for lane in LANES:
            resource = enrollments[lane]["resources"]["coordination"]
            images[lane] = NativePersonalCoordinationImages(
                root=resource["path"], native_root=resource["native_id"],
                enrollment_digest=digest(enrollments[lane]),
            )
            ledgers[lane] = PersonalNativeCoordination(
                manifest=manifests[lane], images=images[lane],
                path=Path(resource["path"]) / "coordination.image",
            )
        commissioner = NativeSelectedPersonalAccountCommissioner(
            owner=owner, release=release, clock=clock, ledgers=ledgers,
            enrollments=enrollments, runtime_id=runtime_id,
        )
        now = clock()
        opened = manifests[LANES[0]]["opened_at"]
        if (type(now) is not int
                or not 0 <= now - opened <= MAX_MANIFEST_OPENING_AGE_SECONDS
                or commissioner.phase != "PREINCEPTION_READY"
                or owner.verify_still_running() is not True):
            raise ValueError("PERSONAL_C_D_ORIGINAL_MANIFEST_FRESHNESS_EXPIRED")
        return commissioner, images
    except BaseException:
        # Only our own read/mutex handles are released. Never delete or reset
        # any original native root; no financial journal was created here.
        for item in reversed(tuple(images.values())):
            try:
                item.close()
            except BaseException:
                pass
        raise


def prepare_and_bind_reviewed_original_native_accounts(
        *, self_job, release, clock, runtime_id, personal_policy,
        operator_acceptance_ids, approved_unstamped_manifest_digests,
        hl_cost_amendment=None, hl_source_identifiers=None,
        successor_root_scope=None, reviewed_successor_terms=None):
    """Production C->D admission in ONE selected native process.

    Original R26 keeps its original preinception path. A distinct successor
    may enter only through the separately verified historical-custody and
    new-root-scope Stage C path, never by reusing the R26 draft, process, or
    accounts. Later genuine exact local journal/activation approvals remain
    mandatory; this composition never grants PAPER or live trading.
    """
    bind_scope={}
    if successor_root_scope is None:
        if reviewed_successor_terms is not None:
            raise ValueError('PERSONAL_C_D_SUCCESSOR_TERMS_WITHOUT_NATIVE_SCOPE_REFUSED')
        inceptions, admission = prepare_original_fresh_two_account_inceptions(
            self_job=self_job, release=release, clock=clock, runtime_id=runtime_id,
            personal_policy=personal_policy,
            operator_acceptance_ids=operator_acceptance_ids,
            approved_unstamped_manifest_digests=approved_unstamped_manifest_digests,
            hl_cost_amendment=hl_cost_amendment,
            hl_source_identifiers=hl_source_identifiers,
        )
    else:
        if (reviewed_successor_terms is None
                or hl_cost_amendment is not None or hl_source_identifiers is not None):
            raise ValueError('PERSONAL_C_D_SUCCESSOR_CANNOT_USE_ORIGINAL_R26_DRAFT_AMENDMENTS')
        from scripts.observation_runtime.personal_successor_stage_c_candidates import (
            prepare_fresh_successor_account_candidates,
        )
        inceptions, admission = prepare_fresh_successor_account_candidates(
            self_job=self_job, release=release, clock=clock, runtime_id=runtime_id,
            successor_root_scope=successor_root_scope,
            reviewed_successor_terms=reviewed_successor_terms,
            personal_policy=personal_policy,
            operator_acceptance_ids=operator_acceptance_ids,
            approved_unstamped_manifest_digests=approved_unstamped_manifest_digests,
        )
        bind_scope['successor_root_scope']=successor_root_scope
    return bind_original_native_two_account_commissioner(
        self_job=self_job, release=release, clock=clock, runtime_id=runtime_id,
        inceptions=inceptions, admission=admission, **bind_scope,
    )


class NativeSelectedPersonalAccountCommissioner:
    """No automatic approval; only coordinates existing installed native issuers.

    All four sequential approval/publication phases happen within the SAME selected
    process and owner, with fresh externally reviewed per-phase records.
    Caller owns and finally closes its original release, clock, Job and ledgers.
    """

    def __init__(self, *, owner, release, clock, ledgers, enrollments, runtime_id):
        if (type(owner) is not RetainedSelectedNativeOwnerPreflight
                or type(release) is not NativePersonalReleaseIdentity
                or type(clock) is not NativeVersionSafePaperOperatorClock
                or type(runtime_id) is not str or not runtime_id
                or type(ledgers) is not dict or set(ledgers) != set(LANES)
                or type(enrollments) is not dict or set(enrollments) != set(LANES)
                or owner._phase != "PREINCEPTION"
                or type(getattr(owner, "_release_admission", None))
                is not NativeFinancialReleaseAdmission
                or owner._release_admission.release is not release):
            raise ValueError("PERSONAL_COMMISSION_EXACT_SELECTED_ORIGINAL_OWNER_REQUIRED")
        if owner.verify_still_running() is not True:
            raise ValueError("PERSONAL_COMMISSION_ORIGINAL_OWNER_NOT_LIVE")
        release.verify(release_digest=owner.release_digest)
        owner._release_admission.verify(release_digest=owner.release_digest)
        if require_version_safe_release_digest(
            clock=clock, runtime_id=runtime_id,
            release_digest=owner.release_digest,
        ) is not True:
            raise ValueError("PERSONAL_COMMISSION_ONE_SELECTED_NTP_REQUIRED")
        roots = owner._inspect_roots()
        if (roots["native_root_total"] != 12
                or roots["all_twelve_distinct_and_empty"] is not True):
            raise ValueError("PERSONAL_COMMISSION_ORIGINAL_ROOTS_NOT_EMPTY")
        qd, hl = enrollments["QUALITY_DIPS"], enrollments["HYPERLIQUID"]
        if (owner.require_exact_roster(qd=qd, perp=hl) is not True
                or any(
                    type(ledgers[lane]) is not PersonalNativeCoordination
                    or ledgers[lane].manifest["release"] != owner.release_digest
                    or ledgers[lane].manifest.get("opening_cash") != "1000"
                    or ledgers[lane].manifest.get("currency")
                    != ("USD" if lane == "QUALITY_DIPS" else "USDC")
                    or ledgers[lane].images.enrollment != digest(enrollments[lane])
                    or ledgers[lane].manifest.get("opened_at") is None
                    for lane in LANES)):
            raise ValueError("PERSONAL_COMMISSION_EXACT_TWO_ORIGINAL_MANIFESTS_REQUIRED")
        self.owner = owner
        self.release = release
        self.clock = clock
        self.ledgers = ledgers
        self.enrollments = {lane: strict(body(enrollments[lane])) for lane in LANES}
        self.runtime_id = runtime_id
        self._ports = (owner, release, clock, ledgers, runtime_id)
        self._digest = {
            lane: digest(self.enrollments[lane]) for lane in LANES
        }
        self._state = "PREINCEPTION_READY"
        self._activation_binding = None
        self._initial_activation_root = None
        self._post_data_result = None
        self._post_data_operator_bound = False

    @property
    def phase(self):
        return self._state

    def _require(self, phase):
        if self._state != phase:
            raise ValueError("PERSONAL_COMMISSION_PHASE_REPLAY_OR_UNKNOWN")
        if ((self.owner, self.release, self.clock, self.ledgers,
             self.runtime_id) != self._ports):
            raise ValueError("PERSONAL_COMMISSION_RETAINED_PORT_CHANGED")
        if any(
            digest(self.enrollments[lane]) != self._digest[lane]
            for lane in LANES
        ):
            raise ValueError("PERSONAL_COMMISSION_ACCOUNT_ENROLLMENT_CHANGED")
        if self.owner.verify_still_running() is not True:
            raise ValueError("PERSONAL_COMMISSION_ORIGINAL_OWNER_GONE")
        if self.owner._release_admission.release is not self.release:
            raise ValueError("PERSONAL_COMMISSION_ORIGINAL_RELEASE_LOST")
        self.owner._release_admission.verify(release_digest=self.owner.release_digest)
        self.clock.require_operational(self.runtime_id)

    def initialize_two_journals_once(self, *, operator_scope):
        """Stage D: this is a genuine ONE-WAY original financial-root effect."""
        self._require("PREINCEPTION_READY")
        if self.owner._phase != "PREINCEPTION":
            raise ValueError("PERSONAL_COMMISSION_ORIGINAL_JOURNAL_PHASE_REFUSED")
        if type(operator_scope) is not dict or not operator_scope:
            raise ValueError("PERSONAL_COMMISSION_EXPLICIT_JOURNAL_APPROVAL_REQUIRED")
        # A failed constructor may leave all roots empty; caller must still
        # inspect them. After entering original publisher, NEVER auto-retry.
        permit = NativeOriginalTwoJournalPreinceptionPermit(
            job=self.owner, clock=self.clock, runtime_id=self.runtime_id,
            ledgers=self.ledgers, operator_scope=operator_scope,
        )
        self._state = "JOURNALS_UNKNOWN"
        result = permit.publish_both_original_journals_once()
        if (result.get("native_initial_journal_count") != 2
                or result.get("paper_start_authorized") is not False
                or self.owner._phase != "PREINCEPTION_COORDINATION_READY"):
            raise ValueError("PERSONAL_COMMISSION_TWO_NATIVE_JOURNALS_UNVERIFIED")
        self._state = "TWO_JOURNALS_ACKNOWLEDGED"
        return strict(body(result))

    def publish_initialization_activation_once(
        self, *, root, record_path, policy_path, accounts_path,
        qd_enrollment_path, perp_enrollment_path,
    ):
        """Stage E: require an already reviewed original LOCAL_OPERATOR record.

        No default/operator record is created, and only READ_ONLY+INITIALIZE
        can be accepted by the original preinception activation guard.
        """
        self._require("TWO_JOURNALS_ACKNOWLEDGED")
        if self.owner._phase != "PREINCEPTION_COORDINATION_READY":
            raise ValueError("PERSONAL_COMMISSION_TWO_JOURNAL_ACKS_NOT_LIVE")
        paths = (root, record_path, policy_path, accounts_path,
                 qd_enrollment_path, perp_enrollment_path)
        if any(type(x) is not str or not x for x in paths):
            raise ValueError("PERSONAL_COMMISSION_EXPLICIT_ACTIVATION_INPUTS_REQUIRED")
        self._state = "ACTIVATION_UNKNOWN"
        # Original publisher reopens and authenticates the operator file,
        # native account enrolments, exact policy, UTC and selected process.
        result = commission_native_activation(
            root=root, record_path=record_path, policy_path=policy_path,
            release_digest=self.owner.release_digest,
            accounts_path=accounts_path, expected_clock_source=SOURCE,
            runtime_id=self.runtime_id,
            qd_enrollment_path=qd_enrollment_path,
            perp_enrollment_path=perp_enrollment_path,
            clock_profile=CLOCK_PROFILE, owned_job=self.owner,
            prequalified_clock=self.clock,
        )
        if (type(result) is not dict
                or result.get("schema") != "ATLAS_PERSONAL_ACTIVATION_PUBLICATION_V1"
                or result.get("status") != "NATIVE_VERIFIED"
                or type(result.get("binding")) is not dict
                or result.get("paper_start_authorized") is not False
                or result.get("live_trading_authorized") is not False):
            raise ValueError("PERSONAL_COMMISSION_ORIGINAL_ACTIVATION_UNVERIFIED")
        self._activation_binding = strict(body(result["binding"]))
        self._initial_activation_root = root
        self._state = "INITIALIZE_ACTIVATION_ACKNOWLEDGED"
        return strict(body(result))

    def initialize_two_accounts_once(self, *, reader, operators,
                                     inception_enrollments):
        """Stage F: two original FS1/FS3 simulated inceptions, never trading.

        The original publisher and owner are retained throughout both writes.
        If either account fails, the first may exist; UNKNOWN must be
        reconciled instead of starting over or silently deleting files.
        """
        self._require("INITIALIZE_ACTIVATION_ACKNOWLEDGED")
        if (type(reader) is not NativePersonalActivationReader
                or type(operators) is not dict or set(operators) != set(LANES)
                or type(inception_enrollments) is not dict
                or set(inception_enrollments) != set(LANES)
                or self.owner._phase != "PREINCEPTION_COORDINATION_READY"):
            raise ValueError("PERSONAL_COMMISSION_GENUINE_INITIALIZATION_PORTS_REQUIRED")
        if any(
            inception_enrollments[lane].get("native_enrollment")
            != self.enrollments[lane] for lane in LANES
        ):
            raise ValueError("PERSONAL_COMMISSION_EXACT_ACCOUNT_ROSTERS_REQUIRED")
        self._state = "TWO_ACCOUNTS_UNKNOWN"
        owners = {}
        try:
            # This original production factory performs ALL actual native
            # operator, activation reader, release, clock, ledger checks.
            pair, owners = assemble_selected_two_account_inception(
                job=self.owner, release=self.release, clock=self.clock,
                reader=reader, operators=operators, ledgers=self.ledgers,
                enrollments=inception_enrollments, runtime_id=self.runtime_id,
            )
            result = pair.publish_both_once()
            if (result.get("status")
                != "TWO_NATIVE_SIMULATED_ACCOUNT_OPENINGS_ACKNOWLEDGED"
                    or result.get("paper_start_authorized") is not False
                    or result.get("live_trading_authorized") is not False
                    or self.owner._phase != "INITIAL_READBACK_ONLY"
                    or self.owner.verify_still_running() is not True):
                raise ValueError("PERSONAL_COMMISSION_TWO_FINANCIAL_ACCOUNT_ACKS_REQUIRED")
        finally:
            # These native publishers own writer HANDLE capabilities.
            # Their ownership must never outlive this one-shot operation.
            # Any failed handle close leaves the account outcome UNKNOWN;
            # still attempt to close every other owned writer capability.
            close_error = None
            for owner in reversed(tuple(owners.values())):
                try:
                    owner.close()
                except BaseException as error:
                    if close_error is None:
                        close_error = error
            if close_error is not None:
                raise close_error
        self._state = "TWO_ACCOUNTS_ACKNOWLEDGED"
        return strict(body(result))

    def publish_initialization_activation_and_open_both_once(
            self, *, root, record_path, policy_path, accounts_path,
            qd_enrollment_path, perp_enrollment_path, personal_policy,
            inception_enrollments):
        """Real E->F handoff under ONE selected owner and original approval.

        Constructs the genuine reader and both native operator authorities from
        the activation publisher's independently bound native root/file IDs.
        Never creates the local operator approval or an AUTO_PAPER grant.
        A partial/uncertain activation or account attempt is terminal.
        """
        from app.services.personal_paper_runtime import validate_policy
        from scripts.observation_runtime.personal_local_authority import (
            NativePersonalOperatorAuthority,
        )
        from scripts.observation_runtime.personal_paper_inception import (
            validate_personal_inception,
        )

        self._require("TWO_JOURNALS_ACKNOWLEDGED")
        approved_policy = validate_policy(personal_policy)
        if (type(inception_enrollments) is not dict
                or set(inception_enrollments) != set(LANES)):
            raise ValueError("PERSONAL_E_F_REVIEWED_TWO_INCEPTIONS_REQUIRED")
        for lane in LANES:
            entry = inception_enrollments[lane]
            actual_lane, native, manifest = validate_personal_inception(entry)
            if (actual_lane != lane
                    or native != self.enrollments[lane]
                    or manifest != self.ledgers[lane].manifest
                    or entry.get("personal_policy") != approved_policy):
                raise ValueError("PERSONAL_E_F_ONE_APPROVED_ACCOUNT_POLICY_REQUIRED")
        activation = self.publish_initialization_activation_once(
            root=root, record_path=record_path, policy_path=policy_path,
            accounts_path=accounts_path, qd_enrollment_path=qd_enrollment_path,
            perp_enrollment_path=perp_enrollment_path,
        )
        # Publication may have committed before an unreadable/malformed
        # receipt returned. Never replay E or proceed to financial FS1/FS3.
        if (activation.get("root") != root
                or type(activation.get("native_root")) is not list
                or len(activation["native_root"]) != 3
                or any(type(v) is not int or v < 0 for v in activation["native_root"])
                or activation.get("paper_start_authorized") is not False
                or activation.get("live_trading_authorized") is not False):
            self._state = "ACTIVATION_UNKNOWN"
            raise ValueError("PERSONAL_E_F_ORIGINAL_NATIVE_ACTIVATION_ROOT_REFUSED")
        operators = {}
        try:
            reader = NativePersonalActivationReader(
                root=root, native_root=activation["native_root"],
                binding=activation["binding"],
            )
            for lane in LANES:
                operators[lane] = NativePersonalOperatorAuthority(
                    policy=approved_policy, enrollment=self.enrollments[lane],
                    reader=reader, clock=self.clock, runtime_id=self.runtime_id,
                    clock_profile=CLOCK_PROFILE, accounts=self._digest,
                )
            result = self.initialize_two_accounts_once(
                reader=reader, operators=operators,
                inception_enrollments=inception_enrollments,
            )
            return {"schema": "ATLAS_PERSONAL_ORIGINAL_E_F_ACCOUNT_OPENING_V1",
                    "initial_activation": strict(body(activation)),
                    "simulated_accounts": strict(body(result)),
                    "paper_start_authorized": False,
                    "live_trading_authorized": False}
        except BaseException:
            if self._state == "INITIALIZE_ACTIVATION_ACKNOWLEDGED":
                self._state = "TWO_ACCOUNTS_UNKNOWN"
            raise
        finally:
            for operator in reversed(tuple(operators.values())):
                operator.revoke()

    def initialize_reviewed_original_two_accounts_once(
            self, *, operator_scope, initial_activation, personal_policy,
            inception_enrollments):
        """One original D-E-F sequence, only under independent human scopes.

        Validate the genuine existing signed-in-session initialization record
        BEFORE creating either irreversible financial journal. Once effects
        begin, every uncertainty is terminal. Does not create an approval,
        switch a provider or authorize PAPER/real-money operation.
        """
        from app.services.personal_paper_runtime import (
            validate_activation_record, validate_policy,
        )
        from scripts.observation_runtime.personal_activation_commission import (
            read_bounded_activation_input,
        )
        from scripts.volume_inspector.windows_output import current_sid

        self._require("PREINCEPTION_READY")
        required = {
            "root", "record_path", "policy_path", "accounts_path",
            "qd_enrollment_path", "perp_enrollment_path",
        }
        if (type(initial_activation) is not dict
                or set(initial_activation) != required
                or any(type(value) is not str or not value
                       for value in initial_activation.values())
                or type(operator_scope) is not dict or not operator_scope):
            raise ValueError("PERSONAL_D_F_EXACT_EXISTING_APPROVAL_INPUTS_REQUIRED")
        policy = validate_policy(personal_policy)
        # Catch absent, stale or conflicting E inputs BEFORE D creates a
        # financial coordination journal. Original E still re-reads and
        # re-verifies their native root identity and selected-process scope.
        record = read_bounded_activation_input(
            initial_activation["record_path"], role="record",
        )
        policy_on_disk = read_bounded_activation_input(
            initial_activation["policy_path"], role="policy",
        )
        accounts_on_disk = read_bounded_activation_input(
            initial_activation["accounts_path"], role="accounts",
        )
        qd_on_disk = read_bounded_activation_input(
            initial_activation["qd_enrollment_path"],
            role="quality_dips_enrollment",
        )
        hl_on_disk = read_bounded_activation_input(
            initial_activation["perp_enrollment_path"],
            role="hyperliquid_enrollment",
        )
        if (validate_policy(policy_on_disk) != policy
                or accounts_on_disk != self._digest
                or qd_on_disk != self.enrollments[LANES[0]]
                or hl_on_disk != self.enrollments[LANES[1]]):
            raise ValueError("PERSONAL_D_F_EXISTING_INITIALIZATION_FILES_CONFLICT")
        now = self.clock()
        if (type(record) is not dict
                or record.get("actions") not in (
                    ["READ_ONLY", "INITIALIZE_SIMULATED_ACCOUNTS"],
                    ["INITIALIZE_SIMULATED_ACCOUNTS", "READ_ONLY"],
                )
                or record.get("accounts") != self._digest):
            raise ValueError("PERSONAL_D_F_EXACT_INITIALIZATION_SCOPE_REQUIRED")
        for action in ("READ_ONLY", "INITIALIZE_SIMULATED_ACCOUNTS"):
            validate_activation_record(
                record, policy=policy, operator_id=current_sid(),
                release=self.owner.release_digest, accounts=self._digest,
                now=now, action=action,
            )
        # Stage D is intentionally the FIRST native financial write.
        # The original one-shot issuer verifies the user's distinct journal
        # approval, fresh image digests, 5-second UTC and 12 root identities.
        journals = self.initialize_two_journals_once(
            operator_scope=operator_scope,
        )
        opened = self.publish_initialization_activation_and_open_both_once(
            **initial_activation, personal_policy=policy,
            inception_enrollments=inception_enrollments,
        )
        return {
            "schema": "ATLAS_PERSONAL_ORIGINAL_D_F_TWO_ACCOUNT_SEQUENCE_V1",
            "journals": strict(body(journals)),
            "activation": strict(body(opened["initial_activation"])),
            "simulated_accounts": strict(body(opened["simulated_accounts"])),
            "paper_start_authorized": False,
            "live_trading_authorized": False,
        }

    def publish_postinception_data_activation_once(
        self, *, root, record_path, policy_path, accounts_path,
        qd_enrollment_path, perp_enrollment_path,
    ):
        """Stage G: separately approved CONNECT_APPROVED_DATA, no trading.

        This is NOT a source subscription or a PAPER entry approval.
        Actual approved-source connection, QD archive genesis and issuer
        currentness remain separate independently verified operations.
        """
        self._require("TWO_ACCOUNTS_ACKNOWLEDGED")
        if self.owner._phase not in (
                "INITIAL_READBACK_ONLY", "CURRENT_READBACK_ONLY"):
            raise ValueError("PERSONAL_COMMISSION_TWO_FS1_FS3_ACCOUNTS_REQUIRED")
        from scripts.observation_runtime.personal_activation_commission import (
            read_bounded_activation_input,
        )
        import ntpath
        paths = (root, record_path, policy_path, accounts_path,
                 qd_enrollment_path, perp_enrollment_path)
        if (any(type(p) is not str or not p
                or not ntpath.normcase(p).startswith("d:\\") for p in paths)
                or ntpath.normcase(ntpath.normpath(root)) ==
                ntpath.normcase(ntpath.normpath(self._initial_activation_root))):
            raise ValueError("PERSONAL_COMMISSION_DISTINCT_D_ONLY_DATA_ACTIVATION_REQUIRED")
        record = read_bounded_activation_input(record_path, role="record")
        if (type(record.get("actions")) is not list
                or len(record["actions"]) != 2
                or set(record["actions"]) != {"READ_ONLY", "CONNECT_APPROVED_DATA"}
                or record.get("origin") != "LOCAL_OPERATOR"
                or record.get("release_digest") != self.owner.release_digest
                or record.get("accounts") != self._digest):
            raise ValueError("PERSONAL_COMMISSION_POSTINIT_ONLY_EXPLICIT_DATA_ACTION")
        self._state = "DATA_ACTIVATION_UNKNOWN"
        # Re-enter the original publisher with EXACTLY the same retained
        # original selected process, clock and real current account rosters.
        result = commission_native_activation(
            root=root, record_path=record_path, policy_path=policy_path,
            release_digest=self.owner.release_digest,
            accounts_path=accounts_path, expected_clock_source=SOURCE,
            runtime_id=self.runtime_id,
            qd_enrollment_path=qd_enrollment_path,
            perp_enrollment_path=perp_enrollment_path,
            clock_profile=CLOCK_PROFILE, owned_job=self.owner,
            prequalified_clock=self.clock,
        )
        if (type(result) is not dict
                or result.get("schema") != "ATLAS_PERSONAL_ACTIVATION_PUBLICATION_V1"
                or result.get("status") != "NATIVE_VERIFIED"
                or type(result.get("binding")) is not dict
                or result.get("paper_start_authorized") is not False
                or result.get("live_trading_authorized") is not False):
            raise ValueError("PERSONAL_COMMISSION_ORIGINAL_DATA_ACTIVATION_UNVERIFIED")
        self._post_data_result = strict(body(result))
        self._state = "POSTINCEPTION_DATA_ACTIVATION_ACKNOWLEDGED"
        return strict(body(result))

    def bind_verified_postinception_data_operators_once(
            self, *, personal_policy):
        """Stage G->H: construct the TWO original approved data-only operators.

        The Hyperliquid native authority cannot accept CONNECT_APPROVED_DATA
        in its original first-inception mode. Construct a NEW one instead,
        bound to genuine ACK'd QD+HL accounts, the retained selected owner,
        original native G activation, and the exact same version-safe UTC.
        No fresh approval, provider connection, root/image write, PAPER
        account mutation or financial Start is performed by this method.
        """
        from app.services.personal_paper_runtime import validate_policy
        from scripts.observation_runtime.personal_local_authority import (
            NativePersonalOperatorAuthority,
        )
        self._require("POSTINCEPTION_DATA_ACTIVATION_ACKNOWLEDGED")
        if self._post_data_operator_bound:
            raise ValueError("PERSONAL_G_H_DATA_OPERATOR_PORT_ALREADY_BOUND")
        data = self._post_data_result
        if (type(data) is not dict
                or data.get("schema") != "ATLAS_PERSONAL_ACTIVATION_PUBLICATION_V1"
                or data.get("status") != "NATIVE_VERIFIED"
                or type(data.get("root")) is not str
                or type(data.get("native_root")) is not list
                or len(data["native_root"]) != 3
                or any(type(v) is not int or v < 0
                       for v in data["native_root"])
                or type(data.get("binding")) is not dict
                or data.get("paper_start_authorized") is not False
                or data.get("live_trading_authorized") is not False
                or self.owner._phase not in (
                    "INITIAL_READBACK_ONLY", "CURRENT_READBACK_ONLY")
                or self.owner.require_exact_roster(
                    qd=self.enrollments["QUALITY_DIPS"],
                    perp=self.enrollments["HYPERLIQUID"]) is not True):
            raise ValueError("PERSONAL_G_H_EXACT_ORIGINAL_POSTINIT_DATA_ACK_REQUIRED")
        self._post_data_operator_bound = True
        ports = {}
        try:
            reader = NativePersonalActivationReader(
                root=data["root"], native_root=data["native_root"],
                binding=data["binding"],
            )
            policy = validate_policy(personal_policy)
            for lane in LANES:
                args = {
                    "policy": policy, "enrollment": self.enrollments[lane],
                    "reader": reader, "clock": self.clock,
                    "runtime_id": self.runtime_id,
                    "clock_profile": CLOCK_PROFILE, "accounts": self._digest,
                }
                if lane == "HYPERLIQUID":
                    args.update(
                        postinception_owner=self.owner,
                        qd_enrollment=self.enrollments["QUALITY_DIPS"],
                    )
                ports[lane] = NativePersonalOperatorAuthority(**args)
                record = ports[lane].activation("CONNECT_APPROVED_DATA")
                if (type(record) is not dict
                        or type(record.get("actions")) is not list
                        or len(record["actions"]) != 2
                        or set(record["actions"])
                        != {"READ_ONLY", "CONNECT_APPROVED_DATA"}
                        or record.get("origin") != "LOCAL_OPERATOR"
                        or record.get("release_digest") != self.owner.release_digest
                        or record.get("accounts") != self._digest):
                    raise ValueError(
                        "PERSONAL_G_H_SEPARATELY_APPROVED_SOURCE_ONLY_SCOPE_REQUIRED"
                    )
            self.clock.require_operational(self.runtime_id)
            if (self.owner.verify_still_running() is not True
                    or ports["QUALITY_DIPS"].reader is not reader
                    or ports["HYPERLIQUID"].reader is not reader):
                raise ValueError("PERSONAL_G_H_NATIVE_OWNER_OR_ACTIVATION_LOST")
            return {
                "schema": "ATLAS_PERSONAL_G_H_ORIGINAL_SOURCE_OPERATOR_PORTS_V1",
                "reader": reader,
                "operators": ports,
                "source_provider_rights_accepted": False,
                "financial_paper_start_authorized": False,
                "live_trading_authorized": False,
            }
        except BaseException:
            for operator in reversed(tuple(ports.values())):
                operator.revoke()
            raise
