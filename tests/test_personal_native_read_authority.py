"""Actual read lease/coordination code with explicit memory native-I/O doubles."""
import copy

import pytest
from app.services.paper_financial_replay import digest
from app.services.personal_current_pins import PersonalCurrentPins
from app.services.personal_native_coordination import PersonalNativeCoordination
from test_personal_local_authority_memory import owner
from test_personal_native_coordination_memory import Images
from test_personal_paper_inception_memory import system

from scripts.observation_runtime.personal_paper_inception import (
    PersonalInceptionBootstrap,
    PersonalInceptionPublisher,
)
from scripts.observation_runtime.personal_runtime_current import PersonalNativeReadAuthority


def setup(monkeypatch, result=0):
    s = system('QUALITY_DIPS')
    s.ledger.db.close()
    w = owner(monkeypatch, result, enrollment=s.n)
    s.e['native_enrollment'] = w.e
    images = Images(PersonalNativeCoordination.initial_image(s.m))
    ledger = PersonalNativeCoordination(manifest=s.m, images=images, path='SYNTHETIC-MEMORY-ONLY')
    s.custody.ledger = ledger
    b = PersonalInceptionBootstrap(enrollment=s.e, publication=s.custody, issuer=s.issuer,
                                   clock=lambda: s.now[0], readback=s.b.readback)
    pub = PersonalInceptionPublisher(bootstrap=b, custody=s.custody, ownership=s.owner,
                                     observer=s.observer, files=s.file_port)
    current = pub.publish()['current']
    with ledger.connect() as db:
        for role in ('source', 'reports'): PersonalCurrentPins.initialize(db, role, current[role])
    w.port.ledger = w.port._ledger = ledger
    w.now[0] = s.now[0]
    source = PersonalCurrentPins(ledger=ledger, name='source', clock=w.auth.clock)
    reports = PersonalCurrentPins(ledger=ledger, name='reports', clock=w.auth.clock)
    enrollment = {'schema': 'QD_AUTO_OP_READ_ENROLLMENT_V1', 'account_id': w.e['account_id'],
                  'epoch': w.e['epoch'], 'manifest_digest': digest(s.m), 'policy_digest': w.e['policy_digest'],
                  'inception': current['source']['inception'],
                  **{r+'_root': w.e['resources'][r]['native_id'] for r in ('source', 'projection', 'report')}}
    port = PersonalNativeReadAuthority(bootstrap=b, source=source, reports=reports,
                                       ownership=w.port, enrollment=enrollment)
    return s, w, images, ledger, port


def test_native_read_lease_excludes_writers_and_has_no_publication(monkeypatch):
    s, w, images, _ledger, port = setup(monkeypatch)
    before = list(images.history), copy.deepcopy(s.files.values), copy.deepcopy(w.files)
    with port.lease(port.enrollment, w.now[0]) as lease:
        assert w.port.active == 1
        assert lease.snapshot['source'] == port.source.current()
        assert lease.snapshot['generation'] == 1
        assert lease.snapshot['high_water'] == lease.snapshot['acknowledged_revision'] == 0
        assert lease.check(lease.snapshot, w.now[0])
    assert w.port.active == 0 and len(w.released) == 1
    assert (images.history, s.files.values, w.files) == before
    w.port.close()


@pytest.mark.parametrize('damage', ['foreign', 'pending', 'unknown', 'projection', 'stale', 'changed', 'pin'])
def test_read_refuses_incomplete_or_changed_evidence_without_repair(monkeypatch, damage):
    s, w, images, ledger, port = setup(monkeypatch)
    if damage in ('pending', 'unknown', 'projection'):
        with ledger.connect() as db:
            if damage == 'projection': db.execute("INSERT INTO projections VALUES('x','{}',NULL)")
            else: db.execute('UPDATE personal_publications SET state=?', (damage.upper(),))
    before = list(images.history), copy.deepcopy(s.files.values), copy.deepcopy(w.files)
    enrollment = copy.deepcopy(port.enrollment)
    if damage == 'foreign': enrollment['epoch'] = 'FOREIGN'
    with pytest.raises(ValueError), port.lease(enrollment, w.now[0]) as lease:
        if damage == 'stale': w.now[0] += 6
        elif damage == 'changed': lease.snapshot['high_water'] = 99
        elif damage == 'pin': port.enrollment['inception'] = {}
        else: pytest.fail('invalid evidence admitted')
    assert (images.history, s.files.values, w.files) == before
    w.port.close()


def test_read_abandoned_writer_refuses_without_unknown_file_write(monkeypatch):
    s, w, images, _ledger, port = setup(monkeypatch, result=128)
    before = list(images.history), copy.deepcopy(s.files.values), copy.deepcopy(w.files)
    with pytest.raises(ValueError, match='NO_MUTATION'), port.lease(port.enrollment, w.now[0]):
        pytest.fail('abandoned writer admitted')
    assert (images.history, s.files.values, w.files) == before
    assert w.port.poisoned
    w.port.close()


def test_read_authority_defaults_refuse():
    with pytest.raises(ValueError): PersonalNativeReadAuthority()
