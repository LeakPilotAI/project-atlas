"""Exact controller target, inherited handoff and create-new bootstrap receipt.

No launcher, native loader, grant issuer or financial execution authority.
The logical argv and the actual fenced process command are BOTH verified.
"""

import copy
import ntpath
from dataclasses import dataclass

from app.services.paper_financial_replay import body, digest, strict
from scripts.observation_runtime.aip06_harness import BASE, ROOTS, SCOPE_HASH, need

REPO = ntpath.dirname(ntpath.dirname(BASE))
ENTRY = ntpath.join(REPO, 'scripts', 'observation_runtime', 'aip06_acceptance_controller.py')
CONTRACT = ntpath.join(REPO, 'scripts', 'observation_runtime', 'aip06_controller_contract.py')
MANIFEST = ntpath.join(REPO, 'docs', 'AIP_06_NATIVE_CANDIDATE_RUN_MANIFEST_2026-11-05.json')
ROLE = 'acceptance_controller'


def controller_argv(argv, targets):
    need(type(argv) in (tuple, list) and len(argv) == 9 and type(targets) is dict and targets.get(ROLE) == ENTRY
         and argv[1:8] == type(argv)(('-B', ENTRY, '--role', 'controller', '--manifest', MANIFEST, '--manifest-sha256'))
         and type(argv[0]) is str and argv[0].startswith('D:\\') and ntpath.normpath(argv[0]) == argv[0]
         and type(argv[8]) is str and len(argv[8]) == 64 and set(argv[8]) <= set('0123456789abcdef'),
         'EXACT_PREDECLARED_CONTROLLER_COMMAND')
    return tuple(argv)


def bootstrap_argv(executable, nonce):
    need(type(nonce) is str and len(nonce) == 32 and set(nonce) <= set('0123456789abcdef'), 'CONTROLLER_BOOTSTRAP_NONCE')
    return (executable, '-B', '-m', 'scripts.observation_runtime.aip06_child_bootstrap', '--inherited-session', nonce)


@dataclass(frozen=True)
class ControllerIntent:
    raw: bytes
    sha256: str

    def plan(self):
        from scripts.observation_runtime.aip06_acceptance_plan import decode_plan
        value = decode_plan(self.raw, self.sha256)
        need(CONTRACT in value['source_pins'], 'PINNED_CONTROLLER_CONTRACT_SOURCE_REQUIRED')
        return value

    @property
    def argv(self):
        value = self.plan()
        return (value['executable'], '-B', ENTRY, '--role', 'controller', '--manifest', MANIFEST,
                '--manifest-sha256', self.sha256)

    def declare(self, port):
        plan = self.plan(); port.guard.check()
        need(getattr(port, 'controller_intent', None) is None and not port.sessions
             and port.executable == plan['executable'] and port.controller.profile['source_pins'] == plan['source_pins'],
             'ONE_CONTROLLER_INTENT_BEFORE_CREATION')
        need(port.guard.resources.state['controller'] == port.guard.owner, 'ONLY_ROOT_OWNER_DECLARATION')
        controller_argv(self.argv, port.controller.profile['targets'])
        port.controller.verify_source(CONTRACT)
        port.controller_intent = self
        return {'scope': SCOPE_HASH, 'manifest': self.sha256, 'argv': self.argv,
                'process_created': False, 'native_acceptance': False}

    def claim(self, port, argv):
        port.guard.check()
        need(port.guard.resources.state['controller'] == port.guard.owner, 'ONLY_ROOT_OWNER_DECLARATION')
        need(type(self) is ControllerIntent and tuple(argv) == self.argv
             and port.controller.profile['source_pins'] == self.plan()['source_pins']
             and not getattr(port, 'controller_claimed', False), 'ONCE_ONLY_EXACT_CONTROLLER_INTENT')
        port.controller_claimed = True
        return ROLE


@dataclass(frozen=True)
class PrecreationReceipt:
    """Snapshot, not authority: rechecked against the ONE newly bound root."""
    manifest: str
    parent: str
    roots: str
    started_ns: int
    finished_ns: int

    @classmethod
    def capture(cls, intent, *, paths, clock_ns, deadline_ns):
        need(type(intent) is ControllerIntent, 'TYPED_PRECREATION_INTENT')
        intent.plan(); start = clock_ns()
        need(start < deadline_ns, 'PRECREATION_DEADLINE')
        parent = paths.parent()
        values = {k: paths.prepare(k) for k in ROOTS}
        done = clock_ns()
        need(start <= done < deadline_ns and done-start <= 60*10**9, 'BOUNDED_CREATE_NEW_PREFLIGHT')
        return cls(intent.sha256, body(parent), body(values), start, done)

    def bind(self, intent, *, guard, clock_ns, deadline_ns):
        need(type(intent) is ControllerIntent and self.manifest == intent.sha256
             and type(self.parent) is str and type(self.roots) is str
             and type(self.started_ns) is int and type(self.finished_ns) is int
             and self.started_ns <= self.finished_ns <= clock_ns() < deadline_ns
             and clock_ns()-self.started_ns <= 60*10**9, 'FRESH_MATCHED_PRECREATION_RECEIPT')
        roots = strict(self.roots)
        need(body(guard.paths.parent()) == self.parent and set(roots) == set(ROOTS)
             and all(type(v) is dict and set(v) == {'alias','path','parent'} and v['alias'] == k
                     and v['path'] == ROOTS[k] and body(v['parent']) == self.parent for k,v in roots.items()),
             'PRECREATION_PARENT_CHANGED')
        # Initialization must have bound E through its existing create-new
        # guard. No new ledger or discovery-based adoption is performed here.
        guard.paths.verify('E')
        snapshot = guard.resources.read()
        need(snapshot['scope'] == SCOPE_HASH and snapshot['state']['controller'] == guard.owner,
             'ONE_ROOT_OWNER_SHARED_LEDGER_REQUIRED')
        for alias in ROOTS:
            if alias != 'E':
                need(alias not in guard.paths.bound and guard.io.inspect(ROOTS[alias]) is None,
                     'UNEXPECTED_ROOT_BETWEEN_PREFLIGHT_AND_INITIALIZATION')
        return {'scope': SCOPE_HASH, 'manifest': self.manifest, 'root_owner': guard.owner,
                'root_identity': copy.deepcopy(guard.paths.bound['E']), 'native_acceptance': False}


def inherited_context(guard, descriptor, packet):
    """Private INPUT after HELLO/BIND/guard/ACK/RELEASE, never CLI authority."""
    from scripts.observation_runtime.aip06_fixture_guard import FixtureGuard
    from scripts.observation_runtime.aip06_ipc import RemoteResources
    need(type(guard) is FixtureGuard and type(guard.resources) is RemoteResources
         and getattr(guard, 'launch_role', None) == 'acceptance_supervisor', 'INHERITED_CONTROLLER_GUARD_REQUIRED')
    guard.check(); binding = guard.resources.channel.binding
    need(type(packet) is dict and set(packet) == {'schema','scope','manifest','raw','nonce','owner','parent_owner'}
         and len(body(packet).encode('utf-8')) <= 65536
         and packet['schema'] == 'AIP06_CONTROLLER_PREPARE_V1' and packet['scope'] == SCOPE_HASH
         and packet['nonce'] == binding['nonce'] and packet['owner'] == guard.owner == digest(binding['child'])
         and packet['parent_owner'] == digest(binding['parent']) and type(packet['raw']) is str,
         'PRIVATE_CONTROLLER_INPUT_CORRELATION')
    intent = ControllerIntent(packet['raw'].encode('utf-8'), packet['manifest'])
    plan = intent.plan()
    need(tuple(descriptor['argv']) == intent.argv and descriptor['source_pins'] == plan['source_pins'],
         'INHERITED_CONTROLLER_ARGV_OR_SOURCE_PINS')
    controller_argv(descriptor['argv'], descriptor['targets'])
    snapshot = guard.resources.read()
    need(snapshot['state']['mode'] == 'WORK' and snapshot['state']['owners'].get(guard.owner) == binding['child'],
         'CURRENT_CONTROLLER_SHARED_LEDGER_OWNER')
    return ControllerContext(intent, guard, snapshot['state']['controller'], binding['nonce'])


def verify_prepared(value, *, binding, manifest, root_owner):
    need(type(value) is dict and set(value) == {'schema','manifest','owner','root_owner','native_acceptance'}
         and value['schema'] == 'AIP06_CONTROLLER_PREPARED_V1' and value['manifest'] == manifest
         and value['owner'] == digest(binding.runtime) and value['root_owner'] == root_owner
         and value['native_acceptance'] is False, 'EXACT_CONTROLLER_PREPARATION_PUBLICATION')
    return copy.deepcopy(value)


@dataclass(frozen=True)
class ControllerContext:
    intent: ControllerIntent
    guard: object
    root_owner: str
    nonce: str

    def bind_dispatcher(self, dispatcher):
        from scripts.observation_runtime.aip06_acceptance_control import Dispatcher, GuardedScenarioBridge
        from scripts.observation_runtime.aip06_acceptance_grade import IndependentGrader
        port = getattr(self.guard.processes, 'port', None)
        need(type(dispatcher) is Dispatcher and type(dispatcher.adapter) is GuardedScenarioBridge
             and type(dispatcher.grader) is IndependentGrader
             and port is not None and dispatcher.adapter.guard is self.guard and dispatcher.adapter.controller is port.controller
             and dispatcher.grader.pin == self.intent.sha256, 'EXACT_INHERITED_DISPATCHER_CONTEXT')
        self.guard.check()
        return ControllerDispatch(self, dispatcher)

    def require_native_execution(self):
        from scripts.observation_runtime.aip06_acceptance_plan import require_execution_ready
        self.guard.check()
        require_execution_ready(self.intent.plan())  # Still refuses unresolved gates.


@dataclass(frozen=True)
class ControllerDispatch:
    context: ControllerContext
    dispatcher: object

    def run(self):
        # A successful bind is not execution authority. This check precedes
        # every adapter query/reservation, even with a fully populated registry.
        self.context.require_native_execution()
        return self.dispatcher.run()
