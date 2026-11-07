"""One minimal synthetic browser witness, not the integrated rehearsal or Atlas."""

import http.server
import json
import os
import secrets
import sys
import threading
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if len(sys.argv) != 3 or sys.argv[1] != "--disposable-browser-only":
    raise SystemExit("EXPLICIT_DISPOSABLE_BROWSER_ONLY")
root = Path(sys.argv[2]).absolute()
if (
    root.parent != REPO / "logs/diagnostics"
    or not root.name.startswith("qd-v6-browser-prerequisite-")
    or root.exists()
    or any(p.is_symlink() or p.is_junction() for p in [root, *root.parents])
):
    raise SystemExit("FRESH_CONFINED_BROWSER_ROOT_REQUIRED")
root.mkdir()
sys.path[:0] = [str(REPO), str(REPO / "backend")]
from scripts.observation_runtime.acceptance_http_probe import probe
from scripts.observation_runtime.disposable_host_owner import observe_pid
from scripts.observation_runtime.installed_acceptance_handoff import BrowserWindow

host_id = secrets.token_hex(16)
body = (
    "<!doctype html><html><head><title>Atlas browser prerequisite</title></head><body>"
    "<h1>ATLAS HARNESS V3 DISPOSABLE FIXTURE</h1><p>Cycle 1</p>"
    f"<p>Host {host_id}</p><h2>Selected PAPER account: UNAVAILABLE</h2>"
    "<p>NO PROVIDERS. NO TRADING.</p><p>synthetic test evidence</p>"
    "<p>Browser prerequisite only. No integrated rehearsal or installed application.</p></body></html>"
).encode()
result = {
    "accepted": False,
    "kind": "MINIMAL_BROWSER_PREREQUISITE_NOT_INTEGRATED",
    "pid": os.getpid(),
    "owned_browser": False,
    "browser_in_cleanup_job": False,
    "spawned_children": 0,
    "installed_launches": 0,
    "selection_mutations": 0,
    "financial_actions": 0,
    "provider_connections": 0,
}
started = time.perf_counter()
lock = threading.Lock()
requests = []


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        with lock:
            requests.append({"path": self.path, "observed_ns": time.perf_counter_ns()})
            admitted = len(requests) <= 96
        self.send_response(200 if admitted else 429)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        data = body if admitted else b"BUDGET_REFUSED"
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *_):
        pass


server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01})
thread.start()
try:
    ready = {
        "mode": "DISPOSABLE_CONTROL_FIXTURE",
        "host_id": host_id,
        "pid": os.getpid(),
        "image": sys.executable,
        "release": "SYNTHETIC_FIXTURE",
        "head": "f" * 64,
        "url": f"http://127.0.0.1:{server.server_port}/",
        "providers": False,
        "financial_writers": False,
        "trading": False,
        "automatic_startup": False,
    }
    result["identity"] = observe_pid(os.getpid())
    result["ready"] = ready
    (root / "ready.json").write_text(json.dumps(ready))
    window = BrowserWindow(
        root=root,
        cycle=1,
        ready=ready,
        expected={k: ready[k] for k in ("release", "head", "image")},
        ready_ns=time.perf_counter_ns(),
        domain="DISPOSABLE",
    )
    print(
        json.dumps(
            {
                "stage": "MINIMAL_BROWSER_REQUIRED",
                "root": str(root),
                "ticket": window.ticket,
            }
        ),
        flush=True,
    )
    result["receipt"] = window.wait()
    response = probe(port=server.server_port, path="/")
    assert response["status"] == 200 and response["data"] == body
    result["peer_eof_and_client_handle_closed"] = True
    result["accepted"] = True
except Exception as exc:  # noqa: BLE001 - preserve refusal before exact server cleanup.
    result["error"] = repr(exc)
finally:
    server.shutdown()
    server.server_close()
    thread.join(timeout=3)
    result["server_thread_closed"] = not thread.is_alive()
    result["server_socket_closed"] = server.fileno() == -1
    result["requests"] = requests
    result["seconds"] = time.perf_counter() - started
    result["accepted"] &= (
        result["server_thread_closed"]
        and result["server_socket_closed"]
        and result["seconds"] <= 180
    )
    (root / "browser-prerequisite-result.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result), flush=True)
raise SystemExit(0 if result["accepted"] else 2)
