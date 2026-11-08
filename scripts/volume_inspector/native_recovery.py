"""Native approval + synthetic authenticated-source proof acceptance.

NO production Docker adapter. Imported JSON/exit codes are not authority.
Normal trusted-owner desktop UI is not secure-attention reauthentication.
"""
import copy
import importlib.util
import secrets
import time
from datetime import datetime
from pathlib import Path


def load(name):
    spec = importlib.util.spec_from_file_location('recovery_'+name, Path(__file__).with_name(name+'.py'))
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


h = load('manual_handoff')
d = load('native_dialog')
s, Refused = h.s, h.Refused


class Clock:
    def now(self):
        return time.time()


class FixtureClock:
    def __init__(self, now=1000):
        self.value = now

    def now(self):
        return self.value


class MockDocker:
    """An explicit, non-network fixture transport; never a real Engine client."""
    def __init__(self, container, image):
        self.container, self.image = container, image
        self.connected, self.delay, self.cached = True, 0, False

    def inspect(self, _identity, nonce, clock):
        if self.connected is not True:
            raise ConnectionError('Synthetic Engine unavailable')
        if type(clock) is FixtureClock:
            clock.value += self.delay
        return {'request': '0'*64 if self.cached else nonce, 'container': copy.deepcopy(self.container),
                'image': copy.deepcopy(self.image)}


class MockDialog:
    def __init__(self, approved=False):
        self.approved = approved

    def confirm(self, _text, _timeout_ms=45000):
        return {'approved': self.approved is True, 'created': True, 'timed_out': False,
                'button': 6 if self.approved is True else 2, 'verified': self.approved is True}


def timestamp(value):
    if not isinstance(value, str):
        raise Refused('Missing timestamp')
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.tzinfo is None:
        raise Refused('Timestamp timezone required')
    return result.timestamp()


class ExitCollector:
    def __init__(self, transport, expected, output, clock):
        if type(transport) is not MockDocker or type(clock) not in (Clock, FixtureClock):
            raise Refused('Synthetic source transport only; real Docker not authorized')
        if set(expected) != {'id', 'image', 'manifest', 'labels'}:
            raise Refused('Pinned identity/ownership/image required')
        if (not isinstance(expected['id'], str) or len(expected['id']) != 64
                or any(c not in 'abcdef0123456789' for c in expected['id'])
                or any(not isinstance(expected[k], str) or not expected[k].startswith('sha256:')
                       or len(expected[k]) != 71 or any(c not in 'abcdef0123456789' for c in expected[k][7:]) for k in ('image', 'manifest'))
                or not isinstance(expected['labels'], dict) or set(expected['labels']) != {'atlas.project', 'atlas.inspection.instance', 'atlas.inspection.operation'}
                or expected['labels']['atlas.project'] != 'projectatlas'):
            raise Refused('Malformed pinned ownership/image')
        s.native.operation(expected['labels']['atlas.inspection.operation'])
        self.transport, self.expected, self.output, self.clock = transport, copy.deepcopy(expected), output, clock

    def collect(self):
        nonce, begin = secrets.token_hex(32), self.clock.now()
        proof = {'source': 'SYNTHETIC_MOCK_DOCKER', 'request': nonce, 'observed': begin,
                 'status': 'UNKNOWN', 'reason': 'MALFORMED', 'fingerprint': None}
        try:
            reply = self.transport.inspect(self.expected['id'], nonce, self.clock)
            end = self.clock.now()
            proof['observed'] = end
            if not 0 <= end-begin <= 2 or len(s.encoded(reply)) > 65536 or set(reply) != {'request', 'container', 'image'} or reply['request'] != nonce:
                raise Refused('Stale/uncorrelated/oversized proof')
            c, image = reply['container'], reply['image']
            if c is None:
                proof.update(status='MISSING', reason='NOT_FOUND')
            elif (not isinstance(c, dict) or set(c) != {'Id', 'Image', 'Labels', 'Created', 'State'}
                  or not isinstance(image, dict) or set(image) != {'Id', 'Manifest'}):
                raise Refused('Malformed source')
            elif c['Id'] != self.expected['id'] or c['Image'] != self.expected['image'] or c['Labels'] != self.expected['labels'] or image != {'Id': self.expected['image'], 'Manifest': self.expected['manifest']}:
                proof.update(status='REPLACED', reason='IDENTITY_OR_OWNERSHIP_CHANGED')
            else:
                state = c['State']
                if (not isinstance(state, dict) or set(state) != {'Status', 'Running', 'Pid', 'StartedAt', 'FinishedAt'}
                        or type(state['Running']) is not bool or type(state['Pid']) is not int or state['Pid'] < 0):
                    raise Refused('Malformed state')
                if state['Status'] == 'running' and state['Running'] is True and state['Pid'] > 0:
                    proof.update(status='RUNNING', reason='NOT_EXITED')
                elif state['Status'] == 'exited' and state['Running'] is False and state['Pid'] == 0:
                    created, started, finished = timestamp(c['Created']), timestamp(state['StartedAt']), timestamp(state['FinishedAt'])
                    if not 0 < created <= started <= finished <= end:
                        raise Refused('Contradictory exit times')
                    proof.update(status='EXITED', reason='EXACT_EXIT_OBSERVED', fingerprint=s.sha(s.encoded(c)))
        except ConnectionError:
            proof.update(reason='ENGINE_UNAVAILABLE')
        except (ValueError, TypeError, KeyError, OverflowError):
            proof.update(status='UNKNOWN', reason='MALFORMED_OR_STALE', fingerprint=None)
        self.output._write(self.output.root_handle, 'proof-'+nonce+'.json', s.encoded(proof))
        return proof


class ApprovalWorkflow:
    """Actual native identity; UI source recorded as native vs simulated.

    Approval receipts must be minted in this process and retain verified file
    bindings. Surviving files alone cannot restore a usable approval after crash.
    """
    def __init__(self, handoff, collector, output, expected_context, clock):
        if type(handoff) is not h.Handoff or type(collector) is not ExitCollector:
            raise Refused('Isolated handoff and proof collector required')
        self.handoff, self.collector, self.output = handoff, collector, output
        self.expected_context, self.clock = copy.deepcopy(expected_context), clock
        self.tickets = {}

    def context(self):
        context = d.token_context(s.w)
        if context != self.expected_context or not context['interactive'] or context['restricted']:
            raise Refused('Expected interactive Windows account/logon/session required')
        return context

    def audit(self, event, detail):
        self.output._write(self.output.root_handle, event+'-'+secrets.token_hex(32)+'.json', s.encoded(detail))

    def request(self, dialog, timeout_ms=45000):
        if type(dialog) not in (d.NativeDialog, MockDialog):
            raise Refused('Native or explicitly simulated UI only')
        nonce = secrets.token_hex(32)
        try:
            context = self.context()
            state = self.handoff.store.snapshot()
            intent = state['inspection']
            expected = self.collector.expected
            if (not intent or intent['phase'] != 'UNCERTAIN' or intent['helper'] != expected['id']
                    or intent['operation'] != expected['labels']['atlas.inspection.operation']
                    or state['instance'] != expected['labels']['atlas.inspection.instance']):
                raise Refused('Exact uncertain inspection required')
            before = self.collector.collect()
            if before['status'] != 'EXITED':
                raise Refused('Fresh exact exit proof required')
            issued = self.clock.now()
            challenge = {'nonce': nonce, 'state': s.sha(s.encoded(state)), 'revision': state['revision'], 'instance': state['instance'],
                         'helper': intent['helper'], 'operation': intent['operation'], 'action': 'RECORD_FAILED_EXIT_PROVEN',
                         'proof': before['fingerprint'], 'context': context, 'issued': issued, 'expires': issued+45}
            self.audit('challenge', challenge)
            text = ('SYNTHETIC FIXTURE ONLY. Recovery is blocked by an UNCERTAIN inspection.\n'
                    'Required: verified Windows operator, exact fresh helper exit, unchanged state and durable evidence.\n\n'
                    f"Operation: {intent['operation']}\nHelper: {intent['helper']}\nRevision: {state['revision']}\n"
                    f"State SHA-256: {challenge['state']}\nProof SHA-256: {before['fingerprint']}\n\n"
                    'Action: record failed inspection after proven exit. No startup/retry. Fresh evidence will be checked again after confirmation.')
            answer = dialog.confirm(text, timeout_ms)
            if not isinstance(answer, dict) or set(answer) != {'approved', 'created', 'timed_out', 'button', 'verified'}:
                raise Refused('Malformed UI response')
            self.audit('decision', {'nonce': nonce, 'ui': 'NATIVE_WINDOWS' if type(dialog) is d.NativeDialog else 'SIMULATED_UI', 'response': answer})
            if (answer['approved'] is not True
                    or answer['created'] is not True or answer['timed_out'] is not False or type(answer['button']) is not int
                    or answer['button'] != 6 or answer['verified'] is not True):
                raise Refused('Operator declined, timed out or did not verify details')
            self.context()
            if not issued <= self.clock.now() <= challenge['expires']:
                raise Refused('Approval window expired')
            after = self.collector.collect()
            if after['status'] != 'EXITED' or after['fingerprint'] != before['fingerprint'] or s.sha(s.encoded(self.handoff.store.snapshot())) != challenge['state']:
                raise Refused('Evidence/state changed during confirmation')
            receipt = {'challenge': challenge, 'proof': after, 'approved_at': self.clock.now(),
                       'ui': 'NATIVE_WINDOWS' if type(dialog) is d.NativeDialog else 'SIMULATED_UI'}
            name = 'approval-'+nonce+'.json'
            raw = s.encoded(receipt)
            self.output._write(self.output.root_handle, name, raw)
            stored, binding = s.read_bound(self.output, name)
            if stored != raw:
                raise Refused('Approval publication changed')
            self.tickets[nonce] = {'binding': binding, 'receipt': receipt, 'used': False}
            return nonce
        except Exception:
            self.audit('refusal', {'nonce': nonce, 'reason': 'APPROVAL_NOT_ESTABLISHED'})
            raise

    def recover(self, nonce):
        try:
            self.context()
            ticket = self.tickets.get(nonce)
            if not ticket or ticket['used']:
                raise Refused('Forged/replayed/unretained approval')
            receipt = ticket['receipt']
            raw, _ = s.read_bound(self.output, 'approval-'+nonce+'.json', ticket['binding'])
            if raw != s.encoded(receipt):
                raise Refused('Approval changed')
            proof = self.collector.collect()  # No remote I/O under the state lock.
            if (proof['status'] != 'EXITED' or proof['fingerprint'] != receipt['proof']['fingerprint']
                    or not receipt['approved_at'] <= self.clock.now() <= receipt['challenge']['expires']):
                raise Refused('Fresh unchanged exit evidence required')
            with self.handoff.store.guard():
                self.context()
                state = self.handoff.store.snapshot()
                if s.sha(s.encoded(state)) != receipt['challenge']['state'] or not s.native.fresh(proof['observed'], self.clock.now()):
                    raise Refused('State revision or proof freshness changed')
                # Persist consumption BEFORE any recovery; errors leave uncertainty.
                self.output._write(self.output.root_handle, 'consumed-'+nonce+'.json', s.encoded({'approval': ticket['binding'], 'proof': proof}))
                ticket['used'] = True
                # Compatibility conversion only AFTER approval + collector checks.
                # Downstream remains explicitly synthetic, never production proof.
                auth = self.handoff.authority.recovery
                facts = auth.attest_exit(receipt['challenge']['helper'], receipt['challenge']['operation'], self.clock.now())
                grant = auth.approve(state, facts, approved=True)
                return self.handoff.recover_synthetic(facts, grant, self.clock.now())
        except Exception:
            self.audit('refusal', {'reason': 'RECOVERY_NOT_ESTABLISHED'})
            raise

    def production_admission(self):
        raise Refused('Synthetic transport and unintegrated startup paths; no production authority')
