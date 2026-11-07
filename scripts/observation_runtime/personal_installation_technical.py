"""Factual personal QD installation checks; no enrollment or startup defaults.

Inception checks recognize only this process's active, bound publication protocol.
Runtime checks require acknowledged native accounting. Market freshness is checked
separately by the bounded driver before session reservation and at each dispatch.
"""
import sqlite3
from pathlib import Path

from app.services.paper_financial_replay import body, digest, strict
from app.services.personal_native_coordination import MAX_IMAGE, PersonalNativeCoordination
from app.services.personal_paper_runtime import CHECKS
from app.services.quality_dips_autonomous_paper import AutonomousPaper, validate_autonomous_manifest

from scripts.observation_runtime.personal_coordination_store import (
    MAX_REVISIONS,
    NativePersonalCoordinationImages,
)
from scripts.observation_runtime.personal_market_inputs import NativePersonalMarketInputs
from scripts.observation_runtime.personal_paper_inception import (
    NativePersonalInceptionFiles,
    NativePersonalInitialReadback,
    PersonalInceptionBootstrap,
    validate_personal_inception,
)
from scripts.observation_runtime.personal_release_identity import NativePersonalReleaseIdentity
from scripts.observation_runtime.personal_runtime_current import PersonalRuntimeCurrent
from scripts.observation_runtime.personal_windows_clock import LocalWindowsClock
from scripts.observation_runtime.personal_writer_ownership import NativePersonalWriterOwnership


class NativePersonalTechnicalChecks:
    def __init__(self, *, bootstrap=None, release=None, clock=None, runtime_id=None,
                 ownership=None, ledger=None, files=None, current=None, engine=None):
        if (type(bootstrap) is not PersonalInceptionBootstrap
                or type(release) is not NativePersonalReleaseIdentity
                or type(clock) is not LocalWindowsClock or type(runtime_id) is not str or not runtime_id
                or type(ownership) is not NativePersonalWriterOwnership
                or type(ledger) is not PersonalNativeCoordination
                or type(ledger.images) is not NativePersonalCoordinationImages
                or ownership.ledger is not ledger or ownership.authority.clock is not clock
                or bootstrap.publication.ledger is not ledger):
            raise ValueError('PERSONAL_TECHNICAL_NATIVE_DEPENDENCIES_REQUIRED')
        lane, enrollment, manifest = validate_personal_inception(bootstrap.enrollment)
        validate_autonomous_manifest(manifest)
        if (lane != 'QUALITY_DIPS' or body(enrollment) != body(ownership.enrollment)
                or body(manifest) != body(ledger.manifest) or release.artifact_digest != enrollment['release_digest']
                or ledger.images.enrollment != digest(enrollment)
                or ledger.images.root_id != enrollment['resources']['coordination']['native_id']):
            raise ValueError('PERSONAL_TECHNICAL_ACCOUNT_OR_RELEASE')
        if current is None:
            if type(files) is not NativePersonalInceptionFiles or engine is not None or ownership.read_only:
                raise ValueError('PERSONAL_TECHNICAL_INCEPTION_PORTS')
        elif (type(current) is not PersonalRuntimeCurrent
                or current.bootstrap is not bootstrap or current.source.ledger is not ledger
                or current.clock is not clock):
            raise ValueError('PERSONAL_TECHNICAL_RUNTIME_PORTS')
        if current is not None and ownership.read_only:
            if engine is not None or files is not None:
                raise ValueError('PERSONAL_TECHNICAL_READ_ONLY_NO_ENGINE')
        elif current is not None and (type(engine) is not AutonomousPaper
                or engine.ledger is not ledger or engine.clock is not clock
                or type(engine.source_authority) is not NativePersonalMarketInputs
                or engine.source_authority.operator is not ownership.authority):
            raise ValueError('PERSONAL_TECHNICAL_RUNTIME_PORTS')
        self.bootstrap, self.release, self.clock, self.runtime_id = bootstrap, release, clock, runtime_id
        self.ownership, self.ledger, self.files, self.current, self.engine = ownership, ledger, files, current, engine
        self._ports = bootstrap, release, clock, ownership, ledger, files, current, engine
        self._scope = body(bootstrap.enrollment), runtime_id
        self.last_failure = None

    def _inception(self, request):
        if (set(request) != {'schema','action','scope'}
                or request['schema'] != 'ATLAS_PERSONAL_INCEPTION_REQUEST_V1'
                or request['action'] != 'INITIALIZE_SIMULATED_ACCOUNTS'
                or request['scope'] != self.bootstrap.scope()):
            raise ValueError('PERSONAL_TECHNICAL_INCEPTION_REQUEST')
        row = self.bootstrap.publication.row(request['scope']['operation_id'])
        if row is None or row[2] == 'PENDING':
            if row is not None and row[0] != body(request['scope']):
                raise ValueError('PERSONAL_TECHNICAL_FOREIGN_RESERVATION')
            active = self.files.verify_active(self.bootstrap.enrollment)
            if not active and any(list(Path(self.ownership.outputs[r].root).iterdir()) for r in ('source','projection','report')):
                raise ValueError('PERSONAL_TECHNICAL_PARTIAL_INCEPTION_NO_REPLAY')
            return True
        if row[2] in ('COMMITTED','ACKNOWLEDGED'):
            if row[0] != body(request['scope']) or row[3] is None:
                raise ValueError('PERSONAL_TECHNICAL_INCEPTION_COMMIT_CONFLICT')
            return NativePersonalInitialReadback().verify(self.bootstrap.enrollment, strict(row[3])) is True
        raise ValueError('PERSONAL_TECHNICAL_INCEPTION_UNKNOWN')

    def inspect(self, request):
        facts = dict.fromkeys(CHECKS, False)
        self.last_failure = None
        try:
            if (any(a is not b for a, b in zip((self.bootstrap,self.release,self.clock,self.ownership,
                    self.ledger,self.files,self.current,self.engine), self._ports, strict=True))
                    or (body(self.bootstrap.enrollment),self.runtime_id) != self._scope):
                raise ValueError('PERSONAL_TECHNICAL_COMPONENT_CHANGED')
            lane, enrollment, manifest = validate_personal_inception(self.bootstrap.enrollment)
            validate_autonomous_manifest(manifest)
            policy = self.bootstrap.enrollment['personal_policy']['accounts']['QUALITY_DIPS']
            facts['SIMULATION_ONLY'] = manifest['schema'] == 'PAPER_EPOCH_AUTONOMOUS_QD_V1'
            facts['ACCOUNT_ISOLATION'] = lane == 'QUALITY_DIPS' and manifest['currency'] == 'USD'
            facts['RISK_LIMITS'] = (policy['max_entry_notional']=='100' and policy['max_open_positions']==1
                and policy['long_only'] is True and policy['scale_in'] is False
                and manifest['fees_bps']==manifest['slippage_bps']=='2')
            release = self.release.verify(release_digest=enrollment['release_digest'])
            process = {'schema':'QD_OP_PROCESS_ID_V1',**release['process']}
            if self.ownership.read_only:
                if request.get('action') != 'READ_ONLY' or process != self.ownership.identity:
                    raise ValueError('PERSONAL_TECHNICAL_READ_ONLY_ACTION')
            elif any(writer != process for writer in enrollment['writers'].values()):
                raise ValueError('PERSONAL_TECHNICAL_RELEASE_WRITER_MISMATCH')
            self.ownership._verify()
            facts['NATIVE_RESOURCES'] = body(self.ownership.enrollment) == body(enrollment)
            self.clock.require_operational(self.runtime_id)
            sample = self.clock.runtime_sample()
            facts['CLOCK_CONTINUITY'] = self.clock.verify_runtime_sample(sample) is True
            read = {'schema':'QD_AUTO_OP_READ_ENROLLMENT_V1','account_id':enrollment['account_id'],'epoch':enrollment['epoch'],
                    **{r+'_root':enrollment['resources'][r]['native_id'] for r in ('source','projection','report')}}
            context = {'schema':'PERSONAL_NATIVE_READ_LEASE_V1','reader_enrollment':read}
            with self.ownership.lease(context, sample['utc']) as lease:
                if self.current is None:
                    facts['FINANCIAL_INTEGRITY'] = self._inception(strict(body(request)))
                    # This purpose has no engine or financial command dispatcher.
                    facts['DATA_REFUSAL_CONTROLS'] = self.engine is None and type(self.files) is NativePersonalInceptionFiles
                else:
                    cut, _generation, _publication = self.current._capture(self.clock())
                    with self.ledger.connect(readonly=True) as db:
                        state, _head, _operations = self.ledger._load(db)
                        pending = db.execute('SELECT 1 FROM projections WHERE receipt IS NULL').fetchone()
                    facts['FINANCIAL_INTEGRITY'] = pending is None and cut['state_digest'] == digest(state)
                    if self.ownership.read_only:
                        facts['DATA_REFUSAL_CONTROLS'] = self.engine is None
                    else:
                        market = self.engine.source_authority
                        facts['DATA_REFUSAL_CONTROLS'] = (type(market) is NativePersonalMarketInputs
                            and self.engine.candidates.ranking_authority is market
                            and self.engine.candidates.execution_authority is market
                            and market.session is self.engine.session_authority)
                image, pin = self.ledger.images._load()
                reserve = self.ledger.images._stop_capacity
                if self.ownership.read_only:
                    # A verified historical read needs no financial Stop room.
                    # Exhaustion still refuses every writable construction.
                    capacity = 1 <= pin['revision'] <= MAX_REVISIONS and 0 < len(image) <= MAX_IMAGE
                elif reserve is None:
                    capacity = pin['revision']+40 <= MAX_REVISIONS and len(image)+256*1024 <= MAX_IMAGE
                else:
                    capacity = (reserve['phase'] in ('RUN','STOP')
                        and reserve['limits']=={'RUN':(MAX_REVISIONS-32,MAX_IMAGE-256*1024),'STOP':(MAX_REVISIONS,MAX_IMAGE)}
                        and 1 <= pin['revision'] <= MAX_REVISIONS and 0 < len(image) <= MAX_IMAGE)
                facts['CAPACITY_WITH_STOP_RESERVES'] = capacity
                facts['WRITER_OWNERSHIP'] = lease.check(lease.snapshot,self.clock()) is True
        except (ValueError,OSError,KeyError,TypeError,AttributeError,sqlite3.Error):
            self.last_failure = 'PERSONAL_TECHNICAL_EVIDENCE_UNAVAILABLE_OR_CHANGED'
        return facts
