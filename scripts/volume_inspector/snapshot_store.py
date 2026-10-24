"""Isolated NTFS immutable control snapshots; NO production admission API.

Caller-held witness pins model an independent, non-rollbackable authority. That
authority is NOT supplied here. SyntheticAuthority is never production proof.
No SQLite/VFS, Docker, process control, automatic recovery or directory reset.
"""
import copy
import ctypes as C
import hashlib
import hmac
import importlib.util
import json
import secrets
import uuid
from contextlib import contextmanager
from pathlib import Path

spec = importlib.util.spec_from_file_location('snapshot_native', Path(__file__).with_name('shared_fence.py'))
native = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native)
w = native.w
Refused = native.Refused
encoded = native.encoded


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read_bound(output, leaf, expected=None):
    """Check native identity/ACL/link BEFORE ReadFile; hash BEFORE JSON decode.

    NtCreateFile's regular-file share mode is READ only: concurrent write/delete
    opens conflict for the lifetime of this same native handle.
    """
    output._verify()
    handle = w.relative_open(output.root_handle, leaf, output.sid, False, access=w.READ | w.READ_CONTROL)
    try:
        w.validate_acl(handle, output.sid)
        info = w.info(handle)
        fid = native.file_identity(handle)
        size = (info.size_hi << 32) | info.size_lo
        if info.links != 1 or size > 65536 or (expected is not None and fid != expected['id']):
            raise Refused('Identity, link or size refused before read')
        buf, count = C.create_string_buffer(65537), native.W.DWORD()
        w.check(w.read_file(handle, buf, 65537, C.byref(count), None))
        raw = buf.raw[:count.value]
        if count.value != size or native.file_identity(handle) != fid or w.info(handle).links != 1:
            raise Refused('Inconsistent handle read')
        if expected is not None and sha(raw) != expected['sha256']:
            raise Refused('Content commitment mismatch before decode')
        return raw, {'id': fid, 'sha256': sha(raw)}
    finally:
        w.close_handle(handle)


def exists(output, leaf):
    try:
        handle = w.relative_open(output.root_handle, leaf, output.sid, False)
    except OSError as exc:
        if exc.winerror == 2:
            return False
        raise
    else:
        w.close_handle(handle)
        return True


def validate_pin(pin):
    if (not isinstance(pin, dict) or set(pin) != {'instance', 'revision', 'snapshot', 'commit', 'root_id', 'witness_root_id'}
            or type(pin['revision']) is not int or not 0 <= pin['revision'] <= 128
            or str(uuid.UUID(pin['instance'])) != pin['instance']):
        raise Refused('Explicit canonical independent pin required')
    for key in ('snapshot', 'commit'):
        part = pin[key]
        if (not isinstance(part, dict) or set(part) != {'id', 'sha256'} or not isinstance(part['sha256'], str)
                or len(part['sha256']) != 64 or any(c not in 'abcdef0123456789' for c in part['sha256'])):
            raise Refused('Malformed independent commitment')
    for value in (pin['root_id'], pin['witness_root_id'], pin['snapshot']['id'], pin['commit']['id']):
        if not isinstance(value, list) or len(value) != 3 or any(type(i) is not int or i < 0 for i in value):
            raise Refused('Malformed native identity pin')


class SyntheticAuthority:
    """Two synthetic signing roles, not independent deployed principals/keys."""
    def __init__(self):
        self.witness_key = secrets.token_bytes(32)
        self.operator_key = secrets.token_bytes(32)

    def attest_exit(self, helper, operation, now):
        facts = {'helper': helper, 'operation': operation, 'state': 'exited', 'pid': 0, 'observed': now}
        return {'facts': facts, 'signature': hmac.new(self.witness_key, encoded(facts), hashlib.sha256).hexdigest()}

    def approve(self, state, evidence, *, approved=False):
        if approved is not True:
            raise Refused('Explicit synthetic operator authorization required')
        payload = {'instance': state['instance'], 'revision': state['revision'], 'state': sha(encoded(state)),
                   'evidence': evidence, 'nonce': secrets.token_hex(32)}
        return {'payload': payload, 'signature': hmac.new(self.operator_key, encoded(payload), hashlib.sha256).hexdigest()}

    def verify(self, state, evidence, grant, now):
        if not isinstance(evidence, dict) or set(evidence) != {'facts', 'signature'}:
            raise Refused('Authenticated exit evidence required')
        facts = evidence['facts']
        if (not isinstance(facts, dict) or set(facts) != {'helper', 'operation', 'state', 'pid', 'observed'}
                or facts['state'] != 'exited' or type(facts['pid']) is not int or facts['pid'] != 0
                or not native.fresh(facts['observed'], now)
                or not isinstance(evidence['signature'], str)
                or not hmac.compare_digest(evidence['signature'], hmac.new(self.witness_key, encoded(facts), hashlib.sha256).hexdigest())):
            raise Refused('Invalid or stale exit witness')
        if not isinstance(grant, dict) or set(grant) != {'payload', 'signature'}:
            raise Refused('Explicit revision-bound approval required')
        payload = grant['payload']
        if (not isinstance(payload, dict) or set(payload) != {'instance', 'revision', 'state', 'evidence', 'nonce'}
                or payload['instance'] != state['instance'] or type(payload['revision']) is not int
                or payload['revision'] != state['revision'] or payload['state'] != sha(encoded(state))
                or payload['evidence'] != evidence or not isinstance(grant['signature'], str)
                or not hmac.compare_digest(grant['signature'], hmac.new(self.operator_key, encoded(payload), hashlib.sha256).hexdigest())):
            raise Refused('Invalid recovery approval')
        intent = state['inspection']
        if not intent or facts['helper'] != intent['helper'] or facts['operation'] != intent['operation']:
            raise Refused('Wrong helper or inspection')


class SnapshotStore:
    """Explicit synthetic root + independently retained latest witness pin.

    Missing/stale pin never triggers discovery/initialization/rollback. The
    independent pin's authenticity and durable high-water mark remain a gate.
    """
    def __init__(self, root, witness_root, pin):
        validate_pin(pin)
        self.output = w.WindowsOutput(root)
        self.witness = None
        self.mutex = None
        self.poisoned = False
        try:
            self.witness = w.WindowsOutput(witness_root)
            self.pin = copy.deepcopy(pin)
            if native.file_identity(self.output.root_handle) != pin['root_id'] or native.file_identity(self.witness.root_handle) != pin['witness_root_id']:
                raise Refused('Wrong independently pinned root')
            # Reuse only D's reviewed native coordinator construction, never DB.
            self.coordinator = native.Registry.__new__(native.Registry)
            self.coordinator.output = self.output
            self.coordinator.root_id = pin['root_id']
            self.coordinator._create_mutex()
            self.mutex = self.coordinator.mutex
            self.snapshot()
        except BaseException:
            self.close()
            raise

    @classmethod
    def provision_synthetic(cls, root, witness_root):
        with w.WindowsOutput.create_root(root) as output, w.WindowsOutput.create_root(witness_root) as witness:
            instance = str(uuid.uuid4())
            state = {'schema': 1, 'instance': instance, 'revision': 0, 'previous': None,
                     'startup': None, 'inspection': None, 'used': [], 'event': 'INITIALIZED'}
            raw = encoded(state)
            output._write(output.root_handle, 'snapshot-00000000.json', raw)
            _, binding = read_bound(output, 'snapshot-00000000.json')
            head = {'instance': instance, 'revision': 0, 'snapshot': binding}
            witness._write(witness.root_handle, 'commit-00000000.json', encoded(head))
            _, commitment = read_bound(witness, 'commit-00000000.json')
            pin = {**head, 'commit': commitment, 'root_id': native.file_identity(output.root_handle),
                   'witness_root_id': native.file_identity(witness.root_handle)}
        return cls(root, witness_root, pin)

    def close(self):
        if self.mutex:
            w.close_handle(self.mutex)
            self.mutex = None
        self.output.close()
        if self.witness:
            self.witness.close()

    @contextmanager
    def guard(self):
        if self.poisoned or not self.mutex:
            raise Refused('Unavailable or failed synthetic store')
        code = self.coordinator.wait(self.mutex, 500)
        if code not in (0, 128):
            raise Refused('Bounded coordinator unavailable')
        try:
            if code == 128:
                self.poisoned = True
                try:
                    self.witness._write(self.witness.root_handle, 'recovery-required.json', b'{"reason":"ABANDONED"}')
                except FileExistsError:
                    pass
                raise Refused('Abandoned coordinator')
            yield
        finally:
            w.check(self.coordinator.release(self.mutex))

    def _state(self):
        try:
            return self._checked_state()
        except Exception:
            self.poisoned = True
            try:
                self.witness._write(self.witness.root_handle, 'recovery-required.json', b'{"reason":"UNTRUSTED_STATE"}')
            except FileExistsError:
                pass
            raise

    def _checked_state(self):
        self.output._verify()
        self.witness._verify()
        if exists(self.witness, 'recovery-required.json'):
            raise Refused('Persistent recovery fence')
        revision = self.pin['revision']
        # Unfinished/unknown newer publication can never fall back to old state.
        if exists(self.witness, f'intent-{revision+1:08d}.json'):
            raise Refused('Newer publication unresolved or stale authority pin')
        for leaf in ('fence.sqlite3', 'fence.sqlite3-journal', 'fence.sqlite3-wal', 'fence.sqlite3-shm'):
            if exists(self.output, leaf):
                raise Refused('Unexpected legacy SQLite surface')
        name = f'snapshot-{revision:08d}.json'
        for suffix in ('-journal', '-wal', '-shm'):
            if exists(self.output, name+suffix):
                raise Refused('Unexpected snapshot sidecar')
        commit_raw, _ = read_bound(self.witness, f'commit-{revision:08d}.json', self.pin['commit'])
        expected = {k: self.pin[k] for k in ('instance', 'revision', 'snapshot')}
        if commit_raw != encoded(expected):
            raise Refused('Witness mismatch')
        raw, _ = read_bound(self.output, name, self.pin['snapshot'])
        # Trust bytes only after native ID and externally pinned digest checks.
        state = json.loads(raw)
        if (not isinstance(state, dict) or set(state) != {'schema', 'instance', 'revision', 'previous', 'startup', 'inspection', 'used', 'event'}
                or type(state['schema']) is not int or state['schema'] != 1
                or type(state['revision']) is not int or state['revision'] != revision
                or state['instance'] != self.pin['instance'] or encoded(state) != raw
                or not isinstance(state['used'], list) or len(state['used']) != len(set(state['used']))
                or any(not isinstance(op, str) for op in state['used'])
                or (revision == 0 and state['previous'] is not None)
                or (revision > 0 and (not isinstance(state['previous'], str) or len(state['previous']) != 64
                                     or any(c not in 'abcdef0123456789' for c in state['previous'])))
                or state['event'] not in {'INITIALIZED', 'STARTUP_PENDING', 'WORKER_ADMITTED', 'INSPECTION_UNCERTAIN', 'EXIT_PROVEN_FAILED'}
                or (state['startup'] is not None and state['inspection'] is not None)):
            raise Refused('Malformed authenticated state')
        if state['startup'] is not None:
            i = state['startup']
            if not isinstance(i, dict) or set(i) != {'operation', 'parent', 'worker', 'phase'} or i['phase'] not in {'PENDING', 'STARTING'}:
                raise Refused('Malformed startup')
            native.operation(i['operation'])
            native.identity(i['parent'])
            if i['worker'] is not None:
                native.identity(i['worker'])
            elif i['phase'] != 'PENDING':
                raise Refused('Missing admitted worker')
        if state['inspection'] is not None:
            i = state['inspection']
            if not isinstance(i, dict) or set(i) != {'operation', 'helper', 'phase'} or i['phase'] != 'UNCERTAIN':
                raise Refused('Malformed inspection')
            native.operation(i['operation'])
            if not isinstance(i['helper'], str) or len(i['helper']) != 64 or any(c not in 'abcdef0123456789' for c in i['helper']):
                raise Refused('Malformed helper')
        return state

    def snapshot(self):
        with self.guard():
            return self._state()

    def production_admission(self):
        raise Refused('Synthetic authority cannot authorize production')

    def _transition(self, change):
        with self.guard():
            prior = self._state()
            state = copy.deepcopy(prior)
            change(state)
            revision = prior['revision']+1
            if revision > 128:
                raise Refused('Synthetic history capacity reached')
            state['revision'], state['previous'] = revision, self.pin['snapshot']['sha256']
            raw = encoded(state)
            if len(raw) > 65536:
                raise Refused('Bounded control snapshot')
            try:
                self.witness._write(self.witness.root_handle, f'intent-{revision:08d}.json', encoded({'previous': self.pin, 'next_sha256': sha(raw)}))
                self.output._write(self.output.root_handle, f'snapshot-{revision:08d}.json', raw)
                confirmed, binding = read_bound(self.output, f'snapshot-{revision:08d}.json')
                if confirmed != raw:
                    raise Refused('Publication substitution')
                head = {'instance': state['instance'], 'revision': revision, 'snapshot': binding}
                self.witness._write(self.witness.root_handle, f'commit-{revision:08d}.json', encoded(head))
                _, commitment = read_bound(self.witness, f'commit-{revision:08d}.json')
                self.pin = {**self.pin, **head, 'commit': commitment}
                return self._state()
            except BaseException:
                # A failed publication is never silently reusable, even when
                # intent creation itself failed. Preserve the original error.
                self.poisoned = True
                try:
                    self.witness._write(self.witness.root_handle, 'recovery-required.json', b'{"reason":"PUBLICATION_FAILED"}')
                except (OSError, ValueError):
                    # Unavailable storage cannot promise a durable marker;
                    # the caller must retain failure evidence and refusal.
                    pass
                raise

    def reserve_start(self, op, parent):
        native.operation(op)
        native.identity(parent)
        def change(state):
            if state['startup'] or state['inspection'] or op in state['used']:
                raise Refused('Startup refused')
            state['used'].append(op)
            state['startup'] = {'operation': op, 'parent': parent, 'worker': None, 'phase': 'PENDING'}
            state['event'] = 'STARTUP_PENDING'
        return self._transition(change)

    def admit_worker(self, op, parent, worker):
        native.identity(worker)
        def change(state):
            i = state['startup']
            if not i or i['phase'] != 'PENDING' or i['operation'] != op or i['parent'] != parent:
                raise Refused('Worker refused')
            i['worker'], i['phase'] = worker, 'STARTING'
            state['event'] = 'WORKER_ADMITTED'
        return self._transition(change)

    def inspect(self, op, helper, *, approved=False):
        native.operation(op)
        if approved is not True or not isinstance(helper, str) or len(helper) != 64 or any(c not in 'abcdef0123456789' for c in helper):
            raise Refused('Explicit synthetic inspection approval/identity required')
        def change(state):
            if state['startup'] or state['inspection'] or op in state['used']:
                raise Refused('Inspection refused')
            state['used'].append(op)
            state['inspection'] = {'operation': op, 'helper': helper, 'phase': 'UNCERTAIN'}
            state['event'] = 'INSPECTION_UNCERTAIN'
        return self._transition(change)

    def recover(self, authority, evidence, grant, now):
        if type(authority) is not SyntheticAuthority:
            raise Refused('Synthetic two-role contract only')
        def change(state):
            authority.verify(state, evidence, grant, now)
            state['inspection'] = None
            state['event'] = 'EXIT_PROVEN_FAILED'
        return self._transition(change)
