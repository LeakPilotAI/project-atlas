"""No native execution:guard,control-budget and pre-I/O validation tests only."""
import hashlib
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest
from personal_native_compatibility_fixture import ControlLedger
from test_personal_paper_inception_memory import system

from scripts.observation_runtime import personal_native_compatibility_run as runner
from scripts.observation_runtime import personal_paper_inception as inception
from scripts.observation_runtime.native_fixture_budget import (
    BudgetRefused,
    NativeFixtureBudget,
)
from scripts.observation_runtime.personal_native_scope import AUTHORIZATION, ROOT


@pytest.mark.parametrize('args',[[],['--execute'],['--execute','--approved-scope','OLD-GRANT'],['--plan','--execute','--approved-scope',AUTHORIZATION]])
def test_runner_does_not_reach_native_creation_without_exact_separate_grant(monkeypatch,args):
    monkeypatch.setattr(runner,'execute',lambda _:pytest.fail('native execution reached'))
    with pytest.raises(ValueError):runner.main(args)


def test_plan_is_inert_and_states_permission_is_missing(monkeypatch,capsys):
    monkeypatch.setattr(runner,'execute',lambda _:pytest.fail('plan must not execute'))
    assert runner.main(['--plan'])==0
    assert 'PROPOSED_NOT_AUTHORIZED' in capsys.readouterr().out
    assert runner.plan()['root']==ROOT


@pytest.mark.parametrize('field',['seconds','entries','charged_bytes'])
def test_approval_caps_cannot_be_retyped_as_float(field):
    budget=NativeFixtureBudget.__new__(NativeFixtureBudget);budget.root=Path(ROOT)
    budget.anchor={'authorization':AUTHORIZATION,'seconds':600,'entries':4096,'charged_bytes':134217728}
    budget.anchor[field]=float(budget.anchor[field])
    with pytest.raises(BudgetRefused):budget.limits()


def test_sql_sidecar_reservations_are_sequential_not_recursive_os_locks(monkeypatch):
    events=[];active=[False]
    @contextmanager
    def mutation(path,**kw):
        assert not active[0], 'nested non-reentrant Windows budget lock'
        active[0]=True;events.append((Path(path).name,kw))
        try:yield
        finally:active[0]=False
    class DB:
        def execute(self,sql):return SimpleNamespace(fetchone=lambda:(64,) if 'max_page_count' in sql else ('delete',))
        def __enter__(self):return self
        def __exit__(self,*_):pass
        def close(self):events.append('closed')
    import personal_native_compatibility_fixture as fixture
    monkeypatch.setattr(fixture.sqlite3,'connect',lambda *a,**kw:DB())
    budget=SimpleNamespace(confined_path=lambda *a,**kw:None,mutation=mutation)
    path=Path(__file__).with_name('SYNTHETIC_NOT_CREATED.sqlite')
    with ControlLedger(path,budget).connect() as db:db.execute('SYNTHETIC_NO_EFFECT')
    assert events[0][0].endswith('-journal') and events[1][0].endswith('.sqlite') and events[-1]=='closed'
    assert not path.exists()


def test_malformed_native_open_refuses_before_native_backend_import(monkeypatch):
    s=system('QUALITY_DIPS')
    try:
        s.e['report_scope']['account_id']='FOREIGN'
        monkeypatch.setattr(inception,'native_primitives',lambda:pytest.fail('unvalidated native open'))
        with pytest.raises(ValueError),inception.NativePersonalInceptionFiles().open(s.e):pytest.fail('opened')
    finally:s.ledger.db.close()


@pytest.mark.parametrize('seconds,allowed',[(599,True),(600,False),(601,False)])
def test_personal_deadline_cannot_fall_back_to_old_thirty_minute_limit(monkeypatch,seconds,allowed):
    from scripts.observation_runtime import native_fixture_budget as module
    class Root:
        def __str__(self):return ROOT
        def is_dir(self):return True
        def is_symlink(self):return False
        def is_junction(self):return False
    budget=NativeFixtureBudget.__new__(NativeFixtureBudget);budget.root=Root()
    budget.anchor={'authorization':AUTHORIZATION,'seconds':600,'entries':4096,'charged_bytes':134217728,
                   'started_monotonic_ns':0,'namespace':[]}
    monkeypatch.setattr(module.time,'monotonic_ns',lambda:seconds*10**9)
    if allowed:assert budget.check()==seconds
    else:
        with pytest.raises(BudgetRefused,match='10_MINUTE'):budget.check()


@pytest.mark.parametrize('damage',[None,'root','source','missing'])
def test_source_scope_drift_refuses_before_any_native_session(damage):
    raw=b'SYNTHETIC SOURCE ONLY'
    scope={'schema':'ATLAS_PERSONAL_NATIVE_COMPATIBILITY_PROPOSAL_V1','authorization_required':AUTHORIZATION,
           'root':ROOT,'limits':{'seconds':600,'entries':4096,'charged_bytes':134217728},
           'source_files':dict.fromkeys(runner.SOURCE_FILES,hashlib.sha256(raw).hexdigest())}
    if damage=='root':scope['root']+='-unapproved'
    elif damage=='source':scope['source_files'][runner.SOURCE_FILES[0]]='0'*64
    elif damage=='missing':scope['source_files'].pop(runner.SOURCE_FILES[0])
    if damage:
        with pytest.raises(ValueError):runner.verify_source_scope(scope,read=lambda _:raw)
    else:runner.verify_source_scope(scope,read=lambda _:raw)
