"""Versioned current-readback handoff and fresh READ_ONLY owner reconstruction.

No issuer, writer re-enrollment, phase restoration, process launch or grants.
Native use requires this exact module in a separately selected installation.
"""
from pathlib import Path

from app.services.paper_financial_replay import body, digest, strict
from app.services.personal_current_pins import PersonalCurrentPins
from app.services.personal_native_coordination import PersonalNativeCoordination
from app.services.personal_publication_custody import PersonalPublicationCustody
from app.services.quality_dips_operational_presentation import OperationalAutonomousSelectedRead
from scripts.observation_runtime.personal_coordination_store import NativePersonalCoordinationImages
from scripts.observation_runtime.personal_financial_authority import (
    NativePersonalFinancialAuthority, NativePersonalFinancialReadAuthority,
)
from scripts.observation_runtime.personal_native_financial_release_origin import require_selected_native_origin
from scripts.observation_runtime.personal_native_original_self_job import NativeOriginalSelfJob
from scripts.observation_runtime.personal_paper_inception import (
    PersonalInceptionBootstrap, native_primitives, validate_personal_inception,
    verify_all_native_inception_roots,
)
from scripts.observation_runtime.personal_perp_runtime_current import PersonalPerpRuntimeCurrent
from scripts.observation_runtime.personal_runtime_current import (
    PersonalNativeReadAuthority, PersonalRuntimeCurrent,
)
from scripts.observation_runtime.personal_writer_ownership import NativePersonalWriterOwnership
from scripts.volume_inspector.operational_autonomous_store import OperationalAutonomousReader
from scripts.volume_inspector.financial_reporting import ProjectionTarget
from scripts.observation_runtime.personal_version_safe_release_clock import (
    NativeVersionSafePaperOperatorClock, require_version_safe_release_digest,
)
from scripts.observation_runtime.quality_dips_read_service import observe_self

LANES = ('QUALITY_DIPS', 'HYPERLIQUID')
CURRENT_PHASE = 'CURRENT_READBACK_ONLY'


def verify_original_account_roots(enrollments):
    """Existing native metadata/ACL checks; unknown control/custody stays closed.

    Reuse the six-root identity check without the initial-only FS1/FS3
    namespace restriction. All twelve native directory identities must differ.
    """
    native = native_primitives()
    seen = set()
    for lane in LANES:
        outputs = {}
        enrollment = enrollments[lane]
        try:
            for role, resource in enrollment['resources'].items():
                outputs[role] = native.w.WindowsOutput(resource['path'])
            verify_all_native_inception_roots(
                {'native_enrollment':enrollment}, outputs, native)
            for output in outputs.values():
                identity = tuple(native.native.file_identity(output.root_handle))
                if identity in seen:
                    raise ValueError('OWNER_V2_NATIVE_ACCOUNT_ROOT_ALIAS')
                seen.add(identity)
        finally:
            for output in outputs.values():
                output.close()
    if len(seen)!=12:
        raise ValueError('OWNER_V2_TWELVE_ORIGINAL_NATIVE_ROOTS_REQUIRED')
    return True


def require_installed_continuity_source(release_digest):
    origin = require_selected_native_origin(release_digest=release_digest)
    expected = (Path('D:/AtlasRuntime/releases') / origin['selected_code_release'] /
                'scripts/observation_runtime/personal_owner_continuity_v2.py')
    if Path(__file__).absolute() != expected:
        raise ValueError('OWNER_V2_SELECTED_INSTALLED_CONTINUITY_MODULE_REQUIRED')
    return origin


class NativeTwoAccountCurrentReadback:
    """Capture real existing readers; caller JSON/boolean proofs are not ports."""

    def __init__(self, *, quality_dips, hyperliquid, clock, runtime_id):
        if (type(quality_dips) is not PersonalRuntimeCurrent
                or type(hyperliquid) is not PersonalPerpRuntimeCurrent
                or type(clock) is not NativeVersionSafePaperOperatorClock
                or quality_dips.clock is not clock or hyperliquid.clock is not clock
                or type(runtime_id) is not str or not runtime_id):
            raise ValueError('OWNER_V2_EXACT_CURRENT_READERS_AND_CLOCK_REQUIRED')
        self._require_qd_chain(quality_dips, clock)
        self.readers = {'QUALITY_DIPS':quality_dips, 'HYPERLIQUID':hyperliquid}
        self.clock, self.runtime_id = clock, runtime_id
        self.enrollments = {}
        for lane, reader in self.readers.items():
            actual_lane, native, _ = validate_personal_inception(reader.bootstrap.enrollment)
            if actual_lane != lane:
                raise ValueError('OWNER_V2_ACCOUNT_LANE_CONFLICT')
            self.enrollments[lane] = native
        qd, hl = (self.enrollments[k] for k in LANES)
        if (qd['account_id']==hl['account_id'] or qd['epoch']==hl['epoch']
                or qd['release_digest']!=hl['release_digest']):
            raise ValueError('OWNER_V2_DISTINCT_ACCOUNTS_ONE_RELEASE_REQUIRED')
        self.release_digest = qd['release_digest']
        require_installed_continuity_source(self.release_digest)
        self._ports = quality_dips, hyperliquid, clock, runtime_id
        self._enrollments = body(self.enrollments)
        self._release_digest = self.release_digest
        self._water = None

    @staticmethod
    def _require_qd_chain(q, clock):
        if (type(q.reader) is not OperationalAutonomousSelectedRead
                or type(q.bootstrap) is not PersonalInceptionBootstrap
                or type(q.bootstrap.publication) is not PersonalPublicationCustody
                or type(q.native_reader) is not OperationalAutonomousReader
                or q.reader.port is not q.native_reader
                or type(q.reader.authority) is not PersonalNativeReadAuthority
                or type(q.reader.authority.ownership) is not NativePersonalWriterOwnership
                or q.reader.authority.bootstrap is not q.bootstrap
                or q.reader.authority.source is not q.source
                or q.reader.authority.reports is not q.reports
                or type(q.source) is not PersonalCurrentPins
                or type(q.reports) is not PersonalCurrentPins
                or q.source.ledger is not q.reports.ledger
                or q.source.ledger is not q.bootstrap.publication.ledger
                or type(q.source.ledger) is not PersonalNativeCoordination
                or type(q.source.ledger.images) is not NativePersonalCoordinationImages
                or len(q.native_reader.dependencies) != 5
                or q.native_reader.dependencies[1] is not q.source
                or type(q.native_reader.dependencies[2]) not in (
                    NativePersonalFinancialReadAuthority, NativePersonalFinancialAuthority)
                or q.native_reader.dependencies[2].ownership is not q.reader.authority.ownership
                or q.native_reader.dependencies[2].source is not q.source
                or q.native_reader.dependencies[3] is not clock
                or type(q.native_reader.dependencies[4]) is not ProjectionTarget):
            raise ValueError('OWNER_V2_QD_CONCRETE_NATIVE_READ_CHAIN_REQUIRED')

    def _verify(self):
        if (tuple(self.readers)!=LANES
                or any(a is not b for a,b in zip(
                    (*self.readers.values(),self.clock,self.runtime_id),self._ports,strict=True))
                or body(self.enrollments)!=self._enrollments
                or self.release_digest != self._release_digest
                or any(reader.clock is not self.clock for reader in self.readers.values())):
            raise ValueError('OWNER_V2_READBACK_COMPONENT_CHANGED')
        self._require_qd_chain(self.readers['QUALITY_DIPS'], self.clock)
        if require_version_safe_release_digest(
                clock=self.clock,runtime_id=self.runtime_id,
                release_digest=self.release_digest) is not True:
            raise ValueError('OWNER_V2_NATIVE_CLOCK_RELEASE_REFUSED')
        for lane, reader in self.readers.items():
            actual_lane, native, _ = validate_personal_inception(reader.bootstrap.enrollment)
            if actual_lane!=lane or native!=self.enrollments[lane]:
                raise ValueError('OWNER_V2_NATIVE_ACCOUNT_CHANGED')
        if verify_original_account_roots(self.enrollments) is not True:
            raise ValueError('OWNER_V2_ORIGINAL_NATIVE_RESOURCE_EVIDENCE_MISSING')

    def capture(self):
        self._verify()
        start = self.clock()
        if type(start) is not int:
            raise ValueError('OWNER_V2_INTEGER_CURRENT_UTC_REQUIRED')
        q = self.readers['QUALITY_DIPS']
        cut, _generation, _publication = q._capture(start)
        native = q.native_reader.read_committed()
        if (native['source_pin']!=cut['source']
                or digest(native['state'])!=cut['state_digest']):
            raise ValueError('OWNER_V2_QD_FINANCIAL_CUT_CHANGED')
        _original, ack = q.bootstrap.publication.acknowledged(q.bootstrap.scope()['operation_id'])
        qd = {'enrollment_digest':digest(self.enrollments['QUALITY_DIPS']),
              'source':cut['source'],'reports':cut['reports'],
              'source_revision':cut['source_revision'],
              'report_revision':len(cut['reports']['reports'])-1,
              'state':native['state'],'genesis_ack_digest':digest(ack)}
        hl = self.readers['HYPERLIQUID'].capture()
        # A double collect establishes an overlap between the two independently
        # audited lane cuts. Do not silently accept a mixed account revision.
        checked_q, _, _ = q._capture(self.clock())
        checked_h = self.readers['HYPERLIQUID'].capture()
        if (checked_q['source'] != qd['source'] or checked_q['reports'] != qd['reports']
                or checked_q['state_digest'] != digest(qd['state'])
                or {k:v for k,v in checked_h.items() if k!='observed_at'} !=
                   {k:v for k,v in hl.items() if k!='observed_at'}):
            raise ValueError('OWNER_V2_TWO_ACCOUNT_CUT_CHANGED')
        self._verify()
        end = self.clock()
        if type(end) is not int or not start <= end <= start+5:
            raise ValueError('OWNER_V2_CURRENT_CAPTURE_EXPIRED')
        result = {'schema':'ATLAS_ORIGINAL_TWO_ACCOUNT_CURRENT_READBACK_V2',
                  'release_digest':self.release_digest,'observed_at':end,
                  'accounts':{'QUALITY_DIPS':qd,'HYPERLIQUID':hl},
                  'financial_write_authority':False,'paper_start_authority':False}
        mark = tuple((result['accounts'][lane]['source_revision'],
                      result['accounts'][lane]['report_revision']) for lane in LANES)
        if self._water:
            for lane, prior, current in zip(LANES,self._water[0],mark,strict=True):
                old = self._water[1]['accounts'][lane]
                new = result['accounts'][lane]
                if (any(c<p for p,c in zip(prior,current,strict=True))
                        or new['source']['entries'][:len(old['source']['entries'])]!=old['source']['entries']
                        or new['reports']['reports'][:len(old['reports']['reports'])]!=old['reports']['reports']
                        or {k:v for k,v in new['source'].items() if k!='entries'} !=
                           {k:v for k,v in old['source'].items() if k!='entries'}
                        or {k:v for k,v in new['reports'].items() if k!='reports'} !=
                           {k:v for k,v in old['reports'].items() if k!='reports'}
                        or new['genesis_ack_digest']!=old['genesis_ack_digest']):
                    raise ValueError('OWNER_V2_CURRENT_HISTORY_ROLLBACK_OR_SUBSTITUTION')
                if (prior==current and
                        {k:v for k,v in new.items() if k!='observed_at'} !=
                        {k:v for k,v in old.items() if k!='observed_at'}):
                    raise ValueError('OWNER_V2_SAME_REVISION_FINANCIAL_CONFLICT')
        self._water = mark, strict(body(result))
        return strict(body(result))

    def require_readonly(self):
        """Cold recovery cannot silently inherit a historical writer lease."""
        self._verify()
        q = self.readers['QUALITY_DIPS']
        h = self.readers['HYPERLIQUID']
        authority = getattr(q.reader,'authority',None)
        if (getattr(getattr(authority,'ownership',None),'read_only',None) is not True
                or type(q.native_reader.dependencies[2]) is not NativePersonalFinancialReadAuthority
                or h.store.authority.ownership.read_only is not True):
            raise ValueError('OWNER_V2_RECOVERY_REQUIRES_READONLY_NATIVE_LEASES')
        return True


class NativeRecoveredReadOnlyOwner:
    """Fresh retained self-Job plus existing native history; never writer adoption.

    Deliberately cannot pass the exact financial owner type or issue a lease.
    Financial restart needs separately implemented/accepted writer handoff.
    """

    def __init__(self, *, original_self_job, readback):
        if (type(original_self_job) is not NativeOriginalSelfJob
                or type(readback) is not NativeTwoAccountCurrentReadback):
            raise ValueError('OWNER_V2_FRESH_ORIGINAL_JOB_AND_NATIVE_READBACK_REQUIRED')
        require_installed_continuity_source(readback.release_digest)
        if original_self_job.verify() is not True:
            raise ValueError('OWNER_V2_FRESH_ORIGINAL_JOB_REFUSED')
        if original_self_job.identity!=observe_self():
            raise ValueError('OWNER_V2_RECOVERY_MUST_RUN_IN_FRESH_ORIGINAL_PROCESS')
        readback.require_readonly()
        self.job, self.readback = original_self_job, readback
        self.identity = strict(body(observe_self()))
        self._ports = original_self_job, readback
        self._identity = body(self.identity)
        self._terminal = False
        self.read_accounts()

    def read_accounts(self):
        if (self._terminal or (self.job,self.readback)!=self._ports
                or body(self.identity)!=self._identity or observe_self()!=self.identity):
            self._terminal = True
            raise ValueError('OWNER_V2_READONLY_RECOVERY_IDENTITY_CHANGED')
        try:
            if self.job.verify() is not True:
                raise ValueError('OWNER_V2_FRESH_ORIGINAL_JOB_REFUSED')
            self.readback.require_readonly()
            result = self.readback.capture()
            if self.job.verify() is not True:
                raise ValueError('OWNER_V2_FRESH_ORIGINAL_JOB_REFUSED')
            if observe_self()!=self.identity:
                raise ValueError('OWNER_V2_RECOVERY_PROCESS_CHANGED_DURING_READ')
            return {'schema':'ATLAS_ORIGINAL_FRESH_OWNER_READONLY_RECOVERY_V1',
                    'observer_identity':strict(self._identity),'accounts':result['accounts'],
                    'historical_writer_rosters_unchanged':True,
                    'writer_admission_authorized':False,'paper_start_authorized':False}
        except BaseException:
            self._terminal = True
            raise

    def require_exact_roster(self, **_kwargs):
        raise ValueError('OWNER_V2_READONLY_RECOVERY_CANNOT_ADOPT_FINANCIAL_WRITERS')
