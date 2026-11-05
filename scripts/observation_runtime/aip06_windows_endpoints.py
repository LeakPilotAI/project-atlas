"""Concrete private anonymous-pipe endpoint construction for guarded sessions.

No native calls at import/construction and no launcher or grant. prepare is
called only inside the existing suspended-launch guard. Every created pipe end
uses the session's pre-reserved allocator; only four child pipe ends and the
original parent/Job handles are inherited. No sockets or named-pipe discovery.
"""

import copy
import ntpath
import struct

from app.services.paper_financial_replay import body, digest, strict
from scripts.observation_runtime.aip06_harness import BASE, SCOPE_HASH, need
from scripts.observation_runtime.aip06_ipc import Broker, Channel, MAX_IPC_NS
from scripts.observation_runtime.aip06_pipe_transport import CreditedPipeEndpoint
from scripts.observation_runtime.aip06_remote_handles import RetainedPeerHandles
from scripts.observation_runtime.aip06_session_io import ParentFrames


DESCRIPTOR = "AIP06_INHERITED_PIPE_DESCRIPTOR_V1"
MAX_BOOTSTRAP = 65536


class WindowsChildEndpoints:
    resource_kinds = ("pipe",) * 8
    requires_aggregate = True

    def __init__(
        self, *, pipe_calls, clock_ns, output, objects=None, descendant_factory=None
    ):
        self.pipes, self.clock, self.output = pipe_calls, clock_ns, output
        self.objects, self.descendant_factory = objects, descendant_factory
        self.plans, self.state = {}, {}

    def command(self, argv, options, *, nonce):
        need(
            type(nonce) is str
            and len(nonce) == 32
            and set(nonce) <= set("0123456789abcdef")
            and nonce not in self.plans,
            "ONE_EXACT_PIPE_BOOTSTRAP_NONCE",
        )
        need(
            type(argv) is tuple
            and len(argv) >= 3
            and argv[0].startswith("D:\\")
            and argv[1] == "-B",
            "EXACT_PIPE_TARGET_COMMAND",
        )
        self.plans[nonce] = (argv, copy.deepcopy(options))
        return (
            argv[0],
            "-B",
            "-m",
            "scripts.observation_runtime.aip06_child_bootstrap",
            "--inherited-session",
            nonce,
        )

    def prepare(self, child, port):
        nonce = child.plan["request"].nonce
        need(
            nonce in self.plans
            and nonce not in self.state
            and self.plans[nonce] == (child.argv, child.options),
            "EXACT_PIPE_SESSION_PLAN",
        )
        entry = ntpath.join(
            ntpath.dirname(ntpath.dirname(BASE)),
            "scripts",
            "observation_runtime",
            "aip06_child_bootstrap.py",
        )
        port.controller.verify_source(entry)
        pairs = []
        # Record each successfully allocated pair immediately; a later failure
        # leaves the already owned handles in Session.native for guarded abort.
        for _ in range(4):
            pairs.append(port.allocate(child, ("pipe", "pipe"), port.calls.pipe))
        data_in, data_out, credit_in, credit_out = pairs
        capacities = {
            "data": min(
                self.pipes.capacity(data_in[0]), self.pipes.capacity(data_out[0])
            ),
            "credit": min(
                self.pipes.capacity(credit_in[0]), self.pipes.capacity(credit_out[0])
            ),
        }
        need(
            all(type(v) is int and 4096 <= v <= 65536 for v in capacities.values()),
            "NATIVE_PIPE_BUFFER_BOUND",
        )
        parent = (data_out[0], data_in[1], credit_in[0], credit_out[1])
        peer = (data_in[0], data_out[1], credit_out[0], credit_in[1])
        need(len(set(parent + peer)) == 8, "DISTINCT_PRIVATE_PIPE_ENDS")
        self.state[nonce] = {
            "port": port,
            "child": child,
            "parent": parent,
            "peer": peer,
            "capacities": capacities,
            "channel": None,
            "transport": None,
            "verifier": None,
            "closed": False,
        }
        env = copy.deepcopy(child.options.get("env", {}))
        need(
            not any(k.startswith("ATLAS_AIP06_INHERITED_") for k in env),
            "NO_INHERITED_DESCRIPTOR_OVERRIDE",
        )
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["ATLAS_AIP06_INHERITED_HANDLES"] = ",".join(
            str(h) for h in peer + (child.parent_handle, child.job)
        )
        inherited = list(peer) + [child.parent_handle, child.job]
        return {
            "environment": env,
            "cwd": ntpath.dirname(ntpath.dirname(BASE)),
            "inherit_handles": inherited,
            "stdin": peer[0],
            "stdout": peer[1],
            "stderr": peer[1],
        }

    def _state(self, child):
        state = self.state.get(child.plan["request"].nonce)
        need(
            state is not None and state["child"] is child and not state["closed"],
            "KNOWN_OPEN_NATIVE_PIPE_SESSION",
        )
        return state

    def channel(self, child, observed):
        state = self._state(child)
        need(state["channel"] is None, "PIPE_CHANNEL_ONCE_ONLY")
        port = state["port"]
        parent = port.resources.state["owners"][port.guard.owner]
        wire = {
            "scope": SCOPE_HASH,
            "session": port.controller.profile["session"],
            "nonce": child.plan["request"].nonce,
            "parent": strict(body(parent)),
            "child": strict(body(observed)),
            "job": child.job,
            "launch": strict(body(observed)),
        }

        def verify(binding):
            need(body(binding) == body(wire), "PIPE_CURRENT_BINDING_CONFLICT")
            need(
                body(child.observer.observe(child.parent_handle)) == body(parent)
                and body(child.observer.observe(child.launch_handle)) == body(observed)
                and child.observer.members() == {observed["pid"]},
                "PIPE_ORIGINAL_PARENT_CHILD_OR_JOB_CHANGED",
            )

        r, w, cr, cw = state["parent"]
        transport = CreditedPipeEndpoint(
            api=self.pipes,
            read_handle=r,
            write_handle=w,
            credit_read=cr,
            credit_write=cw,
            clock_ns=self.clock,
            verify_peer=verify,
            session_tag=bytes.fromhex(wire["nonce"]),
            capacities=state["capacities"],
        )
        descriptor = {
            "schema": DESCRIPTOR,
            "binding": wire,
            "accounts": port.controller.profile["accounts"],
            "capacities": state["capacities"],
            "handles": list(state["peer"]) + [child.parent_handle, child.job],
            "argv": list(child.argv),
            "source_pins": port.controller.profile["source_pins"],
            "images": port.controller.profile["images"],
        }
        raw = body(descriptor).encode()
        need(0 < len(raw) <= MAX_BOOTSTRAP, "INHERITED_DESCRIPTOR_CAPACITY")
        transport.verify_peer(wire)
        transport.write_all(
            struct.pack("!I", len(raw)) + raw, deadline_ns=self.clock() + MAX_IPC_NS
        )
        channel = Channel(
            transport,
            binding=wire,
            clock_ns=self.clock,
            account_scope=descriptor["accounts"],
            role="PARENT",
        )
        frames = ParentFrames(channel, broker=None, output=self.output)
        state.update(
            channel=frames, transport=transport, descriptor_digest=digest(descriptor)
        )
        return frames

    def receive_guard_receipt(self, child, *, snapshot, deadline_ns):
        state = self._state(child)
        need(
            child.binding is not None
            and state["channel"] is child.channel
            and state["verifier"] is None,
            "RETAINED_PEER_BEFORE_RESOURCE_BROKER",
        )
        port = state["port"]

        def path_allowed(path):
            if path in port.controller.profile["source_pins"]:
                return port.controller.verify_source(path)
            if ntpath.normcase(path) in port.controller.profile["images"]:
                pin = port.controller.profile["images"][ntpath.normcase(path)]
                need(
                    ntpath.normcase(path) == ntpath.normcase(port.executable)
                    and port.files.describe(child.image_handle)["id"]
                    == list(pin["file_id"]),
                    "REMOTE_IMAGE_REQUIRES_RETAINED_PARENT_LEASE",
                )
                return pin
            port.io.allowed(path)

        verifier = RetainedPeerHandles(
            binding=child.binding,
            resources=port.resources,
            calls=port.calls,
            files=port.files,
            allocations=port.allocations_port,
            allowed_path=path_allowed,
            objects=self.objects,
            sid=getattr(port.io, "sid", None),
        )
        if self.descendant_factory is not None:
            verifier.descendants = self.descendant_factory(verifier)
        broker = Broker(
            resources=port.resources,
            channel=child.channel.channel,
            peer_owner=digest(child.binding.runtime),
            verifier=verifier,
            output=self.output,
            clock_ns=self.clock,
        )
        child.channel.broker = broker
        state["verifier"] = verifier
        receipt = child.channel.receive(deadline_ns=deadline_ns, expected_kind="ACK")[
            "payload"
        ]
        need(
            receipt
            == {
                "scope": SCOPE_HASH,
                "nonce": child.plan["request"].nonce,
                "owner": digest(child.binding.runtime),
                "reservation_head": snapshot["head"],
                "guarded": True,
            },
            "PIPE_CHILD_GUARD_ACK_CONFLICT",
        )
        return receipt

    def communicate(self, child, value, *, deadline_ns, maximum_bytes):
        self._state(child)
        if value is not None:
            if type(value) in (str, bytes):
                value = strict(value.decode() if type(value) is bytes else value)
            child.channel.send(
                "INPUT", value, deadline_ns=min(deadline_ns, self.clock() + MAX_IPC_NS)
            )
        frame = child.channel.receive(deadline_ns=deadline_ns, expected_kind="EXIT")[
            "payload"
        ]
        need(
            type(frame) is dict
            and set(frame) == {"target", "result"}
            and frame["target"] == child.argv[2],
            "PIPE_EXIT_TARGET_CONFLICT",
        )
        lines = {"stdout": [], "stderr": []}
        for record in child.channel.saved_outputs:
            item = record["payload"]
            if type(item) is dict and item.get("schema") == "AIP06_CHILD_OUTPUT_V1":
                need(
                    item.get("owner") == digest(child.binding.runtime)
                    and item.get("stream") in lines,
                    "PIPE_OUTPUT_OWNER_OR_STREAM",
                )
                lines[item["stream"]].append(item["text"] + "\n")
        result = tuple("".join(lines[k]) for k in ("stdout", "stderr"))
        need(
            sum(len(v.encode()) for v in result) <= maximum_bytes,
            "PIPE_COMMUNICATION_OUTPUT_CAPACITY",
        )
        return result

    def close(self, child, *, deadline_ns):
        state = self.state.get(child.plan["request"].nonce)
        if state is None:
            return  # Partial prepare allocations remain in Session.native.
        need(self.clock() < deadline_ns, "PIPE_CLOSE_DEADLINE")
        port = state["port"]
        if child.launch_handle is not None:
            life = port.calls.lifecycle(child.launch_handle)
            need(
                child.creation_native is not None
                and life["pid"] == child.creation_native["pid"]
                and life["created"] == child.creation_native["created"]
                and life["exited"],
                "PIPE_CLOSE_REQUIRES_ORIGINAL_CHILD_EXIT",
            )
        if state["verifier"] is not None:
            state["verifier"].dispose_after_exit(deadline_ns=deadline_ns)
        # Session.close_owned_handles owns the actual eight endpoint handles.
        # Do not double-close or fabricate a release inside the protocol.
        state["closed"] = True


class InheritedChannel:
    """Decode only original inherited handles, then independently verify them.

    The environment integers are locators, never authority. A child-side native
    observer must cross-check the actual current process, inherited parent and
    Job before any Channel is accepted. Missing observer/escrow/guard wiring
    must still refuse at ChildBootstrap.main; this decoder grants no execution.
    """

    @staticmethod
    def open(*, handles, nonce, pipes, identity, clock_ns):
        need(
            type(handles) is tuple
            and len(handles) == 6
            and len(set(handles)) == 6
            and all(type(h) is int and h > 0 for h in handles)
            and type(nonce) is str
            and len(nonce) == 32
            and set(nonce) <= set("0123456789abcdef"),
            "EXACT_INHERITED_HANDLE_LOCATORS",
        )
        r, w, cr, cw, parent, job = handles
        capacities = {"data": pipes.capacity(r), "credit": pipes.capacity(cr)}
        transport = CreditedPipeEndpoint(
            api=pipes,
            read_handle=r,
            write_handle=w,
            credit_read=cr,
            credit_write=cw,
            clock_ns=clock_ns,
            verify_peer=identity.verify,
            session_tag=bytes.fromhex(nonce),
            capacities=capacities,
        )
        end = clock_ns() + MAX_IPC_NS
        count = struct.unpack("!I", transport.read_exact(4, deadline_ns=end))[0]
        need(0 < count <= MAX_BOOTSTRAP, "INHERITED_DESCRIPTOR_CAPACITY")
        raw = transport.read_exact(count, deadline_ns=end)
        value = strict(raw.decode())
        need(
            body(value).encode() == raw
            and set(value)
            == {
                "schema",
                "binding",
                "accounts",
                "capacities",
                "handles",
                "argv",
                "source_pins",
                "images",
            }
            and value["schema"] == DESCRIPTOR
            and value["handles"] == list(handles)
            and value["binding"]["nonce"] == nonce
            and value["binding"]["job"] == job
            and value["capacities"] == capacities,
            "INHERITED_DESCRIPTOR_SCOPE_OR_HANDLES_CONFLICT",
        )
        need(
            identity.observer.parent == parent and identity.observer.job == job,
            "INHERITED_OBSERVER_ORIGINAL_HANDLES",
        )
        identity.verify(value["binding"])
        return Channel(
            transport,
            binding=value["binding"],
            clock_ns=clock_ns,
            account_scope=value["accounts"],
            role="CHILD",
        ), value
