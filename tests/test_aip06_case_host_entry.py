"""Fail-closed tests for the dedicated case-host child entry."""

import pytest
from types import SimpleNamespace

from scripts.observation_runtime import aip06_case_host_entry as host
from scripts.observation_runtime.aip06_launch_roles import launch_role
from scripts.observation_runtime.aip06_fixture_guard import require_fixture
from scripts.observation_runtime.aip06_child_entry import ChildServices

VERIFIER = host.ntpath.join(host.ntpath.dirname(host.HOST_ENTRY), 'aip06_host_preflight.py')


def test_case_host_inherited_bootstrap_refuses_after_guarded_release(monkeypatch):
    from test_aip06_windows_adapters import bootstrap_fixture
    f = bootstrap_fixture(target_override=host.HOST_ENTRY)
    assert launch_role(['python', '-B', host.HOST_ENTRY],
                       {'case_host': host.HOST_ENTRY}) == 'acceptance_worker'
    seen = []

    def guarded_preflight():
        assert require_fixture('independent-case-host-preflight') is f.boot.guard
        seen.append('guarded')
        return {'native_acceptance': False, 'execution_authorized': False}

    monkeypatch.setattr(host, 'inspect_inherited_handoff', guarded_preflight)
    f.boot.prepare()
    assert f.boot.guard.launch_role == 'acceptance_worker'
    with pytest.raises(ValueError, match='NATIVE_CASE_HOST_EXECUTION_NOT_YET_QUALIFIED'):
        f.boot.run(lambda path: host.main())
    assert seen == ['guarded']
    assert f.events[:3] == ['HELLO', 'REQUEST', 'ACK']
    assert 'EXIT' not in f.events
    assert f.boot.failed and f.boot.state == 'RUNNING'
    with pytest.raises(ValueError, match='BOUND_CHILD_TARGET_REQUIRED'):
        f.boot.run(lambda path: pytest.fail('refused case host must not retry'))
    with pytest.raises(ValueError):
        require_fixture('independent-case-host-preflight')


@pytest.mark.parametrize('damage', [
    'ancestry', 'job', 'roots', 'ledger', 'factory',
    'source', 'source-close', 'release',
])
def test_case_host_inherited_bootstrap_failure_matrix_never_enters_target(damage):
    from test_aip06_windows_adapters import bootstrap_fixture
    f = bootstrap_fixture(damage=damage, target_override=host.HOST_ENTRY)
    entered = []
    with pytest.raises(ValueError):
        f.boot.prepare()
        f.boot.run(lambda path: entered.append(path))
    assert entered == []
    assert f.boot.failed
    assert 'EXIT' not in f.events
    with pytest.raises(ValueError):
        f.boot.run(lambda path: pytest.fail('bootstrap refusal must be terminal'))


def test_case_host_launch_is_exact_inherited_worker_role():
    argv = ['python', '-B', host.HOST_ENTRY]
    targets = {'case_host': host.HOST_ENTRY}
    assert launch_role(argv, targets) == 'acceptance_worker'


@pytest.mark.parametrize('damage', ['missing-target', 'wrong-target', 'extra-argument', 'no-bytecode'])
def test_case_host_launch_role_refuses_noncanonical_commands(damage):
    argv = ['python', '-B', host.HOST_ENTRY]
    targets = {'case_host': host.HOST_ENTRY}
    if damage == 'missing-target':
        targets.clear()
    elif damage == 'wrong-target':
        targets['case_host'] = 'foreign.py'
    elif damage == 'extra-argument':
        argv.append('--role=acceptance_supervisor')
    else:
        argv[1] = '-c'
    with pytest.raises(ValueError, match='EXACT_CASE_HOST_INHERITED_LAUNCH_REQUIRED'):
        launch_role(argv, targets)


def test_case_host_main_checks_handoff_then_refuses_native_execution(monkeypatch):
    observed = []
    monkeypatch.setattr(host, 'inspect_inherited_handoff', lambda: observed.append('checked'))
    with pytest.raises(ValueError, match='NATIVE_CASE_HOST_EXECUTION_NOT_YET_QUALIFIED'):
        host.main()
    assert observed == ['checked']


def test_case_host_main_never_promotes_failed_handoff(monkeypatch):
    def reject():
        raise ValueError('ORIGINAL_PHYSICAL_HOST_RESERVATION_STILL_HELD')
    monkeypatch.setattr(host, 'inspect_inherited_handoff', reject)
    with pytest.raises(ValueError, match='ORIGINAL_PHYSICAL_HOST_RESERVATION_STILL_HELD'):
        host.main()


def test_case_host_uses_original_child_services_private_stream(monkeypatch):
    descriptor = {'argv': ['python', '-B', host.HOST_ENTRY],
                  'targets': {'case_host': host.HOST_ENTRY},
                  'source_pins': {host.HOST_ENTRY: 'a' * 64, VERIFIER: 'b' * 64}}
    runtime = SimpleNamespace(descriptor=descriptor, verify_source=lambda path: {'path': path, 'sha256': 'b'*64, 'closed': True})
    services = ChildServices(SimpleNamespace(resources=None), runtime)
    reads = []

    def read_input(*, maximum_bytes, timeout):
        reads.append((maximum_bytes, timeout))
        return b'{"schema":"packet"}'

    services.streams = SimpleNamespace(read_input=read_input)
    guard = SimpleNamespace(processes=services)
    monkeypatch.setattr(host, 'require_fixture', lambda name: guard)
    monkeypatch.setattr(host, 'inspect', lambda packet, desc, owner: (packet, desc, owner))
    packet, desc, owner = host.inspect_inherited_handoff()
    assert packet == {'schema': 'packet'} and desc is descriptor and owner is guard
    assert reads == [(65536, 6)]


@pytest.mark.parametrize('missing_pin', [True, False])
def test_case_host_refuses_unverified_preflight_before_input(monkeypatch, missing_pin):
    pins = {host.HOST_ENTRY: 'a' * 64, VERIFIER: 'b' * 64}
    if missing_pin:
        pins.pop(VERIFIER)
    def reject_source(path):
        assert path == VERIFIER
        raise ValueError('CHILD_UNREVIEWED_SOURCE')
    runtime = SimpleNamespace(
        descriptor={'argv': ['python', '-B', host.HOST_ENTRY],
                    'targets': {'case_host': host.HOST_ENTRY}, 'source_pins': pins},
        verify_source=reject_source)
    services = ChildServices(SimpleNamespace(resources=None), runtime)
    services.streams = SimpleNamespace(read_input=lambda **kw: pytest.fail('input before source verification'))
    monkeypatch.setattr(host, 'require_fixture', lambda name: SimpleNamespace(processes=services))
    expected = 'PINNED_CASE_HOST_PREFLIGHT_SOURCE_REQUIRED' if missing_pin else 'CHILD_UNREVIEWED_SOURCE'
    with pytest.raises(ValueError, match=expected):
        host.inspect_inherited_handoff()


@pytest.mark.parametrize('damage', ['missing', 'wrong_path', 'wrong_hash', 'unclosed'])
def test_case_host_rejects_invalid_closed_source_receipt_before_input(monkeypatch, damage):
    pins = {host.HOST_ENTRY: 'a'*64, VERIFIER: 'b'*64}
    descriptor = {'argv': ['python', '-B', host.HOST_ENTRY],
                  'targets': {'case_host': host.HOST_ENTRY}, 'source_pins': pins}
    receipt = {'path': VERIFIER, 'sha256': 'b'*64, 'closed': True}
    if damage == 'missing': receipt = None
    if damage == 'wrong_path': receipt['path'] = 'foreign.py'
    if damage == 'wrong_hash': receipt['sha256'] = 'c'*64
    if damage == 'unclosed': receipt['closed'] = False
    runtime = SimpleNamespace(descriptor=descriptor, verify_source=lambda path: receipt)
    guard = SimpleNamespace(processes=SimpleNamespace(runtime=runtime,
        read_input=lambda **kw: pytest.fail('read before closed source receipt')))
    monkeypatch.setattr(host, 'require_fixture', lambda name: guard)
    with pytest.raises(ValueError, match='CLOSED_INHERITED_PREFLIGHT_SOURCE_RECEIPT_REQUIRED'):
        host.inspect_inherited_handoff()


def test_case_host_reads_bounded_private_handoff_and_calls_preflight(monkeypatch):
    observed = []
    descriptor = {'private': 'descriptor', 'argv': ['python', '-B', host.HOST_ENTRY],
                  'targets': {'case_host': host.HOST_ENTRY},
                  'source_pins': {host.HOST_ENTRY: 'a' * 64, VERIFIER: 'b' * 64}}
    packet = {'schema': 'packet'}
    guard = SimpleNamespace(processes=SimpleNamespace(runtime=SimpleNamespace(descriptor=descriptor, verify_source=lambda path: {'path': path, 'sha256': 'b'*64, 'closed': True})))
    def read_input(*, maximum_bytes, timeout):
        observed.append((maximum_bytes, timeout))
        return b'{"schema":"packet"}'
    guard.processes.read_input = read_input
    monkeypatch.setattr(host, 'require_fixture', lambda name: guard)
    monkeypatch.setattr(host, 'inspect', lambda p, d, g: (p, d, g))
    assert host.inspect_inherited_handoff() == (packet, descriptor, guard)
    assert observed == [(65536, 6)]


@pytest.mark.parametrize('field', ['argv', 'targets', 'source_pins'])
def test_case_host_refuses_unbound_launch_descriptor_before_read(monkeypatch, field):
    descriptor = {'argv': ['python', '-B', host.HOST_ENTRY],
                  'targets': {'case_host': host.HOST_ENTRY},
                  'source_pins': {host.HOST_ENTRY: 'a' * 64, VERIFIER: 'b' * 64}}
    descriptor.pop(field)
    guard = SimpleNamespace(processes=SimpleNamespace(runtime=SimpleNamespace(descriptor=descriptor, verify_source=lambda path: {'path': path, 'sha256': 'b'*64, 'closed': True})),
                            read_input=lambda **kwargs: pytest.fail('read before launch verification'))
    monkeypatch.setattr(host, 'require_fixture', lambda name: guard)
    with pytest.raises(ValueError, match='PINNED_INHERITED_CASE_HOST_COMMAND_REQUIRED'):
        host.inspect_inherited_handoff()


@pytest.mark.parametrize('maximum_bytes,timeout', [(0, 6), (65537, 6), (65536, 0), (65536, 7), (True, 6), (65536, True)])
def test_case_host_rejects_unbounded_read_before_fixture_lookup(maximum_bytes, timeout, monkeypatch):
    monkeypatch.setattr(host, 'require_fixture', lambda name: pytest.fail('unexpected fixture lookup'))
    with pytest.raises(ValueError, match='BOUNDED_CASE_HOST_HANDOFF_READ_REQUIRED'):
        host.inspect_inherited_handoff(maximum_bytes=maximum_bytes, timeout=timeout)


def test_case_host_rejects_invalid_private_payload_before_preflight(monkeypatch):
    descriptor = {'argv': ['python', '-B', host.HOST_ENTRY],
                  'targets': {'case_host': host.HOST_ENTRY},
                  'source_pins': {host.HOST_ENTRY: 'a' * 64, VERIFIER: 'b' * 64}}
    guard = SimpleNamespace(processes=SimpleNamespace(runtime=SimpleNamespace(descriptor=descriptor, verify_source=lambda path: {'path': path, 'sha256': 'b'*64, 'closed': True})),
                            read_input=lambda **kwargs: b'not-json')
    monkeypatch.setattr(host, 'require_fixture', lambda name: guard)
    guard.processes.read_input = guard.read_input
    monkeypatch.setattr(host, 'inspect', lambda *args: pytest.fail('preflight must not run'))
    with pytest.raises((ValueError, TypeError)):
        host.inspect_inherited_handoff()


def test_case_host_requires_original_guard(monkeypatch):
    def refuse(name):
        assert name == 'independent-case-host-preflight'
        raise ValueError('ORIGINAL_GUARD_NOT_INSTALLED')
    monkeypatch.setattr(host, 'require_fixture', refuse)
    with pytest.raises(ValueError, match='ORIGINAL_GUARD_NOT_INSTALLED'):
        host.inspect_inherited_handoff()
