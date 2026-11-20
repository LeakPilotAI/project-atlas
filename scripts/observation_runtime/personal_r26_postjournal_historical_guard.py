"""Selected-native R26 postjournal historical custody, never issuer authority.

Future successor release capability: retain original native revision-one
journals strictly as historical evidence under a fresh genuine self-Job.
This class cannot create/update journals, enroll accounts, mint activation,
adopt historical writer identities, start PAPER, or issue real-money orders.
A DISTINCT fresh-epoch financial issuer is still independently required.
"""
from __future__ import annotations

from pathlib import Path
from app.services.paper_financial_replay import body, digest, strict
from app.services.personal_native_coordination import PersonalNativeCoordination
from app.services.quality_dips_autonomous_enrollment import (
    validate_enrollment as validate_qd)
from app.services.perp_operational_contract import (
    validate_enrollment as validate_hl)

from scripts.observation_runtime.personal_coordination_store import (
    NativePersonalCoordinationImages)
from scripts.observation_runtime.personal_existing_native_resource_evidence import (
    inspect_two_lane_native_roots)
from scripts.observation_runtime.personal_native_original_self_job import (
    NativeFinancialReleaseAdmission, NativeOriginalSelfJob)
from scripts.observation_runtime.personal_writer_generation import verify_previous_exited
from scripts.observation_runtime.personal_release_identity import (
    NativePersonalReleaseIdentity)
from scripts.observation_runtime.personal_paper_inception import (
    native_primitives)
from scripts.observation_runtime.quality_dips_read_service import observe_self

SCHEMA="ATLAS_NATIVE_HISTORICAL_R26_POSTJOURNAL_READ_GUARD_V1"
LANES=("QUALITY_DIPS","HYPERLIQUID")
SOURCE_RELEASE=Path("D:/AtlasRuntime/releases")
R26_DIGEST="f3213ed6f798ccfd162e0f4f7538ed5e8ca16f97c77d657be49e50c1083407c2"


class NativeR26HistoricalPostjournalGuard:
    """Fresh-release readback of ORIGINAL R26 images, no writer transition.

    This isn't a substitute for current PAPER account readback, nor a finance
    license. Its successful capture can only attest that the original
    rejected first inception remains non-replayable and unchanged.
    """
    def __init__(self, *, self_job, release_admission,
                 old_enrollments, old_activation, old_failure):
        if (type(self_job) is not NativeOriginalSelfJob
                or type(release_admission) is not NativeFinancialReleaseAdmission
                or type(old_enrollments) is not dict
                or set(old_enrollments)!=set(LANES)
                or type(old_activation) is not dict
                or type(old_failure) is not dict):
            raise ValueError("POSTJOURNAL_GUARD_EXACT_NATIVE_PORTS_REQUIRED")
        release=release_admission.release
        if (type(release) is not NativePersonalReleaseIdentity
                or release_admission.verify(release_digest=release.artifact_digest)
                   is None or release.artifact_digest==R26_DIGEST
                or release.root.parent!=SOURCE_RELEASE
                or Path(__file__).absolute()!=release.root/
                   "scripts/observation_runtime/personal_r26_postjournal_historical_guard.py"):
            raise ValueError("POSTJOURNAL_GUARD_NEW_SELECTED_INSTALLED_COHORT_REQUIRED")
        if self_job.verify() is not True or self_job.identity!=observe_self():
            raise ValueError("POSTJOURNAL_GUARD_FRESH_NATIVE_JOB_REQUIRED")
        originals={
            "QUALITY_DIPS":validate_qd(old_enrollments["QUALITY_DIPS"]),
            "HYPERLIQUID":validate_hl(old_enrollments["HYPERLIQUID"]),
        }
        if (any(item["release_digest"]!=R26_DIGEST for item in originals.values())
                or originals["QUALITY_DIPS"]["epoch"]==originals["HYPERLIQUID"]["epoch"]
                or originals["QUALITY_DIPS"]["account_id"]==
                   originals["HYPERLIQUID"]["account_id"]):
            raise ValueError("POSTJOURNAL_GUARD_ONLY_ORIGINAL_TWO_HISTORICAL_ACCOUNTS")
        previous=None
        for item in originals.values():
            for writer in item["writers"].values():
                identity={k:writer[k] for k in ("pid","creation_filetime","image")}
                if previous is None:previous=identity
                elif identity!=previous:
                    raise ValueError("POSTJOURNAL_GUARD_ORIGINAL_WRITER_ROSTER_MISMATCH")
        if (previous is None or previous==self_job.identity
                or verify_previous_exited(previous).get("excluded")!=
                   "ORIGINAL_PROCESS_EXITED_NATIVE_CROSSCHECK"):
            raise ValueError("POSTJOURNAL_GUARD_HISTORICAL_WRITER_NOT_EXCLUDED")
        if (set(old_activation)!={"origin","actions","accounts","original_only"}
                or old_activation["origin"]!="LOCAL_OPERATOR"
                or old_activation["actions"]!=["READ_ONLY","INITIALIZE_SIMULATED_ACCOUNTS"]
                or old_activation["accounts"]!={k:digest(v) for k,v in originals.items()}
                or old_activation["original_only"] is not True):
            raise ValueError("POSTJOURNAL_GUARD_OLD_APPROVAL_NOT_BOUND")
        if (set(old_failure)!={"phase","error","attempt_reserved"}
                or old_failure["phase"]!="ORIGINAL_STAGE_D_E_F_ONCE_POSSIBLY_IRREVERSIBLE"
                or old_failure["error"]!="PERSONAL_TECHNICAL_CHECKS_FAILED"
                or old_failure["attempt_reserved"] is not True):
            raise ValueError("POSTJOURNAL_GUARD_FIRST_ATTEMPT_NOT_TERMINAL")
        self.job=self_job
        self.admission=release_admission
        self.release=release
        self.old_enrollments=strict(body(originals))
        self.activation=strict(body(old_activation))
        self.failure=strict(body(old_failure))
        self.previous=strict(body(previous))
        self._binding=(self_job,release_admission,release,release.artifact_digest,
                       body(originals),body(old_activation),body(old_failure),body(previous))
        self._unknown=False
        self.capture()

    def capture(self):
        """Reopen native original images READ-ONLY; fail terminally on any drift."""
        if self._unknown:
            raise ValueError("POSTJOURNAL_GUARD_TERMINAL_UNKNOWN")
        job,admission,release,selected,accounts,activation,failure,previous=self._binding
        if (self.job is not job or self.admission is not admission
                or self.release is not release or release.artifact_digest!=selected
                or body(self.old_enrollments)!=accounts
                or body(self.activation)!=activation
                or body(self.failure)!=failure or body(self.previous)!=previous):
            self._unknown=True
            raise ValueError("POSTJOURNAL_GUARD_COMPONENT_DRIFT")
        try:
            if (self.job.verify() is not True
                    or self.job.identity!=observe_self()
                    or self.admission.verify(release_digest=selected) is None
                    or verify_previous_exited(self.previous).get("excluded")!=
                       "ORIGINAL_PROCESS_EXITED_NATIVE_CROSSCHECK"):
                raise ValueError("POSTJOURNAL_GUARD_FRESH_OWNER_OR_SELECTION_LOST")
            roots=inspect_two_lane_native_roots()
            if (roots["native_root_total"]!=12
                    or roots["native_root_ids_verified"]!=12
                    or roots["existing_empty_root_namespaces"]!=10
                    or roots["all_twelve_distinct_and_empty"] is not False):
                raise ValueError("POSTJOURNAL_GUARD_ORIGINAL_ROOT_NAMESPACE_CHANGED")
            for lane in LANES:
                item=self.old_enrollments[lane]
                for role,resource in item["resources"].items():
                    actual=roots["lanes"][lane]["roots"][role]
                    if (actual["path"]!=resource["path"]
                            or actual["native_id"]!=resource["native_id"]
                            or actual["existing_empty_namespace_verified"] is not
                               (role!="coordination")):
                        raise ValueError("POSTJOURNAL_GUARD_ORIGINAL_ROOT_IDENTITY_CHANGED")
                resource=item["resources"]["coordination"]
                image=NativePersonalCoordinationImages(
                    root=resource["path"],native_root=resource["native_id"],
                    enrollment_digest=digest(item))
                try:
                    with image.read_view():
                        raw,pin=image._load()
                        if pin["revision"]!=1:
                            raise ValueError("POSTJOURNAL_GUARD_JOURNAL_MUTATED")
                        # Original initial journal must have exactly its
                        # initial manifest row, with no account activity.
                        import sqlite3
                        db=sqlite3.connect(":memory:")
                        try:
                            db.deserialize(raw)
                            rows=db.execute("SELECT body FROM inception").fetchall()
                            if len(rows)!=1:
                                raise ValueError("POSTJOURNAL_GUARD_INITIAL_MANIFEST_MISSING")
                            from app.services.paper_financial_replay import strict
                            manifest=strict(rows[0][0])
                            if (item["inception_digest"]!=digest(manifest)
                                    or raw!=PersonalNativeCoordination.initial_image(manifest)
                                    or any(db.execute("SELECT COUNT(*) FROM "+table).fetchone()[0]
                                           for table in ("events","projections",
                                                         "personal_sessions","personal_publications"))):
                                raise ValueError("POSTJOURNAL_GUARD_NOT_EMPTY_INITIAL_COORDINATION")
                        finally:db.close()
                finally:image.close()
            if self.job.verify() is not True:
                raise ValueError("POSTJOURNAL_GUARD_SELF_JOB_LOST")
            return {"schema":SCHEMA,
                "status":"TWO_HISTORICAL_R26_INITIAL_COORDINATION_JOURNALS_NATIVE_READ_ONLY",
                "original_journals_verified":2,
                "original_financial_account_publications":0,
                "fresh_new_selected_release_verified":True,
                "old_writer_native_exited":True,
                "historical_writer_adoption_authorized":False,
                "same_epoch_replay_authorized":False,
                "new_account_issuer_authorized":False,
                "new_activation_issued":False,
                "paper_start_authorized":False,
                "live_money_trading_authorized":False}
        except BaseException:
            self._unknown=True
            raise

    def require_exact_roster(self, **_kwargs):
        raise ValueError("POSTJOURNAL_GUARD_HISTORICAL_READONLY_CANNOT_ADOPT_WRITERS")

    def publish_both_once(self, **_kwargs):
        raise ValueError("POSTJOURNAL_GUARD_NO_FINANCIAL_PUBLICATION")
