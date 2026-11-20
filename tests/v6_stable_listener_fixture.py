"""Single stable disposable socket with native bind/listen/lifetime witnesses."""

import http.server
import json
import os
import queue
import secrets
import socket
import sys
import threading
import time
from pathlib import Path

repo = Path(__file__).resolve().parents[1]
if len(sys.argv) != 3 or sys.argv[1] != "--disposable-stable-listener-only":
    raise SystemExit("EXPLICIT_STABLE_LISTENER_FIXTURE_ONLY")
root = Path(sys.argv[2]).absolute()
if (
    root.parent != repo / "logs/diagnostics"
    or not root.name.startswith("qd-v6-integrated-rehearsal-")
    or any(p.is_symlink() or p.is_junction() for p in [root, *root.parents])
):
    raise SystemExit("CONFINED_OWNED_STABLE_LISTENER_ROOT_REQUIRED")
sys.path.insert(0, str(repo))
from scripts.observation_runtime.disposable_host_owner import observe_pid

deadline = time.monotonic() + 180
commands = queue.Queue()


def event(name, **details):
    row = {
        "event": name,
        "monotonic_ns": time.perf_counter_ns(),
        "utc_ns": time.time_ns(),
        "pid": os.getpid(),
        **details,
    }
    with (root / "stable-listener-events.jsonl").open("a") as stream:
        stream.write(json.dumps(row) + "\n")
    return row


def reader():
    for line in sys.stdin:
        commands.put(line.strip())
    commands.put("EOF")


def command():
    return commands.get(timeout=max(0.01, deadline - time.monotonic()))


threading.Thread(target=reader, daemon=True).start()
seed = socket.socket()
seed.bind(("127.0.0.1", 0))
seed.listen(1)
print(
    json.dumps({"seed_port": seed.getsockname()[1], "fixture_only": True}), flush=True
)
try:
    if command() != "RELEASE_SEED":
        raise SystemExit(0)
finally:
    seed.close()
print(json.dumps({"seed_closed": True}), flush=True)
if command() != "BEGIN":
    raise SystemExit(0)
host = secrets.token_hex(16)
body = f"ATLAS STABLE DISPOSABLE FIXTURE {host} synthetic test evidence; NO PROVIDERS OR TRADING".encode()


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.server.requests += 1
        event("HTTP_REQUEST", path=self.path, attempt=self.server.requests)
        admitted = self.server.requests <= 96
        data = body if admitted else b"REQUEST_BUDGET_REFUSED"
        self.send_response(200 if admitted else 429)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(data)
        event("HTTP_RESPONSE_WRITTEN", status=200 if admitted else 429, size=len(data))

    def log_message(self, *_):
        pass


class Server(http.server.HTTPServer):
    def server_bind(self):
        event("BIND_BEGIN", requested_endpoint=self.server_address)
        super().server_bind()
        event(
            "BIND_END",
            endpoint=self.socket.getsockname(),
            socket=self.socket.fileno(),
            acceptconn=self.socket.getsockopt(socket.SOL_SOCKET, socket.SO_ACCEPTCONN),
        )

    def server_activate(self):
        event("LISTEN_BEGIN", socket=self.socket.fileno())
        super().server_activate()
        assert self.socket.getsockopt(socket.SOL_SOCKET, socket.SO_ACCEPTCONN) == 1
        event(
            "LISTEN_END",
            endpoint=self.socket.getsockname(),
            socket=self.socket.fileno(),
            acceptconn=1,
        )


server = Server(("127.0.0.1", 0), Handler)
server.requests = 0
thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01})
thread.start()
identity = observe_pid(os.getpid())


def witness():
    row = {
        **identity,
        "socket": server.socket.fileno(),
        "family": 4,
        "address": server.socket.getsockname()[0],
        "port": server.server_port,
        "acceptconn": server.socket.getsockopt(socket.SOL_SOCKET, socket.SO_ACCEPTCONN),
        "closed": False,
        "observed_ns": time.perf_counter_ns(),
    }
    event("LIVE_WITNESS", **{k: v for k, v in row.items() if k != "pid"})
    return row


ready = {
    "mode": "DISPOSABLE_CONTROL_FIXTURE",
    "host_id": host,
    "pid": os.getpid(),
    "image": sys.executable,
    "release": "SYNTHETIC_FIXTURE",
    "head": "f" * 64,
    "url": f"http://127.0.0.1:{server.server_port}/",
    "providers": False,
    "financial_writers": False,
    "trading": False,
    "automatic_startup": False,
    "socket_witness": witness(),
}
event("READY", url=ready["url"])
print(json.dumps(ready), flush=True)
request = None
try:
    while True:
        request = command()
        if request == "WITNESS":
            print(json.dumps(witness()), flush=True)
        else:
            break
finally:
    start = time.perf_counter()
    event(
        "SHUTDOWN_BEGIN",
        socket=server.socket.fileno(),
        acceptconn=server.socket.getsockopt(socket.SOL_SOCKET, socket.SO_ACCEPTCONN),
    )
    server.shutdown()
    server.server_close()
    thread.join(timeout=3)
    assert not thread.is_alive() and server.fileno() == -1
    event("SOCKET_CLOSED", thread_closed=True, socket=server.fileno())
if request == "STOP " + host:
    print(
        json.dumps(
            {
                "closed": True,
                "financial_actions": 0,
                "seconds": time.perf_counter() - start,
            }
        ),
        flush=True,
    )
    command()  # Original owner's EOF; never NEXT or automatic restart.
