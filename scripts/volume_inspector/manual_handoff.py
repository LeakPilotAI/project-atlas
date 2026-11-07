"""Synthetic durable pin handoff under a trusted workstation operator.

Local append-only receipts are NOT an independent anti-rollback anchor. No
native approval/exit-proof collector, DPAPI/TPM keys or production entry points.
"""
import copy
import importlib.util
import json
from pathlib import Path

spec = importlib.util.spec_from_file_location('handoff_snapshot', Path(__file__).with_name('snapshot_store.py'))
s = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)
Refused = s.Refused


def seal(body):
    return s.encoded({'body': body, 'sha256': s.sha(s.encoded(body))})


def read_receipt(output, name):
    raw, _ = s.read_bound(output, name)
    envelope = json.loads(raw)
    if (not isinstance(envelope, dict) or set(envelope) != {'body', 'sha256'}
            or s.encoded(envelope) != raw or envelope['sha256'] != s.sha(s.encoded(envelope['body']))):
        raise Refused('Corrupt local handoff receipt')
    return envelope['body'], s.sha(raw)


class ManualFixtureAuthority:
    """Logical test roles only. Never a production identity/proof issuer."""
    def __init__(self):
        self.available = True
        self.recovery = s.SyntheticAuthority()

    def require(self):
        if self.available is not True:
            raise Refused('Manual authority unavailable; startup remains prohibited')


class Handoff:
    def __init__(self, store, root, expected_root_id, authority):
        if type(store) is not s.SnapshotStore or type(authority) is not ManualFixtureAuthority:
            raise Refused('Synthetic local manual authority required')
        authority.require()
        self.store, self.authority = store, authority
        self.output = s.w.WindowsOutput(root)
        try:
            if s.native.file_identity(self.output.root_handle) != expected_root_id:
                raise Refused('Changed handoff root')
            self.root_id = copy.deepcopy(expected_root_id)
            with self.store.guard():
                _, pin, _ = self._current()
                if pin != self.store.pin:
                    raise Refused('Store and durable handoff disagree')
                self.store.snapshot()
        except BaseException:
            self.output.close()
            raise

    @classmethod
    def provision_synthetic(cls, store, root, authority):
        if type(authority) is not ManualFixtureAuthority:
            raise Refused('Synthetic authority required')
        authority.require()
        state = store.snapshot()
        with s.w.WindowsOutput.create_root(root) as output:
            body = {'sequence': 0, 'instance': state['instance'], 'pin': store.pin, 'previous': None}
            output._write(output.root_handle, 'ack-00000000.json', seal(body))
            root_id = s.native.file_identity(output.root_handle)
        return cls(store, root, root_id, authority)

    @classmethod
    def reopen_synthetic(cls, snapshot_root, witness_root, root, expected_root_id, authority):
        # Read only the trusted local receipt chain; never initialize missing state.
        if type(authority) is not ManualFixtureAuthority:
            raise Refused('Missing manual authority')
        authority.require()
        temp = cls.__new__(cls)
        temp.authority = authority
        temp.output = s.w.WindowsOutput(root)
        try:
            if s.native.file_identity(temp.output.root_handle) != expected_root_id:
                raise Refused('Changed handoff root')
            _, pin, _ = temp._current()
        finally:
            temp.output.close()
        store = s.SnapshotStore(snapshot_root, witness_root, pin)
        try:
            return cls(store, root, expected_root_id, authority)
        except BaseException:
            store.close()
            raise

    def close(self):
        self.output.close()
        self.store.close()

    def _current(self):
        self.authority.require()
        try:
            if s.exists(self.output, 'manual-review-required.json'):
                raise Refused('Durable manual review fence')
            return self._checked_current()
        except Exception:
            self.output._verify()
            try:
                self.output._write(self.output.root_handle, 'manual-review-required.json', b'{"reason":"HANDOFF_UNCERTAIN"}')
            except FileExistsError:
                pass
            raise

    def _checked_current(self):
        self.authority.require()
        body, previous = read_receipt(self.output, 'ack-00000000.json')
        if (set(body) != {'sequence', 'instance', 'pin', 'previous'} or type(body['sequence']) is not int
                or body['sequence'] != 0 or body['previous'] is not None):
            raise Refused('Invalid initialization receipt')
        s.validate_pin(body['pin'])
        if body['instance'] != body['pin']['instance']:
            raise Refused('Foreign initialization instance')
        pin = body['pin']
        sequence = 0
        for n in range(1, 129):
            intent_name, ack_name = f'intent-{n:08d}.json', f'ack-{n:08d}.json'
            intent_exists, ack_exists = s.exists(self.output, intent_name), s.exists(self.output, ack_name)
            if not intent_exists:
                if ack_exists:
                    raise Refused('Acknowledgement without reservation')
                # Bounded sparse-tail detection; never skip an absent revision.
                for later in range(n+1, 129):
                    if s.exists(self.output, f'intent-{later:08d}.json') or s.exists(self.output, f'ack-{later:08d}.json'):
                        raise Refused('Handoff history gap')
                break
            intent, ihash = read_receipt(self.output, intent_name)
            if (set(intent) != {'sequence', 'base', 'previous', 'action', 'authorization'} or type(intent['sequence']) is not int
                    or intent['sequence'] != n or intent['base'] != pin or intent['previous'] != previous
                    or intent['action'] not in {'START', 'INSPECT', 'RECOVER'}):
                raise Refused('Stale or inconsistent handoff reservation')
            if not ack_exists:
                raise Refused('Interrupted handoff requires manual review')
            ack, ahash = read_receipt(self.output, ack_name)
            if (set(ack) != {'sequence', 'pin', 'intent'} or type(ack['sequence']) is not int
                    or ack['sequence'] != n or ack['intent'] != ihash):
                raise Refused('Inconsistent handoff acknowledgement')
            s.validate_pin(ack['pin'])
            if (ack['pin']['instance'] != pin['instance'] or ack['pin']['revision'] != pin['revision']+1
                    or any(ack['pin'][k] != pin[k] for k in ('root_id', 'witness_root_id'))):
                raise Refused('Invalid handoff progression')
            pin, previous, sequence = ack['pin'], ahash, n
        return sequence, pin, previous

    def _perform(self, action, effect, authorization=None):
        self.authority.require()
        with self.store.guard():
            sequence, pin, previous = self._current()
            if pin != self.store.pin:
                raise Refused('Durable current pin mismatch')
            self.store.snapshot()
            if sequence >= 128:
                raise Refused('Synthetic handoff capacity reached')
            n = sequence+1
            intent = {'sequence': n, 'base': pin, 'previous': previous, 'action': action, 'authorization': authorization}
            raw = seal(intent)
            self.output._write(self.output.root_handle, f'intent-{n:08d}.json', raw)
            self.authority.require()
            effect()
            self.authority.require()
            ack = {'sequence': n, 'pin': self.store.pin, 'intent': s.sha(raw)}
            self.output._write(self.output.root_handle, f'ack-{n:08d}.json', seal(ack))
            self._current()
            return self.store.snapshot()

    def start_synthetic(self, op, parent):
        return self._perform('START', lambda: self.store.reserve_start(op, parent))

    def inspect_synthetic(self, op, helper, *, approved=False):
        if approved is not True:
            raise Refused('Explicit inspection approval required')
        return self._perform('INSPECT', lambda: self.store.inspect(op, helper, approved=True))

    def recover_synthetic(self, proof, grant, now):
        self.authority.require()
        # Recheck inside the serialized action, before durable handoff reservation.
        with self.store.guard():
            self.authority.recovery.verify(self.store.snapshot(), proof, grant, now)
            return self._perform('RECOVER', lambda: self.store.recover(self.authority.recovery, proof, grant, now),
                                 s.sha(s.encoded(grant)))

    def production_admission(self):
        raise Refused('No native operator/exit-proof collector; fixture is not production authority')
