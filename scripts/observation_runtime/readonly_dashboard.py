"""Loopback-only immutable Workspace V2 host; never imports the Atlas backend."""
from __future__ import annotations

import argparse
import hashlib
import json
import socket
import subprocess
import sys
import threading
import uuid
import webbrowser
from http.client import HTTPConnection
from http.server import BaseHTTPRequestHandler, HTTPServer, ThreadingHTTPServer
from pathlib import Path

MEMBERS = {"index.html", "market.html", "forecast.html", "comparison.html", "README.txt"}


def load_bundle(root: Path, pin: str) -> dict[str, bytes]:
    """Verify the existing contract, then retain only hash-checked bytes in memory."""
    verifier = Path(__file__).resolve().parents[2] / "frontend/offline/workspace/build-v2.mjs"
    subprocess.run(
        ["node", str(verifier), "--verify", str(root), "--expected-manifest-sha256", pin],
        check=True, capture_output=True, timeout=30,
    )
    raw = (root / "manifest.json").read_bytes()
    if hashlib.sha256(raw).hexdigest() != pin:
        raise ValueError("Manifest changed after verification")
    entries = json.loads(raw)["files"]
    if {entry["path"] for entry in entries} != MEMBERS:
        raise ValueError("Unexpected bundle members")
    result = {}
    for entry in entries:
        data = (root / entry["path"]).read_bytes()
        if len(data) != entry["bytes"] or hashlib.sha256(data).hexdigest() != entry["sha256"]:
            raise ValueError("Bundle changed after verification")
        result["/" + entry["path"]] = data
    return result


def make_host(assets: dict[str, bytes], port: int = 0) -> HTTPServer:
    if set(assets) != {"/" + name for name in MEMBERS}:
        raise ValueError("Exact static allowlist required")
    snapshot = dict(assets)
    identity = uuid.uuid4().hex

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.headers.get("Host") != f"127.0.0.1:{self.server.server_port}":
                self.send_error(403)
                return
            route = "/index.html" if self.path == "/" else self.path
            if route == "/health":
                data = json.dumps({"host_id": identity, "mode": "READ_ONLY_STATIC",
                                   "backend": "UNAVAILABLE", "production": "NO-GO"}).encode()
                mime = "application/json"
            elif route in snapshot:
                data = snapshot[route]
                mime = "text/html; charset=utf-8" if route.endswith(".html") else "text/plain; charset=utf-8"
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *_args):
            pass

    class ExclusiveServer(ThreadingHTTPServer):
        allow_reuse_address = False
        daemon_threads = True
        block_on_close = False

        def server_bind(self):
            if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
                self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            super().server_bind()

    server = ExclusiveServer(("127.0.0.1", port), Handler)
    server.timeout = 1
    server.host_id = identity
    return server


def verify_ready(server: HTTPServer) -> str:
    connection = HTTPConnection("127.0.0.1", server.server_port, timeout=3)
    try:
        connection.request("GET", "/health")
        response = connection.getresponse()
        evidence = json.loads(response.read(4096))
        if response.status != 200 or evidence.get("host_id") != server.host_id:
            raise RuntimeError("Host ownership/readiness mismatch")
        return f"http://127.0.0.1:{server.server_port}/"
    finally:
        connection.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--open-browser", action="store_true")
    parser.add_argument("--gui-control", action="store_true")
    args = parser.parse_args()
    server = make_host(load_bundle(args.bundle, args.manifest_sha256), args.port)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        url = verify_ready(server)
        print(json.dumps({"url": url, "host_id": server.host_id, "mode": "READ_ONLY_STATIC", "backend": "UNAVAILABLE"}), flush=True)
        if args.open_browser and not webbrowser.open(url):
            raise RuntimeError("Browser did not accept launch request")
        if args.gui_control:
            # EOF (including a crashed parent) closes only this owned static host.
            sys.stdin.readline()
        else:
            while worker.is_alive():
                worker.join(1)
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()
        server.server_close()
        worker.join(5)


if __name__ == "__main__":
    main()
