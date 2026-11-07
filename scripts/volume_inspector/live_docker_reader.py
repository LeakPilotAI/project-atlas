"""Isolated read-only Windows named-pipe reader. Never recovery authority.

The same handle supplies server PID and response bytes. Docker Desktop's proxy
identity is NOT the Linux daemon generation. No production imports this module.
"""
import ctypes as C
import hashlib
import importlib.util
import json
import re
import secrets
import time
from ctypes import wintypes as W
from datetime import datetime, timezone
from pathlib import Path

spec = importlib.util.spec_from_file_location('live_contracts', Path(__file__).with_name('native_recovery.py'))
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)
Refused = r.Refused
ENDPOINT = 'npipe:////./pipe/dockerDesktopLinuxEngine'
PIPE = r'\\.\pipe\dockerDesktopLinuxEngine'
PIN = 'sha256:2ec3306c7d7e5714f49db15ea0db636622e01d061e87ceac27d0ec2bbd1b2574'
HELPER = '39c207ea4fac5c578dcfc1e64bc6ff9680ef9029c68aee453c9ede1adff227c7'
ENGINE = '1b4f668e-97b1-4e02-8647-454cf431e1b2'
LABELS = {'org.atlas.inspector.source': 'sha256:06d1ba89a7b89d0289ea0db87d5385797536eaa5033555822cb8f5d0325fe9a6',
          'org.atlas.synthetic.case': 'good', 'org.atlas.synthetic.operation': 'r7e46z-c5d18d33a88e42cc'}
QUARANTINE = []  # Retain buffers/handles if Windows cannot confirm cancelled I/O.


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise Refused('Duplicate JSON field')
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs)


class OVERLAPPED(C.Structure):
    _fields_ = [('Internal', C.c_size_t), ('InternalHigh', C.c_size_t),
                ('Offset', W.DWORD), ('OffsetHigh', W.DWORD), ('hEvent', W.HANDLE)]


class NativePipe:
    """GET-only HTTP over overlapped local pipe; no command or socket interface."""
    def __init__(self, expected_server_path):
        expected = str(Path(expected_server_path).resolve())
        allowed = Path('C:/Program Files/Docker/Docker/resources/com.docker.backend.exe')
        if Path(expected) != allowed or not allowed.is_file():
            raise Refused('Explicit installed Docker Desktop server path required')
        self.path = expected
        self.k = C.WinDLL('kernel32', use_last_error=True)
        self._bind('CreateFileW', [W.LPCWSTR, W.DWORD, W.DWORD, C.c_void_p, W.DWORD, W.DWORD, W.HANDLE], W.HANDLE)
        self._bind('CloseHandle', [W.HANDLE], W.BOOL)
        self._bind('GetNamedPipeServerProcessId', [W.HANDLE, C.POINTER(W.ULONG)], W.BOOL)
        self._bind('OpenProcess', [W.DWORD, W.BOOL, W.DWORD], W.HANDLE)
        self._bind('GetProcessTimes', [W.HANDLE, *[C.POINTER(W.FILETIME)]*4], W.BOOL)
        self._bind('QueryFullProcessImageNameW', [W.HANDLE, W.DWORD, W.LPWSTR, C.POINTER(W.DWORD)], W.BOOL)
        self._bind('CreateEventW', [C.c_void_p, W.BOOL, W.BOOL, W.LPCWSTR], W.HANDLE)
        self._bind('WaitForSingleObject', [W.HANDLE, W.DWORD], W.DWORD)
        self._bind('CancelIoEx', [W.HANDLE, C.POINTER(OVERLAPPED)], W.BOOL)
        self._bind('GetOverlappedResult', [W.HANDLE, C.POINTER(OVERLAPPED), C.POINTER(W.DWORD), W.BOOL], W.BOOL)
        for name in ('ReadFile', 'WriteFile'):
            self._bind(name, [W.HANDLE, C.c_void_p, W.DWORD, C.POINTER(W.DWORD), C.POINTER(OVERLAPPED)], W.BOOL)

    def _bind(self, name, args, result):
        fn = getattr(self.k, name)
        fn.argtypes, fn.restype = args, result

    def identity(self, handle):
        pid = W.ULONG()
        if not self.k.GetNamedPipeServerProcessId(handle, C.byref(pid)) or not pid.value:
            raise Refused('Pipe server identity unavailable')
        process = self.k.OpenProcess(0x1000, False, pid.value)
        if not process:
            raise Refused('Pipe server process inaccessible')
        try:
            size, buf = W.DWORD(32768), C.create_unicode_buffer(32768)
            times = [W.FILETIME() for _ in range(4)]
            if not self.k.QueryFullProcessImageNameW(process, 0, buf, C.byref(size)):
                raise Refused('Server image unavailable')
            if str(Path(buf.value).resolve()).casefold() != self.path.casefold():
                raise Refused('Unexpected pipe server executable')
            if not self.k.GetProcessTimes(process, *[C.byref(t) for t in times]):
                raise Refused('Server creation time unavailable')
            return {'pid': pid.value, 'created': (times[0].dwHighDateTime << 32) | times[0].dwLowDateTime,
                    'image_path_sha256': hashlib.sha256(self.path.casefold().encode()).hexdigest()}
        finally:
            self.k.CloseHandle(process)

    def _io(self, handle, write, data, deadline):
        buf = C.create_string_buffer(data if write else 4096)
        length = len(data) if write else 4096
        event = self.k.CreateEventW(None, True, False, None)
        if not event:
            raise Refused('I/O event unavailable')
        ov, count = OVERLAPPED(), W.DWORD()
        ov.hEvent = event
        keep = False
        try:
            fn = self.k.WriteFile if write else self.k.ReadFile
            ok = fn(handle, buf, length, C.byref(count), C.byref(ov))
            error = C.get_last_error() if not ok else 0
            if not ok and error in (109, 232):
                return b''
            if not ok and error != 997:
                raise Refused('Pipe I/O refused: '+str(error))
            if not ok:
                left = max(0, int((deadline-time.monotonic())*1000))
                if self.k.WaitForSingleObject(event, left) != 0:
                    self.k.CancelIoEx(handle, C.byref(ov))
                    if self.k.WaitForSingleObject(event, 250) != 0:
                        keep = True
                        QUARANTINE.append((handle, event, ov, buf))
                        raise Refused('Uncertain client I/O; quarantine retained')
                    self.k.GetOverlappedResult(handle, C.byref(ov), C.byref(count), False)
                    raise Refused('Pipe response deadline')
                if not self.k.GetOverlappedResult(handle, C.byref(ov), C.byref(count), False):
                    error = C.get_last_error()
                    if not write and error in (109, 232):
                        return b''
                    raise Refused('Pipe completion refused: '+str(error))
            if time.monotonic() > deadline:
                raise Refused('Pipe response deadline')
            if write and count.value != length:
                raise Refused('Incomplete request')
            return bytes(buf.raw[:count.value])
        finally:
            if not keep:
                self.k.CloseHandle(event)

    def get(self, path, request_id):
        if path not in ('/info', '/version', '/containers/'+HELPER+'/json', '/images/'+PIN+'/json'):
            raise Refused('GET allowlist violation')
        if QUARANTINE:
            raise Refused('Client I/O unresolved')
        begin = time.monotonic()
        handle = self.k.CreateFileW(PIPE, 0xC0000000, 0, None, 3, 0x40000000, None)
        if handle == C.c_void_p(-1).value:
            raise Refused('Intended Linux pipe unavailable: '+str(C.get_last_error()))
        try:
            before = self.identity(handle)
            self._io(handle, True, ('GET '+path+' HTTP/1.1\r\nHost: docker\r\nConnection: close\r\n\r\n').encode(), begin+2)
            raw = bytearray()
            while True:
                block = self._io(handle, False, None, begin+2)
                if not block:
                    break
                raw.extend(block)
                if len(raw) > 65536:
                    raise Refused('Response exceeds 64 KiB wire limit')
            after = self.identity(handle)
            if before != after:
                raise Refused('Pipe server changed')
            status, payload = decode_http(bytes(raw))
            return {'request': request_id, 'source': before, 'status': status, 'payload': payload,
                    'observed': time.time(), 'elapsed': time.monotonic()-begin,
                    'wire_bytes': len(raw), 'response_sha256': hashlib.sha256(raw).hexdigest()}
        finally:
            if not any(item[0] == handle for item in QUARANTINE):
                self.k.CloseHandle(handle)


def decode_http(raw):
    if len(raw) > 65536:
        raise Refused('Oversize HTTP')
    header, separator, body = raw.partition(b'\r\n\r\n')
    if not separator or len(header) > 8192:
        raise Refused('Incomplete HTTP header')
    lines = header.split(b'\r\n')
    if not re.fullmatch(rb'HTTP/1\.[01] (200|404) [^\r\n]*', lines[0]):
        raise Refused('Unexpected HTTP status')
    status, fields = int(lines[0].split()[1]), {}
    for line in lines[1:]:
        key, sep, value = line.partition(b':')
        key = key.strip().lower()
        if not sep or key in fields:
            raise Refused('Malformed/duplicate HTTP header')
        fields[key] = value.strip().lower()
    if b'content-length' in fields and b'transfer-encoding' in fields:
        raise Refused('Ambiguous HTTP framing')
    if fields.get(b'transfer-encoding') == b'chunked':
        decoded = bytearray()
        while True:
            line, sep, body = body.partition(b'\r\n')
            if not sep or not re.fullmatch(rb'[0-9a-fA-F]{1,8}', line):
                raise Refused('Invalid chunk')
            size = int(line, 16)
            if not size:
                if body != b'\r\n':
                    raise Refused('Unexpected trailers')
                break
            if len(body) < size+2 or body[size:size+2] != b'\r\n':
                raise Refused('Truncated chunk')
            decoded.extend(body[:size])
            body = body[size+2:]
        body = bytes(decoded)
    elif b'content-length' in fields:
        if not fields[b'content-length'].isdigit() or int(fields[b'content-length']) != len(body):
            raise Refused('Incomplete HTTP body')
    else:
        raise Refused('Explicit HTTP framing required')
    return status, strict_json(body)


class LiveReader:
    """Observation only: generation unknown means recovery is always refused."""
    def __init__(self, transport, expected, output):
        if set(expected) != {'context', 'endpoint', 'id', 'image', 'labels', 'scope'}:
            raise Refused('Explicit plan required')
        if expected['context'] != 'desktop-linux' or expected['endpoint'] != ENDPOINT:
            raise Refused('Unexpected context/endpoint')
        if expected['scope'] != 'RETAINED_SYNTHETIC_HELPER' or expected['id'] != HELPER:
            raise Refused('Only exact retained synthetic helper permitted')
        if expected['image'] != PIN or expected['labels'] != LABELS:
            raise Refused('Pinned image/ownership required')
        self.transport, self.expected, self.output = transport, strict_json(json.dumps(expected)), output

    def observe(self):
        began, wall = time.monotonic(), time.time()
        evidence, source = [], None
        result = {'source': 'LIVE_READ_ONLY' if type(self.transport) is NativePipe else 'SYNTHETIC',
                  'observation_status': 'UNKNOWN', 'recovery_authorized': False,
                  'daemon_generation': 'UNVERIFIED', 'reason': 'UNVERIFIED', 'evidence': evidence,
                  'observed_utc': datetime.now(timezone.utc).isoformat()}
        def read(path):
            nonlocal source
            nonce = secrets.token_hex(32)
            response = self.transport.get(path, nonce)
            required = {'request', 'source', 'status', 'payload', 'observed', 'elapsed', 'wire_bytes', 'response_sha256'}
            if not isinstance(response, dict) or set(response) != required:
                raise Refused('Incomplete response envelope')
            # Preserve only bounded non-secret facts, never raw inspect Config/Env.
            entry = {k: response[k] for k in ('request', 'source', 'status', 'observed', 'elapsed', 'wire_bytes', 'response_sha256')}
            evidence.append(entry)
            if len(r.s.encoded(entry)) > 2048:
                evidence[-1] = {'invalid_envelope': True}
                raise Refused('Envelope output limit')
            if (response['request'] != nonce or type(response['wire_bytes']) is not int
                    or not 0 < response['wire_bytes'] <= 65536 or not 0 <= response['elapsed'] <= 2
                    or not 0 <= time.time()-response['observed'] <= 2 or time.monotonic()-began > 5):
                raise Refused('Cached/slow/oversize response')
            if not isinstance(response['source'], dict) or set(response['source']) != {'pid', 'created', 'image_path_sha256'}:
                raise Refused('Source identity incomplete')
            if (any(type(response['source'][k]) is not int or response['source'][k] <= 0 for k in ('pid', 'created'))
                    or not isinstance(response['source']['image_path_sha256'], str)
                    or not re.fullmatch('[a-f0-9]{64}', response['source']['image_path_sha256'])):
                raise Refused('Malformed source identity')
            if source is None:
                source = response['source']
            if source != response['source']:
                raise Refused('Source replaced or connection interrupted')
            if response['status'] == 404:
                if path.startswith('/containers/'):
                    result['observation_status'] = 'MISSING'
                raise Refused('MISSING_NEVER_EXIT_PROOF')
            if response['status'] != 200 or not isinstance(response['payload'], dict):
                raise Refused('Invalid response')
            return response['payload']
        try:
            first_engine = read('/info')
            version = read('/version')
            first = read('/containers/'+self.expected['id']+'/json')
            image = read('/images/'+PIN+'/json')
            second = read('/containers/'+self.expected['id']+'/json')
            last_engine = read('/info')
            engine = lambda p: {k: p[k] for k in ('ID', 'OSType', 'ServerVersion')}
            if (first_engine['ID'] != ENGINE or engine(first_engine) != engine(last_engine)
                    or first_engine['OSType'] != 'linux' or version['Os'] != 'linux'
                    or not re.fullmatch(r'[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}', first_engine['ServerVersion'])
                    or any(not re.fullmatch(r'1\.[0-9]{1,3}', version[k]) for k in ('ApiVersion', 'MinAPIVersion'))):
                raise Refused('Engine replacement/contradiction')
            for info in (first_engine, last_engine):
                if not isinstance(info.get('SystemTime'), str) or len(info['SystemTime']) > 64:
                    raise Refused('Malformed Engine clock metadata')
                r.timestamp(info['SystemTime'])  # Syntax only; never a freshness/generation witness.
            result['engine'] = engine(first_engine)
            result['api'] = {k: version[k] for k in ('ApiVersion', 'MinAPIVersion', 'Os')}
            result['engine_system_times'] = [first_engine.get('SystemTime'), last_engine.get('SystemTime')]
            result['engine_time_is_freshness_or_generation_witness'] = False
            def select(p):
                return {'Id': p['Id'], 'Image': p['Image'], 'Created': p['Created'],
                        'Labels': p['Config']['Labels'], 'State': {k: p['State'][k] for k in
                        ('Status', 'Running', 'Pid', 'StartedAt', 'FinishedAt')}}
            a, b = select(first), select(second)
            if a != b:
                result['observation_status'] = 'REPLACED'
                raise Refused('Contradictory helper observations')
            if a['Id'] != self.expected['id'] or a['Image'] != PIN or a['Labels'] != self.expected['labels']:
                result['observation_status'] = 'REPLACED'
                raise Refused('Helper identity/image/ownership mismatch')
            if image['Id'] != PIN or image['Descriptor']['digest'] != PIN:
                result['observation_status'] = 'REPLACED'
                raise Refused('Image identity mismatch')
            state = a['State']
            times = [r.timestamp(a['Created']), r.timestamp(state['StartedAt'])]
            if not times[0] <= times[1] <= wall or type(state['Pid']) is not int or type(state['Running']) is not bool:
                raise Refused('Malformed/future timestamps or PID')
            if state['Status'] == 'exited' and state['Running'] is False and state['Pid'] == 0:
                if not times[1] <= r.timestamp(state['FinishedAt']) <= wall:
                    raise Refused('Malformed/future exit timestamp')
                result['helper'] = a  # Only approved, validated metadata reaches output.
                result.update(observation_status='EXITED', reason='DAEMON_GENERATION_UNVERIFIED')
            else:
                running = state['Status'] == 'running' and state['Running'] is True and state['Pid'] > 0
                if running:
                    r.timestamp(state['FinishedAt'])
                    result['helper'] = a
                result.update(observation_status='RUNNING' if running else 'UNKNOWN',
                              reason='HELPER_NOT_CONFIRMED_EXITED')
        except (ValueError, TypeError, KeyError, OSError) as exc:
            # Exception text is fixed-code or Win32 numeric; never server payload.
            result['reason'] = 'REFUSED_'+type(exc).__name__
            result['failure_digest'] = hashlib.sha256(str(exc).encode()).hexdigest()
            if re.fullmatch(r'Intended Linux pipe unavailable: [0-9]+', str(exc)):
                result['exact_source_failure'] = str(exc)
        result['elapsed_seconds'] = time.monotonic()-began
        data = r.s.encoded(result)
        if len(data) > 16384:
            raise Refused('Audit bound exceeded')
        name = 'live-read-'+secrets.token_hex(32)+'.json'
        self.output._write(self.output.root_handle, name, data)
        # Digest audit is independently persisted before returning any observation.
        self.output._write(self.output.root_handle, name+'.sha256', hashlib.sha256(data).hexdigest().encode())
        return result

    def authorize_recovery(self):
        raise Refused('No daemon generation proof or production binding; recovery refused')
