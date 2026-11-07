"""Offline adversarial contract tests. Synthetic source is never live proof."""
import copy
import importlib.util
import json
import os
import threading
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.skipif(os.name != 'nt', reason='Native Windows required')
spec = importlib.util.spec_from_file_location('live_reader_test', ROOT/'scripts/volume_inspector/live_docker_reader.py')
m = importlib.util.module_from_spec(spec)
if os.name == 'nt':
    spec.loader.exec_module(m)


class FixtureTransport:
    def __init__(self):
        self.calls = 0
        self.case = None
        raw = json.loads((ROOT/'tests/fixtures/r7e47j/helper-before.json').read_text())['payload']
        self.container = {**raw, 'Config': {'Labels': raw['Labels']}}
        self.source = {'pid': 123, 'created': 123456, 'image_path_sha256': 'a'*64}

    def get(self, path, nonce):
        self.calls += 1
        if self.case == 'disconnect':
            raise ConnectionError('Synthetic interruption')
        engine = {'ID': '1b4f668e-97b1-4e02-8647-454cf431e1b2', 'OSType': 'linux',
                  'ServerVersion': '29.8.1', 'SystemTime': '2026-10-18T22:00:00Z'}
        if path == '/info':
            payload = engine
        elif path == '/version':
            payload = {'ApiVersion': '1.54', 'MinAPIVersion': '1.44', 'Os': 'linux'}
        elif path.startswith('/containers/'):
            payload = copy.deepcopy(self.container)
        else:
            payload = {'Id': m.PIN, 'Descriptor': {'digest': m.PIN}}
        response = {'request': nonce, 'source': self.source.copy(), 'status': 200, 'payload': payload,
                    'observed': time.time(), 'elapsed': .01, 'wire_bytes': 1024, 'response_sha256': 'b'*64}
        if self.case == 'cached': response['request'] = 'old'
        if self.case == 'stale': response['observed'] -= 60
        if self.case == 'future': response['observed'] += 60
        if self.case == 'delayed': response['elapsed'] = 3
        if self.case == 'oversize': response['wire_bytes'] = 65537
        if self.case == 'envelope': response.pop('source')
        if self.case == 'missing' and path.startswith('/containers/'): response['status'] = 404
        if self.case == 'source-change' and self.calls == 6: response['source']['created'] += 1
        if self.case == 'engine-change' and self.calls == 6: payload['ID'] = 'different'
        if self.case == 'replacement' and self.calls == 5: payload['Id'] = 'f'*64
        if self.case == 'image' and path.startswith('/images/'): payload['Descriptor']['digest'] = 'sha256:'+'f'*64
        if path.startswith('/containers/'):
            if self.case == 'ownership': payload['Config']['Labels'] = {'secret': 'NEVER_PUBLISH'}
            if self.case == 'timestamp': payload['State']['FinishedAt'] = 'invalid'
            if self.case == 'pid-bool': payload['State']['Pid'] = False
            if self.case == 'contradiction': payload['State']['Running'] = True
            if self.case == 'running': payload['State'].update(Status='running', Running=True, Pid=1)
        return response


@pytest.fixture
def reader(tmp_path):
    output = m.r.s.w.WindowsOutput.create_root(str(tmp_path/'audit'))
    transport = FixtureTransport()
    plan = {'context': 'desktop-linux', 'endpoint': m.ENDPOINT, 'id': transport.container['Id'], 'image': m.PIN,
            'labels': transport.container['Labels'], 'scope': 'RETAINED_SYNTHETIC_HELPER'}
    value = m.LiveReader(transport, plan, output)
    try:
        yield value
    finally:
        output.close()


def test_exact_exit_observation_is_never_authorization(reader):
    result = reader.observe()
    assert result['observation_status'] == 'EXITED'
    assert result['daemon_generation'] == 'UNVERIFIED'
    assert result['source'] == 'SYNTHETIC'
    assert result['recovery_authorized'] is False
    with pytest.raises(m.Refused): reader.authorize_recovery()
    audits = list(Path(reader.output.root).glob('live-read-*.json'))
    assert len(audits) == 1
    assert audits[0].with_name(audits[0].name+'.sha256').read_text() == m.hashlib.sha256(audits[0].read_bytes()).hexdigest()


@pytest.mark.parametrize('case', ['cached', 'stale', 'future', 'delayed', 'oversize', 'envelope', 'missing',
                                 'source-change', 'engine-change', 'replacement', 'image', 'ownership',
                                 'timestamp', 'pid-bool', 'contradiction', 'disconnect'])
def test_uncertain_observations_refuse(reader, case):
    reader.transport.case = case
    result = reader.observe()
    assert result['observation_status'] != 'EXITED'
    assert result['recovery_authorized'] is False
    assert 'NEVER_PUBLISH' not in json.dumps(result)


def test_running_never_exit(reader):
    reader.transport.case = 'running'
    result = reader.observe()
    assert result['observation_status'] == 'RUNNING' and not result['recovery_authorized']


def test_missing_never_means_exit(reader):
    reader.transport.case = 'missing'
    assert reader.observe()['observation_status'] == 'MISSING'


def test_identical_info_and_proxy_never_prove_generation(reader):
    result = reader.observe()
    assert result['engine_system_times'][0] == result['engine_system_times'][1]
    assert result['engine_time_is_freshness_or_generation_witness'] is False
    assert not result['recovery_authorized']


@pytest.mark.parametrize('key,value', [('context', 'default'), ('endpoint', 'tcp://remote:2375'),
                                     ('scope', 'PRODUCTION'), ('id', 'name-only'), ('id', 'f'*64),
                                     ('labels', {'arbitrary': 'not-approved'}), ('image', 'latest')])
def test_wrong_plan_rejected(reader, key, value):
    plan = {**reader.expected, key: value}
    with pytest.raises(m.Refused): m.LiveReader(reader.transport, plan, reader.output)


@pytest.mark.parametrize('raw', [b'', b'HTTP/1.1 200 OK\r\n\r\n{}',
    b'HTTP/1.1 200 OK\r\nContent-Length: 3\r\n\r\n{}',
    b'HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n2\r\n{}',
    b'HTTP/1.1 200 OK\r\nContent-Length: 2\r\nTransfer-Encoding: chunked\r\n\r\n{}',
    b'HTTP/1.1 200 OK\r\nContent-Length: 2\r\nContent-Length: 2\r\n\r\n{}', b'x'*65537],
    ids=['empty', 'unframed', 'short-body', 'short-chunk', 'ambiguous', 'duplicate', 'oversize'])
def test_truncation_framing_bounds(raw):
    with pytest.raises(m.Refused): m.decode_http(raw)


def test_valid_content_length_and_chunked():
    assert m.decode_http(b'HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\n{}') == (200, {})
    assert m.decode_http(b'HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n2\r\n{}\r\n0\r\n\r\n') == (200, {})
    with pytest.raises(m.Refused): m.strict_json(b'{"id":1,"id":2}')


def test_audit_failure_does_not_return_observation(reader, monkeypatch):
    def fail(*_args): raise OSError('Synthetic evidence unavailable')
    monkeypatch.setattr(reader.output, '_write', fail)
    with pytest.raises(OSError): reader.observe()


def test_allowlist_precedes_connection():
    transport = object.__new__(m.NativePipe)
    for path in ('/containers/json', '/containers/a/start', '/volumes', 'http://remote/info', '/exec/x/json',
                 '/containers/'+'f'*64+'/json', '/images/sha256:'+'f'*64+'/json'):
        with pytest.raises(m.Refused): transport.get(path, 'a'*64)


def test_unresolved_client_io_prevents_new_connection(monkeypatch):
    monkeypatch.setattr(m, 'QUARANTINE', [('synthetic-pending',)])
    with pytest.raises(m.Refused): object.__new__(m.NativePipe).get('/info', 'a'*64)


@pytest.mark.parametrize('field,value', [('ID', 'unexpected'), ('ServerVersion', 'secret-value'),
                                       ('SystemTime', 'malformed')])
def test_malformed_engine_metadata_is_not_published(reader, monkeypatch, field, value):
    original = reader.transport.get
    def altered(path, nonce):
        reply = original(path, nonce)
        if path == '/info': reply['payload'][field] = value
        return reply
    monkeypatch.setattr(reader.transport, 'get', altered)
    result = reader.observe()
    assert result['observation_status'] == 'UNKNOWN' and 'engine' not in result


def test_source_pid_type_is_strict(reader, monkeypatch):
    reader.transport.source['pid'] = True
    assert reader.observe()['observation_status'] == 'UNKNOWN'


@pytest.mark.parametrize('case', ['valid', 'timeout', 'oversize', 'truncated', 'wrong-server'])
def test_native_private_pipe_bounds_and_source_identity(monkeypatch, case):
    """Real Win32 I/O, disposable private pipe, no Docker/production connection."""
    transport = m.NativePipe('C:/Program Files/Docker/Docker/resources/com.docker.backend.exe')
    pipe = r'\\.\pipe\atlas-k-test-'+m.secrets.token_hex(16)
    monkeypatch.setattr(m, 'PIPE', pipe)
    if case != 'wrong-server':
        # A Windows venv launcher can differ from the actual interpreter image.
        current = transport.k.OpenProcess(0x1000, False, os.getpid())
        buf, size = m.C.create_unicode_buffer(32768), m.W.DWORD(32768)
        try:
            assert transport.k.QueryFullProcessImageNameW(current, 0, buf, m.C.byref(size))
            transport.path = str(Path(buf.value).resolve())  # Explicit synthetic server, not Docker evidence.
        finally:
            transport.k.CloseHandle(current)
    k = transport.k
    transport._bind('CreateNamedPipeW', [m.W.LPCWSTR, m.W.DWORD, m.W.DWORD, m.W.DWORD, m.W.DWORD, m.W.DWORD, m.W.DWORD, m.C.c_void_p], m.W.HANDLE)
    transport._bind('ConnectNamedPipe', [m.W.HANDLE, m.C.POINTER(m.OVERLAPPED)], m.W.BOOL)
    server = k.CreateNamedPipeW(pipe, 3 | 0x40000000, 0, 1, 4096, 4096, 0, None)
    assert server != m.C.c_void_p(-1).value
    errors = []
    def serve():
        event = k.CreateEventW(None, True, False, None)
        ov = m.OVERLAPPED()
        ov.hEvent = event
        try:
            if not k.ConnectNamedPipe(server, m.C.byref(ov)):
                error = m.C.get_last_error()
                if error == 997:
                    assert k.WaitForSingleObject(event, 3500) == 0
                else:
                    assert error == 535
            request = transport._io(server, False, None, time.monotonic()+2)
            if not request: return
            if case == 'timeout':
                threading.Event().wait(2.3)
                return
            body = b'{}' if case != 'oversize' else b'x'*70000
            raw = b'HTTP/1.1 200 OK\r\nContent-Length: '+str(len(body)).encode()+b'\r\n\r\n'+body
            if case == 'truncated': raw = raw[:-1]
            transport._io(server, True, raw, time.monotonic()+2)
        except (m.Refused, AssertionError) as exc:
            errors.append(type(exc).__name__)
        finally:
            k.CloseHandle(event)
            k.CloseHandle(server)
    thread = threading.Thread(target=serve)
    thread.start()
    start = time.monotonic()
    try:
        if case == 'valid':
            result = transport.get('/info', 'a'*64)
            assert result['payload'] == {} and result['source']['pid'] == os.getpid()
        else:
            reasons = {'timeout': 'deadline', 'oversize': '64 KiB', 'truncated': 'Incomplete HTTP body',
                       'wrong-server': 'Unexpected pipe server executable'}
            with pytest.raises(m.Refused, match=reasons[case]): transport.get('/info', 'a'*64)
        assert time.monotonic()-start < 2.6
    finally:
        thread.join(4)
    assert not thread.is_alive() and not m.QUARANTINE
    assert not errors or case in ('oversize', 'wrong-server')
