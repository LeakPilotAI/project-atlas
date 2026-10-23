"""Isolated Windows shared-fence registry. No production paths or Docker calls.

Standard SQLite Win32 VFS uses paths; pinned/protected directory plus cooperative
mutex and before/after binding checks are NOT exclusion of privileged external
writers. FixtureRecoveryAuthority is intentionally not a production authority.
"""
import ctypes as C
import hashlib
import hmac
import importlib.util
import json
import os
import re
import secrets
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from ctypes import wintypes as W
from pathlib import Path

spec = importlib.util.spec_from_file_location('native_fence_output', Path(__file__).with_name('windows_output.py'))
w = importlib.util.module_from_spec(spec)
spec.loader.exec_module(w)
SURFACE = ('fence.sqlite3', 'fence.sqlite3-journal', 'fence.sqlite3-wal', 'fence.sqlite3-shm')


class Refused(ValueError):
    pass


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def operation(value):
    if not isinstance(value, str) or not re.fullmatch('[a-z0-9-]{8,64}', value):
        raise Refused('Invalid operation identity')


def identity(value):
    if (not isinstance(value, dict) or set(value) != {'pid', 'created', 'exe', 'command'}
            or type(value['pid']) is not int or value['pid'] <= 0
            or type(value['created']) not in (int, float) or not 0 < value['created'] < 10**12
            or any(not isinstance(value[k], str) or not re.fullmatch('[a-f0-9]{64}', value[k]) for k in ('exe', 'command'))):
        raise Refused('Incomplete process identity')


def fresh(observed, now):
    return type(observed) in (int, float) and 0 <= now-observed <= 5


def file_identity(handle):
    i = w.info(handle)
    return [i.volume, i.index_hi, i.index_lo]


def current_process_identity():
    """Self-only native identity; no process enumeration or foreign PID access."""
    get_times = w.bind(w.K, 'GetProcessTimes', [W.HANDLE, C.POINTER(W.FILETIME), C.POINTER(W.FILETIME), C.POINTER(W.FILETIME), C.POINTER(W.FILETIME)])
    creation, exit_time, kernel, user = W.FILETIME(), W.FILETIME(), W.FILETIME(), W.FILETIME()
    w.check(get_times(w.process(), C.byref(creation), C.byref(exit_time), C.byref(kernel), C.byref(user)))
    command = w.bind(w.K, 'GetCommandLineW', [], W.LPWSTR)()
    image_path = C.create_unicode_buffer(32768)
    length = w.bind(w.K, 'GetModuleFileNameW', [W.HMODULE, W.LPWSTR, W.DWORD], W.DWORD)(None, image_path, len(image_path))
    if not 0 < length < len(image_path):
        raise Refused('Own executable identity unavailable')
    return {'pid': os.getpid(), 'created': ((creation.dwHighDateTime << 32) | creation.dwLowDateTime)/10000000-11644473600,
            'exe': hashlib.sha256(Path(image_path.value).read_bytes()).hexdigest(),
            'command': hashlib.sha256(command.encode('utf-16-le')).hexdigest()}


def inherited_acl(handle, sid):
    """SQLite sidecars may inherit ONLY the two restrictive parent grants."""
    owner, acl, sd = C.c_void_p(), C.c_void_p(), C.c_void_p()
    error = w.get_sd(handle, 1, 5, C.byref(owner), None, C.byref(acl), None, C.byref(sd))
    if error:
        raise PermissionError('Sidecar DACL inaccessible')
    try:
        if not acl or w.sid_text(owner) != sid:
            raise PermissionError('Sidecar owner mismatch')
        size = w.AclSize()
        w.check(w.acl_info(acl, C.byref(size), C.sizeof(size), 2))
        found, flags = set(), []
        for n in range(size.count):
            ptr = C.c_void_p()
            w.check(w.get_ace(acl, n, C.byref(ptr)))
            ace = C.cast(ptr, C.POINTER(w.Ace)).contents
            principal = w.sid_text(ptr.value + w.Ace.sid.offset)
            if ace.type != 0 or ace.flags not in (0, 3, 16, 19) or ace.mask != 0x1F01FF or principal not in {sid, 'S-1-5-18'}:
                raise PermissionError('Broad or unexpected sidecar permission')
            found.add(principal)
            flags.append(ace.flags)
        if size.count != 2 or found != {sid, 'S-1-5-18'}:
            raise PermissionError('Sidecar grants incomplete')
        return {'aces': 2, 'inherited': any(f & 16 for f in flags), 'restricted': True}
    finally:
        w.local_free(sd)


def kernel_acl(handle, sid):
    owner, acl, sd = C.c_void_p(), C.c_void_p(), C.c_void_p()
    error = w.get_sd(handle, 6, 5, C.byref(owner), None, C.byref(acl), None, C.byref(sd))
    if error:
        raise PermissionError("Coordination ACL unavailable")
    try:
        control, revision = W.WORD(), W.DWORD()
        w.check(w.control_sd(sd, C.byref(control), C.byref(revision)))
        if not acl or w.sid_text(owner) != sid or not control.value & 0x1000:
            raise PermissionError("Protected coordinator required")
        size = w.AclSize()
        w.check(w.acl_info(acl, C.byref(size), C.sizeof(size), 2))
        found = set()
        for n in range(size.count):
            ptr = C.c_void_p()
            w.check(w.get_ace(acl, n, C.byref(ptr)))
            ace = C.cast(ptr, C.POINTER(w.Ace)).contents
            principal = w.sid_text(ptr.value + w.Ace.sid.offset)
            if ace.type != 0 or ace.flags not in (0, 3) or ace.mask != 0x1F0001 or principal not in {sid, 'S-1-5-18'}:
                raise PermissionError("Unexpected coordinator grant")
            found.add(principal)
        if size.count != 2 or found != {sid, 'S-1-5-18'}:
            raise PermissionError("Coordinator grants incomplete")
    finally:
        w.local_free(sd)


class FixtureRecoveryAuthority:
    """Ephemeral synthetic authority; no deployment/key provisioning API."""
    def __init__(self):
        self.key = secrets.token_bytes(32)

    def issue(self, state, proof, *, approved=False):
        if approved is not True:
            raise Refused('Explicit approval required')
        payload = {'instance': state['instance'], 'revision': state['revision'], 'state': digest(state),
                   'proof': proof, 'nonce': secrets.token_hex(16)}
        return {'payload': payload, 'mac': hmac.new(self.key, encoded(payload), hashlib.sha256).hexdigest()}

    def verify(self, grant, state, proof):
        if not isinstance(grant, dict) or set(grant) != {'payload', 'mac'}:
            raise Refused('Missing independent authorization')
        p = grant['payload']
        if (not isinstance(p, dict) or set(p) != {'instance', 'revision', 'state', 'proof', 'nonce'}
                or p['instance'] != state['instance'] or p['revision'] != state['revision']
                or p['state'] != digest(state) or p['proof'] != proof
                or not isinstance(grant['mac'], str)
                or not hmac.compare_digest(grant['mac'], hmac.new(self.key, encoded(p), hashlib.sha256).hexdigest())):
            raise Refused('Invalid or replayed authorization')


class Registry:
    def __init__(self, root, instance):
        self.instance = str(uuid.UUID(instance))
        self.output = w.WindowsOutput(root)
        self.root_id = file_identity(self.output.root_handle)
        self.mutex = None
        self.poisoned = False
        self.local = threading.local()
        try:
            ready = self._read_json('ready.json')
            if (not isinstance(ready, dict) or set(ready) != {'schema', 'instance', 'root_id', 'mode', 'db_id'}
                    or type(ready['schema']) is not int or ready['schema'] != 1 or ready['instance'] != self.instance
                    or ready['root_id'] != self.root_id or ready['mode'] not in {'PERSIST', 'WAL'}):
                raise Refused('Unverified registry initialization')
            self.mode = ready['mode']
            self.db_id = ready['db_id']
            self._create_mutex()
            self.snapshot()
        except BaseException:
            self.close()
            raise

    @classmethod
    def provision(cls, root, *, mode='PERSIST'):
        if mode not in {'PERSIST', 'WAL'}:
            raise Refused('Unsupported journal policy')
        out = w.WindowsOutput.create_root(root)
        instance = str(uuid.uuid4())
        rid = file_identity(out.root_handle)
        try:
            out._write(out.root_handle, 'provision.json', encoded({'schema': 1, 'instance': instance, 'root_id': rid}))
            h = w.relative_open(out.root_handle, SURFACE[0], out.sid, False, create=True, access=w.READ | w.WRITE | w.READ_CONTROL)
            try:
                w.check(w.flush(h))
                db_id = file_identity(h)
            finally:
                w.close_handle(h)
            # Initialization only; no auto repair of any pre-existing file.
            db = sqlite3.connect((Path(root)/SURFACE[0]).as_uri()+'?mode=rw', uri=True, timeout=.5)
            try:
                db.execute('PRAGMA synchronous=FULL')
                db.execute('PRAGMA temp_store=MEMORY')
                if db.execute('PRAGMA journal_mode='+mode).fetchone()[0].upper() != mode:
                    raise Refused('Journal policy unavailable')
                db.execute('CREATE TABLE state (id INTEGER PRIMARY KEY CHECK(id=1), value TEXT NOT NULL)')
                db.execute('CREATE TABLE audit (revision INTEGER PRIMARY KEY, value TEXT NOT NULL)')
                db.execute('CREATE TABLE used (operation TEXT PRIMARY KEY)')
                state = {'schema': 1, 'instance': instance, 'revision': 0, 'startup': None, 'inspection': None}
                db.execute('INSERT INTO state VALUES (1,?)', (encoded(state).decode(),))
                initial_audit = {'state': state, 'event': {'type': 'INITIALIZED'}}
                db.execute('INSERT INTO audit VALUES (0,?)', (encoded(initial_audit).decode(),))
                db.commit()
            finally:
                db.close()
            out._write(out.root_handle, 'revision-00000000.json', encoded({'revision': 0, 'digest': digest(state), 'audit_digest': digest(initial_audit)}))
            out._write(out.root_handle, 'ready.json', encoded({'schema': 1, 'instance': instance, 'root_id': rid, 'mode': mode, 'db_id': db_id}))
        finally:
            out.close()
        return cls(root, instance)

    def _create_mutex(self):
        create = w.bind(w.K, 'CreateMutexW', [C.POINTER(w.SA), W.BOOL, W.LPCWSTR], W.HANDLE)
        self.wait = w.bind(w.K, 'WaitForSingleObject', [W.HANDLE, W.DWORD], W.DWORD)
        self.release = w.bind(w.K, 'ReleaseMutex', [W.HANDLE])
        sd = w.descriptor(self.output.sid)
        try:
            sa = w.SA(C.sizeof(w.SA), sd, False)
            name = 'Global\\Atlas-Isolated-Fence-'+hashlib.sha256(encoded(self.root_id)).hexdigest()
            self.mutex_name = name
            self.mutex = create(C.byref(sa), False, name)
            w.check(self.mutex)
            kernel_acl(self.mutex, self.output.sid)
        finally:
            w.local_free(sd)

    def close(self):
        if self.mutex:
            w.close_handle(self.mutex)
            self.mutex = None
        self.output.close()

    def _read_json(self, leaf):
        h = w.relative_open(self.output.root_handle, leaf, self.output.sid, False, access=w.READ | w.READ_CONTROL)
        try:
            w.validate_acl(h, self.output.sid)
            if w.info(h).links != 1:
                raise Refused('Linked state witness')
            buf, count = C.create_string_buffer(65537), W.DWORD()
            w.check(w.read_file(h, buf, 65537, C.byref(count), None))
            if count.value > 65536:
                raise Refused('Oversize state witness')
            return json.loads(buf.raw[:count.value])
        finally:
            w.close_handle(h)

    def _binding(self):
        self.output._verify()
        with w.WindowsOutput(self.output.root) as current:
            if file_identity(current.root_handle) != self.root_id:
                raise Refused('Registry path substitution')

    def _poison(self, reason):
        self.poisoned = True
        # Persist before SQLite may remove a rejected sidecar on close. Never
        # repair ACLs, overwrite earlier failure evidence, or clear this marker.
        self.output._verify()
        try:
            self.output._write(self.output.root_handle, 'recovery-required.json', encoded({'reason': reason}))
        except FileExistsError:
            pass

    def surface(self):
        try:
            return self._surface()
        except Exception:
            self._poison('STORAGE_IDENTITY_OR_DACL')
            raise

    def _surface(self):
        self._binding()
        rows = {}
        for name in SURFACE:
            try:
                h = w.relative_open(self.output.root_handle, name, self.output.sid, False, access=w.READ_CONTROL | w.ATTR)
            except OSError as exc:
                if exc.winerror == 2 and name != SURFACE[0]:
                    continue
                raise
            try:
                if w.info(h).links != 1:
                    raise Refused('Linked SQLite storage')
                if name == SURFACE[0] and file_identity(h) != self.db_id:
                    raise Refused('Database identity replaced')
                rows[name] = inherited_acl(h, self.output.sid)
            finally:
                w.close_handle(h)
        return rows

    @contextmanager
    def guard(self):
        if self.poisoned:
            raise Refused("Unresolved registry storage failure")
        self._binding()
        code = self.wait(self.mutex, 500)
        if code not in (0, 128):
            raise Refused('Bounded registry lock unavailable')
        try:
            if code == 128:
                self._poison('ABANDONED_COORDINATOR')
                raise Refused('Abandoned coordinator requires independent recovery')
            try:
                self._read_json('recovery-required.json')
            except OSError as exc:
                if exc.winerror != 2:
                    raise
            else:
                raise Refused('Persistent recovery fence')
            self.local.depth = getattr(self.local, "depth", 0) + 1
            try:
                yield
            finally:
                self.local.depth -= 1
        finally:
            w.check(self.release(self.mutex))

    @contextmanager
    def database(self):
        # Call only inside guard. Exposed for native synthetic sidecar tests;
        # no application SQL or production connection API is provided.
        if not getattr(self.local, "depth", 0):
            raise Refused("SQLite access requires coordinator lease")
        self.surface()
        db = sqlite3.connect((Path(self.output.root)/SURFACE[0]).as_uri()+'?mode=rw', uri=True, timeout=.5)
        try:
            db.setlimit(sqlite3.SQLITE_LIMIT_ATTACHED, 0)
            db.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, 65536)
            db.execute('PRAGMA temp_store=MEMORY')
            db.execute('PRAGMA synchronous=FULL')
            db.execute('PRAGMA trusted_schema=OFF')
            if db.execute('PRAGMA journal_mode='+self.mode).fetchone()[0].upper() != self.mode:
                raise Refused('Unexpected journal policy')
            def sql_policy(action, first, second, _database, _trigger):
                if action in {sqlite3.SQLITE_ATTACH, sqlite3.SQLITE_DETACH, sqlite3.SQLITE_CREATE_TEMP_TABLE,
                              sqlite3.SQLITE_CREATE_VTABLE, sqlite3.SQLITE_DROP_VTABLE}:
                    return sqlite3.SQLITE_DENY
                if action == sqlite3.SQLITE_PRAGMA and second is not None and first.lower() in {
                        'temp_store', 'journal_mode', 'synchronous', 'trusted_schema', 'temp_store_directory', 'data_store_directory'}:
                    return sqlite3.SQLITE_DENY
                if action == sqlite3.SQLITE_FUNCTION and (second or '').lower() == 'load_extension':
                    return sqlite3.SQLITE_DENY
                return sqlite3.SQLITE_OK
            db.set_authorizer(sql_policy)
            self.surface()
            yield db
        finally:
            db.close()
            self.surface()

    def _state(self, db):
        try:
            return self._state_checked(db)
        except Exception:
            self._poison('STATE_OR_COMMIT_INTEGRITY')
            raise

    def _state_checked(self, db):
        if db.execute('PRAGMA quick_check').fetchone() != ('ok',):
            raise Refused('Corrupt state')
        state = json.loads(db.execute('SELECT value FROM state WHERE id=1').fetchone()[0])
        if (set(state) != {'schema', 'instance', 'revision', 'startup', 'inspection'} or state['schema'] != 1
                or type(state['schema']) is not int or state['instance'] != self.instance or type(state['revision']) is not int or not 0 <= state['revision'] < 100000000):
            raise Refused('Malformed registry state')
        if state['startup'] is not None:
            i = state['startup']
            if (not isinstance(i, dict) or set(i) != {'phase', 'operation', 'parent', 'worker', 'nonce', 'issued', 'expires'}
                    or i['phase'] not in {'PENDING', 'STARTING'} or not isinstance(i['nonce'], str)
                    or not re.fullmatch('[a-f0-9]{64}', i['nonce']) or type(i['issued']) not in (int, float)
                    or type(i['expires']) not in (int, float) or not 0 < i['issued'] < i['expires'] <= i['issued']+30):
                raise Refused('Unknown or malformed startup state')
            operation(i['operation'])
            identity(i['parent'])
            if i['parent']['created'] > i['issued']:
                raise Refused('Contradictory parent identity')
            if i['worker'] is not None:
                identity(i['worker'])
                if not i['issued'] <= i['worker']['created'] < i['expires']:
                    raise Refused('Contradictory worker creation')
            elif i['phase'] != 'PENDING':
                raise Refused('Missing admitted worker')
        if state['inspection'] is not None:
            i = state['inspection']
            if (not isinstance(i, dict) or set(i) != {'phase', 'operation', 'helper'} or i['phase'] != 'UNCERTAIN'
                    or (i['helper'] is not None and (not isinstance(i['helper'], str) or not re.fullmatch('[a-f0-9]{64}', i['helper'])))):
                raise Refused('Unknown inspection state')
            operation(i['operation'])
        if state['startup'] is not None and state['inspection'] is not None:
            raise Refused('Contradictory writer authorization')
        audit = json.loads(db.execute('SELECT value FROM audit WHERE revision=?', (state['revision'],)).fetchone()[0])
        if audit.get('state') != state or db.execute('SELECT MIN(revision), MAX(revision), COUNT(*) FROM audit').fetchone() != (0, state['revision'], state['revision']+1):
            raise Refused('Missing or contradictory audit history')
        if self._read_json(f"revision-{state['revision']:08d}.json") != {'revision': state['revision'], 'digest': digest(state), 'audit_digest': digest(audit)}:
            raise Refused('Missing or contradictory independent commit receipt')
        try:
            self._read_json(f"revision-{state['revision']+1:08d}.json")
        except OSError as exc:
            if exc.winerror != 2:
                raise
        else:
            raise Refused('Rolled-back database or stray committed receipt')
        return state

    def snapshot(self):
        with self.guard(), self.database() as db:
            return self._state(db)

    def startup_allowed(self):
        try:
            state = self.snapshot()
            return state['startup'] is None and state['inspection'] is None
        except Exception:  # noqa: BLE001 - unknown/corrupt/unavailable state must prohibit startup.
            return False

    def _change(self, mutate):
        with self.guard(), self.database() as db:
            db.execute('BEGIN IMMEDIATE')
            state = self._state(db)
            event = mutate(state, db) or {"type": "TRANSITION"}
            state['revision'] += 1
            db.execute('UPDATE state SET value=? WHERE id=1', (encoded(state).decode(),))
            audit = {'state': state, 'event': event}
            db.execute('INSERT INTO audit VALUES (?,?)', (state['revision'], encoded(audit).decode()))
            self.surface()
            db.commit()
            # If process/storage fails here, next read REFUSES missing receipt.
            self.output._write(self.output.root_handle, f"revision-{state['revision']:08d}.json", encoded({'revision': state['revision'], 'digest': digest(state), 'audit_digest': digest(audit)}))
            return state

    def reserve_start(self, op, parent, now=None):
        now = time.time() if now is None else now
        operation(op)
        identity(parent)
        if parent['created'] > now:
            raise Refused('Future process identity')
        def apply(s, db):
            if s['startup'] is not None or s['inspection'] is not None:
                raise Refused('Writer or inspection already pending')
            db.execute('INSERT INTO used VALUES (?)', (op,))
            s['startup'] = {'phase': 'PENDING', 'operation': op, 'parent': parent, 'worker': None,
                            'nonce': secrets.token_hex(32), 'issued': now, 'expires': now+30}
        return self._change(apply)

    def bind_worker(self, op, nonce, parent, worker, now):
        identity(worker)
        def apply(s, _):
            i = s['startup']
            if (not i or i['phase'] != 'PENDING' or i['operation'] != op or i['nonce'] != nonce
                    or encoded(i['parent']) != encoded(parent) or i['worker'] is not None or not i['issued'] <= worker['created'] <= now < i['expires']):
                raise Refused('Stale, replayed or replaced worker binding')
            i['worker'] = worker
        return self._change(apply)

    def admit_worker(self, op, nonce, worker, now):
        identity(worker)
        def apply(s, _):
            i = s['startup']
            if (s['inspection'] is not None or not i or i['phase'] != 'PENDING' or i['operation'] != op
                    or i['nonce'] != nonce or encoded(i['worker']) != encoded(worker) or not i['issued'] <= now < i['expires']):
                raise Refused('Independent worker admission refused')
            i['phase'] = 'STARTING'
        return self._change(apply)

    def begin_inspection(self, op, facts, now, *, approved=False):
        operation(op)
        if (approved is not True or not isinstance(facts, dict) or set(facts) != {'observed', 'stopped', 'no_pending'}
                or not fresh(facts['observed'], now) or facts['stopped'] is not True or facts['no_pending'] is not True):
            raise Refused('Fresh independent preconditions and approval required')
        def apply(s, db):
            if s['startup'] is not None or s['inspection'] is not None:
                raise Refused('Startup/inspection exclusion')
            db.execute('INSERT INTO used VALUES (?)', (op,))
            s['inspection'] = {'operation': op, 'phase': 'UNCERTAIN', 'helper': None}
        return self._change(apply)

    def bind_helper(self, op, helper):
        if not isinstance(helper, str) or not re.fullmatch('[a-f0-9]{64}', helper):
            raise Refused('Exact helper identity required')
        def apply(s, _):
            i = s['inspection']
            if not i or i['operation'] != op or i['helper'] is not None:
                raise Refused('Helper replacement refused')
            i['helper'] = helper
        return self._change(apply)

    def recover_inspection(self, authority, grant, proof, now):
        if type(authority) is not FixtureRecoveryAuthority:
            raise Refused('Synthetic independent authority only')
        def apply(s, _):
            authority.verify(grant, s, proof)
            i = s['inspection']
            if (not i or i['helper'] is None or not isinstance(proof, dict)
                    or set(proof) != {'id', 'operation', 'state', 'pid', 'observed'}
                    or proof['id'] != i['helper'] or proof['operation'] != i['operation']
                    or proof['state'] != 'exited' or type(proof['pid']) is not int or proof['pid'] != 0
                    or not fresh(proof['observed'], now)):
                raise Refused('Independent exact helper exit proof required')
            s['inspection'] = None
            return {'type': 'INSPECTION_FAILED_EXIT_PROVEN', 'proof': proof, 'grant_digest': digest(grant)}
        return self._change(apply)
