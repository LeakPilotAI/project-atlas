"""Synthetic lifecycle bridge; no process, Docker or production entry point.

FixtureWorld is the ONLY accepted identity/action provider. Its process table
models independent observations, not a production process-identity authority.
Registry construction/provisioning remains outside this bridge.
"""
import copy
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location('bridge_shared_fence', Path(__file__).with_name('shared_fence.py'))
fence = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fence)


class FixtureWorld:
    """No callbacks or real transport; generated control facts only."""
    def __init__(self, parent, worker, now=1000):
        self.now = now
        self.processes = {'parent': copy.deepcopy(parent), 'worker': copy.deepcopy(worker)}
        self.helper = None
        self.effects = []

    def observe(self, role):
        value = copy.deepcopy(self.processes[role])
        fence.identity(value)
        return value

    def create_worker(self):
        self.effects.append('synthetic-worker-created')
        return self.observe('worker')

    def dependencies(self):
        self.effects.append('synthetic-dependencies-admitted')

    def exit_proof(self, op):
        if not isinstance(self.helper, dict):
            raise fence.Refused('Synthetic independent helper observation unavailable')
        return {**copy.deepcopy(self.helper), 'operation': op, 'observed': self.now}


class IsolatedBridge:
    def __init__(self, registry, world):
        if type(registry) is not fence.Registry or type(world) is not FixtureWorld:
            raise fence.Refused('Isolated registry and fixture world required')
        self.registry, self.world = registry, world

    def manager_admission(self, op):
        parent = self.world.observe('parent')
        # Commit intent and receipt before ANY synthetic worker side effect.
        state = self.registry.reserve_start(op, parent, self.world.now)
        intent = state['startup']
        return {'operation': op, 'nonce': intent['nonce'], 'parent': parent}

    def create_and_bind_worker(self, ticket):
        parent = self.world.observe('parent')
        def claim(state, db):
            intent = state['startup']
            if (not intent or intent['phase'] != 'PENDING' or intent['worker'] is not None
                    or intent['operation'] != ticket['operation'] or intent['nonce'] != ticket['nonce']
                    or intent['parent'] != parent or ticket['parent'] != intent['parent']
                    or not intent['issued'] <= self.world.now < intent['expires']):
                raise fence.Refused('Independent parent or startup ticket mismatch')
            # Durable one-use claim prevents concurrent/restarted duplicate creates.
            # Colon is excluded from operation(), so this namespace cannot collide.
            db.execute('INSERT INTO used VALUES (?)', ('bridge-worker-create:'+ticket['operation'],))
            return {'type': 'SYNTHETIC_WORKER_CREATE_CLAIMED'}
        self.registry._change(claim)
        worker = self.world.create_worker()
        # A changed identity after creation leaves durable PENDING, never reset.
        if worker != self.world.observe('worker'):
            raise fence.Refused('Worker identity changed')
        self.registry.bind_worker(ticket['operation'], ticket['nonce'], ticket['parent'], worker, self.world.now)
        return worker

    def worker_admission(self, ticket, claimed):
        actual = self.world.observe('worker')
        if claimed != actual:
            raise fence.Refused('Independent worker observation mismatch')
        state = self.registry.admit_worker(ticket['operation'], ticket['nonce'], actual, self.world.now)
        # No registry mutex is retained while performing the synthetic action.
        self.world.dependencies()
        return state

    def inspection_admission(self, op, *, approved=False):
        if self.world.processes.get('active') is not None:
            raise fence.Refused('Synthetic writer active')
        return self.registry.begin_inspection(op, {'observed': self.world.now, 'stopped': True,
                                                   'no_pending': True}, self.world.now, approved=approved)

    def bind_helper(self, op, helper):
        return self.registry.bind_helper(op, helper)

    def recover(self, op, authority, grant):
        # Caller-supplied exit claims cannot replace the independent fixture table.
        proof = self.world.exit_proof(op)
        return self.registry.recover_inspection(authority, grant, proof, self.world.now)
