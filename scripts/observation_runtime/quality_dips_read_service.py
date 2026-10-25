"""Unenrolled operational read composition. No default launcher or trust root.

Only a separately accepted composition may inject custody/resources/clock and
read-service acceptance. A Python object is not authenticated merely because it
implements an interface. This module never imports app.main or a dispatcher.
"""
import ctypes
import os
import socket
import threading
import time
import uuid
from contextlib import closing
from http.client import HTTPConnection
from pathlib import Path

from app.api.quality_dips_selected_paper import create_router
from app.investment.quality_dips_operational_contract import (
    ENROLLMENT,
    OperationalReadCapability,
)
from app.investment.quality_dips_read_capability import SelectedReadCapability
from app.services.paper_financial_replay import body, digest, strict
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response

STATIC = Path(__file__).resolve().parents[2] / "backend/app/static"
SELECTED = "/api/investments/quality-dips/selected-paper"
ASSETS = {"/quality_dips.html": "quality_dips.html", "/static/runtime_poll.js": "runtime_poll.js",
          "/static/quality_dips_selected_paper.js": "quality_dips_selected_paper.js"}
MODE = "QD_OPERATIONAL_READ_ONLY"


def observe_self():
    """Native identity only, never ownership or read-service authorization."""
    if os.name != "nt":
        raise ValueError("WINDOWS_IDENTITY_REQUIRED")
    from ctypes import wintypes
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    kernel.GetProcessTimes.argtypes = [wintypes.HANDLE, *([ctypes.POINTER(wintypes.FILETIME)] * 4)]
    kernel.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR,
                                                 ctypes.POINTER(wintypes.DWORD)]
    handle = kernel.GetCurrentProcess()
    stamps = [wintypes.FILETIME() for _ in range(4)]
    image, size = ctypes.create_unicode_buffer(32768), wintypes.DWORD(32768)
    if (not kernel.GetProcessTimes(handle, *(ctypes.byref(stamp) for stamp in stamps))
            or not kernel.QueryFullProcessImageNameW(handle, 0, image, ctypes.byref(size))):
        raise OSError(ctypes.get_last_error(), "Native self identity unavailable")
    return {"pid": os.getpid(), "creation_filetime": (stamps[0].dwHighDateTime << 32) | stamps[0].dwLowDateTime,
            "image": image.value}


class ReadComposition:
    """acceptance.lease(context, now) must authenticate complete read-only scope.

    Its check(context, now) must enforce accepted account/resource/process scope,
    trusted freshness and continuity; it grants ONLY read-service permission.
    Current-pin custody separately authenticates every immutable financial read.
    No default implementation or operational enrollment is supplied.
    """
    def __init__(self, *, account_id, epoch, enrollment, custody, clock, resources, acceptance, observer):
        if any(value is None for value in (enrollment, custody, clock, resources, acceptance, observer)):
            raise ValueError("ACCEPTED_READ_DEPENDENCIES_REQUIRED")
        self.account, self.epoch = account_id, epoch
        self.clock, self.acceptance, self.observer = clock, acceptance, observer
        self.enrollment = strict(body(enrollment))
        self.operational = self.enrollment.get("schema") == ENROLLMENT
        if self.enrollment.get("schema") not in (ENROLLMENT, "QD_READ_ENROLLMENT_V1"):
            raise ValueError("READ_ENROLLMENT_VERSION_UNSUPPORTED")
        account = self.enrollment.get("account", {}) if self.operational else self.enrollment
        if account.get("account_id") != account_id or account.get("epoch") != epoch:
            raise ValueError("READ_ACCOUNT_SCOPE_MISMATCH")
        self.host_id = uuid.uuid4().hex
        self.host_claim_lock, self.host_claimed = threading.Lock(), False
        self.identity = strict(body(observer()))
        if (set(self.identity) != {"pid", "creation_filetime", "image"}
                or type(self.identity["pid"]) is not int or self.identity["pid"] != os.getpid()
                or type(self.identity["creation_filetime"]) is not int or self.identity["creation_filetime"] <= 0
                or type(self.identity["image"]) is not str or not self.identity["image"]):
            raise ValueError("READ_PROCESS_IDENTITY_UNVERIFIED")
        arguments = {"enrollment": self.enrollment, "authority": custody, "clock": clock, "port": resources}
        if self.operational:
            self.capability = OperationalReadCapability(**arguments,
                process_identity={"schema": "QD_OP_PROCESS_ID_V1", **self.identity}, host_id=self.host_id)
        else:
            self.capability = SelectedReadCapability(**arguments)

    def admitted(self, operation):
        context = {"schema": "QD_READ_SERVICE_CONTEXT_V1", "mode": MODE, "host_id": self.host_id,
                   "account_id": self.account, "epoch": self.epoch,
                   "enrollment_digest": digest(self.enrollment), "process": self.identity}
        if self.operational:
            context["schema"] = "QD_OP_READ_SERVICE_CONTEXT_V1"
            context["process"] = {"schema": "QD_OP_PROCESS_ID_V1", **self.identity}
        now = self.clock()
        if type(now) is not int or now <= 0 or body(self.observer()) != body(self.identity):
            raise ValueError("READ_PROCESS_OR_CLOCK_CHANGED")
        with self.acceptance.lease(strict(body(context)), now) as lease:
            if lease.check(strict(body(context)), now) is not True:
                raise ValueError("READ_SERVICE_ACCEPTANCE_MISSING")
            value = operation()
            end = self.clock()
            if (type(end) is not int or not now <= end <= now + 30
                    or body(self.observer()) != body(self.identity)
                    or lease.check(strict(body(context)), end) is not True):
                raise ValueError("READ_SERVICE_CONTINUITY_LOST")
            checked = self.clock()
            if type(checked) is not int or not end <= checked <= now + 30:
                raise ValueError("READ_SERVICE_CLOCK_CHANGED")
            return value

    def read_committed(self, account_id, epoch):
        if (account_id, epoch) != (self.account, self.epoch):
            raise ValueError("READ_ACCOUNT_SCOPE_MISMATCH")
        return self.admitted(lambda: self.capability.read_committed(account_id, epoch))

    def verify(self, payload, **context):
        return self.admitted(lambda: self.capability.verify(payload, **context))

    def preflight(self):
        return self.read_committed(self.account, self.epoch)


def build_app(composition, port, *, market_reader=None, unified_reader=None):
    composition.preflight()  # Refuse before even publishing an application.
    origin = f"http://127.0.0.1:{port}"
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    app.include_router(create_router(reader=composition, verifier=composition, clock=composition.clock,
                                    account_id=composition.account, epoch=composition.epoch,
                                    market_reader=market_reader, unified_reader=unified_reader))
    assets = {route: (STATIC / leaf).read_bytes() for route, leaf in ASSETS.items()}

    @app.middleware("http")
    async def boundary(request: Request, call_next):
        path, query = request.url.path, request.url.query
        if (request.headers.getlist("host") != [origin.removeprefix("http://")]
                or request.headers.getlist("origin") not in ([], [origin])
                or request.headers.get("sec-fetch-site") == "cross-site" or request.method != "GET"):
            response = Response(status_code=403)
        elif (path not in {*ASSETS, "/health", SELECTED}
                or (path == "/quality_dips.html" and query != "mode=selected-paper")
                or (path != "/quality_dips.html" and query)):
            response = Response(status_code=404)
        else:
            try:
                composition.admitted(lambda: None)
            except (ValueError, OSError, KeyError, TypeError, RuntimeError):
                response = JSONResponse({"status": "UNKNOWN", "reason": "READ_SERVICE_UNAVAILABLE"}, status_code=503)
            else:
                response = await call_next(request)
        response.headers.update({"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "no-referrer", "Content-Security-Policy":
            "default-src 'none'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'"})
        return response

    @app.get("/health")
    def health():
        try:
            composition.preflight()
        except (ValueError, OSError, KeyError, TypeError, RuntimeError):
            return JSONResponse({"status": "UNKNOWN", "reason": "READ_SERVICE_UNAVAILABLE"}, status_code=503)
        return {"host_id": composition.host_id, "mode": MODE, "process": composition.identity,
                "account_id": composition.account, "epoch": composition.epoch, "paper_startup": False}

    for route, raw in assets.items():
        def serve(content=raw, path=route):
            return Response(content, media_type="text/html" if path.endswith(".html") else "application/javascript")
        app.add_api_route(route, serve, methods=["GET"], include_in_schema=False)
    return app


class OwnedReadHost:
    """Owns only its listener/server thread. No process termination API."""
    def __init__(self, composition, *, market_reader=None, unified_reader=None):
        self.composition = composition
        self.market_reader = market_reader
        self.unified_reader = unified_reader
        self.listener = self.server = self.thread = self.ready = None

    def open_read_only_session(self):
        if self.ready is None:
            return self.start()
        if self.verify_read_only_session(self.ready) is not True:
            raise ValueError("READ_HOST_REUSE_UNVERIFIED")
        return strict(body(self.ready))

    def verify_read_only_session(self, expected):
        if (self.ready is None or body(expected) != body(self.ready)
                or body(self.composition.observer()) != body(self.composition.identity)):
            return False
        self.composition.preflight()
        port = self.listener.getsockname()[1]
        with closing(HTTPConnection("127.0.0.1", port, timeout=3)) as connection:
            connection.request("GET", "/health")
            response = connection.getresponse()
            actual = strict(response.read().decode())
            return (response.status == 200 and actual.get("host_id") == self.ready["host_id"]
                    and actual.get("mode") == MODE and actual.get("process") == self.ready["process"]
                    and actual.get("account_id") == self.composition.account and actual.get("epoch") == self.composition.epoch)

    def close_read_only_session(self, expected):
        self.close(expected)
        return self.listener is None

    def start(self):
        import uvicorn
        if self.listener is not None:
            raise ValueError("READ_HOST_ALREADY_OWNED")
        with self.composition.host_claim_lock:
            if self.composition.host_claimed:
                raise ValueError("READ_HOST_CONTEXT_RETIRED_OR_SHARED_RECOMPOSE_REQUIRED")
            self.composition.host_claimed = True
        self.composition.preflight()  # No listener allocation before admission.
        self.listener = socket.socket()
        try:
            self.listener.bind(("127.0.0.1", 0))
            self.listener.listen(16)
            port = self.listener.getsockname()[1]
            app = (build_app(self.composition, port)
                   if self.market_reader is None and self.unified_reader is None else
                   build_app(self.composition, port, market_reader=self.market_reader, unified_reader=self.unified_reader))
            self.ready = {"host_id": self.composition.host_id, "mode": MODE,
                          "process": self.composition.identity,
                          "url": f"http://127.0.0.1:{port}/quality_dips.html?mode=selected-paper"}
            self.server = uvicorn.Server(uvicorn.Config(app, lifespan="off", access_log=False, log_level="error",
                                                        proxy_headers=False, timeout_graceful_shutdown=5))
            self.thread = threading.Thread(target=self.server.run, kwargs={"sockets": [self.listener]}, daemon=True)
            self.thread.start()
            deadline = time.monotonic() + 15
            while not self.server.started:
                if not self.thread.is_alive() or time.monotonic() >= deadline:
                    raise ValueError("READ_HOST_READINESS_FAILED")
                time.sleep(.01)
            with closing(HTTPConnection("127.0.0.1", port, timeout=3)) as connection:
                connection.request("GET", "/health")
                response = connection.getresponse()
                actual = strict(response.read().decode())
                if (response.status != 200 or actual["host_id"] != self.ready["host_id"]
                        or actual["process"] != self.ready["process"] or actual["mode"] != MODE):
                    raise ValueError("READ_HOST_READINESS_IDENTITY_MISMATCH")
            return strict(body(self.ready))
        except BaseException:
            self.close(self.ready)
            raise

    def close(self, expected):
        if self.listener is None:
            return
        if body(expected) != body(self.ready) or body(self.composition.observer()) != body(self.composition.identity):
            raise ValueError("READ_HOST_OWNERSHIP_MISMATCH_RETAINED")
        if self.server:
            self.server.should_exit = True
        if self.thread:
            self.thread.join(12)
            if self.thread.is_alive():
                raise ValueError("READ_HOST_TIMEOUT_OWNERSHIP_RETAINED")
        self.listener.close()
        self.listener = self.server = self.thread = self.ready = None


if __name__ == "__main__":
    raise SystemExit("REFUSED: accepted in-process enrollment/custody/clock/resources/read-service composition required")
