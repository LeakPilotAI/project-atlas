"""Source archive over actual native-image protocol with explicit in-memory I/O.

All authority here is synthetic and confined to tests; no filesystem or provider.
"""
import copy
from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from app.services.paper_financial_replay import body, digest
from test_personal_native_coordination_memory import (
    installation_authority,
    native_double,
)

from scripts.observation_runtime.personal_research_archive import (
    NativePersonalResearchArchive,
    initial_image,
)


class SyntheticSourceAuthority:
    def __init__(self):self.valid=True;self.checks=0;self.revoke_at=None;self.exit_failure=False
    def verify_archive(self,enrollment,images,clock):return self.valid
    def verify_archive_head(self,enrollment,head,now):return self.valid
    @contextmanager
    def lease_source_publication(self,request,now):
        def check(value,stamp):
            self.checks+=1
            return self.valid and value==request and now<=stamp<=now+1 and self.checks!=self.revoke_at
        yield SimpleNamespace(check=check)
        if self.exit_failure:raise ValueError('SYNTHETIC_CUSTODY_EXIT_UNKNOWN')


def scope(root):
    return {'schema':'PERSONAL_QD_SOURCE_ARCHIVE_V1','account_id':'SYNTHETIC-QD','epoch':'SYNTHETIC-EPOCH',
        'source_id':'SYNTHETIC-SCANNER','release_digest':'b'*64,'source_commit':'c'*40,'root_id':root}


def setup(monkeypatch):
    s=native_double(monkeypatch);e=scope(s.owner.root_id);s.owner.enrollment=digest(e)
    s.owner._binding=(s.owner.output,s.owner.root,tuple(s.owner.root_id),digest(e))
    s.owner.initialize(initial_image(e),authorization=SimpleNamespace(lease=installation_authority))
    now=[100];auth=SyntheticSourceAuthority();clock=lambda:now[0]
    archive=NativePersonalResearchArchive(enrollment=e,images=s.owner,authority=auth,clock=clock)
    return SimpleNamespace(s=s,e=e,now=now,auth=auth,clock=clock,archive=archive)


def packet(s,revision=1):
    return {'schema':'QD_SCANNER_PUBLICATION_V1','source_id':s.e['source_id'],'revision':revision,
        'observed_at':s.now[0],'bundles':[],'monitors':{}}


def publish(s,revision=1):
    s.archive.publish(expected=s.archive.current(),packet=packet(s,revision),sources={'SYNTHETIC_RESEARCH':'NO_PROVIDER'})


def test_exact_source_history_and_restart_reuse_native_ack_without_financial_initialization(monkeypatch):
    s=setup(monkeypatch);original=copy.deepcopy(s.s.files);publish(s)
    first=s.archive.current();assert s.archive.read(first)==packet(s)
    publish(s,2)
    assert all(s.s.files[k]==v for k,v in original.items())
    other=NativePersonalResearchArchive(enrollment=s.e,images=s.s.owner,authority=s.auth,clock=s.clock)
    assert other.current()==s.archive.current() and other.read(other.current())==packet(s,2)
    before=copy.deepcopy(s.s.files)
    for _ in range(3):other.read(other.current())
    assert s.s.files==before and s.s.owner.remaining_commits()==125


@pytest.mark.parametrize('fault',['authority','release','resource','stale-head','wrong-source','wrong-revision',
    'stale-packet','future','schema','capacity','bad-sources'])
def test_invalid_publication_refuses_before_any_native_effect(monkeypatch,fault):
    s=setup(monkeypatch);head=s.archive.current();p=packet(s);sources={};before=copy.deepcopy(s.s.files)
    if fault=='authority':s.auth.valid=False
    elif fault=='release':s.archive.enrollment['release_digest']='0'*64
    elif fault=='resource':s.archive.enrollment['root_id']=[9,8,7]
    elif fault=='stale-head':head['revision']=9
    elif fault=='wrong-source':p['source_id']='FOREIGN'
    elif fault=='wrong-revision':p['revision']=2
    elif fault=='stale-packet':p['observed_at']=69
    elif fault=='future':p['observed_at']=101
    elif fault=='schema':p['schema']='FINANCIAL_RECORD'
    elif fault=='capacity':sources={'too_large':'x'*1024**2}
    elif fault=='bad-sources':sources=[]
    with pytest.raises(ValueError):s.archive.publish(expected=head,packet=p,sources=sources)
    assert s.s.files==before


@pytest.mark.parametrize('stage',[1,2,3,'exit','write'])
def test_ambiguous_source_publication_never_retries_or_repairs(monkeypatch,stage):
    s=setup(monkeypatch);s.auth.revoke_at=stage if type(stage) is int else None
    s.auth.exit_failure=stage=='exit'
    if stage=='write':s.s.owner.fail_leaf='0002-commit.json'
    head=s.archive.current()
    with pytest.raises((ValueError,OSError)):s.archive.publish(expected=head,packet=packet(s),sources={})
    before=copy.deepcopy(s.s.files)
    if stage in (1,2):assert 'unknown.json' not in before
    else:
        assert s.s.owner.poisoned and 'unknown.json' in before
        with pytest.raises(ValueError):s.archive.current()
    assert s.s.files==before


def test_duplicate_stale_revision_and_old_pin_cannot_duplicate_source(monkeypatch):
    s=setup(monkeypatch);old=s.archive.current();publish(s);before=copy.deepcopy(s.s.files)
    with pytest.raises(ValueError):s.archive.publish(expected=old,packet=packet(s),sources={})
    with pytest.raises(ValueError):s.archive.read(old)
    assert s.s.files==before


def test_bounded_native_capacity_remains_unchanged(monkeypatch):
    import scripts.observation_runtime.personal_coordination_store as native
    s=setup(monkeypatch);publish(s);before=copy.deepcopy(s.s.files);monkeypatch.setattr(native,'MAX_REVISIONS',2)
    with pytest.raises(ValueError,match='CAPACITY'):publish(s,2)
    assert s.s.files==before and s.archive.current()['revision']==1


def test_cannot_adopt_financial_or_foreign_initial_bytes(monkeypatch):
    s=setup(monkeypatch);bad=body({'schema':'FINANCIAL','cash':'1000'}).encode()
    with s.s.owner.transaction(readonly=False) as tx:tx.publish(tx.read(),bad)
    before=copy.deepcopy(s.s.files)
    with pytest.raises(ValueError):s.archive.current()
    assert s.s.files==before


def test_default_archive_construction_has_no_initialization_authority():
    with pytest.raises(ValueError):NativePersonalResearchArchive()


def test_natively_acknowledged_duplicate_image_is_not_a_logical_source_successor(monkeypatch):
    s=setup(monkeypatch);s.archive.current()
    with s.s.owner.transaction(readonly=False) as tx:
        before=tx.read();tx.publish(before,before)
    frozen=copy.deepcopy(s.s.files)
    with pytest.raises(ValueError,match='NATIVE_REVISION'):s.archive.current()
    assert s.s.files==frozen


def test_cold_coherent_rollback_still_requires_accepted_external_current_cut(monkeypatch):
    s=setup(monkeypatch);publish(s);old_files=copy.deepcopy(s.s.files);publish(s,2);accepted=s.archive.current()
    s.auth.verify_archive_head=lambda enrollment,head,now:head==accepted
    s.s.files.clear();s.s.files.update(old_files);s.s.owner.known=None;s.s.owner._verified_prefix=None;s.s.owner._page_cut=None
    reader=NativePersonalResearchArchive(enrollment=s.e,images=s.s.owner,authority=s.auth,clock=s.clock)
    frozen=copy.deepcopy(s.s.files)
    with pytest.raises(ValueError,match='CUSTODY'):reader.current()
    assert s.s.files==frozen


def test_original_source_producer_roundtrips_candidate_bundle_through_native_image_port(monkeypatch,tmp_path):
    from datetime import UTC, datetime

    from app.services.paper_source_publication import QualityDipsSourcePublication
    from test_quality_dips_autonomous_paper import candidate
    from test_quality_dips_autonomous_paper import setup as engine_setup
    s=setup(monkeypatch);n=engine_setup(tmp_path);s.now[0]=n.now[0];b=candidate(n)
    raw={'board':b['board'],'observations':{b['instrument']['symbol']:b['observation']},
        'instruments':[b['instrument']],'quotes':{b['instrument']['symbol']:b['quote']},
        'publication':b['publication'],'monitors':{}}
    for name in ('verify_components','verify_publication','verify_head','verify_current','verify_research'):
        setattr(s.auth,name,lambda *args:s.auth.valid)
    producer=QualityDipsSourcePublication(research=SimpleNamespace(read_current=lambda:copy.deepcopy(raw)),
        candidates=n.engine.candidates,source_id=s.e['source_id'],authority=s.auth,archive=s.archive,clock=s.clock)
    before=n.ledger.snapshot();packet=producer.publish_scanner(b['board'],datetime.fromtimestamp(s.now[0],UTC).isoformat())
    assert packet['bundles']==[b] and producer.read_current()==packet and n.ledger.snapshot()==before
    s.now[0]+=31
    with pytest.raises(ValueError):producer.read_current()



def test_original_127_source_successors_are_not_a_months_long_paper_lease(monkeypatch):
    """Native head and forecast are read-only and cannot manufacture an epoch."""
    s = setup(monkeypatch)
    frozen = copy.deepcopy(s.s.files)
    p = s.archive.capacity_readonly(
        horizon_seconds=90 * 24 * 3600,
        publication_interval_seconds=30,
    )
    assert p["schema"] == "QD_ORIGINAL_NATIVE_SOURCE_CAPACITY_READONLY_V1"
    assert p["native_revision"] == 1 and p["logical_revision"] == 0
    assert p["native_remaining_publications"] == 127
    assert p["required_new_publications_for_horizon"] == 259200
    # A single 6.5-hour U.S. equities session needs 780 cuts if every
    # source stays at most 30 seconds old, already > six times the limit.
    equity_session = s.archive.capacity_readonly(
        horizon_seconds=6 * 3600 + 1800, publication_interval_seconds=30,
    )
    assert equity_session["required_new_publications_for_horizon"] == 780
    assert equity_session["requires_new_original_source_epoch"] is True
    assert p["within_existing_epoch"] is False
    assert p["requires_new_original_source_epoch"] is True
    assert p["automatic_rollover_verified"] is False
    assert p["paper_startup_authorized"] is False
    assert p["live_trading_authorized"] is False
    assert frozen == s.s.files
    assert s.archive.capacity_readonly(
        horizon_seconds=127 * 30, publication_interval_seconds=30,
    )["within_existing_epoch"] is True
    assert s.archive.capacity_readonly(
        horizon_seconds=128 * 30, publication_interval_seconds=30,
    )["within_existing_epoch"] is False
    publish(s)
    p2 = s.archive.capacity_readonly(horizon_seconds=127 * 30)
    assert p2["logical_revision"] == 1
    assert p2["native_revision"] == 2
    assert p2["native_remaining_publications"] == 126
    assert p2["requires_new_original_source_epoch"] is True


@pytest.mark.parametrize("damage", [
    "fake_remaining", "forged_native_ack", "foreign_enrollment",
    "revoke_authority", "noncanonical_epoch",
])
def test_source_capacity_rejects_false_original_ack_or_revoked_custody(
    monkeypatch, damage,
):
    s = setup(monkeypatch)
    frozen = copy.deepcopy(s.s.files)
    if damage == "fake_remaining":
        monkeypatch.setattr(s.s.owner, "remaining_commits", lambda: 9999)
    elif damage == "forged_native_ack":
        s.s.owner.known["revision"] = 5
    elif damage == "foreign_enrollment":
        s.archive.enrollment["epoch"] = "NOT_THE_REAL_EPOCH"
    elif damage == "revoke_authority":
        s.auth.valid = False
    else:
        import scripts.observation_runtime.personal_coordination_store as native
        monkeypatch.setattr(native, "MAX_REVISIONS", 512)
    with pytest.raises(ValueError):
        s.archive.capacity_readonly(horizon_seconds=30)
    assert frozen == s.s.files


@pytest.mark.parametrize("seconds, interval", [
    (-1, 30), (367 * 86400, 30), (False, 30),
    (30, 0), (30, -1), (30, True), (30, "30"),
    (30, 31), (30, 60), (30, 86401),
    (0.5, 30), (None, 30),
])
def test_source_capacity_cannot_infer_an_unbounded_or_forged_horizon(
    monkeypatch, seconds, interval,
):
    s = setup(monkeypatch)
    frozen = copy.deepcopy(s.s.files)
    with pytest.raises(ValueError, match="EXACT_BOUNDED_HORIZON"):
        s.archive.capacity_readonly(
            horizon_seconds=seconds, publication_interval_seconds=interval,
        )
    assert frozen == s.s.files


def test_source_capacity_writes_never_occur_in_months_long_forecast(monkeypatch):
    s = setup(monkeypatch)
    def fail(*args, **kwargs):
        raise AssertionError("read-only capacity admission attempted a native write")
    monkeypatch.setattr(s.s.owner.output, "write_bound", fail)
    for _ in range(3):
        report = s.archive.capacity_readonly(
            horizon_seconds=45 * 86400,
            publication_interval_seconds=15,
        )
        assert not report["within_existing_epoch"]
        assert report["native_root_modified"] is False
        assert report["paper_startup_authorized"] is False
