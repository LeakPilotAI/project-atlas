"""Personal custody integration, explicit in-memory native/presentation doubles."""
import copy
import json
from types import SimpleNamespace

import pytest
from app.services.paper_financial_replay import body, digest, initial_state
from app.services.personal_current_pins import PersonalCurrentPins
from test_personal_paper_inception_memory import system as inception

from scripts.observation_runtime.personal_runtime_current import PersonalRuntimeCurrent


def system():
    s = inception('QUALITY_DIPS')
    ready = s.pub.publish()
    PersonalCurrentPins.install_schema(s.ledger.db)
    for role in ('source', 'reports'):
        PersonalCurrentPins.initialize(s.ledger.db, role, ready['current'][role])
    s.ledger.db.commit()
    s.source = PersonalCurrentPins(ledger=s.ledger, name='source', clock=lambda: s.now[0])
    s.reports = PersonalCurrentPins(ledger=s.ledger, name='reports', clock=lambda: s.now[0])
    s.native_value = {'schema': 'QD_AUTO_OP_READ_V1', 'manifest': s.m, 'rows': [],
                      'state': initial_state(s.m), 'source_pin': s.source.current()}
    s.native = SimpleNamespace(enrollment=s.n, verify_resources=lambda: True,
                               read_committed=lambda: copy.deepcopy(s.native_value))
    s.payload = {'account_id': s.n['account_id'], 'epoch': s.n['epoch'],
                 'source_revision': 0, 'state': initial_state(s.m)}
    s.read_enrollment = {'schema': 'QD_AUTO_OP_READ_ENROLLMENT_V1',
                         'account_id': s.n['account_id'], 'epoch': s.n['epoch']}
    s.reader = SimpleNamespace(enrollment=s.read_enrollment,
                              read_committed=lambda *args: copy.deepcopy(s.payload),
                              verify=lambda *args, **kwargs: {'verified': True})
    s.port = PersonalRuntimeCurrent(bootstrap=s.b, source=s.source, reports=s.reports,
                                    reader=s.reader, native_reader=s.native, clock=lambda: s.now[0])
    s.request = {'scope': 'LOCAL_ENROLLED', 'enrollment': s.n, 'grant': {'synthetic': True}}
    return s


def test_native_and_runtime_current_views_bind_existing_ack_without_any_writes():
    s = system()
    try:
        before = s.ledger.db.serialize(), copy.deepcopy(s.files.values)
        with s.port.lease(s.request, s.now[0]) as lease:
            current = copy.deepcopy(lease.snapshot)
            assert current['revision'] == current['acknowledged_revision'] == current['high_water'] == 0
            assert current['generation'] == 1 and lease.check(current, s.now[0])
            assert current['publication'] == s.b.native_publication()
            cut = {'schema': 'QD_AUTO_NATIVE_FINANCIAL_CUT_V5', 'execution_domain': 'PERSONAL_PAPER',
                   'enrollment_digest': digest(s.n), 'source_revision': 0,
                   'state_digest': digest(initial_state(s.m)), 'source': s.source.current(),
                   'reports': s.reports.current()}
            assert current['financial_digest'] == digest(cut)
        runtime = {'schema': 'QD_AUTO_LOCAL_RUNTIME_V3', 'scope': 'LOCAL_ENROLLED',
                   'reader_enrollment': s.read_enrollment}
        v3 = s.port.runtime_port().current({'enrollment': runtime}, now=s.now[0])
        assert v3['source'] == cut['source'] and v3['reports'] == cut['reports']
        assert v3['enrollment_digest'] == digest(runtime)
        assert (s.ledger.db.serialize(), s.files.values) == before
    finally:
        s.ledger.db.close()


@pytest.mark.parametrize('damage', ['missing', 'pending', 'unknown', 'intent', 'state',
                                  'test-pin', 'generation', 'report-root', 'native-root',
                                  'native-state', 'presentation', 'schema', 'account'])
def test_missing_foreign_corrupt_or_uncertain_current_refuses_without_repair(damage):
    s = system()
    try:
        if damage == 'missing':
            s.ledger.db.execute('DELETE FROM personal_current WHERE name=?', ('source',))
        elif damage in ('pending', 'unknown'):
            s.ledger.db.execute('UPDATE personal_publications SET state=?', (damage.upper(),))
        elif damage == 'intent':
            row = s.custody.row(s.b.scope()['operation_id'])
            value = json.loads(row[0]); value['epoch'] = 'FOREIGN'
            s.ledger.db.execute('UPDATE personal_publications SET intent=?', (body(value),))
        elif damage == 'state':
            s.payload['state']['cash'] = '1001'
        elif damage in ('test-pin', 'report-root'):
            pin = (s.source if damage == 'test-pin' else s.reports).current()
            pin['schema' if damage == 'test-pin' else 'root'] = 'FS2_TEST_PIN_V1' if damage == 'test-pin' else [9, 9, 9]
            s.ledger.db.execute('UPDATE personal_current SET body=? WHERE name=?',
                                (body(pin), 'source' if damage == 'test-pin' else 'reports'))
        elif damage == 'generation':
            s.ledger.db.execute('UPDATE personal_current SET generation=1 WHERE name=?', ('source',))
        elif damage == 'native-root':
            s.native.verify_resources = lambda: False
        elif damage == 'native-state':
            s.native_value['state']['cash'] = '999'
        elif damage == 'presentation':
            s.reader.verify = lambda *args, **kwargs: {'verified': False}
        elif damage == 'schema':
            s.native_value['schema'] = 'SYNTHETIC_TEST_RECORD'
        elif damage == 'account':
            s.payload['epoch'] = 'FOREIGN'
        s.ledger.db.commit()
        before = s.ledger.db.serialize(), copy.deepcopy(s.files.values)
        with pytest.raises(ValueError), s.port.lease(s.request, s.now[0]):
            pytest.fail('invalid current admitted')
        assert (s.ledger.db.serialize(), s.files.values) == before
    finally:
        s.ledger.db.close()


def test_report_advance_preserves_financial_revision_and_initial_publication_identity():
    s = system()
    try:
        with s.port.lease(s.request, s.now[0]) as lease:
            first = copy.deepcopy(lease.snapshot)
        # This tests custody mapping, not report authenticity; real FS3 readback
        # supplies authenticity. The explicitly synthetic reader is unchanged.
        before = s.reports.current()
        after = copy.deepcopy(before)
        after['reports'].append({'id': [1, 99, 0], 'sha256': 'b' * 64})
        s.reports.advance(before, after)
        # Initial-only readback must not run after later acknowledged reports.
        s.b.readback.verify = lambda *args: pytest.fail('initial-only readback reused')
        with s.port.lease(s.request, s.now[0]) as lease:
            assert lease.snapshot['revision'] == 0 and lease.snapshot['generation'] == 2
            assert lease.snapshot['publication'] == first['publication']
            assert lease.snapshot['financial_digest'] != first['financial_digest']
        restarted = PersonalRuntimeCurrent(bootstrap=s.b, source=s.source, reports=s.reports,
                                           reader=s.reader, native_reader=s.native, clock=lambda: s.now[0])
        with restarted.lease(s.request, s.now[0]) as lease:
            assert lease.snapshot['generation'] == 2
    finally:
        s.ledger.db.close()


@pytest.mark.parametrize('damage', ['expiry', 'mutation', 'report-race', 'capture-race', 'clock-rollback'])
def test_lease_or_capture_change_is_not_a_reusable_authority(damage):
    s = system()
    try:
        if damage == 'capture-race':
            def verify(*args, **kwargs):
                pin = s.reports.current(); after = copy.deepcopy(pin)
                after['reports'].append({'id': [1, 88, 0], 'sha256': 'c' * 64})
                s.reports.advance(pin, after)
                return {'verified': True}
            s.reader.verify = verify
        with pytest.raises(ValueError), s.port.lease(s.request, s.now[0]) as lease:
            if damage == 'expiry':
                s.now[0] += 6
            elif damage == 'clock-rollback':
                s.now[0] -= 1
            elif damage == 'mutation':
                lease.snapshot['generation'] = 42
            elif damage == 'report-race':
                before = s.reports.current(); after = copy.deepcopy(before)
                after['reports'].append({'id': [1, 99, 0], 'sha256': 'b' * 64})
                s.reports.advance(before, after)
    finally:
        s.ledger.db.close()


def test_observed_coherent_pin_rollback_refuses_even_after_pin_object_reopen():
    s = system()
    try:
        before = s.reports.current(); after = copy.deepcopy(before)
        after['reports'].append({'id': [1, 99, 0], 'sha256': 'b' * 64})
        s.reports.advance(before, after)
        with s.port.lease(s.request, s.now[0]):
            pass
        s.ledger.db.execute('UPDATE personal_current SET body=?,generation=0 WHERE name=?', (body(before), 'reports'))
        s.ledger.db.commit()
        s.reports.known = None  # Simulate lost per-pin memory; outer high water remains.
        with pytest.raises(ValueError, match='ROLLBACK'), s.port.lease(s.request, s.now[0]):
            pytest.fail('observed rollback admitted')
    finally:
        s.ledger.db.close()


def test_installed_factory_requires_same_concrete_custody_for_both_protocols(monkeypatch):
    from test_personal_paper_runtime import installed

    from scripts.observation_runtime.personal_paper_activation import (
        NativePersonalActivationReader,
        compose_installed_personal_qd,
    )
    from scripts.observation_runtime.personal_windows_clock import LocalWindowsClock

    s = system()
    i = installed()
    # Explicit offline type-boundary test: no Windows clock, activation read or
    # resource access. The actual installed factory must refuse the foreign port.
    i.i.reader = object.__new__(NativePersonalActivationReader)
    clock = object.__new__(LocalWindowsClock)
    monkeypatch.setattr(LocalWindowsClock, 'require_operational', lambda *args: None)
    try:
        with pytest.raises(ValueError, match='CURRENT_CUSTODY_BINDING'):
            compose_installed_personal_qd(policy=i.p, enrollment=s.n,
                runtime_dependencies={'engine': SimpleNamespace(ledger=s.ledger), 'custody': object()},
                native_dependencies={'custody': s.port}, store=object(), native_reader=s.native,
                installation=i.i, local_clock=clock, runtime_id='EXPLICIT-SYNTHETIC-TEST')
    finally:
        s.ledger.db.close()
