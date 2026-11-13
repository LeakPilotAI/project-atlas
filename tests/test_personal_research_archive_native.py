"""Explicitly confined native nonfinancial research archive; no providers/accounts."""
import copy
import hashlib
import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
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


def test_original_qd_candidate_and_provenance_publish_to_actual_native_source_archive(archive,tmp_path):
    from app.services.paper_source_publication import QualityDipsSourcePublication
    from test_quality_dips_autonomous_paper import candidate
    from test_quality_dips_autonomous_paper import setup as engine_setup
    s=archive;engine_root=tmp_path/'synthetic-engine';engine_root.mkdir()
    n=engine_setup(engine_root);s.now[0]=n.now[0];b=candidate(n)
    raw={'board':b['board'],'observations':{b['instrument']['symbol']:b['observation']},
        'instruments':[b['instrument']],'quotes':{b['instrument']['symbol']:b['quote']},
        'publication':b['publication'],'monitors':{}}
    for name in ('verify_components','verify_publication','verify_head','verify_current','verify_research'):
        setattr(s.auth,name,lambda *args:s.auth.valid)
    producer=QualityDipsSourcePublication(research=SimpleNamespace(read_current=lambda:copy.deepcopy(raw)),
        candidates=n.engine.candidates,source_id=s.e['source_id'],authority=s.auth,archive=s.archive,clock=s.clock)
    before=n.ledger.snapshot()
    published=producer.publish_scanner(b['board'],datetime.fromtimestamp(s.now[0],UTC).isoformat())
    assert published['bundles']==[b] and producer.read_current()==published and n.ledger.snapshot()==before



def test_original_native_handle_bound_capacity_readback_does_not_create_a_successor(
    archive,
):
    s = archive
    before = s.hashes()
    report = s.archive.capacity_readonly(
        horizon_seconds=30 * 127,
        publication_interval_seconds=30,
    )
    assert report["schema"] == "QD_ORIGINAL_NATIVE_SOURCE_CAPACITY_READONLY_V1"
    assert report["native_revision"] == 1
    assert report["logical_revision"] == 0
    assert report["native_remaining_publications"] == 127
    assert report["within_existing_epoch"] is True
    assert report["paper_startup_authorized"] is False
    assert before == s.hashes()
    publish(s)
    after = s.hashes()
    report = s.archive.capacity_readonly(
        horizon_seconds=90 * 86400,
        publication_interval_seconds=30,
    )
    assert report["native_revision"] == 2
    assert report["logical_revision"] == 1
    assert report["native_remaining_publications"] == 126
    assert report["requires_new_original_source_epoch"] is True
    assert report["automatic_rollover_verified"] is False
    assert report["paper_startup_authorized"] is False
    assert report["live_trading_authorized"] is False
    assert after == s.hashes()



def _second_original_native_epoch(s, *, mismatch=None):
    """Only a disposable native test root; never a financial/runtime root."""
    from scripts.observation_runtime.personal_source_epoch_readback import (
        propose_link_readonly,
    )

    target = s.root.parent / "source-successor"
    native = native_primitives()
    with native.w.WindowsOutput.create_root(str(target)) as out:
        ident = native.native.file_identity(out.root_handle)
    successor_enrollment = scope(ident)
    successor_enrollment.update(
        epoch="SYNTHETIC-NEW-EPOCH",
        source_id="SYNTHETIC-NEW-SCANNER",
    )
    if mismatch == "account":
        successor_enrollment["account_id"] = "FOREIGN-ACCOUNT"
    elif mismatch == "release":
        successor_enrollment["release_digest"] = "f" * 64
    elif mismatch == "source_commit":
        successor_enrollment["source_commit"] = "a" * 40
    elif mismatch == "epoch":
        successor_enrollment["epoch"] = s.e["epoch"]
    elif mismatch == "source_id":
        successor_enrollment["source_id"] = s.e["source_id"]
    images = NativePersonalCoordinationImages(
        root=str(target), native_root=ident,
        enrollment_digest=digest(successor_enrollment),
    )
    try:
        images.initialize(
            initial_image(successor_enrollment),
            authorization=SimpleNamespace(lease=installation_authority),
        )
        new = NativePersonalResearchArchive(
            enrollment=successor_enrollment, images=images,
            authority=s.auth, clock=s.clock,
        )
        if mismatch is not None:
            with pytest.raises(ValueError, match="DISTINCT_NATIVE_SAME_ACCOUNT"):
                propose_link_readonly(predecessor=s.archive, successor=new)
        return SimpleNamespace(
            enrollment=successor_enrollment, images=images,
            archive=new, root=target,
        )
    except BaseException:
        images.close()
        raise


def test_two_real_original_native_source_epoch_ack_link_is_readback_only(archive):
    from scripts.observation_runtime.personal_source_epoch_readback import (
        propose_link_readonly,
        verify_link_readonly,
    )
    s = archive
    publish(s)
    previous_hashes = s.hashes()
    successor = _second_original_native_epoch(s)
    try:
        new = successor.archive
        init_hashes = {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in successor.root.iterdir()
        }
        link = propose_link_readonly(predecessor=s.archive, successor=new)
        assert link["predecessor"]["head"] == s.archive.current()
        assert s.hashes() == previous_hashes
        assert len(init_hashes) == len(list(successor.root.iterdir()))
        # Genuine original native transaction with DISPOSABLE synthetic
        # authority ONLY; this tests the physical storage protocol, not an
        # operational source issuer or account.
        new.publish(
            expected=new.current(),
            packet={
                "schema": "QD_SCANNER_PUBLICATION_V1",
                "source_id": successor.enrollment["source_id"],
                "revision": 1,
                "observed_at": s.now[0],
                "bundles": [],
                "monitors": {},
            },
            sources={"epoch_link": link, "research": {
                "SYNTHETIC_ONLY": True,
            }},
        )
        frozen_successor = {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in successor.root.iterdir()
        }
        result = verify_link_readonly(
            predecessor=s.archive, successor=new,
        )
        assert result["cross_epoch_link_structurally_verified"] is True
        assert result["original_predecessor_ack_readback"] is True
        assert result["original_successor_ack_readback"] is True
        assert result["operational_reader_switch_accepted"] is False
        assert result["market_issuer_independently_verified"] is False
        assert result["paper_startup_authorized"] is False
        assert result["live_trading_authorized"] is False
        restarted = NativePersonalResearchArchive(
            enrollment=successor.enrollment, images=successor.images,
            authority=s.auth, clock=s.clock,
        )
        assert verify_link_readonly(
            predecessor=s.archive, successor=restarted,
        ) == result
        assert s.hashes() == previous_hashes
        assert frozen_successor == {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in successor.root.iterdir()
        }
        # Every later successor cut must re-attest the same immutable old
        # native head. The original native append-only store is continuous.
        new.publish(
            expected=new.current(),
            packet={
                "schema": "QD_SCANNER_PUBLICATION_V1",
                "source_id": successor.enrollment["source_id"],
                "revision": 2,
                "observed_at": s.now[0],
                "bundles": [],
                "monitors": {},
            },
            sources={"epoch_link": link, "research": {
                "SYNTHETIC_ONLY": True,
            }},
        )
        ongoing = verify_link_readonly(
            predecessor=s.archive, successor=new,
        )
        assert ongoing["successor_native_revision"] == 3
        assert ongoing["paper_startup_authorized"] is False
        # The old native authority cannot continue writing after the link
        # without invalidating the immutable predecessor cut.
        publish(s, 2)
        with pytest.raises(ValueError, match="CHAIN_LINK_MISSING_OR_CHANGED"):
            verify_link_readonly(predecessor=s.archive, successor=new)
    finally:
        successor.images.close()


@pytest.mark.parametrize("mismatch", [
    "account", "release", "source_commit", "epoch", "source_id",
])
def test_original_native_epoch_refuses_foreign_account_release_or_alias(
    archive, mismatch,
):
    s = archive
    publish(s)
    old = s.hashes()
    next_epoch = _second_original_native_epoch(s, mismatch=mismatch)
    try:
        assert s.hashes() == old
        assert next_epoch.archive.current()["revision"] == 0
        from scripts.observation_runtime.personal_source_epoch_readback import (
            verify_link_readonly,
        )
        with pytest.raises(ValueError):
            verify_link_readonly(
                predecessor=s.archive, successor=next_epoch.archive,
            )
    finally:
        next_epoch.images.close()


def test_original_native_source_epoch_link_does_not_accept_unpublished_successor(
    archive,
):
    from scripts.observation_runtime.personal_source_epoch_readback import (
        propose_link_readonly,
        verify_link_readonly,
    )
    s = archive
    publish(s)
    second = _second_original_native_epoch(s)
    try:
        original_hashes = s.hashes()
        next_hashes = {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in second.root.iterdir()
        }
        assert propose_link_readonly(
            predecessor=s.archive, successor=second.archive,
        )["schema"] == "QD_ORIGINAL_NATIVE_SOURCE_EPOCH_LINK_V1"
        with pytest.raises(ValueError, match="SUCCESSOR_PUBLISHED_IMAGE_REQUIRED"):
            verify_link_readonly(
                predecessor=s.archive, successor=second.archive,
            )
        assert s.hashes() == original_hashes
        assert next_hashes == {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in second.root.iterdir()
        }
    finally:
        second.images.close()



def test_native_successor_missing_epoch_provenance_fails_without_rewriting(
    archive,
):
    from scripts.observation_runtime.personal_source_epoch_readback import (
        propose_link_readonly,
        verify_link_readonly,
    )

    s = archive
    publish(s)
    second = _second_original_native_epoch(s)
    try:
        expected = propose_link_readonly(
            predecessor=s.archive, successor=second.archive,
        )
        assert expected["predecessor"]["head"] == s.archive.current()
        second.archive.publish(
            expected=second.archive.current(),
            packet={
                "schema": "QD_SCANNER_PUBLICATION_V1",
                "source_id": second.enrollment["source_id"],
                "revision": 1,
                "observed_at": s.now[0],
                "bundles": [],
                "monitors": {},
            },
            sources={"epoch_link": {
                "schema": "FORGED_DIGEST_IS_NOT_AUTHORITY",
            }},
        )
        frozen_old = s.hashes()
        frozen_new = {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in second.root.iterdir()
        }
        with pytest.raises(ValueError, match="CHAIN_LINK_MISSING_OR_CHANGED"):
            verify_link_readonly(
                predecessor=s.archive, successor=second.archive,
            )
        assert s.hashes() == frozen_old
        assert frozen_new == {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in second.root.iterdir()
        }
        assert second.archive.current()["revision"] == 1
    finally:
        second.images.close()


def test_native_source_epoch_cannot_link_before_predecessor_first_publication(
    archive,
):
    from scripts.observation_runtime.personal_source_epoch_readback import (
        propose_link_readonly,
    )

    s = archive
    original_hashes = s.hashes()
    next_epoch = _second_original_native_epoch(s)
    try:
        with pytest.raises(ValueError, match="FINAL_AND_EMPTY_NEW_REQUIRED"):
            propose_link_readonly(
                predecessor=s.archive, successor=next_epoch.archive,
            )
        assert s.hashes() == original_hashes
    finally:
        next_epoch.images.close()
