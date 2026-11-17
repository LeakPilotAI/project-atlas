"""Selected-source-only native writer-generation admission. Import never writes.

An existing protected LOCAL_OPERATOR handoff is mandatory. No account, approval,
schema, process, release, activation, source permission or Start is created here.
The retained native self-Job is NEW; historical writer enrollments never change.
"""
import ctypes
import os
import time
from contextlib import contextmanager
from pathlib import Path
from threading import RLock, get_ident

from app.services.paper_financial_replay import body, digest, number, strict
from app.services.personal_current_pins import PersonalCurrentPins
from app.services.personal_native_coordination import PersonalNativeCoordination
from app.services.personal_writer_generation import WriterGenerationJournal, accept_generation, replay
from scripts.observation_runtime.personal_coordination_store import NativePersonalCoordinationImages
from scripts.observation_runtime.personal_local_authority import NativePersonalOperatorAuthority
from scripts.observation_runtime.personal_native_original_self_job import NativeOriginalSelfJob
from scripts.observation_runtime.personal_owner_continuity_v2 import (
    LANES, NativeRecoveredReadOnlyOwner, NativeTwoAccountCurrentReadback,
    require_installed_continuity_source,
)
from scripts.observation_runtime.personal_paper_inception import native_primitives
from scripts.observation_runtime.quality_dips_read_service import observe_self
from scripts.volume_inspector.resting_order_store import RestingOrderStore
from scripts.volume_inspector.unified_portfolio_store import PortfolioControlStore


def _selected_source(release, release_admission=None):
    origin=(require_installed_continuity_source(release) if release_admission is None
            else require_installed_continuity_source(release,release_admission))
    expected=Path('D:/AtlasRuntime/releases')/origin['selected_code_release']/ 'scripts/observation_runtime/personal_writer_generation.py'
    if Path(__file__).absolute()!=expected:
        raise ValueError('WRITER_GENERATION_SELECTED_INSTALLED_SOURCE_REQUIRED')


class NativeWriterHandoffReader:
    """Existing-only protected handoff.json, separate from all activation grants."""
    def __init__(self, *, root, native_root, binding):
        # Reuse the existing strict native approval path/binding validation.
        from scripts.observation_runtime.personal_paper_activation import NativePersonalActivationReader
        self.reader=NativePersonalActivationReader(root=root,native_root=native_root,binding=binding)
        self._config=body({'root':root,'native_root':native_root,'binding':binding})

    def read(self):
        r=self.reader
        if body({'root':r.root,'native_root':r.native_root,'binding':r.binding})!=self._config:
            raise ValueError('WRITER_HANDOFF_APPROVAL_BINDING_CHANGED')
        n=native_primitives()
        with n.w.WindowsOutput(r.root) as output:
            if n.native.file_identity(output.root_handle)!=r.native_root:
                raise ValueError('WRITER_HANDOFF_APPROVAL_ROOT_CHANGED')
            value=strict(n.read_bound(output,'handoff.json',r.binding)[0].decode())
        return value


def verify_previous_exited(previous):
    """OpenProcess + complete EnumProcesses; never infer exit from access denial.

    A different creation identity on a retained handle proves PID reuse, not
    ownership. No old process is adopted or terminated. Absent PID requires
    ERROR_INVALID_PARAMETER AND an independent complete native PID snapshot.
    """
    from ctypes import wintypes
    from scripts.observation_runtime.atlas_r15_disposable_writer_process_audit import _windows_handle_identity
    if (os.name!='nt' or type(previous) is not dict
            or set(previous)!={'pid','creation_filetime','image'}
            or type(previous['pid']) is not int or previous['pid']<=4
            or type(previous['creation_filetime']) is not int or previous['creation_filetime']<=0):
        raise ValueError('WRITER_HANDOFF_EXACT_PREVIOUS_NATIVE_PROCESS_REQUIRED')
    k=ctypes.WinDLL('kernel32',use_last_error=True)
    ps=ctypes.WinDLL('psapi',use_last_error=True)
    k.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD];k.OpenProcess.restype=wintypes.HANDLE
    k.CloseHandle.argtypes=[wintypes.HANDLE];k.CloseHandle.restype=wintypes.BOOL
    k.GetProcessId.argtypes=[wintypes.HANDLE];k.GetProcessId.restype=wintypes.DWORD
    k.WaitForSingleObject.argtypes=[wintypes.HANDLE,wintypes.DWORD];k.WaitForSingleObject.restype=wintypes.DWORD
    ps.EnumProcesses.argtypes=[ctypes.POINTER(wintypes.DWORD),wintypes.DWORD,ctypes.POINTER(wintypes.DWORD)]
    ps.EnumProcesses.restype=wintypes.BOOL
    start=time.monotonic()
    handle=k.OpenProcess(0x1000|0x100000,False,previous['pid'])
    error=ctypes.get_last_error() if not handle else 0
    try:
        values=(wintypes.DWORD*65536)();used=wintypes.DWORD()
        if (not ps.EnumProcesses(values,ctypes.sizeof(values),ctypes.byref(used))
                or used.value>=ctypes.sizeof(values) or used.value%ctypes.sizeof(wintypes.DWORD)):
            raise ValueError('WRITER_HANDOFF_INCOMPLETE_NATIVE_PROCESS_ENUMERATION')
        pids=set(values[:used.value//ctypes.sizeof(wintypes.DWORD)])
        if not handle:
            if error!=87 or previous['pid'] in pids:
                raise ValueError('WRITER_HANDOFF_PREVIOUS_EXIT_UNPROVED')
        else:
            observed=_windows_handle_identity(handle)
            if k.GetProcessId(handle)!=previous['pid']:
                raise ValueError('WRITER_HANDOFF_PREVIOUS_HANDLE_CHANGED')
            if observed['creation_filetime']==previous['creation_filetime']:
                if (observed['image'].casefold()!=previous['image'].casefold()
                        or k.WaitForSingleObject(handle,0)!=0):
                    raise ValueError('WRITER_HANDOFF_PREVIOUS_WRITER_STILL_LIVE_OR_AMBIGUOUS')
            elif previous['pid'] not in pids:
                raise ValueError('WRITER_HANDOFF_REUSED_PID_SNAPSHOT_CONFLICT')
        if time.monotonic()-start>1:
            raise ValueError('WRITER_HANDOFF_EXCLUSION_QUERY_EXPIRED')
        return {'previous_owner':previous,'excluded':'ORIGINAL_PROCESS_EXITED_NATIVE_CROSSCHECK'}
    finally:
        if handle and not k.CloseHandle(handle):
            raise ValueError('WRITER_HANDOFF_PROCESS_QUERY_HANDLE_CLOSE_FAILED')


class NativeWriterRecoveryCut:
    """Read-only current accounting + original immutable control/order replay."""
    def __init__(self, *, readback, portfolio=None, orders=None):
        if type(readback) is not NativeTwoAccountCurrentReadback:
            raise ValueError('WRITER_RECOVERY_NATIVE_TWO_ACCOUNT_READBACK_REQUIRED')
        readback.require_readonly()
        self.readback,self.portfolio,self.orders=readback,portfolio,orders
        self._ports=readback,portfolio,orders
        self._control_ports=None
        if (portfolio is None)!=(orders is None):
            raise ValueError('WRITER_RECOVERY_BOTH_NATIVE_CONTROL_READERS_REQUIRED')
        if portfolio is not None:
            if type(portfolio) is not PortfolioControlStore or type(orders) is not RestingOrderStore:
                raise ValueError('WRITER_RECOVERY_CONCRETE_CONTROL_READERS_REQUIRED')
            for lane,port in (('QUALITY_DIPS',portfolio),('HYPERLIQUID',orders)):
                e=readback.enrollments[lane]
                if (port.execution_domain!='LOCAL_ENROLLED'
                        or type(port.trust) is not PersonalCurrentPins
                        or port.trust.ledger is not readback.readers[lane].source.ledger
                        or port.clock is not readback.clock
                        or str(port.output.root)!=e['resources']['custody']['path']):
                    raise ValueError('WRITER_RECOVERY_EXACT_NATIVE_CUSTODY_BINDING')
            readback.bind_custody_readers({'QUALITY_DIPS':portfolio,'HYPERLIQUID':orders})
            self._control_ports=tuple((p.trust,p.authority,p.output,p.clock,body(p.manifest))
                                      for p in (portfolio,orders))

    def capture(self):
        if (self.readback,self.portfolio,self.orders)!=self._ports:
            raise ValueError('WRITER_RECOVERY_CUT_COMPONENT_CHANGED')
        if self._control_ports is not None:
            for p,sealed in zip((self.portfolio,self.orders),self._control_ports,strict=True):
                if (any(a is not b for a,b in zip((p.trust,p.authority,p.output,p.clock),sealed[:4],strict=True))
                        or body(p.manifest)!=sealed[4]):
                    raise ValueError('WRITER_RECOVERY_CONTROL_BINDING_CHANGED')
        self.readback.require_readonly()
        captured=self.readback.capture();accounts=captured['accounts']
        control={}
        for lane in LANES:
            reader=self.readback.readers[lane]
            state=accounts[lane]['state']
            if (type(state.get('positions')) is not dict
                    or any(number(p['remaining'])!=0 for p in state['positions'].values())
                    or lane=='HYPERLIQUID' and any(number(p['remaining_funding'])!=0 for p in state['positions'].values())):
                raise ValueError('WRITER_RECOVERY_NOT_INDEPENDENTLY_FLAT')
            with reader.source.ledger.connect(readonly=True) as db:
                reader.source.ledger._load(db)
                if (db.execute('SELECT 1 FROM projections WHERE receipt IS NULL').fetchone()
                        or db.execute("SELECT 1 FROM personal_publications WHERE state!='ACKNOWLEDGED' OR state IS NULL").fetchone()
                        or db.execute("SELECT 1 FROM personal_sessions WHERE state!='ACKNOWLEDGED' OR state IS NULL").fetchone()):
                    raise ValueError('WRITER_RECOVERY_PENDING_OR_UNKNOWN_PUBLICATION')
                if self.portfolio is None:
                    if (accounts[lane]['source_revision']!=0 or accounts[lane]['report_revision']!=0
                            or any(db.execute('SELECT 1 FROM '+table).fetchone()
                                   for table in ('events','autonomous_control','autonomous_activity','personal_sessions'))):
                        raise ValueError('WRITER_RECOVERY_DURABLE_STOP_AND_ORDER_READERS_REQUIRED')
        if self.portfolio is not None:
            portfolio=self.portfolio.snapshot();orders=self.orders.snapshot()
            s=portfolio['state'];o=orders['state']
            expected={lane:digest(self.readback.readers[lane].source.ledger.manifest) for lane in LANES}
            if (self.portfolio.manifest['accounts']!=expected
                    or digest(self.orders.manifest)!=self.readback.readers['HYPERLIQUID'].store.enrollment['inception_digest']
                    or portfolio['execution_domain']!='LOCAL_ENROLLED' or orders['execution_domain']!='LOCAL_ENROLLED'
                    or s['entry_closed'] is not True or s['session'] is not None and s['finalized'] is None
                    or any(row['state']!='ACKNOWLEDGED' for row in s['operations'].values())
                    or any(row['state'] not in ('ACKNOWLEDGED','CANCELLED') for row in o['orders'].values())
                    or self.portfolio.remaining_slots()<3):
                raise ValueError('WRITER_RECOVERY_STOP_ORDER_DRAIN_OR_CAPACITY_UNPROVED')
            if s['session'] is not None and (set(s['finalized']['outcomes'])!=set(LANES)
                    or any(v.get('state')!='ACKNOWLEDGED_FLAT_AND_DRAINED' for v in s['finalized']['outcomes'].values())):
                raise ValueError('WRITER_RECOVERY_DURABLE_FLAT_ACK_MISSING')
            if s['session'] is not None:
                stop=s.get('stop_context')
                if (type(stop) is not dict or set(stop)!={'schema','session_id','command_id','reason','requested_at'}
                        or stop['schema']!='ATLAS_DESKTOP_STOP_V1'
                        or type(stop['session_id']) is not str or not stop['session_id']
                        or stop['reason'] not in ('USER_SHUTDOWN','RISK_SHUTDOWN','UNKNOWN')
                        or stop['command_id']!='stop:'+digest([s['session'],stop['reason']])
                        or type(stop['requested_at']) is not int or not 0<=stop['requested_at']<=s['last_clock']
                        or s['finalized']['grant_digest']!=s['session']):
                    raise ValueError('WRITER_RECOVERY_ORIGINAL_DURABLE_STOP_CONTEXT_REQUIRED')
            control={'portfolio':portfolio,'orders':orders}
        # Strip observation time, never the financial source/report identities.
        stable={lane:{k:v for k,v in cut.items() if k!='observed_at'} for lane,cut in accounts.items()}
        checked=self.readback.capture()
        if ({lane:{k:v for k,v in cut.items() if k!='observed_at'}
             for lane,cut in checked['accounts'].items()}!=stable
                or control and (self.portfolio.snapshot()!=control['portfolio']
                                or self.orders.snapshot()!=control['orders'])):
            raise ValueError('WRITER_RECOVERY_ACCOUNT_OR_CONTROL_CUT_CHANGED')
        return {'accounts':stable,'control':control,'genesis_only':self.portfolio is None}


class NativeWriterGeneration:
    """An accepted fence is ownership only; existing financial grants still apply."""
    def __init__(self, *, job, recovery, operator, approval):
        if (type(job) is not NativeOriginalSelfJob or type(recovery) is not NativeWriterRecoveryCut
                or type(operator) is not NativePersonalOperatorAuthority
                or type(approval) is not NativeWriterHandoffReader):
            raise ValueError('WRITER_GENERATION_EXACT_NATIVE_PORTS_REQUIRED')
        r=recovery.readback
        admission=getattr(r,'_release_admission',None)
        if admission is None:_selected_source(r.release_digest)
        else:_selected_source(r.release_digest,admission)
        q=r.readers['QUALITY_DIPS'].source.ledger
        if (type(q) is not PersonalNativeCoordination or type(q.images) is not NativePersonalCoordinationImages
                or job.verify() is not True or job.identity!=observe_self()
                or operator.clock is not r.clock or operator.runtime_id!=r.runtime_id
                or operator.accounts!={k:digest(v) for k,v in r.enrollments.items()}):
            raise ValueError('WRITER_GENERATION_NATIVE_JOB_LEDGER_CLOCK_OR_ACCOUNT_CONFLICT')
        self.job,self.recovery,self.operator,self.approval=job,recovery,operator,approval
        self.clock,self.runtime_id,self.release_digest=r.clock,r.runtime_id,r.release_digest
        self.enrollments=strict(body(r.enrollments));self.identity=strict(body(job.identity))
        self.journal=WriterGenerationJournal(ledger=q,accounts=operator.accounts)
        self._ports=job,recovery,operator,approval,self.clock,self.journal
        self._readback=r
        self._operator_sid=operator.current_operator()
        self._config=body([self.enrollments,self.identity,self.runtime_id,self.release_digest])
        self._active=None;self._terminal=False;self._scope=None;self._depth=0;self._lock=RLock()

    def _native(self):
        if (self._terminal or any(a is not b for a,b in zip(
                (self.job,self.recovery,self.operator,self.approval,self.clock,self.journal),self._ports,strict=True))
                or body([self.enrollments,self.identity,self.runtime_id,self.release_digest])!=self._config
                or self.job.verify() is not True or self.identity!=observe_self()
                or self.job.identity!=self.identity):
            raise ValueError('WRITER_GENERATION_CURRENT_RETAINED_OWNER_CHANGED')
        r=self.recovery.readback
        if (r is not self._readback or self.operator.clock is not self.clock
                or self.operator.runtime_id!=self.runtime_id
                or self.operator.accounts!=self.journal.accounts
                or self.operator.current_operator()!=self._operator_sid):
            raise ValueError('WRITER_GENERATION_OPERATOR_OR_RECOVERY_PORT_CHANGED')
        r._verify()
        if r.clock is not self.clock or r.enrollments!=self.enrollments:
            raise ValueError('WRITER_GENERATION_CURRENT_ACCOUNT_OR_CLOCK_CHANGED')
        return True

    def _authorize(self, context):
        self._native();now=self.clock();record=self.approval.read()
        expected={'schema':'ATLAS_PERSONAL_WRITER_HANDOFF_V1','origin':'LOCAL_OPERATOR',
                  'action':'ACCEPT_NEW_WRITER_GENERATION_ONLY','operator_id':self.operator.current_operator(),
                  'release_digest':self.release_digest,'runtime_id':self.runtime_id,'context':context}
        if (type(record) is not dict or set(record)!=set(expected)|{'approval_id','issued_at','expires_at'}
                or any(record[k]!=v for k,v in expected.items())
                or type(record['approval_id']) is not str or not record['approval_id']
                or type(now) is not int or type(record['issued_at']) is not int or type(record['expires_at']) is not int
                or not record['issued_at']<=now<record['expires_at']<=record['issued_at']+60):
            raise ValueError('WRITER_GENERATION_DISTINCT_CURRENT_LOCAL_APPROVAL_REQUIRED')
        self.operator.activation('READ_ONLY')
        return record

    def _exclude(self, previous):
        self._native()
        if previous is None:
            expected={'schema':'QD_OP_PROCESS_ID_V1',**self.identity}
            if any(p!=expected for e in self.enrollments.values() for p in e['writers'].values()):
                raise ValueError('WRITER_GENERATION_ZERO_REQUIRES_ORIGINAL_LIVING_ROSTERS')
            return {'original_owner':self.identity,'initial_generation':True}
        if previous==self.identity:
            raise ValueError('WRITER_GENERATION_CANNOT_REUSE_OWNER_OR_OLD_LEASE')
        return verify_previous_exited(previous)

    def accept(self, *, fault=lambda phase:None):
        with self._lock:
            if self._active is not None or self._terminal:
                raise ValueError('WRITER_GENERATION_SINGLE_USE_ADMISSION')
            try:
                self._active=accept_generation(journal=self.journal,owner=self.identity,
                    authorize=self._authorize,inspect_cut=self.recovery.capture,
                    exclude_previous=self._exclude,fault=fault)
                self.verify()
                return {'schema':'ATLAS_NATIVE_WRITER_GENERATION_ACK_V1','record':strict(body(self._active)),
                        'account_inception_ack':False,'paper_start_authorized':False}
            except BaseException:
                self._terminal=True
                raise

    def verify(self):
        self._native()
        if (self._active is None or replay(self.journal.read(),self.journal.accounts)!=self._active
                or self._active['state']!='ACTIVE' or self._active['owner']!=self.identity):
            raise ValueError('WRITER_GENERATION_FENCED_OR_NOT_ACCEPTED')
        return True

    def current_roster(self):
        """Versioned current assignment, separate from immutable enrollment."""
        self.verify()
        return {'schema':'ATLAS_NATIVE_CURRENT_WRITER_ROSTER_V1',
                'generation':self._active['generation'],'fence_digest':digest(self._active),
                'original_accounts':{k:digest(v) for k,v in self.enrollments.items()},
                'roles':{lane:{role:{'schema':'QD_OP_PROCESS_ID_V1',**self.identity}
                               for role in e['writers']} for lane,e in self.enrollments.items()}}

    @contextmanager
    def scope(self):
        with self._lock, self.journal.exclusive():
            self.verify()
            current=get_ident()
            if self._scope is not None and self._scope[0]!=current:
                raise ValueError('WRITER_GENERATION_FOREIGN_OPERATION_THREAD')
            if self._scope is None:self._scope=(current,time.monotonic())
            self._depth+=1
            try:
                yield self
                if not 0<=time.monotonic()-self._scope[1]<=5:
                    raise ValueError('WRITER_GENERATION_OPERATION_EXPIRED')
                self.verify()
            except BaseException:
                self._terminal=True
                raise
            finally:
                self._depth-=1
                if self._depth==0:self._scope=None


class NativeRecoveredFinancialWriterOwner:
    """New process admission, never a restored original owner or mutable roster."""
    def __init__(self, *, readonly_owner, generation):
        if (type(readonly_owner) is not NativeRecoveredReadOnlyOwner
                or type(generation) is not NativeWriterGeneration
                or readonly_owner.job is not generation.job
                or readonly_owner.readback is not generation.recovery.readback
                or generation.verify() is not True):
            raise ValueError('WRITER_RECOVERY_FRESH_READONLY_OWNER_AND_ACCEPTED_FENCE_REQUIRED')
        readonly_owner.read_accounts()
        self.readonly_owner,self.generation=readonly_owner,generation
        self.release_digest=generation.release_digest
        self._phase='CURRENT_READBACK_ONLY'
        self._current_operation=None;self._current_readback=readonly_owner.readback
        self._ports=readonly_owner,generation

    def verify_still_running(self):
        if (self._phase!='CURRENT_READBACK_ONLY' or (self.readonly_owner,self.generation)!=self._ports):
            raise ValueError('WRITER_RECOVERY_OWNER_UNKNOWN_OR_CHANGED')
        try:
            self.generation.verify()
            if self._current_operation is None:self.readonly_owner.read_accounts()
            else:
                issuer,ports,session,started=self._current_operation
                if (issuer.owner is not self or issuer._ports!=ports or issuer._session!=session
                        or not issuer._lease_lock.locked() or issuer._revoke
                        or not 0<=time.monotonic()-started<=5):
                    raise ValueError('WRITER_RECOVERY_CURRENT_OPERATION_CHANGED')
            return True
        except BaseException:
            self._phase='CURRENT_READBACK_UNKNOWN'
            raise

    def _verify_original_job(self):
        return self.generation._native()

    def require_exact_roster(self, *, qd, perp):
        if self.generation.enrollments!={'QUALITY_DIPS':qd,'HYPERLIQUID':perp}:
            raise ValueError('WRITER_RECOVERY_HISTORICAL_ACCOUNT_BINDING_CHANGED')
        return self.verify_still_running()

    def require_current_clock(self, *, clock, runtime_id):
        if clock is not self.generation.clock or runtime_id!=self.generation.runtime_id:
            raise ValueError('WRITER_RECOVERY_SHARED_CLOCK_REQUIRED')
        return self.verify_still_running()

    def require_financial_fence(self):
        return self.generation.verify()

    @contextmanager
    def financial_operation_scope(self, issuer):
        from scripts.observation_runtime.personal_native_selected_owned_job_preflight import RetainedSelectedNativeOwnerPreflight
        with self.generation.scope():
            with RetainedSelectedNativeOwnerPreflight.financial_operation_scope(self,issuer):
                yield

    @contextmanager
    def _bounded_current_operation(self, issuer):
        from scripts.observation_runtime.personal_native_selected_owned_job_preflight import RetainedSelectedNativeOwnerPreflight
        with RetainedSelectedNativeOwnerPreflight._bounded_current_operation(self,issuer):
            yield
