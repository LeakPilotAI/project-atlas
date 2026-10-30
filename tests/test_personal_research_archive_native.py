"""Explicitly confined native nonfinancial research archive; no providers/accounts."""
import hashlib
import os
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import pytest
from app.services.paper_financial_replay import digest
from personal_fixture_budget import fixture_budget
from test_personal_native_coordination_memory import installation_authority
from test_personal_research_archive import (
    SyntheticSourceAuthority,
    packet,
    publish,
    scope,
)

from scripts.observation_runtime.personal_coordination_store import (
    NativePersonalCoordinationImages,
)
from scripts.observation_runtime.personal_paper_inception import native_primitives
from scripts.observation_runtime.personal_research_archive import (
    NativePersonalResearchArchive,
    initial_image,
)


@pytest.fixture
def archive(tmp_path):
    value=os.environ.get('ATLAS_QD_RESEARCH_ARCHIVE_TEST_ROOT')
    if value is None:pytest.skip('NOT EXECUTED: confined native source archive scope required')
    root=Path(value);repo=Path(__file__).resolve().parents[1]
    assert root.parent==repo/'logs/diagnostics' and root.name.startswith('qd-research-archive-native-')
    assert tmp_path.is_relative_to(root) and not any(p.is_symlink() or p.is_junction() for p in (tmp_path,*tmp_path.parents))
    started=time.monotonic();native=native_primitives()
    with native.w.WindowsOutput.create_root(str(tmp_path/'source')) as out:ident=native.native.file_identity(out.root_handle)
    e=scope(ident);images=NativePersonalCoordinationImages(root=str(tmp_path/'source'),native_root=ident,enrollment_digest=digest(e))
    images.initialize(initial_image(e),authorization=SimpleNamespace(lease=installation_authority))
    now=[100];auth=SyntheticSourceAuthority();clock=lambda:now[0]
    port=NativePersonalResearchArchive(enrollment=e,images=images,authority=auth,clock=clock)
    s=SimpleNamespace(e=e,images=images,now=now,auth=auth,clock=clock,archive=port,root=tmp_path/'source')
    def hashes():return {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in s.root.iterdir()}
    s.hashes=hashes
    try:yield s
    finally:
        images.close();assert images._retained_reads=={} and images.mutex is None
        fixture_budget(root,started=started,max_entries=2048,max_bytes=32*1024*1024,max_seconds=180)


def test_native_current_read_reopen_has_no_write_side_effect(archive):
    s=archive;publish(s);old=s.archive.current();before=s.hashes()
    other=NativePersonalResearchArchive(enrollment=s.e,images=s.images,authority=s.auth,clock=s.clock)
    assert other.current()==old and other.read(old)==packet(s) and s.hashes()==before


def test_competing_native_source_publications_have_one_acknowledged_successor(archive):
    s=archive;old=s.archive.current()
    def attempt(_):
        try:s.archive.publish(expected=old,packet=packet(s),sources={});return 'ACK'
        except ValueError:return 'REFUSED'
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(attempt,range(2)))
    assert sorted(results)==['ACK','REFUSED'] and s.archive.current()['revision']==1
    assert len(list(s.root.glob('*-ack.json')))==2


@pytest.mark.parametrize('leaf',['0002-intent.json','0002-page-0001.bin','0002-commit.json','0002-ack.json'])
def test_native_interruption_keeps_unknown_and_refuses_cold_reopen(archive,leaf):
    s=archive;write=s.images.output.write_bound
    def fail(name,data):
        result=write(name,data)
        if name==leaf:raise OSError('SYNTHETIC_INTERRUPT_AFTER_NATIVE_FLUSH')
        return result
    s.images.output.write_bound=fail
    with pytest.raises(OSError):publish(s)
    before=s.hashes();assert s.images.poisoned and 'unknown.json' in before
    with pytest.raises(ValueError):s.archive.current()
    # A fresh reader object must also refuse the retained uncertain namespace.
    with NativeClose(s):pass
    assert s.hashes()==before


class NativeClose:
    def __init__(self,s):self.s=s
    def __enter__(self):
        s=self.s
        fresh=NativePersonalCoordinationImages(root=str(s.root),native_root=s.e['root_id'],enrollment_digest=digest(s.e))
        try:
            port=NativePersonalResearchArchive(enrollment=s.e,images=fresh,authority=s.auth,clock=s.clock)
            with pytest.raises(ValueError):port.current()
        finally:fresh.close()
    def __exit__(self,*args):pass


def test_missing_custody_refuses_without_rewriting_native_evidence(archive):
    s=archive;publish(s);before=s.hashes();s.auth.valid=False
    with pytest.raises(ValueError):s.archive.current()
    assert s.hashes()==before


def test_nonparticipating_native_image_write_cannot_hide_as_same_source_revision(archive):
    s=archive;s.archive.current()
    with s.images.transaction(readonly=False) as tx:
        before=tx.read();tx.publish(before,before)
    frozen=s.hashes()
    with pytest.raises(ValueError,match='NATIVE_REVISION'):s.archive.current()
    assert s.hashes()==frozen
