"""Require *owned Windows Job HANDLE* for selected R15 writer activation.

Liveness of an arbitrary exact-PID process is insufficient: it may not be the
parked child which the current Atlas owner is able to stop. The owner must
retain the exact Job and PROCESS HANDLE from suspended Job admission, prove
the process belongs to that job, prove kill-on-close, and prove that all
Quality Dips and Hyperliquid writer roles resolve to this one live process.

This is a necessary prepublication identity/containment check, NOT a lease
over ledgers, source rights, independent issuer approval or a trading grant.
It can be used only in the same trusted owner process retaining the handles.
"""
import ctypes
import ntpath
import os
from pathlib import Path
from copy import deepcopy
from ctypes import wintypes

from app.services.paper_financial_replay import digest
from scripts.observation_runtime.atlas_r15_disposable_writer_process_audit import (
    _windows_handle_identity,
)
from scripts.observation_runtime.atlas_r15_paper_offline_commissioning import (
    ARTIFACT, RELEASE, SELECTED_HEAD, selected_code,
)
from scripts.observation_runtime.personal_native_job import ContainedChild
from scripts.observation_runtime.personal_native_windows_api import (
    JOB_OBJECT_EXTENDED_LIMIT_INFORMATION_CLASS,
    JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE,
    JOBOBJECT_EXTENDED_LIMIT_INFORMATION,
    WindowsJobAPI,
)
from scripts.observation_runtime.personal_native_writer_lifetime import (
    writer_roster,
)
from scripts.observation_runtime.personal_existing_native_resource_evidence import (
    ROLES, inspect_two_lane_native_roots,
)

SCHEMA = "ATLAS_R15_RETAINED_OWNED_JOB_BOTH_FINANCIAL_WRITER_ROSTERS_V1"
WAIT_TIMEOUT = 258


def require_exact_r15_preinception_roots(qd, perp, evidence):
    """Bind real empty native roots to BOTH enrollment rosters, not a PID alone.

    This is a pre-inception constraint, deliberately invalid once account
    files exist. It cannot authorize publication, account creation or PAPER.
    """
    if (type(qd) is not dict or type(perp) is not dict
            or type(evidence) is not dict
            or evidence.get("schema") !=
                "ATLAS_TWO_LANE_EXISTING_NATIVE_ROOT_PRE_ENROLLMENT_V1"
            or evidence.get("native_root_total") != 12
            or evidence.get("native_root_ids_verified") != 12
            or evidence.get("existing_empty_root_namespaces") != 12
            or evidence.get("all_twelve_distinct_and_empty") is not True
            or any(evidence.get(k) is not False for k in (
                "operator_account_enrollment_verified",
                "writer_ownership_verified",
                "financial_inception_verified",
                "paper_start_authorized", "live_trading_authorized"))
            or evidence.get("filesystem_writes") != 0
            or evidence.get("network_requests") != 0
            or type(evidence.get("lanes")) is not dict
            or set(evidence["lanes"]) != {"QUALITY_DIPS", "HYPERLIQUID"}):
        raise ValueError("R15_ACTIVATION_EXACT_EMPTY_NATIVE_PREINCEPTION_REQUIRED")
    bound = []
    ids = set()
    paths = set()
    for lane, enrollment in (("QUALITY_DIPS", qd), ("HYPERLIQUID", perp)):
        lane_evidence = evidence["lanes"][lane]
        if (type(lane_evidence) is not dict
                or type(enrollment.get("resources")) is not dict
                or set(enrollment["resources"]) != set(ROLES)
                or type(lane_evidence.get("roots")) is not dict
                or set(lane_evidence["roots"]) != set(ROLES)
                or lane_evidence.get("epoch") != enrollment.get("epoch")):
            raise ValueError("R15_ACTIVATION_TWO_EXACT_NATIVE_ENROLLMENT_ROOTS_REQUIRED")
        for role in ROLES:
            actual = lane_evidence["roots"][role]
            expected = enrollment["resources"][role]
            if (type(actual) is not dict or type(expected) is not dict
                    or actual.get("native_identity_verified") is not True
                    or actual.get("existing_empty_namespace_verified") is not True
                    or type(actual.get("native_id")) is not list
                    or len(actual["native_id"]) != 3
                    or any(type(k) is not int or k < 0
                           for k in actual["native_id"])
                    or type(actual.get("path")) is not str
                    or actual["path"] != expected.get("path")
                    or actual["native_id"] != expected.get("native_id")):
                raise ValueError("R15_ACTIVATION_NATIVE_RESOURCE_IDENTITY_CHANGED")
            identity = tuple(actual["native_id"])
            path = actual["path"].casefold()
            if identity in ids or path in paths:
                raise ValueError("R15_ACTIVATION_TWO_LANE_ROOT_ALIAS_REFUSED")
            ids.add(identity)
            paths.add(path)
            bound.append((lane, role, actual["path"], identity))
    if len(ids) != 12:
        raise ValueError("R15_ACTIVATION_ALL_TWELVE_NATIVE_ROOTS_REQUIRED")
    return tuple(bound)


def require_exact_r15_populated_root_identities(qd, perp, evidence, original_binding):
    """Verify original native directory IDs after files MAY exist.

    This is deliberately *identity only*. No file content, native ledger,
    issuer, clock, publication acknowledgement or financial writer lease is
    authenticated here. A populated namespace cannot satisfy the original
    pre-inception empty-root activation gate.
    """
    if (type(original_binding) is not tuple or len(original_binding) != 12
            or type(evidence) is not dict
            or evidence.get("schema") !=
                "ATLAS_TWO_LANE_EXISTING_NATIVE_ROOT_PRE_ENROLLMENT_V1"
            or evidence.get("native_root_total") != 12
            or evidence.get("native_root_ids_verified") != 12
            or type(evidence.get("existing_empty_root_namespaces")) is not int
            or not 0 <= evidence["existing_empty_root_namespaces"] <= 12
            or type(evidence.get("lanes")) is not dict
            or set(evidence["lanes"]) != {"QUALITY_DIPS", "HYPERLIQUID"}
            or evidence.get("filesystem_writes") != 0
            or evidence.get("network_requests") != 0
            or any(evidence.get(k) is not False for k in (
                "operator_account_enrollment_verified",
                "writer_ownership_verified",
                "financial_inception_verified",
                "paper_start_authorized", "live_trading_authorized"))):
        raise ValueError("R15_POPULATED_NATIVE_IDENTITY_EVIDENCE_REQUIRED")
    verified = []
    identities = set()
    paths = set()
    for lane, enrollment in (("QUALITY_DIPS", qd), ("HYPERLIQUID", perp)):
        observed = evidence["lanes"][lane]
        if (type(observed) is not dict
                or type(enrollment) is not dict
                or type(enrollment.get("resources")) is not dict
                or set(enrollment["resources"]) != set(ROLES)
                or type(observed.get("roots")) is not dict
                or set(observed["roots"]) != set(ROLES)
                or observed.get("epoch") != enrollment.get("epoch")):
            raise ValueError("R15_POPULATED_NATIVE_ENROLLMENT_SCOPE_CHANGED")
        for role in ROLES:
            root = observed["roots"][role]
            enrolled = enrollment["resources"][role]
            if (type(root) is not dict or type(enrolled) is not dict
                    or root.get("native_identity_verified") is not True
                    or type(root.get("existing_empty_namespace_verified")) is not bool
                    or type(root.get("native_id")) is not list
                    or len(root["native_id"]) != 3
                    or any(type(v) is not int or v < 0
                           for v in root["native_id"])
                    or type(root.get("path")) is not str
                    or root["path"] != enrolled.get("path")
                    or root["native_id"] != enrolled.get("native_id")):
                raise ValueError("R15_POPULATED_NATIVE_RESOURCE_IDENTITY_CHANGED")
            identity = tuple(root["native_id"])
            path = root["path"].casefold()
            if identity in identities or path in paths:
                raise ValueError("R15_POPULATED_NATIVE_RESOURCE_ALIAS_REFUSED")
            identities.add(identity)
            paths.add(path)
            verified.append((lane, role, root["path"], identity))
    counted_empty = sum(
        int(evidence["lanes"][lane]["roots"][role]["existing_empty_namespace_verified"])
        for lane in ("QUALITY_DIPS", "HYPERLIQUID") for role in ROLES)
    if (evidence["existing_empty_root_namespaces"] != counted_empty
            or evidence.get("all_twelve_distinct_and_empty") is not (counted_empty == 12)):
        raise ValueError("R15_POPULATED_NATIVE_INVENTORY_COUNTERS_INCONSISTENT")
    if tuple(verified) != original_binding:
        raise ValueError("R15_POPULATED_ORIGINAL_NATIVE_ROOT_BINDING_CHANGED")
    return tuple(verified)


class RetainedSelectedR15OwnerJob:
    """Retained native Job+PROCESS handles; no standalone authority issuer."""

    def __init__(self, *, child, qd, perp):
        if (os.name != "nt" or type(child) is not ContainedChild
                or type(child.api) is not WindowsJobAPI or child.closed
                or not child.job or not child.process):
            raise ValueError("R15_ACTIVATION_EXACT_OWNED_JOB_REQUIRED")
        self.child = child
        self.api = child.api
        self.job, self.process = child.job, child.process
        self._original_selected = selected_code()
        if (self._original_selected.get("revision") != 14
                or self._original_selected.get("selected_native_head") != SELECTED_HEAD
                or self._original_selected.get("financial_authority") is not False):
            raise ValueError("R15_ACTIVATION_SELECTED_RELEASE_NOT_FINANCIALLY_QUALIFIED")
        self._qd, self._perp = digest(qd), digest(perp)
        self._original_qd, self._original_perp = deepcopy(qd), deepcopy(perp)
        roster, original_selector = writer_roster(qd, perp, release_digest=ARTIFACT)
        if (original_selector != self._original_selected or len(roster) != 12
                or len(set(roster.values())) != 1):
            raise ValueError("R15_ACTIVATION_EXACT_ONE_PROCESS_BOTH_WRITER_ROSTERS_REQUIRED")
        self._only_writer = next(iter(set(roster.values())))
        self._native_root_snapshot = inspect_two_lane_native_roots()
        self._native_root_binding = require_exact_r15_preinception_roots(
            qd, perp, self._native_root_snapshot)
        self._verified = False
        self.verify_still_running()
        self._verified = True

    def _verify_owned_worker(self):
        if (self.child.closed or self.child.job != self.job
                or self.child.process != self.process
                or self.child.api is not self.api
                or selected_code() != self._original_selected):
            raise ValueError("R15_ACTIVATION_OWNED_JOB_OR_RELEASE_CHANGED")
        k = self.api.kernel32
        k.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        k.WaitForSingleObject.restype = wintypes.DWORD
        k.IsProcessInJob.argtypes = [
            wintypes.HANDLE, wintypes.HANDLE, ctypes.POINTER(wintypes.BOOL)]
        k.IsProcessInJob.restype = wintypes.BOOL
        k.GetProcessId.argtypes = [wintypes.HANDLE]
        k.GetProcessId.restype = wintypes.DWORD
        if k.WaitForSingleObject(self.process, 0) != WAIT_TIMEOUT:
            raise ValueError("R15_ACTIVATION_OWNED_WORKER_EXITED")
        contained = wintypes.BOOL()
        if not k.IsProcessInJob(self.process, self.job, ctypes.byref(contained)):
            raise ValueError("R15_ACTIVATION_JOB_MEMBERSHIP_UNAVAILABLE")
        if not contained.value or self.api.active_processes(self.job) != 1:
            raise ValueError("R15_ACTIVATION_EXACT_ONE_WORKER_IN_OWNED_JOB_REQUIRED")
        limits = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        if not k.QueryInformationJobObject(
                self.job, JOB_OBJECT_EXTENDED_LIMIT_INFORMATION_CLASS,
                ctypes.byref(limits), ctypes.sizeof(limits), None):
            raise ValueError("R15_ACTIVATION_JOB_TERMINATION_POLICY_UNAVAILABLE")
        if not (limits.BasicLimitInformation.LimitFlags &
                JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE):
            raise ValueError("R15_ACTIVATION_OWNED_JOB_KILL_ON_CLOSE_MISSING")
        pid, created, image = self._only_writer
        observed = _windows_handle_identity(self.process)
        if (int(k.GetProcessId(self.process)) != pid
                or observed["creation_filetime"] != created
                or ntpath.normcase(ntpath.normpath(observed["image"])) != image
                or image != ntpath.normcase(str(RELEASE / "python/python.exe"))):
            raise ValueError("R15_ACTIVATION_OWNED_WORKER_INCARCATION_CHANGED")
        return True

    def verify_still_running(self):
        """PRE-inception admission: all 12 directories must stay empty."""
        self._verify_owned_worker()
        roots = inspect_two_lane_native_roots()
        if (roots != self._native_root_snapshot
                or require_exact_r15_preinception_roots(
                    self._original_qd, self._original_perp, roots)
                   != self._native_root_binding):
            raise ValueError("R15_ACTIVATION_NATIVE_ROOTS_CHANGED_DURING_OWNED_JOB")
        return True

    def observe_original_roots_allowing_population(self, *, qd, perp):
        """Identity continuity only: no post-inception financial acceptance.

        Kept separate from require_exact_roster and its EMPTY ROOT gate.
        Cannot produce an activation capability, writer lease or order grant.
        """
        if digest(qd) != self._qd or digest(perp) != self._perp:
            raise ValueError("R15_POPULATED_NATIVE_ENROLLMENT_DRIFT")
        self._verify_owned_worker()
        observed = inspect_two_lane_native_roots()
        require_exact_r15_populated_root_identities(
            self._original_qd, self._original_perp,
            observed, self._native_root_binding)
        return {
            "schema": "ATLAS_R15_NATIVE_ROOT_IDENTITY_CONTINUITY_ONLY_V1",
            "selected_native_head": SELECTED_HEAD,
            "original_root_count_native_identity_verified": 12,
            "original_job_and_process_still_owned": True,
            "empty_root_precondition_required_for_activation": True,
            "financial_file_contents_or_coordination_ledger_audited": False,
            "postinception_writer_lease_issued": False,
            "native_financial_inception_accepted": False,
            "paper_start_authorized": False,
            "live_trading_authorized": False,
        }


    def inspect_both_committed_initial_cuts(self, *, qd, perp,
                                            qd_bootstrap, perp_bootstrap):
        """Read two ACKed native initial cuts while retaining the SAME Job.

        Existing-only and NO financial authority: this is NOT a runtime writer
        lease. Native FS1/FS3 files, durable native coordination receipts,
        initial arithmetic, and the two original roster/root identities must
        each agree before returning even a technical read-only observation.
        """
        from contextlib import ExitStack
        from app.services.paper_financial_replay import (
            body, initial_state, strict,
        )
        from app.services.personal_native_coordination import (
            PersonalNativeCoordination,
        )
        from app.services.personal_publication_custody import (
            PersonalPublicationCustody,
        )
        from app.services.personal_paper_runtime import (
            PersonalOperatorInstallation,
        )
        from scripts.observation_runtime.personal_coordination_store import (
            NativePersonalCoordinationImages,
        )
        from scripts.observation_runtime.personal_paper_inception import (
            NativePersonalInitialReadback, PersonalInceptionBootstrap,
            PersonalPublicationIssuer, validate_personal_inception,
        )

        self.observe_original_roots_allowing_population(qd=qd, perp=perp)
        if (type(qd) is not dict or type(perp) is not dict
                or qd.get("account_id") == perp.get("account_id")
                or qd.get("epoch") == perp.get("epoch")
                or qd.get("release_digest") != ARTIFACT
                or perp.get("release_digest") != ARTIFACT):
            raise ValueError("R15_INITIAL_CUT_TWO_DISTINCT_SELECTED_ACCOUNTS_REQUIRED")
        if (qd_bootstrap is perp_bootstrap
                or getattr(qd_bootstrap, "issuer", None) is not
                   getattr(perp_bootstrap, "issuer", None)):
            raise ValueError("R15_INITIAL_CUT_ONE_OPERATOR_ISSUER_REQUIRED")
        admitted = []
        for lane, enrollment, bootstrap in (
                ("QUALITY_DIPS", qd, qd_bootstrap),
                ("HYPERLIQUID", perp, perp_bootstrap)):
            if (type(bootstrap) is not PersonalInceptionBootstrap
                    or type(bootstrap.readback) is not NativePersonalInitialReadback
                    or type(bootstrap.publication) is not PersonalPublicationCustody
                    or type(bootstrap.issuer) is not PersonalPublicationIssuer
                    or type(bootstrap.issuer.installation) is not PersonalOperatorInstallation):
                raise ValueError("R15_INITIAL_CUT_REAL_NATIVE_BOOTSTRAP_REQUIRED:" + lane)
            account_lane, native_enrollment, manifest = validate_personal_inception(
                bootstrap.enrollment)
            installation = bootstrap.issuer.installation
            if (account_lane != lane
                    or manifest.get("currency") !=
                       ("USD" if lane == "QUALITY_DIPS" else "USDC")
                    or digest(native_enrollment) != digest(enrollment)
                    or installation.accounts.get(lane) != digest(enrollment)
                    or installation.release != ARTIFACT):
                raise ValueError("R15_INITIAL_CUT_ENROLLED_ACCOUNT_OR_RELEASE_CHANGED:" + lane)
            ledger = bootstrap.publication.ledger
            if (type(ledger) is not PersonalNativeCoordination
                    or type(ledger.images) is not NativePersonalCoordinationImages
                    or ledger.images.enrollment != digest(enrollment)
                    or ledger.images.root != enrollment["resources"]["coordination"]["path"]
                    or ledger.images.root_id != enrollment["resources"]["coordination"]["native_id"]
                    or not isinstance(ledger.path, Path)
                    or ledger.path.parent != Path(ledger.images.root)
                    or ledger._ports != (ledger.images, ledger.path)
                    or ledger._manifest != body(manifest)
                    or digest(ledger.manifest) != digest(manifest)):
                raise ValueError("R15_INITIAL_CUT_GENUINE_NATIVE_COORDINATION_REQUIRED:" + lane)
            admitted.append((lane, enrollment, bootstrap, ledger, manifest))
        # Acquire BOTH native immutable coordination read views in the
        # deterministic QD-then-HL order. Keep both held until BOTH native
        # ACK/FS1/FS3 cuts and original Job/root identities agree. This
        # prevents a mixed-time two-account proof under cooperative writers.
        cuts = {}
        with ExitStack() as views:
            for lane, enrollment, bootstrap, ledger, manifest in admitted:
                views.enter_context(ledger.images.read_view())
                self.observe_original_roots_allowing_population(qd=qd, perp=perp)
            for lane, enrollment, bootstrap, ledger, manifest in admitted:
                # Each native ACK and FS1/FS3 verifier reads under its
                # own held immutable coordination image read view.
                ready = bootstrap.verify_publication()
                current = strict(body(ready["current"]))
                with ledger.connect(readonly=True) as db:
                    state, head, operations = ledger._load(db)
                    pending_projections = db.execute(
                        "SELECT 1 FROM projections WHERE receipt IS NULL").fetchone()
                    pending_publications = db.execute(
                        "SELECT 1 FROM personal_publications "
                        "WHERE state!='ACKNOWLEDGED' OR state IS NULL").fetchone()
                    pending_sessions = db.execute(
                        "SELECT 1 FROM personal_sessions "
                        "WHERE state!='ACKNOWLEDGED' OR state IS NULL").fetchone()
                if (ready.get("financial_startup_authorized") is not False
                        or current.get("status") != "ACKNOWLEDGED"
                        or current.get("revision") != 0
                        or state != initial_state(manifest)
                        or head != digest(manifest) or operations
                        or current["state_digest"] != digest(state)
                        or pending_projections or pending_publications or pending_sessions):
                    raise ValueError("R15_INITIAL_CUT_NATIVE_LEDGER_UNACKNOWLEDGED:" + lane)
                cuts[lane] = {
                    "enrollment_digest": digest(enrollment),
                    "initial_current_digest": ready["current_digest"],
                    "once_only_publication_receipt_digest": ready["publication_digest"],
                    "initial_cash_simulated": state["cash"],
                    "initial_position_count": len(state["positions"]),
                }
                self.observe_original_roots_allowing_population(qd=qd, perp=perp)
        if (cuts["QUALITY_DIPS"]["initial_cash_simulated"] != "1000"
                or cuts["HYPERLIQUID"]["initial_cash_simulated"] != "1000"
                or cuts["QUALITY_DIPS"]["initial_position_count"] != 0
                or cuts["HYPERLIQUID"]["initial_position_count"] != 0):
            raise ValueError("R15_INITIAL_CUT_TWO_SEPARATE_BASELINES_REQUIRED")
        return {
            "schema": "ATLAS_R15_TWO_LANE_INITIAL_NATIVE_CUT_TECHNICAL_READBACK_V1",
            "lanes": cuts,
            "same_original_owned_r15_job_and_roots_reverified": True,
            "acknowledged_native_initial_cuts_reverified": True,
            "financial_operating_authority_granted": False,
            "persistent_financial_writer_lease_issued": False,
            "financial_startup_authorized": False,
            "live_trading_authorized": False,
        }

    def require_exact_roster(self, *, qd, perp):
        if (digest(qd) != self._qd or digest(perp) != self._perp):
            raise ValueError("R15_ACTIVATION_OWNED_JOB_ENROLLMENT_DRIFT")
        self.verify_still_running()
        return True

    def nonfinancial_handoff_readback(self):
        self.verify_still_running()
        return {
            "schema": SCHEMA,
            "selected_native_head": SELECTED_HEAD,
            "owned_job_kill_on_close_verified": True,
            "retained_job_has_one_live_selected_r15_worker": True,
            "both_native_writer_rosters_match_same_job_worker": True,
            "writer_roles_examined": 12,
            "genuine_activation_or_owner_lease_issued": False,
            "native_financial_inception_accepted": False,
            "paper_start_authorized": False,
            "live_trading_authorized": False,
        }
