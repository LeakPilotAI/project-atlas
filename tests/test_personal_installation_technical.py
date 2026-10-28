"""Factual check composition with explicit native release/clock/OS doubles."""
import copy
from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from app.services.paper_financial_replay import digest, initial_state
from app.services.personal_native_coordination import PersonalNativeCoordination
from app.services.personal_paper_runtime import CHECKS
from app.services.quality_dips_autonomous_paper import AutonomousPaper
from test_personal_paper_inception_memory import system as inception
from test_personal_runtime_current_memory import system

import scripts.observation_runtime.personal_installation_technical as technical_module
from scripts.observation_runtime.personal_coordination_store import NativePersonalCoordinationImages
from scripts.observation_runtime.personal_installation_technical import (
    NativePersonalTechnicalChecks,
)
from scripts.observation_runtime.personal_market_inputs import NativePersonalMarketInputs
from scripts.observation_runtime.personal_paper_inception import NativePersonalInceptionFiles
from scripts.observation_runtime.personal_release_identity import NativePersonalReleaseIdentity
from scripts.observation_runtime.personal_runtime_current import PersonalRuntimeCurrent
from scripts.observation_runtime.personal_windows_clock import LocalWindowsClock
from scripts.observation_runtime.personal_writer_ownership import NativePersonalWriterOwnership


def setup(monkeypatch, *, initial=False):
    s = inception('QUALITY_DIPS') if initial else system()
    state = initial_state(s.m)
    old = s.ledger
    old.db.execute('CREATE TABLE projections(id TEXT,receipt TEXT)')
    old.db.commit()
    ledger = object.__new__(PersonalNativeCoordination)
    ledger.manifest, ledger.connect = s.m, old.connect
    ledger._load = lambda db: (copy.deepcopy(state),digest(s.m),{})
    images = object.__new__(NativePersonalCoordinationImages)
    images.enrollment = digest(s.n)
    images.root_id = s.n['resources']['coordination']['native_id']
    images._stop_capacity = None
    images._load = lambda: (b'SYNTHETIC_CONFIG_IMAGE',{'revision':1})
    ledger.images = images
    s.b.publication.ledger = ledger
    clock = object.__new__(LocalWindowsClock)
    monkeypatch.setattr(LocalWindowsClock,'__call__',lambda self:s.now[0])
    monkeypatch.setattr(LocalWindowsClock,'require_operational',lambda *args:None)
    sample = {'schema':'QD_AUTO_CLOCK_V3','utc':s.now[0],'monotonic_ns':1000,
              'source_id':'SYNTHETIC_NOT_UTC_AUTHORITY','uncertainty_ms':1}
    monkeypatch.setattr(LocalWindowsClock,'runtime_sample',lambda self:copy.deepcopy(sample))
    monkeypatch.setattr(LocalWindowsClock,'verify_runtime_sample',lambda self,v:v==sample and v['uncertainty_ms']<=1000)
    owner = object.__new__(NativePersonalWriterOwnership)
    owner.read_only = False
    owner.enrollment, owner.ledger = s.n, ledger
    owner.authority = SimpleNamespace(clock=clock)
    owner._verify = lambda: None
    owner.outputs = {r:SimpleNamespace(root=r) for r in ('source','projection','report')}
    @contextmanager
    def owned(context, now):
        yield SimpleNamespace(snapshot=context,check=lambda value,stamp:value==context and now<=stamp<=now+30)
    owner.lease = owned
    release = object.__new__(NativePersonalReleaseIdentity)
    release.artifact_digest = s.n['release_digest']
    process = {k:v for k,v in next(iter(s.n['writers'].values())).items() if k!='schema'}
    release.verify = lambda **kw: {'process':process}
    files = NativePersonalInceptionFiles() if initial else None
    if initial:
        current, engine = None, None
        monkeypatch.setattr(technical_module,'Path',lambda path:SimpleNamespace(iterdir=lambda:iter(())))
    else:
        s.source.ledger = s.reports.ledger = ledger
        current = PersonalRuntimeCurrent(bootstrap=s.b,source=s.source,reports=s.reports,
                    reader=s.reader,native_reader=s.native,clock=clock)
        engine = object.__new__(AutonomousPaper)
        engine.ledger, engine.clock = ledger, clock
        market = object.__new__(NativePersonalMarketInputs)
        market.operator = owner.authority
        market.session = object()
        engine.source_authority, engine.session_authority = market, market.session
        engine.candidates = SimpleNamespace(ranking_authority=market,execution_authority=market)
    port = NativePersonalTechnicalChecks(bootstrap=s.b,release=release,clock=clock,runtime_id='SYNTHETIC',
                ownership=owner,ledger=ledger,files=files,current=current,engine=engine)
    return SimpleNamespace(**locals())


def test_runtime_facts_derive_from_bound_account_native_cut_clock_and_owner(monkeypatch):
    s = setup(monkeypatch)
    before = s.old.db.serialize()
    facts = s.port.inspect({'schema':'ATLAS_PERSONAL_QD_COMPOSITION_V1'})
    assert set(facts)==set(CHECKS) and all(value is True for value in facts.values())
    assert s.old.db.serialize()==before and s.port.last_failure is None
    s.old.db.close()


@pytest.mark.parametrize('damage',['release','clock','native-owner','financial-state','pending','market','scope'])
def test_unverified_runtime_facts_refuse_without_repair(monkeypatch,damage):
    s = setup(monkeypatch)
    if damage=='release': s.process['creation_filetime']+=1
    elif damage=='clock': s.sample['uncertainty_ms']=1001
    elif damage=='native-owner':
        def fail(): raise ValueError('SYNTHETIC_OWNER_REFUSAL')
        s.owner._verify=fail
    elif damage=='financial-state': s.state['cash']='1001'
    elif damage=='pending': s.old.db.execute("INSERT INTO projections VALUES('pending',NULL)");s.old.db.commit()
    elif damage=='market': s.engine.source_authority=object()
    else: s.port.runtime_id='OTHER'
    before=s.old.db.serialize()
    assert not all(s.port.inspect({}).values())
    assert s.old.db.serialize()==before
    s.old.db.close()


def test_initial_eligibility_is_not_a_financial_balance_or_recovery_permission(monkeypatch):
    s=setup(monkeypatch,initial=True)
    request={'schema':'ATLAS_PERSONAL_INCEPTION_REQUEST_V1','action':'INITIALIZE_SIMULATED_ACCOUNTS','scope':s.s.b.scope()}
    assert all(s.port.inspect(request).values())
    assert s.s.b.publication.row(request['scope']['operation_id']) is None and s.files._active is None
    assert not all(s.port.inspect({**request,'scope':{}}).values())
    assert not all(s.port.inspect({'action':'AUTO_PAPER'}).values())
    s.old.db.close()


def test_defaults_refuse():
    with pytest.raises(ValueError): NativePersonalTechnicalChecks()


def test_exhausted_verified_store_remains_readable_without_granting_write_capacity(monkeypatch):
    s = setup(monkeypatch)
    s.images._load = lambda: (b'SYNTHETIC_CONFIG_IMAGE', {'revision':128})
    assert s.port.inspect({})['CAPACITY_WITH_STOP_RESERVES'] is False
    s.owner.read_only = True
    s.owner.identity = {'schema':'QD_OP_PROCESS_ID_V1',**s.process}
    reader = NativePersonalTechnicalChecks(bootstrap=s.s.b,release=s.release,clock=s.clock,runtime_id='SYNTHETIC',
        ownership=s.owner,ledger=s.ledger,current=s.current)
    before = s.old.db.serialize()
    assert all(reader.inspect({'action':'READ_ONLY'}).values())
    assert not all(reader.inspect({'action':'AUTO_PAPER'}).values())
    assert s.old.db.serialize() == before
    s.old.db.close()
