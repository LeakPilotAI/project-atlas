"""Synthetic loopback fixture. No Atlas imports, accounts, providers or selector."""

import http.server
import json
import os
import queue
import secrets
import socket
import sys
import threading
import time


def main():
    if sys.argv[1:] != ["--disposable-fixture-only"]:
        raise SystemExit("DISPOSABLE_ONLY")
    deadline = time.monotonic() + 180
    commands = queue.Queue()

    def reader():
        for line in sys.stdin:
            commands.put(line.strip())
        commands.put("EOF")

    threading.Thread(target=reader, daemon=True).start()

    def command():
        return commands.get(timeout=max(0.01, deadline - time.monotonic()))

    seed = socket.socket()
    seed.bind(("127.0.0.1", 0))
    seed.listen(1)
    print(
        json.dumps({"seed_port": seed.getsockname()[1], "fixture_only": True}),
        flush=True,
    )
    try:
        if command() != "RELEASE_SEED":
            return
    finally:
        seed.close()
    print(json.dumps({"seed_closed": True}), flush=True)
    if command() != "BEGIN":
        return
    for cycle in (1, 2):
        host_id = secrets.token_hex(16)
        body = (
            "<!doctype html><html><head><title>Atlas V3 disposable fixture</title></head>"
            "<body><h1>ATLAS HARNESS V3 DISPOSABLE FIXTURE</h1>"
            f"<p>Cycle {cycle}</p><p>Host {host_id}</p>"
            "<h2>Selected PAPER account: UNAVAILABLE</h2>"
            "<p>NO FINANCIAL ENROLLMENT OR INCEPTION. NO PROVIDERS. NO TRADING.</p>"
            "<p>This page is synthetic test evidence, not the installed dashboard.</p>"
            "</body></html>"
        ).encode()

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.server.fixture_requests += 1
                if self.server.fixture_requests > 96:
                    self.send_error(429)
                    return
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(self.server.fixture_body)))
                self.send_header("Connection", "close")
                self.end_headers()
                self.wfile.write(self.server.fixture_body)

            def log_message(self, *_args):
                pass

        server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
        server.fixture_requests = 0
        server.fixture_body = body
        thread = threading.Thread(
            target=server.serve_forever, kwargs={"poll_interval": 0.01}
        )
        thread.start()
        print(
            json.dumps(
                {
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
            ),
            flush=True,
        )
        request = None
        try:
            request = command()
        finally:
            started = time.perf_counter()
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)
            if thread.is_alive():
                raise RuntimeError("FIXTURE_DRAIN_INCOMPLETE")
        if request != "STOP " + host_id:
            return
        print(
            json.dumps(
                {
                    "closed": True,
                    "financial_actions": 0,
                    "seconds": time.perf_counter() - started,
                }
            ),
            flush=True,
        )
        if cycle == 1 and command() != "NEXT":
            return
    command()  # Owner EOF, never automatic restart.


if __name__ == "__main__":
    main()
