"""Explicit disposable-only loopback acceptance host. Never imports app.main.

There is no operational enrollment, financial dispatcher or HTTP control route.
Prebuilt synthetic records are selected only through the owning stdin pipe.
"""
import argparse
import asyncio
import copy
import hashlib
import importlib.util
import json
import os
import socket
import sys
import threading
import time
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from types import SimpleNamespace

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "backend"))

from app.api.quality_dips_selected_paper import create_router
from app.investment.quality_dips_read_capability import SelectedReadCapability
from app.services.paper_financial_replay import strict
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response

SELECTED = "/api/investments/quality-dips/selected-paper"
ASSETS = {"/quality_dips.html": "quality_dips.html", "/static/runtime_poll.js": "runtime_poll.js",
          "/static/quality_dips_selected_paper.js": "quality_dips_selected_paper.js"}


def confined(path):
    root = Path(path).absolute()
    if (root.parent != REPO / "logs/diagnostics" or not root.name.startswith("qd-http-browser-")
            or any(p.is_symlink() or p.is_junction() for p in [root, *root.parents])):
        raise ValueError("EXPLICIT_DISPOSABLE_ROOT_REQUIRED")
    return root


def load_fixture(root, expected):
    raw = (root / "fixture.json").read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError("FIXTURE_MANIFEST_CHANGED")
    fixture = strict(raw.decode())
    if (fixture.get("schema") != "QD_HTTP_SYNTHETIC_ONLY_V1"
            or set(fixture["phases"]) != {"entry", "partial", "final"}):
        raise ValueError("SYNTHETIC_FIXTURE_REQUIRED")
    for phase, data in fixture["phases"].items():
        if data["enrollment"]["account_id"] != "synthetic-selected":
            raise ValueError("NO_OPERATIONAL_ACCOUNT")
        for part in (phase, "source", "projection", "reports"):
            if not part.isidentifier():
                raise ValueError("FIXTURE_PATH_REQUIRED")
        for path in (root / phase, *(root / phase / name for name in ("source", "projection", "reports"))):
            if not path.is_dir() or path.is_symlink() or path.is_junction():
                raise ValueError("FIXTURE_RESOURCE_SUBSTITUTED")
    return fixture


class FixtureAuthority:
    """Only explicit disposable custody; not accepted operational authority."""
    def __init__(self, enrollment, snapshot, mode):
        self.enrollment, self.snapshot, self.mode = enrollment, snapshot, mode

    @contextmanager
    def lease(self, enrollment, now):
        if enrollment != self.enrollment:
            raise ValueError("FOREIGN_FIXTURE_ENROLLMENT")
        observed = now - 60 if self.mode == "stale" else now
        pin = {**copy.deepcopy(self.snapshot), "observed_at": observed, "expires_at": observed + 30}
        if self.mode == "unknown":
            pin["status"] = "UNKNOWN"
        yield SimpleNamespace(snapshot=pin, check=lambda p, t: p == pin)


def build_app(root, fixture, port_number, host_id, request_log):
    spec = importlib.util.spec_from_file_location("disposable_native_read", REPO / "scripts/volume_inspector/financial_read_port.py")
    native = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(native)
    state = {"phase": "entry", "mode": "normal", "delay": 0}
    request_state = ContextVar("fixture_request_state", default=None)
    lock = threading.RLock()
    origin = f"http://127.0.0.1:{port_number}"

    class Reader:
        def capability(self):
            control = request_state.get()
            if control is None:
                raise ValueError("HTTP_READ_CONTEXT_REQUIRED")
            phase, mode = control["phase"], control["mode"]
            descriptor = fixture["phases"][phase]
            enrollment = descriptor["enrollment"]
            base = root / phase
            source = base / ("absent" if mode == "unavailable" else "source")
            port = native.NativeFinancialReadPort(source_root=str(source), projection_root=str(base / "projection"),
                                                   report_root=str(base / "reports"))
            return SelectedReadCapability(enrollment=enrollment,
                authority=FixtureAuthority(enrollment, descriptor["current"], mode),
                clock=lambda: int(time.time()), port=port)

        def read_committed(self, account, epoch):
            return self.capability().read_committed(account, epoch)

        def verify(self, payload, **kwargs):
            return self.capability().verify(payload, **kwargs)

    reader = Reader()
    first = fixture["phases"]["entry"]["enrollment"]
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    app.include_router(create_router(reader=reader, verifier=reader, clock=lambda: int(time.time()),
                                    account_id=first["account_id"], epoch=first["epoch"]))
    assets = {path: (REPO / "backend/app/static" / leaf).read_bytes() for path, leaf in ASSETS.items()}

    @app.middleware("http")
    async def boundary(request: Request, call_next):
        started = time.time()
        path = request.url.path
        # Snapshot control before delay: retired responses remain old responses.
        with lock:
            control = dict(state)
        allowed = set(ASSETS) | {"/health", SELECTED, SELECTED + "/commands"}
        valid_query = not request.url.query or (path == "/quality_dips.html" and request.url.query == "mode=selected-paper")
        if (request.headers.get("host") != origin.removeprefix("http://")
                or request.headers.get("origin") not in (None, origin)
                or request.headers.get("sec-fetch-site") == "cross-site"):
            response = Response(status_code=403)
        elif path not in allowed or not valid_query:
            response = Response(status_code=404)
        elif request.method not in ("GET", "POST") or (request.method == "POST" and path != SELECTED + "/commands"):
            response = Response(status_code=405)
        elif path == SELECTED and control["mode"] == "network_failure":
            response = Response(status_code=503)
        else:
            if path == SELECTED and control["delay"]:
                await asyncio.sleep(control["delay"])
            token = request_state.set(control)
            try:
                response = await call_next(request)
            finally:
                request_state.reset(token)
        response.headers.update({"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "no-referrer", "Content-Security-Policy":
            "default-src 'none'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'"})
        with request_log.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps({"method": request.method, "path": path, "status": response.status_code,
                                     "host_id": host_id, "phase": control["phase"], "time": time.time(),
                                     "started": started, "delay": control["delay"], "mode": control["mode"],
                                     "agent": request.headers.get("user-agent", ""),
                                     "fetch_site": request.headers.get("sec-fetch-site")}) + "\n")
        return response

    @app.get("/health")
    def health():
        return JSONResponse({"host_id": host_id, "mode": "DISPOSABLE_SYNTHETIC_READ_ONLY",
                             "pid": os.getpid(), "backend": "DISABLED", "paper_startup": False})

    for route, data in assets.items():
        def serve(content=data, path=route):
            return Response(content, media_type="text/html" if path.endswith(".html") else "application/javascript")
        app.add_api_route(route, serve, methods=["GET"], include_in_schema=False)
    return app, state, lock


def main():
    import uvicorn
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture-root", required=True)
    parser.add_argument("--fixture-sha256", required=True)
    args = parser.parse_args()
    root = confined(args.fixture_root)
    fixture = load_fixture(root, args.fixture_sha256)
    host_id = uuid.uuid4().hex
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(16)
    port = listener.getsockname()[1]
    app, state, lock = build_app(root, fixture, port, host_id, root / (host_id + "-requests.jsonl"))
    server = uvicorn.Server(uvicorn.Config(app, lifespan="off", access_log=False, log_level="error"))

    def control():
        while not server.started and not server.should_exit:
            time.sleep(.02)
        print(json.dumps({"host_id": host_id, "pid": os.getpid(), "url": f"http://127.0.0.1:{port}",
                          "mode": "DISPOSABLE_SYNTHETIC_READ_ONLY"}), flush=True)
        for line in sys.stdin:
            try:
                value = strict(line)
                if (set(value) != {"phase", "mode", "delay"} or value["phase"] not in fixture["phases"]
                        or value["mode"] not in {"normal", "unknown", "stale", "unavailable", "network_failure"}
                        or type(value["delay"]) is not int or not 0 <= value["delay"] <= 8):
                    raise ValueError("INVALID_FIXTURE_CONTROL")
                with lock:
                    state.update(value)
                print(json.dumps({"control": value, "host_id": host_id}), flush=True)
            except (ValueError, KeyError, TypeError):
                print(json.dumps({"refused": "INVALID_FIXTURE_CONTROL"}), flush=True)
        server.should_exit = True

    threading.Thread(target=control, daemon=True).start()
    try:
        server.run(sockets=[listener])
    finally:
        listener.close()


if __name__ == "__main__":
    main()
