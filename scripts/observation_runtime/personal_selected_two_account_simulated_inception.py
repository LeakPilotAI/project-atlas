"""Selected-native, once-only two-lane SIMULATED PAPER account opening.

Import-only installed process orchestration. No account, activation, market,
external broker, live order, Start, Stop, or job creation. It requires two
pre-enrolled *real* native publishers, a separately issued LOCAL_OPERATOR
read+initialize activation, an independently qualified native clock, and
the original held installed Windows Job/process. No self-signed default.

A failure after the attempt is UNKNOWN: never replay one or both accounts.
After two durable FS1/FS3 ACKs, ownership stays READBACK_ONLY; no PAPER
financial operation lease or trading permission is conferred.
"""
from __future__ import annotations

from app.services.paper_financial_replay import body, digest
from app.services.personal_native_coordination import PersonalNativeCoordination
from app.services.personal_paper_runtime import (
    PersonalOperatorInstallation,
)
from app.services.personal_publication_custody import PersonalPublicationCustody

from scripts.observation_runtime.personal_coordination_store import (
    NativePersonalCoordinationImages,
)
from scripts.observation_runtime.personal_installation_technical import (
    NativePersonalTechnicalChecks,
)
from scripts.observation_runtime.personal_local_authority import (
    NativePersonalOperatorAuthority,
)
from scripts.observation_runtime.personal_native_selected_owned_job_preflight import (
    RetainedSelectedNativeOwnerPreflight,
)
from scripts.observation_runtime.personal_paper_inception import (
    NativePersonalInceptionFiles,
    NativePersonalInitialReadback,
    PersonalInceptionBootstrap,
    PersonalInceptionPublisher,
    PersonalPublicationIssuer,
    validate_personal_inception,
)
from scripts.observation_runtime.personal_version_safe_release_clock import (
    NativeVersionSafePaperOperatorClock,
    require_version_safe_release_digest,
)
from scripts.observation_runtime.personal_writer_ownership import (
    NativePersonalWriterOwnership,
)
from scripts.observation_runtime.quality_dips_read_service import observe_self

SCHEMA = "ATLAS_SELECTED_NATIVE_TWO_ACCOUNT_SIMULATED_INCEPTION_HANDOFF_V1"
ACTIONS = frozenset(("READ_ONLY", "INITIALIZE_SIMULATED_ACCOUNTS"))


class NativeSelectedTwoAccountSimulatedInception:
    """Uses existing authentic *precommissioned* ports. Never synthesizes them."""

    def __init__(self, *, original_job, quality_dips, hyperliquid):
        if (type(original_job) is not RetainedSelectedNativeOwnerPreflight
                or type(quality_dips) is not PersonalInceptionPublisher
                or type(hyperliquid) is not PersonalInceptionPublisher
                or quality_dips is hyperliquid):
            raise ValueError("SELECTED_INCEPTION_ORIGINAL_JOB_AND_TWO_NATIVE_PUBLISHERS_REQUIRED")
        self.original_job = original_job
        self.publishers = (quality_dips, hyperliquid)
        self._used = False
        self._admitted = False
        self._binding = None
        self._verify(entering=True)

    def _verify(self, *, entering=False):
        owner = self.original_job
        q_pub, h_pub = self.publishers
        if (self._used or owner._phase != "PREINCEPTION_COORDINATION_READY"
                or getattr(owner, "_two_lane_inception_claimed", False)):
            raise ValueError("SELECTED_INCEPTION_ALREADY_ATTEMPTED_OR_OWNER_NOT_EMPTY")
        # The existing parked-job probe runs in the PARENT while the genuine
        # writer roster points at its CHILD. That parent must never run the
        # financial publisher with a borrowed child identity. This correctly
        # blocks production until the ORIGINAL installed child owns the
        # financial publisher and retained Job handles in its own process.
        observed = observe_self()
        if (type(observed) is not dict
                or observed != getattr(owner, "_identity", None)):
            raise ValueError("SELECTED_INCEPTION_MUST_EXECUTE_IN_ORIGINAL_WRITER_PROCESS")
        if (type(owner.origin) is not dict
                or owner.origin.get("selected_artifact_digest_bound") is not True
                or any(owner.origin.get(k) is not False for k in (
                    "financial_writer_lease_issued", "financial_activation_published",
                    "paper_start_authorized", "live_trading_authorized"))):
            raise ValueError("SELECTED_INCEPTION_INSTALLED_ORIGINAL_SOURCE_REFUSED")

        bindings = []
        sid_clock = None
        activation_reader = None
        accounts = None
        for lane, publisher in (("QUALITY_DIPS", q_pub),
                                ("HYPERLIQUID", h_pub)):
            bootstrap = publisher.bootstrap
            if (type(bootstrap) is not PersonalInceptionBootstrap
                    or type(publisher.files) is not NativePersonalInceptionFiles
                    or type(publisher.ownership) is not NativePersonalWriterOwnership
                    or type(bootstrap.readback) is not NativePersonalInitialReadback
                    or type(bootstrap.issuer) is not PersonalPublicationIssuer
                    or type(bootstrap.publication) is not PersonalPublicationCustody
                    or publisher.custody is not bootstrap.publication):
                raise ValueError("SELECTED_INCEPTION_EXACT_ONCE_ONLY_NATIVE_PORTS_REQUIRED")
            validated_lane, enrollment, manifest = validate_personal_inception(
                bootstrap.enrollment)
            if (validated_lane != lane
                    or manifest["opening_cash"] != "1000"
                    or enrollment["release_digest"] != owner.release_digest
                    or publisher.ownership.enrollment != enrollment
                    or publisher.ownership.inception_intent != bootstrap.scope()
                    or publisher.ownership._lane != lane
                    or publisher.ownership.read_only
                    or publisher.ownership.ledger is not bootstrap.publication.ledger):
                raise ValueError("SELECTED_INCEPTION_TWO_NATIVE_ACCOUNTS_NOT_BOUND")
            ledger = publisher.ownership.ledger
            installation = bootstrap.issuer.installation
            if (type(ledger) is not PersonalNativeCoordination
                    or type(ledger.images) is not NativePersonalCoordinationImages
                    or ledger.images.enrollment != digest(enrollment)
                    or type(installation) is not PersonalOperatorInstallation
                    or type(installation.identity) is not NativePersonalOperatorAuthority
                    or type(installation.technical) is not NativePersonalTechnicalChecks
                    or installation.technical.bootstrap is not bootstrap
                    or installation.technical.ownership is not publisher.ownership
                    or installation.technical.ledger is not ledger
                    or installation.technical.files is not publisher.files
                    or installation.technical.current is not None
                    or installation.technical.engine is not None
                    or installation.release != owner.release_digest
                    or body(installation.policy) != body(bootstrap.enrollment["personal_policy"])):
                raise ValueError("SELECTED_INCEPTION_GENUINE_FINANCIAL_TECHNICAL_ISSUER_REQUIRED")
            operator = installation.identity
            clock = operator.clock
            if (type(clock) is not NativeVersionSafePaperOperatorClock
                    or installation.clock is not clock
                    or bootstrap.clock is not clock
                    or installation.technical.clock is not clock
                    or operator._lane != lane
                    or operator.enrollment != enrollment
                    or operator.clock_profile != installation.technical.clock_profile):
                raise ValueError("SELECTED_INCEPTION_EXACT_NATIVE_OPERATOR_CLOCK_REQUIRED")
            if (clock is not sid_clock and sid_clock is not None
                    or installation.reader is not activation_reader
                    and activation_reader is not None):
                raise ValueError("SELECTED_INCEPTION_ONE_CLOCK_AND_ACTIVATION_REQUIRED")
            if accounts is not None and (
                    operator.accounts != accounts
                    or installation.accounts != accounts):
                raise ValueError("SELECTED_INCEPTION_BOTH_ACCOUNT_DIGEST_BINDINGS_REQUIRED")
            sid_clock = clock
            activation_reader = installation.reader
            accounts = operator.accounts
            if (installation.accounts != accounts
                    or operator.reader is not activation_reader
                    or installation.identity.clock is not clock
                    or installation.identity.reader is not activation_reader):
                raise ValueError("SELECTED_INCEPTION_LOCAL_OPERATOR_PORT_DRIFT")
            bindings.append((lane, bootstrap, publisher, installation,
                             digest(enrollment), digest(manifest)))
        if (type(accounts) is not dict
                or accounts != {item[0]: item[4] for item in bindings}
                or bindings[0][5] == bindings[1][5]):
            raise ValueError("SELECTED_INCEPTION_TWO_DISTINCT_ACCOUNT_MANIFESTS_REQUIRED")
        owner.require_exact_roster(
            qd=bindings[0][1].enrollment["native_enrollment"],
            perp=bindings[1][1].enrollment["native_enrollment"])
        require_version_safe_release_digest(
            clock=sid_clock, runtime_id=bindings[0][3].identity.runtime_id,
            release_digest=owner.release_digest)
        if (bindings[1][3].identity.runtime_id != bindings[0][3].identity.runtime_id):
            raise ValueError("SELECTED_INCEPTION_SINGLE_NATIVE_RUNTIME_REQUIRED")
        now = sid_clock()
        if type(now) is not int or any(
                not 0 <= now - item[1].enrollment["parameters"]["opened_at"] <= 30
                for item in bindings):
            raise ValueError("SELECTED_INCEPTION_FRESH_TRUE_OPENING_TIME_REQUIRED")
        for lane, bootstrap, _publisher, installation, *_ in bindings:
            record = installation.identity.activation("INITIALIZE_SIMULATED_ACCOUNTS")
            if type(record.get("actions")) is not list or set(record["actions"]) != ACTIONS:
                raise ValueError("SELECTED_INCEPTION_READ_AND_INITIALIZE_ONLY_REQUIRED")
            if record["accounts"] != accounts:
                raise ValueError("SELECTED_INCEPTION_SINGLE_OPERATOR_APPROVAL_REQUIRED")
            scope = {
                "schema": "ATLAS_PERSONAL_INCEPTION_REQUEST_V1",
                "action": "INITIALIZE_SIMULATED_ACCOUNTS",
                "scope": bootstrap.scope(),
            }
            with installation.lease(scope) as lease:
                if lease.check(lease.snapshot) is not True:
                    raise ValueError("SELECTED_INCEPTION_INSTALLATION_LEASE_EXPIRED")
        binding = tuple(
            (lane, digest(bootstrap.enrollment),
             digest(installation.identity.enrollment))
            for lane, bootstrap, _, installation, *_ in bindings)
        if entering:
            self._binding = binding
        elif binding != self._binding:
            raise ValueError("SELECTED_INCEPTION_ENROLLMENT_CHANGED")
        self._admitted = True
        return bindings, sid_clock

    def publish_both_once(self):
        """This is a real one-way financial-file operation when genuinely wired.

        Caller must be the installed native original Windows Job owner. It
        never creates parent directories and never issues a PAPER trading
        grant. Any possible partial effect terminally blocks retry.
        """
        bindings, _clock = self._verify()
        owner = self.original_job
        self._used = True
        owner._two_lane_inception_claimed = True
        try:
            # The ORIGINAL Windows Job must survive the entire publication.
            # After the first account is written, twelve EMPTY roots no longer
            # exist, so only original-handle liveness may be checked between
            # the two publications. Full native FS1/FS3 ACK is checked after.
            owner._verify_original_job()
            q_result = self.publishers[0].publish()
            owner._verify_original_job()
            h_result = self.publishers[1].publish()
            owner._verify_original_job()
            if (q_result.get("financial_startup_authorized") is not False
                    or h_result.get("financial_startup_authorized") is not False):
                raise ValueError("SELECTED_INCEPTION_NO_TRADE_PERMISSION_FROM_GENESIS")
            result = owner.observe_verified_initial_inceptions(
                qd_bootstrap=bindings[0][1], hl_bootstrap=bindings[1][1])
            if (result.get("both_initial_fs1_fs3_readbacks_verified") is not True
                    or result.get("financial_writer_lease_issued") is not False
                    or result.get("paper_start_authorized") is not False
                    or owner._phase != "INITIAL_READBACK_ONLY"):
                raise ValueError("SELECTED_INCEPTION_TWO_ACKNOWLEDGED_NATIVE_BOOKS_REQUIRED")
            owner.verify_still_running()
            return {
                "schema": SCHEMA,
                "status": "TWO_NATIVE_SIMULATED_ACCOUNT_OPENINGS_ACKNOWLEDGED",
                "opened_lanes": ["QUALITY_DIPS", "HYPERLIQUID"],
                "opening_balance_per_lane": "1000",
                "original_windows_job_retained": True,
                "financial_writer_lease_issued": False,
                "paper_start_authorized": False,
                "live_trading_authorized": False,
            }
        except BaseException:
            # Even if only one publisher wrote, DO NOT automatically roll
            # back or retry once-only financial account creation.
            owner._phase = "INITIAL_READBACK_PENDING"
            raise
