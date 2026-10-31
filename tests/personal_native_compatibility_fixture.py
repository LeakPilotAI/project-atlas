"""Unexecuted confined native fixtures. Nothing is provisioned by import."""
import copy
import json
import os
import queue
import sqlite3
import subprocess
import sys
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

from app.services.paper_financial_replay import body, strict
from app.services.personal_publication_custody import PersonalPublicationCustody
from test_personal_paper_inception_memory import system

from scripts.observation_runtime import personal_paper_inception as inception
from scripts.observation_runtime.native_fixture_budget import NativeFixtureBudget
from scripts.observation_runtime.personal_native_scope import (
    AUTHORIZATION,
    ROOT,
    require_scope,
)

ORIGINAL_NATIVE_LOADER=inception.native_primitives


def checked_budget():
    require_scope(os.environ.get('ATLAS_PERSONAL_NATIVE_TEST_APPROVAL'),ROOT)
    b=NativeFixtureBudget(ROOT)
    if b.anchor['authorization']!=AUTHORIZATION:raise ValueError('NATIVE_TEST_SCOPE_CHANGED')
    return b


class ControlLedger:
    """Disposable SQL coordination only; reserve every DB/journal write in advance."""
    def __init__(self,path,budget):self.path,self.budget=Path(path),budget
    @contextmanager
    def connect(self,readonly=False):
        b=self.budget;b.confined_path(self.path,missing_leaf=not readonly)
        if self.path.exists() and self.path.stat().st_size>262144:raise ValueError('BOUNDED_CONTROL_DATABASE_REQUIRED')
        if readonly:
            db=sqlite3.connect(self.path.as_uri()+'?mode=ro',uri=True,timeout=2)
            try:
                db.execute('PRAGMA query_only=ON')
                yield db
            finally:db.close()
            return
        # DELETE journaling +64page cap keeps each prospective reservation bounded.
        # Reserve sidecar first,without recursively acquiring the OS budget lock.
        with b.mutation(Path(str(self.path)+'-journal'),size=266240):pass
        with b.mutation(self.path,entries=0 if self.path.exists() else 1,size=262144):
            db=sqlite3.connect(str(self.path),timeout=2)
            try:
                if db.execute('PRAGMA journal_mode=DELETE').fetchone()[0]!='delete':raise ValueError('FIXTURE_SQL_JOURNAL_MODE')
                db.execute('PRAGMA synchronous=FULL');db.execute('PRAGMA temp_store=MEMORY')
                if db.execute('PRAGMA max_page_count=64').fetchone()[0]!=64:raise ValueError('FIXTURE_SQL_PAGE_CAP')
                with db:yield db
            finally:db.close()


class NativeCase:
    def __init__(self,path,lane,*,create=False):
        self.b=checked_budget();self.path=Path(path)
        if (self.path.parent!=self.b.root/'native' or not self.path.name.startswith('case-')
                or lane not in ('QUALITY_DIPS','HYPERLIQUID')):raise ValueError('EXACT_SYNTHETIC_CASE_ROOT')
        self.native=ORIGINAL_NATIVE_LOADER();s=system(lane);s.ledger.db.close();self.e=copy.deepcopy(s.e)
        if create:
            self.b.directory(self.path)
            n=self.e['native_enrollment'];n['account_id']='SYNTHETIC-NATIVE-'+lane
            self.e['report_scope']['account_id']=n['account_id']
            for role in n['resources']:
                path=self.path/role;identity=[]
                @contextmanager
                def create_bound(path,identity=identity):
                    with self.native.w.WindowsOutput.create_root(path) as out:
                        identity.extend(self.native.native.file_identity(out.root_handle))
                        yield out
                self.b.directory(path,native_factory=create_bound)
                n['resources'][role].update(path=str(path),native_id=identity)
            self.b.write(self.path/'spec.json',body({'schema':'PERSONAL_NATIVE_SYNTHETIC_CASE_V1','lane':lane,'enrollment':self.e}).encode())
        else:
            self.b.confined_path(self.path/'spec.json')
            spec=strict((self.path/'spec.json').read_text())
            if spec['schema']!='PERSONAL_NATIVE_SYNTHETIC_CASE_V1' or spec['lane']!=lane:raise ValueError('FOREIGN_CASE_SPEC')
            self.e=spec['enrollment']
        n=self.e['native_enrollment']
        if not n['account_id'].startswith('SYNTHETIC-NATIVE-'):raise ValueError('NO_OPERATIONAL_ACCOUNT')
        for resource in n['resources'].values():
            self.b.confined_path(resource['path'])
            if Path(resource['path']).parent!=self.path:raise ValueError('CASE_RESOURCE_ESCAPE')
        self.ledger=ControlLedger(self.path/'coordination'/'publication.sqlite',self.b)
        if create:
            with self.ledger.connect() as db:PersonalPublicationCustody.install_schema(db)
        self.custody=PersonalPublicationCustody(self.ledger);self.now=self.e['parameters']['opened_at']+1
        self.allowed=True;self.phase=None

    def bind_native(self):
        owner=self;native=self.native
        class Output:
            def __init__(self,path):
                owner.b.confined_path(path)
                if Path(path).parent!=owner.path:raise ValueError('EXACT_ROLE_OUTPUT')
                self.inner=native.w.WindowsOutput(path)
            def __getattr__(self,k):return getattr(self.inner,k)
            def write_bound(self,name,data):
                value=owner.b.native_write(self.inner,name,data)
                if owner.phase=='source' and name=='inception.json':os._exit(23)
                return value
        inception.native_primitives=lambda:SimpleNamespace(w=SimpleNamespace(WindowsOutput=Output),native=native.native,read_bound=native.read_bound)

    def publisher(self):
        from scripts.observation_runtime.quality_dips_read_service import observe_self
        @contextmanager
        def issuer(scope,stamp):yield SimpleNamespace(check=lambda candidate,t:self.allowed and candidate==scope)
        @contextmanager
        def ownership(context,stamp):
            actual=observe_self()
            yield SimpleNamespace(check=lambda candidate,t:candidate==context and context['process']=={'schema':'QD_OP_PROCESS_ID_V1',**actual} and observe_self()==actual)
        bootstrap=inception.PersonalInceptionBootstrap(enrollment=self.e,publication=self.custody,
            issuer=SimpleNamespace(lease=issuer),clock=lambda:self.now,readback=inception.NativePersonalInitialReadback())
        if self.phase in ('pending','commit','ack'):
            original=self.custody.reserve
            @contextmanager
            def reserve(*args):
                with original(*args) as tx:
                    if self.phase=='pending':os._exit(23)
                    name='commit' if self.phase=='commit' else 'acknowledge';method=getattr(tx,name)
                    def exit_after(*args):method(*args);os._exit(23)
                    setattr(tx,name,exit_after);yield tx
            self.custody.reserve=reserve
        self.bind_native()
        return inception.PersonalInceptionPublisher(bootstrap=bootstrap,custody=self.custody,
            ownership=SimpleNamespace(lease=ownership),observer=lambda:{'schema':'QD_OP_PROCESS_ID_V1',**observe_self()},files=inception.NativePersonalInceptionFiles())

    def hashes(self):
        import hashlib
        return {str(p.relative_to(self.path)):hashlib.sha256(p.read_bytes()).hexdigest()
                for role in ('source','projection','report') for p in (self.path/role).iterdir() if p.is_file()}

    def decode_existing_source(self,current):
        """Read-only existing FS2 codec path;no operational admission is installed."""
        import importlib.util
        filename='operational_autonomous_store.py' if self.e['lane']=='QUALITY_DIPS' else 'operational_perp_store.py'
        spec=importlib.util.spec_from_file_location('personal_native_existing_codec',Path(__file__).resolve().parents[1]/'scripts/volume_inspector'/filename)
        codec=importlib.util.module_from_spec(spec);spec.loader.exec_module(codec)
        cls=codec.OperationalAutonomousStore if self.e['lane']=='QUALITY_DIPS' else codec.OperationalPerpStore
        archive=codec.fs2 if self.e['lane']=='QUALITY_DIPS' else codec.base.fs2
        projection_spec=importlib.util.spec_from_file_location('personal_native_projection',Path(__file__).resolve().parents[1]/'scripts/volume_inspector/financial_reporting.py')
        reporting=importlib.util.module_from_spec(projection_spec);projection_spec.loader.exec_module(reporting)
        n=self.e['native_enrollment'];projection=reporting.ProjectionTarget(n['resources']['projection']['path'],n['resources']['projection']['native_id'])
        reader=cls.__new__(cls);reader.enrollment=n;reader.trust=SimpleNamespace(current=lambda:copy.deepcopy(current['source']));reader.projection=projection
        try:
            with archive.w.WindowsOutput(n['resources']['source']['path']) as out:
                reader.output=out
                return reader._load()[3]
        finally:projection.close()


class OwnedChild:
    """Retains the original Popen handle;only exact-owned timeout termination."""
    def __init__(self,args,*,seconds=30):
        from scripts.observation_runtime.disposable_host_owner import (
            observe_handle,
            observe_pid,
        )
        self.b=checked_budget();self.seconds=seconds;self.started=time.monotonic()
        venv_executable=str(Path(sys.executable).resolve());executable=str(Path(sys._base_executable).resolve());repo=Path(__file__).resolve().parents[1]
        env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',__PYVENV_LAUNCHER__=venv_executable,
                 PYTHONPATH=os.pathsep.join(str(p) for p in (repo,repo/'backend',repo/'tests',Path(sys.prefix)/'Lib/site-packages')))
        self.p=subprocess.Popen([executable,'-B',str(Path(__file__).with_name('personal_native_compatibility_child.py')),*args],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env,text=True,creationflags=subprocess.CREATE_NO_WINDOW)
        self.lines=queue.Queue(maxsize=8);self.errors=[]
        def collect():
            for line in iter(lambda:self.p.stdout.readline(8193),''):
                if len(line)>8192 or self.lines.full():continue
                self.lines.put(line)
        def errors():
            kept=0
            for chunk in iter(lambda:self.p.stderr.read(1024),''):
                if kept<8192:self.errors.append(chunk[:8192-kept]);kept+=len(chunk[:8192-kept])
        self.readers=[threading.Thread(target=collect,daemon=True),threading.Thread(target=errors,daemon=True)]
        for thread in self.readers:thread.start()
        try:
            self.created=observe_handle(int(self.p._handle));self.identity=observe_pid(self.p.pid)
            if self.identity!={'pid':self.p.pid,'created':self.created,'image':str(Path(executable).resolve()).casefold()}:raise ValueError('EXACT_CHILD_IMAGE')
            deadline=time.monotonic()+min(10,seconds)
            while True:
                remaining=deadline-time.monotonic()
                if remaining<=0:
                    raise RuntimeError(
                        'CHILD_STARTUP_TIMEOUT '
                        f'pid={self.p.pid} '
                        f'exitcode={self.p.poll()} '
                        f'stderr={"".join(self.errors)[:8192]!r}'
                    )
                try:
                    line=self.lines.get(timeout=min(0.2,remaining))
                    break
                except queue.Empty:
                    if self.p.poll() is not None:
                        for reader in self.readers:
                            reader.join(timeout=0.5)
                        raise RuntimeError(
                            'CHILD_EXITED_BEFORE_READY '
                            f'pid={self.p.pid} '
                            f'exitcode={self.p.returncode} '
                            f'stderr={"".join(self.errors)[:8192]!r}'
                        )
            ready=json.loads(line)
            if ready.get('ready')!=self.p.pid:raise ValueError('CHILD_HANDSHAKE')
            self.p.stdin.write('GO\n');self.p.stdin.flush();self.p.stdin.close()
        except BaseException as failure:
            failure.owned_child = self
            try:
                self.p.stdin.close()
                try:self.p.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    if not hasattr(self,'created') or observe_handle(int(self.p._handle))!=self.created:raise ValueError('UNVERIFIABLE_CHILD_PRESERVED') from None
                    self.p.terminate();self.p.wait(timeout=5)
            except BaseException as cleanup_failure:
                cleanup_failure.owned_child = self
                raise
            finally:
                self._release_exited_resources()
            raise

    def _release_exited_resources(self):
        # One canonical owner: self retains Popen and every incomplete close.
        if self.p.poll() is None:
            return
        released = getattr(self, '_released_resources', set())
        self._released_resources = released
        errors = []
        for name, resource in (('stdout', self.p.stdout), ('stderr', self.p.stderr),
                               ('process', self.p._handle)):
            if name in released:
                continue
            try:
                if name == 'process':resource.Close()
                else:resource.close()
            except Exception as exc:
                errors.append(f'{name}: {exc}')
            else:
                released.add(name)
        if errors:
            failure = RuntimeError('OWNED_RESOURCE_CLEANUP_INCOMPLETE: ' + '; '.join(errors))
            failure.owned_child = self
            raise failure

    def finish(self):
        from scripts.observation_runtime.disposable_host_owner import observe_handle
        try:
            if hasattr(self, '_finished_evidence'):
                return self._finished_evidence
            if observe_handle(int(self.p._handle))!=self.created:raise ValueError('CHILD_CREATION_CHANGED')
            limit=min(self.seconds,540-self.b.check())
            if limit<=0:raise ValueError('CHILD_BUDGET_DEADLINE')
            try:self.p.wait(timeout=limit)
            except subprocess.TimeoutExpired:
                if observe_handle(int(self.p._handle))!=self.created:raise ValueError('NO_FOREIGN_TERMINATION') from None
                self.p.terminate();self.p.wait(timeout=5);raise ValueError('EXACT_OWNED_CHILD_TIMEOUT') from None
            if self.p.poll() is None:raise ValueError('OWNED_CHILD_STILL_RUNNING')
            if observe_handle(int(self.p._handle))!=self.created:raise ValueError('EXIT_IDENTITY_CHANGED')
            for thread in self.readers:thread.join(timeout=2)
            if any(thread.is_alive() for thread in self.readers):raise ValueError('OWNED_PIPE_DRAIN_INCOMPLETE')
            values=[]
            while not self.lines.empty():values.append(json.loads(self.lines.get()))
            evidence={'process':self.identity,'returncode':self.p.returncode,'reaped':self.p.poll() is not None,
                      'stdout':values,'error':''.join(self.errors)[:8192]}
            self.b.write(self.b.root/'evidence'/('child-'+str(self.created)+'-'+str(self.p.pid)+'.json'),body(evidence).encode())
            self._finished_evidence = evidence
            return evidence
        except BaseException as exc:
            # The exception keeps the canonical owner reachable for explicit
            # reconciliation/retry; never abandon a potentially live process.
            exc.owned_child = self
            raise
        finally:
            # poll() checks the retained Popen handle. An identity or budget
            # refusal does not establish exit or authorize losing that handle.
            self._release_exited_resources()
