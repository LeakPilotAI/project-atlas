"""One-shot ORIGINAL two-journal native PAPER preinception authorization.

Breaks the R18 preinception circle SAFELY: old source-install authority demands
an activation, while R18 activation requires already verified coordination
journals. This distinct preactivation action is limited to the two original
coordination namespaces and can never authorize account FS1/FS3, trades,
financial leases, market feeds, or desktop PAPER Start.

NOT a signed operator record or permission mint. Caller must independently
obtain an exact, explicit Windows-operator approved scope; this class cannot
issue that scope itself. Source-only until included in a selected installed
release. A possibly partial first/second image is UNKNOWN and cannot replay.
"""
from __future__ import annotations

import hashlib
from contextlib import contextmanager

from app.services.paper_financial_replay import body, digest, strict
from app.services.personal_native_coordination import PersonalNativeCoordination

from scripts.observation_runtime.personal_coordination_store import (
    NativePersonalCoordinationImages,
)
from scripts.observation_runtime.personal_existing_native_resource_evidence import (
    inspect_two_lane_native_roots,
)
from scripts.observation_runtime.personal_native_selected_owned_job_preflight import (
    RetainedSelectedNativeOwnerPreflight,
)
from scripts.observation_runtime.personal_r15_owned_job_activation import (
    require_exact_r15_populated_root_identities,
)
from scripts.observation_runtime.personal_version_safe_release_clock import (
    NativeVersionSafePaperOperatorClock,
    require_version_safe_release_digest,
)
from scripts.volume_inspector.windows_output import current_sid

SCHEMA = "ATLAS_ORIGINAL_PREINCEPTION_TWO_COORDINATION_JOURNAL_SCOPE_V1"
ACTION = "INITIALIZE_TWO_COORDINATION_JOURNALS_ONLY"
LANES = ("QUALITY_DIPS", "HYPERLIQUID")
MAX_SCOPE_SECONDS = 180
MAX_MANIFEST_OPENING_AGE_SECONDS = 5


class NativeOriginalTwoJournalPreinceptionPermit:
    """Requires explicit, independently supplied current scope; no default."""

    def __init__(self, *, job, clock, runtime_id, ledgers, operator_scope):
        if (type(job) is not RetainedSelectedNativeOwnerPreflight
                or type(clock) is not NativeVersionSafePaperOperatorClock
                or type(runtime_id) is not str or not runtime_id
                or type(ledgers) is not dict or set(ledgers) != set(LANES)
                or type(operator_scope) is not dict
                or job._phase != "PREINCEPTION"):
            raise ValueError("PREINCEPTION_EXACT_NATIVE_JOB_CLOCK_SCOPE_REQUIRED")
        job.verify_still_running()
        if require_version_safe_release_digest(
                clock=clock, runtime_id=runtime_id,
                release_digest=job.release_digest) is not True:
            raise ValueError("PREINCEPTION_SELECTED_ORIGINAL_NTP_REQUIRED")
        original = inspect_two_lane_native_roots()
        if (original["native_root_total"] != 12
                or original["native_root_ids_verified"] != 12
                or original["existing_empty_root_namespaces"] != 12
                or original["all_twelve_distinct_and_empty"] is not True):
            raise ValueError("PREINCEPTION_TWELVE_ORIGINAL_EMPTY_ROOTS_REQUIRED")
        # The once-only journal permanently binds its manifest. Historical
        # R15/R17 timestamps are NOT a viable R18 initial financial account.
        # Both must start with a freshly qualified true UTC opening timestamp,
        # since the downstream real account issuer permits only 30 seconds.
        now = clock()
        self.expected_images = {}
        self.ledger_binding = {}
        account_digests = {}
        for lane in LANES:
            ledger = ledgers[lane]
            enrollment = job._original_qd if lane == LANES[0] else job._original_perp
            if (type(ledger) is not PersonalNativeCoordination
                    or type(ledger.images) is not NativePersonalCoordinationImages
                    or ledger.images.enrollment != digest(enrollment)
                    or ledger.images.root_id !=
                       enrollment["resources"]["coordination"]["native_id"]
                    or ledger.manifest["release"] != job.release_digest
                    or ledger.manifest.get("opening_cash") != "1000"
                    or ledger.manifest.get("currency") != (
                        "USD" if lane == "QUALITY_DIPS" else "USDC")
                    or type(ledger.manifest.get("opened_at")) is not int
                    or not 0 <= now - ledger.manifest["opened_at"]
                       <= MAX_MANIFEST_OPENING_AGE_SECONDS
                    or enrollment["inception_digest"] != digest(ledger.manifest)
                    or original["lanes"][lane]["epoch"] != enrollment["epoch"]):
                raise ValueError("PREINCEPTION_EXACT_NATIVE_ACCOUNT_JOURNAL_REQUIRED")
            data = PersonalNativeCoordination.initial_image(ledger.manifest)
            if type(data) is not bytes or not data:
                raise ValueError("PREINCEPTION_NONEMPTY_ORIGINAL_IMAGE_REQUIRED")
            self.expected_images[lane] = data
            self.ledger_binding[lane] = ledger
            account_digests[lane] = digest(enrollment)
        scope = strict(body(operator_scope))
        # Recheck time after constructing both genuine initial-image cuts.
        now = clock()
        if (type(scope) is not dict
                or set(scope) != {
                    "schema", "action", "operator_sid", "release_digest",
                    "account_digests", "image_sha256", "issued_at", "expires_at",
                }
                or scope["schema"] != SCHEMA
                or scope["action"] != ACTION
                or scope["operator_sid"] != current_sid()
                or scope["release_digest"] != job.release_digest
                or scope["account_digests"] != account_digests
                or scope["image_sha256"] != {
                    lane: hashlib.sha256(data).hexdigest()
                    for lane, data in self.expected_images.items()
                }
                or type(scope["issued_at"]) is not int
                or type(scope["expires_at"]) is not int
                or not scope["issued_at"] <= now < scope["expires_at"]
                <= scope["issued_at"] + MAX_SCOPE_SECONDS):
            raise ValueError("PREINCEPTION_EXPLICIT_FRESH_OPERATOR_SCOPE_REQUIRED")
        self.job, self.clock, self.runtime_id = job, clock, runtime_id
        self.original_roots = original
        self.operator_scope = scope
        self.original_sid = current_sid()
        self.current_lane = None
        self.position = 0
        self.terminal = False

    def _verify(self, *, expected_count):
        if (self.terminal or self.current_lane not in (None, *LANES)
                or current_sid() != self.original_sid
                or self.job._phase != "PREINCEPTION"
                or self.clock() >= self.operator_scope["expires_at"]):
            raise ValueError("PREINCEPTION_ORIGINAL_OPERATOR_SCOPE_EXPIRED")
        self.job._verify_original_job()
        self.clock.require_operational(self.runtime_id)
        # The genuine native file IDs must never change even when the first
        # journal's exclusive immutable files have now been created.
        roots = inspect_two_lane_native_roots()
        require_exact_r15_populated_root_identities(
            self.job._original_qd, self.job._original_perp,
            roots, self.job._native_binding)
        if roots["existing_empty_root_namespaces"] != expected_count:
            raise ValueError("PREINCEPTION_EXACT_TWO_JOURNAL_NAMESPACES_REQUIRED")
        for lane in LANES:
            for role, item in roots["lanes"][lane]["roots"].items():
                should_be_empty = (role != "coordination"
                                   or LANES.index(lane) >= 12 - expected_count)
                if item["existing_empty_namespace_verified"] is not should_be_empty:
                    raise ValueError("PREINCEPTION_FOREIGN_FINANCIAL_ROOT_WRITE")
        return roots

    @contextmanager
    def lease(self, request):
        """Same bounded interface required by NativePersonalCoordinationImages."""
        if self.terminal or self.current_lane is not None or self.position >= 2:
            raise ValueError("PREINCEPTION_JOURNAL_ONE_SHOT_SCOPE_EXHAUSTED")
        lane = LANES[self.position]
        ledger = self.ledger_binding[lane]
        data = self.expected_images[lane]
        expected_request = {
            "schema": "PERSONAL_COORDINATION_INSTALL_V1",
            "root": ledger.images.root_id,
            "enrollment": ledger.images.enrollment,
            "image_digest": hashlib.sha256(data).hexdigest(),
        }
        if strict(body(request)) != expected_request:
            raise ValueError("PREINCEPTION_EXACT_ORIGINAL_JOURNAL_REQUEST_REQUIRED")
        self._verify(expected_count=12-self.position)
        owner = self
        self.current_lane = lane
        class Lease:
            def check(self, current):
                try:
                    if strict(body(current)) != expected_request:
                        return False
                    # The writer may have created this lane's first image
                    # between its two authorization checks. Never permit any
                    # other lane or role to change.
                    count = inspect_two_lane_native_roots()["existing_empty_root_namespaces"]
                    if count not in (12-owner.position, 11-owner.position):
                        return False
                    owner._verify(expected_count=count)
                    return True
                except (ValueError, KeyError, TypeError, OSError):
                    return False
        try:
            yield Lease()
            self._verify(expected_count=11-self.position)
            raw, pin = ledger.images._load()
            if (raw != data or type(pin) is not dict
                    or pin.get("revision") != 1):
                raise ValueError("PREINCEPTION_EXACT_INITIAL_IMAGE_NOT_ACKNOWLEDGED")
            self.position += 1
        except BaseException:
            # The first journal MAY have committed; never retry with a new
            # local approval, never silently reset the once-only native root.
            self.terminal = True
            raise
        finally:
            self.current_lane = None

    def publish_both_original_journals_once(self):
        """THE one-way financial coordination effect; never starts PAPER.

        Invoke only from selected installed native Windows original worker
        with already reviewed, expressly scoped operator record. Failed or
        unknown outcome is terminal; stop and reconcile original files.
        """
        if self.position or self.terminal:
            raise ValueError("PREINCEPTION_INITIAL_COORDINATION_REPLAY_REFUSED")
        try:
            for lane in LANES:
                ledger = self.ledger_binding[lane]
                ledger.images.initialize(
                    self.expected_images[lane], authorization=self)
            if self.position != 2:
                raise ValueError("PREINCEPTION_TWO_ORIGINAL_JOURNALS_REQUIRED")
            result = self.job.observe_preinception_coordination(
                qd_ledger=self.ledger_binding[LANES[0]],
                hl_ledger=self.ledger_binding[LANES[1]])
            if (result.get("initial_native_coordination_journals_verified") != 2
                    or result.get("paper_start_authorized") is not False):
                raise ValueError("PREINCEPTION_TWO_REAL_INITIAL_JOURNALS_UNVERIFIED")
            self.terminal = True
            return {
                "schema": SCHEMA,
                "status": "TWO_ORIGINAL_COORDINATION_JOURNALS_ACKNOWLEDGED_ONLY",
                "native_initial_journal_count": 2,
                "native_account_inceptions_published": 0,
                "financial_writer_lease_issued": False,
                "paper_start_authorized": False,
                "live_trading_authorized": False,
            }
        except BaseException:
            self.terminal = True
            # A possibly partial effect must never become a guessed success.
            if self.job._phase == "PREINCEPTION":
                self.job._phase = "PREINCEPTION_COORDINATION_PENDING"
            raise
