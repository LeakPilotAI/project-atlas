"""Fenced child bootstrap; no CLI, environment-based admission or default runner.

The launch port must supply original inherited handles and a private Channel.
Nothing executes a target merely because JSON names a PID, Job or fixture root.
This module is inert at import. Native execution requires a separate grant.
"""

import copy
import ntpath

from app.services.paper_financial_replay import body, digest

from scripts.observation_runtime.aip06_fixture_guard import FixtureGuard
from scripts.observation_runtime.aip06_harness import ROOTS, SCOPE_HASH, need
from scripts.observation_runtime.aip06_ipc import MAX_IPC_NS, RemoteResources


class InheritedIdentity:
    """Native/CIM observations of inherited handles, never OpenProcess(PID).

    The parent independently constructs RetainedLaunchBinding before BIND.
    These child-side checks supplement that parent capability; they do not
    manufacture it or attest that a parent has retained a handle merely from
    a scalar handle value in a message. Redirector topologies remain refused.
    """

    def __init__(self, *, observer, current_handle, parent_handle, job_handle):
        need(
            all(
                type(h) is int and h > 0
                for h in (current_handle, parent_handle, job_handle)
            ),
            "INHERITED_ORIGINAL_HANDLES_REQUIRED",
        )
        self.observer, self.current, self.parent, self.job = (
            observer,
            current_handle,
            parent_handle,
            job_handle,
        )
        need(
            observer.job == job_handle and observer.parent == parent_handle,
            "INHERITED_OBSERVER_HANDLE_BINDING",
        )
        self.descendants = None
        self.attested = None
        self.clock = None

    def capture(self, binding):
        child=self.observer.observe(self.current)
        parent=self.observer.observe(self.parent)
        need(body(child)==body(binding['child']) and body(parent)==body(binding['parent'])
             and child['parent_pid']==parent['pid'],'INHERITED_CAPTURE_IDENTITY_CONFLICT')
        return child

    def admit_frame(self, binding, frame):
        if frame['kind']=='REPLY':
            value=frame['payload'].get('ownership')
            if value is not None:
                from scripts.observation_runtime.aip06_graph_evidence import validate_graph_evidence
                need(callable(self.clock),'INHERITED_GRAPH_CLOCK_REQUIRED')
                validate_graph_evidence(value,binding,self.clock())
                self.attested=value
            else:
                need(self.attested is None,'INHERITED_GRAPH_RECEIPT_MISSING')
        return self.verify(binding)

    def verify(self, binding):
        child = self.observer.observe(self.current)
        parent = self.observer.observe(self.parent)
        rows = [] if self.descendants is None else self.descendants()
        need(
            body(child) == body(binding["child"])
            and body(parent) == body(binding["parent"])
            and child["parent_pid"] == parent["pid"]
            and self.observer.members() == {child["pid"]} | {r['pid'] for r in rows},
            "INHERITED_ANCESTRY_OR_JOB_CONFLICT",
        )
        return child


class ChildBootstrap:
    """HELLO -> verified BIND -> installed guard -> receipt -> RELEASE.

    A guard factory supplies concrete NativeIO/RemoteResources process ports.
    No target runs until that factory and the native launch port are connected.
    A missing factory, malformed receipt, timeout or failed check latches refusal.
    EXIT is informational, never a financial ACK, drain proof or clean-Stop proof.
    """

    def __init__(
        self,
        *,
        channel,
        identity,
        target,
        source_pins,
        verify_source,
        guard_factory,
        clock_ns,
        role='acceptance_worker',
        controller_command=None,
        controller_targets=None,
    ):
        need(
            channel.role == "CHILD"
            and type(target) is str
            and type(source_pins) is dict
            and target in source_pins
            and source_pins
            and callable(verify_source)
            and callable(guard_factory),
            "CHILD_EXACT_PINNED_TARGET_REQUIRED",
        )
        need(
            all(
                type(p) is str
                and ntpath.isabs(p)
                and p.startswith("D:\\")
                and type(h) is str
                and len(h) == 64
                and set(h) <= set("0123456789abcdef")
                for p, h in source_pins.items()
            ),
            "CHILD_SOURCE_PIN_FORMAT",
        )
        self.channel, self.identity, self.target = channel, identity, target
        self.pins, self.verify_source, self.factory = (
            copy.deepcopy(source_pins),
            verify_source,
            guard_factory,
        )
        self.clock, self.failed, self.state = clock_ns, False, "NEW"
        self.guard, self.receipt = None, None
        need(role in ('acceptance_worker', 'acceptance_supervisor'), 'EXACT_CHILD_LAUNCH_ROLE')
        if role == 'acceptance_supervisor':
            from scripts.observation_runtime.aip06_harness import BASE
            legacy = ntpath.join(ntpath.dirname(ntpath.dirname(BASE)), 'scripts',
                                 'observation_runtime', 'aip06_legacy_entry.py')
            if target != legacy:
                from scripts.observation_runtime.aip06_controller_contract import ENTRY, CONTRACT, controller_argv
                need(target == ENTRY and CONTRACT in source_pins, 'SUPERVISOR_ONLY_PINNED_LEGACY_TARGET')
                controller_argv(controller_command, controller_targets)
        self.role = role

    def _deadline(self):
        return self.clock() + MAX_IPC_NS

    def prepare(self):
        need(self.state == "NEW" and not self.failed, "CHILD_BOOTSTRAP_ONCE_ONLY")
        self.failed = True
        child = self.identity.verify(self.channel.binding)
        # Return actual file identity + digest, not a True verification callback.
        for path, expected in self.pins.items():
            observed = self.verify_source(path)
            need(
                type(observed) is dict
                and set(observed) == {"path", "file_id", "sha256", "closed"}
                and observed["path"] == path
                and type(observed["file_id"]) in (list, tuple)
                and len(observed["file_id"]) == 3
                and observed["sha256"] == expected
                and observed["closed"] is True,
                "CHILD_SOURCE_INTEGRITY_OR_CLOSE",
            )
        hello = {
            "pid": child["pid"],
            "nonce": self.channel.binding["nonce"],
            "role": self.role,
        }
        self.channel.send("HELLO", hello, deadline_ns=self._deadline())
        message = self.channel.receive(
            deadline_ns=self._deadline(), expected_kind="BIND"
        )["payload"]
        need(
            type(message) is dict
            and set(message) == {"snapshot", "roots", "source_pins", "target", "nonce"}
            and message["roots"] == ROOTS
            and message["source_pins"] == self.pins
            and message["target"] == self.target
            and message["nonce"] == hello["nonce"],
            "CHILD_BIND_SCOPE_OR_SOURCE_CONFLICT",
        )
        snapshot = message["snapshot"]
        owner = digest(child)
        need(
            snapshot["scope"] == SCOPE_HASH
            and snapshot["state"]["owners"].get(owner) == self.channel.binding["child"]
            and snapshot["state"]["mode"] == "WORK",
            "CHILD_CURRENT_PARENT_LEDGER_REQUIRED",
        )
        self._rooted_parent(snapshot)
        guard = self.factory(
            channel=self.channel, owner=owner, initial=copy.deepcopy(snapshot)
        )
        need(
            type(guard) is FixtureGuard
            and type(guard.resources) is RemoteResources
            and guard.resources.channel is self.channel
            and guard.owner == owner
            and guard.resources.head == snapshot["head"],
            "CHILD_SHARED_GUARD_FACTORY_BINDING",
        )
        self.identity.verify(self.channel.binding)
        guard.check()  # Actual parent ledger round trip, not local JSON alone.
        self.guard = guard
        guard.launch_role = self.role
        if hasattr(guard,'bootstrap_export'):
            self.channel.send('BOOTSTRAP',guard.bootstrap_export(),deadline_ns=self._deadline())
        self.receipt = {
            "scope": SCOPE_HASH,
            "nonce": hello["nonce"],
            "owner": owner,
            "reservation_head": snapshot["head"],
            "guarded": True,
        }
        self.channel.send("ACK", self.receipt, deadline_ns=self._deadline())
        self.state, self.failed = "BOUND", False
        return copy.deepcopy(self.receipt)

    def _rooted_parent(self, snapshot):
        """Private bound identities plus the single authenticated root ledger.

        Every non-root ancestor must have its own still-open process slot; a
        registered name/PID alone is insufficient. Native immediate-parent and
        subtree Job evidence is independently checked by InheritedIdentity and
        by the root retained descendant graph before BIND and subsequent RPCs.
        """
        state = snapshot['state']
        parent = self.channel.binding['parent']
        owners = state['owners']
        need(body(owners.get(digest(parent))) == body(parent), 'CHILD_PARENT_OWNER_MISSING')
        by_pid = {v['pid']: (k, v) for k, v in owners.items()}
        need(len(by_pid) == len(owners), 'CHILD_ANCESTOR_PID_ALIAS')
        cursor, seen = digest(parent), set()
        while cursor != state['controller']:
            need(cursor not in seen and cursor in owners, 'CHILD_ROOT_ANCESTRY_CYCLE')
            seen.add(cursor)
            row = owners[cursor]
            slots = [r for r in state['resources'].values()
                     if r == {'owner': cursor, 'kind': 'process', 'closed': False}]
            need(len(slots) == 1 and row['parent_pid'] in by_pid,
                 'CHILD_ROOT_ANCESTOR_PROCESS_SLOT')
            cursor, ancestor = by_pid[row['parent_pid']]
            need(ancestor['created'] <= row['created'], 'CHILD_ANCESTOR_BIRTH_ORDER')
        need(cursor in owners and cursor not in seen, 'CHILD_ROOT_CONTROLLER_MISSING')

    def run(self, runner):
        need(
            self.state == "BOUND" and not self.failed and callable(runner),
            "BOUND_CHILD_TARGET_REQUIRED",
        )
        self.failed = True
        release = self.channel.receive(
            deadline_ns=self._deadline(), expected_kind="RELEASE"
        )["payload"]
        need(
            release
            == {
                "receipt": digest(self.receipt),
                "target": self.target,
                "sha256": self.pins[self.target],
            },
            "CHILD_RELEASE_RECEIPT_OR_TARGET_CONFLICT",
        )
        self.identity.verify(self.channel.binding)
        self.guard.check()
        self.state = "RUNNING"
        with self.guard.installed():
            port = self.guard.processes
            if hasattr(port, "output_context"):
                with port.output_context():
                    result = runner(self.target)
            else:
                result = runner(self.target)
            if hasattr(self.guard.io,'close_cache'):self.guard.io.close_cache()
        self.state = "EXITED"
        self.channel.send(
            "EXIT",
            {"target": self.target, "result": result},
            deadline_ns=self._deadline(),
        )
        self.failed = False
        return result


def main(argv=None, environ=None, **options):
    from scripts.observation_runtime.aip06_child_entry import main as inherited_main
    return inherited_main(argv,environ,**options)


if __name__ == "__main__":
    main()
