"""Pinned host-record observation + separate non-clearing fixture evidence.

No state transitions, source writes, Docker calls or production admission API.
Not full-head certification, directory exclusion or helper-exit authority.
"""
import copy
import ctypes as C
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path

spec = importlib.util.spec_from_file_location('quarantine_handoff', Path(__file__).with_name('manual_handoff.py'))
h = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)
s, w, Refused = h.s, h.s.w, h.Refused


class SyntheticScope:
    def __init__(self, pin, resources, sequence):
        self.pin, self.resources, self.sequence = copy.deepcopy(pin), copy.deepcopy(resources), sequence


class NonClearing:
    def __init__(self, scope, output):
        if type(scope) is not SyntheticScope or type(output) is not w.WindowsOutput:
            raise Refused('Synthetic pinned scope/native output required')
        s.validate_pin(scope.pin)
        if type(scope.sequence) is not int or not 0 < scope.sequence <= 128:
            raise Refused('Exact synthetic handoff revision required')
        if set(scope.resources) != {'snapshot', 'witness', 'handoff'}:
            raise Refused('Explicit three-resource read scope required')
        for value in scope.resources.values():
            if set(value) != {'root', 'root_id', 'leaf', 'file'}:
                raise Refused('Exact resource identities required')
            src, dst = Path(value['root']), Path(output.root)
            if src.is_relative_to(dst) or dst.is_relative_to(src):
                raise Refused('Output must be separate from all source roots')
        self.scope, self.output = copy.deepcopy(scope), output

    def _locked(self):
        """No-op fixture test seam; not a callback or production side effect."""

    def observe_and_record(self, operation, reported_helper='UNKNOWN'):
        s.native.operation(operation)
        if reported_helper not in {'EXITED', 'RUNNING', 'MISSING', 'REPLACED', 'STALE', 'UNAVAILABLE', 'UNKNOWN'}:
            raise Refused('Bounded advisory status required')
        roots, handles, records = {}, [], {}
        try:
            for role, resource in self.scope.resources.items():
                root = roots[role] = w.WindowsOutput(resource['root'])
                if s.native.file_identity(root.root_handle) != resource['root_id']:
                    raise Refused('Source directory identity mismatch')
                handle = w.relative_open(root.root_handle, resource['leaf'], root.sid, False,
                                         access=w.READ | w.READ_CONTROL)
                handles.append((role, handle))
                w.validate_acl(handle, root.sid)
                info = w.info(handle)
                if info.links != 1 or s.native.file_identity(handle) != resource['file']['id']:
                    raise Refused('Source file identity/link mismatch before read')
                size = (info.size_hi << 32) | info.size_lo
                if size > 65536:
                    raise Refused('Source bound')
                buf, count = C.create_string_buffer(65537), w.W.DWORD()
                w.check(w.read_file(handle, buf, 65537, C.byref(count), None))
                raw = buf.raw[:count.value]
                if count.value != size or s.sha(raw) != resource['file']['sha256']:
                    raise Refused('Source commitment mismatch before decode')
                records[role] = json.loads(raw)
                if s.encoded(records[role]) != raw:
                    raise Refused('Noncanonical source')
            pin = self.scope.pin
            state, commit, ack = (records[k] for k in ('snapshot', 'witness', 'handoff'))
            if (state['instance'] != pin['instance'] or type(state['revision']) is not int or state['revision'] != pin['revision']
                    or state['startup'] is not None or state['inspection']['phase'] != 'UNCERTAIN'
                    or self.scope.resources['snapshot']['file'] != pin['snapshot']
                    or self.scope.resources['witness']['file'] != pin['commit']
                    or s.encoded(commit) != s.encoded({k: pin[k] for k in ('instance', 'revision', 'snapshot')})
                    or set(ack) != {'body', 'sha256'} or s.sha(s.encoded(ack['body'])) != ack['sha256']
                    or s.encoded(ack['body']['pin']) != s.encoded(pin)
                    or ack['body']['sequence'] != self.scope.sequence):
                raise Refused('UNCERTAIN subset/commit/handoff mismatch')
            self._locked()
            # Refuse known newer publications without creating poison or repairing anything.
            for role, leaf in [('witness', f'intent-{pin["revision"]+1:08d}.json'),
                               ('witness', 'recovery-required.json'), ('handoff', 'manual-review-required.json'),
                               ('handoff', f'intent-{self.scope.sequence+1:08d}.json')]:
                if s.exists(roots[role], leaf):
                    raise Refused('Known newer or unresolved state')
            result = {'scope': 'SYNTHETIC_PINNED_HOST_SUBSET_ONLY', 'event': 'UNCERTAIN_QUARANTINE_OBSERVATION',
                      'operation': operation, 'revision': pin['revision'], 'pin_sha256': s.sha(s.encoded(pin)),
                      'observed_utc': datetime.now(timezone.utc).isoformat(),
                      'sources': {k: {'root_id': v['root_id'], 'file': v['file']} for k,v in self.scope.resources.items()},
                      'observer': s.native.current_process_identity(), 'reported_helper': reported_helper,
                      'helper_exit_proven': False, 'full_history_or_latest_head_proven': False,
                      'external_writer_exclusion': False, 'startup_permission': False, 'recovery_authorized': False}
            # Exclusive three-file publication in an unrelated protected directory.
            # Commit is written last; no consumer can interpret a partial bundle as complete.
            data = s.encoded(result)
            if len(data) > 16384:
                raise Refused('Evidence bound')
            audit = s.encoded({'event': 'NON_CLEARING_ONLY', 'operation': operation, 'sha256': s.sha(data)})
            for suffix, raw in [('json', data), ('audit', audit), ('commit', s.encoded({'record': s.sha(data), 'audit': s.sha(audit)}))]:
                self.output._verify()
                self.output._write(self.output.root_handle, operation+'.'+suffix, raw)
            if self.read_record(operation) != result:
                raise Refused('Publication verification mismatch')
            return result
        finally:
            for _role, handle in reversed(handles): w.close_handle(handle)
            for root in roots.values(): root.close()

    def read_record(self, operation):
        s.native.operation(operation)
        raw, _ = s.read_bound(self.output, operation+'.json')
        audit, _ = s.read_bound(self.output, operation+'.audit')
        commit, _ = s.read_bound(self.output, operation+'.commit')
        if json.loads(commit) != {'record': s.sha(raw), 'audit': s.sha(audit)}:
            raise Refused('Incomplete or corrupt audit bundle')
        result = json.loads(raw)
        if (json.loads(audit) != {'event': 'NON_CLEARING_ONLY', 'operation': operation, 'sha256': s.sha(raw)}
                or result['operation'] != operation or result['startup_permission'] is not False
                or result['recovery_authorized'] is not False or result['helper_exit_proven'] is not False
                or result['external_writer_exclusion'] is not False or result['full_history_or_latest_head_proven'] is not False
                or result['scope'] != 'SYNTHETIC_PINNED_HOST_SUBSET_ONLY'
                or result['event'] != 'UNCERTAIN_QUARANTINE_OBSERVATION'
                or type(result['revision']) is not int or result['revision'] != self.scope.pin['revision']
                or result['pin_sha256'] != s.sha(s.encoded(self.scope.pin))):
            raise Refused('Invalid non-clearing record')
        return result

    def startup(self):
        raise Refused('Quarantine never authorizes startup')

    def recover(self):
        raise Refused('Read-only verification never authorizes recovery')
