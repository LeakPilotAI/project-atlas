"""Native identity/receipt tests plus explicitly simulated UI/Docker evidence."""
import copy
import importlib.util
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.skipif(os.name != 'nt', reason='Native Windows required')
spec = importlib.util.spec_from_file_location('native_recovery_fixture', ROOT/'scripts/volume_inspector/native_recovery.py')
m = importlib.util.module_from_spec(spec)
if os.name == 'nt': spec.loader.exec_module(m)


def iso(value):
    return datetime.fromtimestamp(value, timezone.utc).isoformat()


@pytest.fixture
def workflow(tmp_path):
    store = m.s.SnapshotStore.provision_synthetic(str(tmp_path/'snapshots'), str(tmp_path/'witness'))
    handoff = m.h.Handoff.provision_synthetic(store, str(tmp_path/'handoff'), m.h.ManualFixtureAuthority())
    handoff.inspect_synthetic('inspection-one', 'c'*64, approved=True)
    output = m.s.w.WindowsOutput.create_root(str(tmp_path/'approval'))
    clock = m.FixtureClock()
    labels = {'atlas.project': 'projectatlas', 'atlas.inspection.instance': store.pin['instance'], 'atlas.inspection.operation': 'inspection-one'}
    expected = {'id': 'c'*64, 'image': 'sha256:'+'d'*64, 'manifest': 'sha256:'+'e'*64, 'labels': labels}
    container = {'Id': expected['id'], 'Image': expected['image'], 'Labels': labels, 'Created': iso(900),
                 'State': {'Status': 'exited', 'Running': False, 'Pid': 0, 'StartedAt': iso(910), 'FinishedAt': iso(990)}}
    transport = m.MockDocker(container, {'Id': expected['image'], 'Manifest': expected['manifest']})
    collector = m.ExitCollector(transport, expected, output, clock)
    value = m.ApprovalWorkflow(handoff, collector, output, m.d.token_context(m.s.w), clock)
    try: yield value
    finally:
        output.close()
        handoff.close()


def test_native_context_and_simulated_positive_recovery(workflow):
    w = workflow
    context = w.context()
    assert context['pid'] == os.getpid() and context['interactive'] and not context['restricted']
    token = w.request(m.MockDialog(True))
    assert w.tickets[token]['receipt']['ui'] == 'SIMULATED_UI'
    assert w.recover(token)['inspection'] is None
    with pytest.raises(m.Refused): w.recover(token)
    assert (Path(w.output.root)/('consumed-'+token+'.json')).exists()


@pytest.mark.parametrize('field', ['sid_hash', 'logon_hash', 'session', 'elevated', 'pid'])
def test_wrong_expected_native_operator_context(workflow, field):
    w = workflow
    if field in ('sid_hash', 'logon_hash'): w.expected_context[field] = '0'*64
    elif field == 'elevated': w.expected_context[field] = not w.expected_context[field]
    else: w.expected_context[field] += 1
    with pytest.raises(m.Refused): w.request(m.MockDialog(True))
    assert w.handoff.store.snapshot()['inspection']['phase'] == 'UNCERTAIN'


def test_noninteractive_context_refused(workflow, monkeypatch):
    context = copy.deepcopy(workflow.expected_context)
    context['interactive'] = False
    workflow.expected_context = context
    monkeypatch.setattr(m.d, 'token_context', lambda _w: context)
    with pytest.raises(m.Refused): workflow.request(m.MockDialog(True))


@pytest.mark.parametrize('case,status', [('missing','MISSING'),('replaced','REPLACED'),('image','REPLACED'),('ownership','REPLACED'),
                                      ('running','RUNNING'),('unknown','UNKNOWN'),('bool-pid','UNKNOWN'),('future','UNKNOWN'),
                                      ('no-zone','UNKNOWN'),('cached','UNKNOWN'),('delay','UNKNOWN'),('disconnect','UNKNOWN')])
def test_explicit_proof_states_no_recovery(workflow, case, status):
    w = workflow
    transport = w.collector.transport
    if case == 'missing': transport.container = None
    elif case == 'replaced': transport.container['Id'] = 'f'*64
    elif case == 'image': transport.image['Manifest'] = 'sha256:'+'f'*64
    elif case == 'ownership': transport.container['Labels'] = {}
    elif case == 'running': transport.container['State'].update(Status='running', Running=True, Pid=2000)
    elif case == 'unknown': transport.container['State']['Status'] = 'dead'
    elif case == 'bool-pid': transport.container['State']['Pid'] = False
    elif case == 'future': transport.container['State']['FinishedAt'] = iso(1001)
    elif case == 'no-zone': transport.container['State']['FinishedAt'] = '1970-01-01T00:16:30'
    elif case == 'cached': transport.cached = True
    elif case == 'delay': transport.delay = 3
    else: transport.connected = False
    assert w.collector.collect()['status'] == status
    with pytest.raises(m.Refused): w.request(m.MockDialog(True))
    assert w.handoff.store.snapshot()['inspection']['phase'] == 'UNCERTAIN'


@pytest.mark.parametrize('case', ['decline', 'unverified', 'timeout', 'stale', 'helper-changed', 'context-changed'])
def test_approval_refusal_and_post_dialog_recheck(workflow, monkeypatch, case):
    # Retain original method to avoid the synthetic callback recursively calling itself.
    original = m.MockDialog.confirm
    def bounded(self, text, timeout):
        if case in ('decline', 'unverified', 'timeout'):
            answer = original(self, text, timeout)
            if case == 'decline': answer['approved'] = False
            elif case == 'unverified': answer['verified'] = False
            else: answer['timed_out'] = True
            return answer
        answer = original(self, text, timeout)
        if case == 'stale': workflow.clock.value += 46
        elif case == 'helper-changed': workflow.collector.transport.container['State']['FinishedAt'] = iso(991)
        else: workflow.expected_context['pid'] += 1
        return answer
    monkeypatch.setattr(m.MockDialog, 'confirm', bounded)
    with pytest.raises(m.Refused): workflow.request(m.MockDialog(True))
    assert workflow.tickets == {}


@pytest.mark.parametrize('case', ['forged','receipt','revision','stale','disconnect','replacement'])
def test_recovery_invalid_or_changed_authority(workflow, case):
    w = workflow
    token = w.request(m.MockDialog(True))
    if case == 'forged': token = 'f'*64
    elif case == 'receipt': (Path(w.output.root)/('approval-'+token+'.json')).write_bytes(b'{}')
    elif case == 'revision':
        proof = w.handoff.authority.recovery.attest_exit('c'*64, 'inspection-one', 1000)
        grant = w.handoff.authority.recovery.approve(w.handoff.store.snapshot(), proof, approved=True)
        w.handoff.recover_synthetic(proof, grant, 1000)
    elif case == 'stale': w.clock.value += 46
    elif case == 'disconnect': w.collector.transport.connected = False
    else: w.collector.transport.container['Id'] = 'f'*64
    with pytest.raises((m.Refused, OSError)): w.recover(token)


@pytest.mark.parametrize('phase', ['approval','consumed','proof','handoff'])
def test_failure_to_persist_evidence_never_clears_inspection(workflow, monkeypatch, phase):
    w = workflow
    obj = w.handoff.output if phase == 'handoff' else w.output
    original = obj._write
    def fail(directory, name, raw):
        prefix = {'approval':'approval-', 'consumed':'consumed-', 'proof':'proof-', 'handoff':'intent-00000002'}[phase]
        if name.startswith(prefix): raise OSError('Synthetic evidence storage unavailable')
        return original(directory, name, raw)
    if phase in ('consumed','handoff'):
        token = w.request(m.MockDialog(True))
        monkeypatch.setattr(obj, '_write', fail)
        with pytest.raises(OSError): w.recover(token)
    else:
        monkeypatch.setattr(obj, '_write', fail)
        with pytest.raises(OSError): w.request(m.MockDialog(True))
    assert w.handoff.store.snapshot()['inspection']['phase'] == 'UNCERTAIN'


def test_interrupted_recovery_retains_consumed_receipt(workflow, monkeypatch):
    w = workflow
    token = w.request(m.MockDialog(True))
    original = w.handoff.store.output._write
    def fail(directory, name, raw):
        if name == 'snapshot-00000002.json': raise OSError('Synthetic interrupted recovery')
        return original(directory, name, raw)
    monkeypatch.setattr(w.handoff.store.output, '_write', fail)
    with pytest.raises(OSError): w.recover(token)
    assert (Path(w.output.root)/('consumed-'+token+'.json')).exists()
    with pytest.raises(m.Refused): w.recover(token)
    with pytest.raises(m.Refused): w.handoff.store.snapshot()


def test_concurrent_recovery_single_use(workflow):
    w = workflow
    token = w.request(m.MockDialog(True))
    barrier = threading.Barrier(2)
    def attempt(_):
        barrier.wait(5)
        try: w.recover(token); return True
        except m.Refused: return False
    with ThreadPoolExecutor(2) as pool:
        assert sorted(pool.map(attempt, [0, 1])) == [False, True]


def test_fixture_and_imported_payload_not_production_authority(workflow):
    with pytest.raises(m.Refused): workflow.production_admission()
    with pytest.raises(m.Refused): m.ExitCollector(object(), workflow.collector.expected, workflow.output, workflow.clock)
    with pytest.raises(m.Refused): workflow.request(object())


@pytest.mark.parametrize('surface', ['snapshot','witness'])
def test_corrupt_state_refuses_before_approval(workflow, surface):
    store = workflow.handoff.store
    path = Path(store.output.root)/'snapshot-00000001.json' if surface == 'snapshot' else Path(store.witness.root)/'commit-00000001.json'
    path.write_bytes(b'INCOMPLETE')
    with pytest.raises(m.Refused): workflow.request(m.MockDialog(True))
    assert workflow.tickets == {}


def test_issuer_restart_does_not_restore_approval_from_file(workflow):
    w = workflow
    token = w.request(m.MockDialog(True))
    restarted = m.ApprovalWorkflow(w.handoff, w.collector, w.output, w.expected_context, w.clock)
    with pytest.raises(m.Refused): restarted.recover(token)
    assert w.handoff.store.snapshot()['inspection']['phase'] == 'UNCERTAIN'


def test_concurrent_startup_and_recovery_cannot_start_uncertain_writer(workflow):
    w = workflow
    token = w.request(m.MockDialog(True))
    barrier = threading.Barrier(2)
    def attempt(recovery):
        barrier.wait(5)
        try:
            if recovery: w.recover(token)
            else: w.handoff.start_synthetic('startup-one', {'pid': 1000, 'created': 1000, 'exe': 'a'*64, 'command': 'b'*64})
            return True
        except m.Refused: return False
    with ThreadPoolExecutor(2) as pool:
        result = list(pool.map(attempt, [True, False]))
    # If recovery commits first, a separately requested start may then enter
    # PENDING. Otherwise startup must refuse while inspection is UNCERTAIN.
    state = w.handoff.store.snapshot()
    assert not (state['startup'] is not None and state['inspection'] is not None)
    if result[1]: assert result[0] and state['inspection'] is None


def test_native_impersonated_thread_is_not_operator_authority(workflow):
    c, W, w = m.s.C, m.s.native.W, m.s.w
    normal, restricted, everyone = W.HANDLE(), W.HANDLE(), c.c_void_p()
    convert = w.bind(w.A, 'ConvertStringSidToSidW', [W.LPCWSTR, c.POINTER(c.c_void_p)])
    restrict = w.bind(w.A, 'CreateRestrictedToken', [W.HANDLE, W.DWORD, W.DWORD, c.c_void_p, W.DWORD, c.c_void_p,
                                                 W.DWORD, c.POINTER(w.SidAttr), c.POINTER(W.HANDLE)])
    impersonate = w.bind(w.A, 'ImpersonateLoggedOnUser', [W.HANDLE])
    revert = w.bind(w.A, 'RevertToSelf', [])
    try:
        w.check(w.open_token(w.process(), 0xE, c.byref(normal)))
        w.check(convert('S-1-1-0', c.byref(everyone)))
        entry = w.SidAttr(everyone, 0)
        w.check(restrict(normal, 1, 0, None, 0, None, 1, c.byref(entry), c.byref(restricted)))
        w.check(impersonate(restricted))
        try:
            with pytest.raises(PermissionError): workflow.context()
        finally: w.check(revert())
    finally:
        if normal: w.close_handle(normal)
        if restricted: w.close_handle(restricted)
        if everyone: w.local_free(everyone)


def test_native_dialog_timeout_is_refusal(tmp_path):
    output = m.s.w.WindowsOutput.create_root(str(tmp_path/'dialog'))
    try:
        answer = m.d.NativeDialog(m.s.w, output).confirm('SYNTHETIC NATIVE TIMEOUT TEST. No real services or containers. This test automatically cancels after one second.', 1000)
        assert answer['created'] and not answer['approved']
        assert answer['timed_out'] and answer['button'] == 2
        (tmp_path/'native-dialog-result.json').write_text(m.s.encoded(answer).decode())
    finally: output.close()
