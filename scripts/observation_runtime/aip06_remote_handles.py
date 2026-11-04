"""Independent remote handle continuity over an original retained process.

The parent duplicates from the verified child creation handle, never a PID.
The child's close declaration is only a request for independent observation.
"""

from app.services.paper_financial_replay import body, digest
from scripts.observation_runtime.aip06_harness import need
from scripts.observation_runtime.launch_ownership import RetainedLaunchBinding


class RemoteHandleProofs:
    def __init__(self, owner):
        self.owner, self.handles = owner, {}

    def bind(self, key, handle):
        need(
            type(handle) is int
            and handle > 0
            and (key not in self.handles or self.handles[key] == handle),
            "REMOTE_ORIGINAL_HANDLE_CONFLICT",
        )
        self.handles[key] = handle
        return {"owner": self.owner, "key": key, "handle": handle}

    def release(self, owner, key, observer):
        need(
            owner == self.owner
            and key in self.handles
            and observer.closed(owner, key) is True,
            "REMOTE_RELEASE_REQUIRES_REGISTERED_ORIGINAL",
        )
        return {"owner": owner, "key": key, "handle": self.handles[key]}

    def child(self, *args):
        raise ValueError("REMOTE_DESCENDANT_ORIGINAL_HANDLE_TRANSFER_NOT_BOUND")


class RetainedPeerHandles:
    """Keep a charged parent duplicate until the remote close is verified.

    A reused remote integer which is still valid is ambiguous and refuses,
    even if it now refers to a different object. No name/PID-based adoption.
    A failed registration retains its allocated duplicate for owned cleanup.
    """

    def __init__(self, *, binding, resources, calls, files, allocations, allowed_path):
        need(type(binding) is RetainedLaunchBinding, "ORIGINAL_RETAINED_PEER_REQUIRED")
        self.binding, self.resources, self.calls = binding, resources, calls
        self.files, self.allocations, self.allowed_path = (
            files,
            allocations,
            allowed_path,
        )
        self.owner = digest(binding.runtime)
        self.live = {}
        self.done = set()
        self.failed = False

    def verify_peer(self, wire):
        need(
            not self.failed
            and body(wire["child"]) == body(self.binding.runtime)
            and body(wire["parent"]) == body(self.binding.parent),
            "REMOTE_WIRE_NATIVE_PEER_CONFLICT",
        )
        self.binding.verify()

    def bind_native_handle(self, wire, key, handle):
        self.verify_peer(wire)
        row = self.resources.state["resources"].get(key)
        need(
            type(handle) is int
            and handle > 0
            and row is not None
            and row["owner"] == self.owner
            and not row["closed"],
            "REMOTE_HANDLE_PRIOR_RESERVATION",
        )
        if key in self.live:
            need(self.live[key]["remote"] == handle, "REMOTE_HANDLE_REBIND")
            return
        ticket = self.allocations.reserve("remote-retained:" + key, "handle")
        duplicate = self.calls.duplicate(self.binding.runtime_handle, handle)
        self.live[key] = {
            "remote": handle,
            "local": duplicate,
            "ticket": ticket,
            "verified": False,
        }
        try:
            native = self.files.describe(duplicate)
            path = self.files.final_path(duplicate)
            self.allowed_path(path)
            need(
                not native["reparse"]
                and native["links"] == 1
                and native["kind"] in ("file", "directory"),
                "REMOTE_NATIVE_FILE_IDENTITY",
            )
            self.binding.verify()
            self.live[key].update(verified=True, identity=native["id"], path=path)
        except BaseException:
            self.failed = True
            raise

    def release_observer(self, wire, key, proof):
        self.verify_peer(wire)
        item = self.live.get(key)
        need(
            item is not None
            and item["verified"]
            and proof == {"owner": self.owner, "key": key, "handle": item["remote"]},
            "REMOTE_RELEASE_IDENTITY",
        )
        ticket = self.allocations.reserve("remote-close-probe:" + key, "handle")
        try:
            probe = self.calls.duplicate(self.binding.runtime_handle, item["remote"])
        except OSError as exc:
            need(getattr(exc, "winerror", None) == 6, "REMOTE_CLOSE_ENUMERATION_FAILED")
            # The API returned no handle. The transient reservation closes only
            # for ERROR_INVALID_HANDLE from this exact retained peer operation.
            self.allocations.release(ticket)
        else:
            self.calls.close(probe)
            need(self.calls.closed(probe), "REMOTE_PROBE_HANDLE_NOT_CLOSED")
            self.allocations.release(ticket)
            raise ValueError("REMOTE_HANDLE_LIVE_OR_REUSED")
        self.calls.close(item["local"])
        need(self.calls.closed(item["local"]), "PARENT_REMOTE_DUPLICATE_NOT_CLOSED")
        self.allocations.release(item["ticket"])
        del self.live[key]
        self.done.add(key)
        return self

    def closed(self, owner, key):
        return owner == self.owner and key in self.done

    def child_binding(self, *args):
        raise ValueError("REMOTE_DESCENDANT_TRANSFER_NOT_BOUND")

    def dispose_after_exit(self, *, deadline_ns):
        """Kernel exit releases child handles; never a financial drain ACK."""
        parent = self.binding.api.observe(self.binding.parent_handle)
        life = self.binding.api.lifecycle(self.binding.runtime_handle)
        need(
            parent == self.binding.parent
            and life["pid"] == self.binding.runtime["pid"]
            and life["created"] == self.binding.runtime["created"]
            and life["exited"] is True
            and self.binding.api.members() == set(),
            "REMOTE_RELEASE_REQUIRES_ORIGINAL_PEER_EXIT",
        )
        for key, item in tuple(self.live.items()):
            need(self.resources.clock() < deadline_ns, "REMOTE_RELEASE_DEADLINE")
            self.calls.close(item["local"])
            need(self.calls.closed(item["local"]), "REMOTE_EXIT_DUPLICATE_STILL_OPEN")
            self.allocations.release(item["ticket"])
            del self.live[key]
            self.done.add(key)
            self.resources.close(self.owner, key, observer=self)
        return {
            "peer": self.owner,
            "exit_code": life["exit_code"],
            "release_only": True,
            "financial_ack": False,
        }
