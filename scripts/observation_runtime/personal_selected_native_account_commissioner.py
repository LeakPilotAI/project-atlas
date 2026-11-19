"""Original selected personal PAPER account commissioning, stages D/E/F.

One SAME selected native Windows process retains the original installation
inventory, Windows Job, genuine original financial writer-roster identities
and independent operational UTC through the existing original:
  D: two coordination journals (separate exact operator scope)
  E: preinception READ_ONLY + INITIALIZE_SIMULATED_ACCOUNTS activation record
  F: two real PAPER-only $1,000-account initial durable native publications

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


class NativeSelectedPersonalAccountCommissioner:
    """No automatic approval; only coordinates existing installed native issuers.

    All three irreversible phases happen within the SAME original selected
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
        from scripts.observation_runtime.personal_existing_native_resource_evidence import (
            inspect_two_lane_native_roots,
        )
        roots = inspect_two_lane_native_roots()
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
                or result.get("paper_start_authorized") is True
                or result.get("live_trading_authorized") is True):
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
                or result.get("paper_start_authorized") is True
                or result.get("live_trading_authorized") is True):
            raise ValueError("PERSONAL_COMMISSION_ORIGINAL_DATA_ACTIVATION_UNVERIFIED")
        self._state = "POSTINCEPTION_DATA_ACTIVATION_ACKNOWLEDGED"
        return strict(body(result))
