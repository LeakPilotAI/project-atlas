"""Injected Control Center action, shared by native GUI and confined HTTP tests.

No environment authorization, process discovery or force termination. The caller
must retain and independently verify the actual runtime/process ownership lease.
"""

from contextlib import contextmanager
from hmac import compare_digest
from threading import Lock

from app.services.paper_financial_replay import body, digest, strict


class PaperStopBridge:
    def __init__(self, *, runtime=None, evidence=None, ownership=None, owned_close=None):
        if runtime is None or ownership is None:
            raise ValueError("PAPER_STOP_ACCEPTED_SESSION_REQUIRED")
        if runtime.enrollment.get('execution_domain') in ('OPERATIONAL_ACCEPTED', 'PERSONAL_PAPER') and owned_close is None:
            raise ValueError('PAPER_STOP_RETAINED_OWNED_CLOSE_REQUIRED')
        self.runtime, self.evidence = runtime, evidence
        self.ownership, self.owned_close = ownership, owned_close
        self.identity = strict(body(runtime.runtime.enrollment["process_identity"]))
        self.binding = digest(runtime.enrollment)
        self._ports = (runtime, evidence, ownership, owned_close)
        self.lock = Lock()
        self.progress = {"schema": "QD_CONTROL_STOP_V1", "phase": "IDLE", "outcome": None}

    def verify_session(self):
        return (
            all(a is b for a, b in zip((self.runtime, self.evidence, self.ownership, self.owned_close), self._ports, strict=True))
            and digest(self.runtime.enrollment) == self.binding
            and self.runtime.runtime.enrollment["process_identity"] == self.identity
            and self.ownership.verify_session(self.binding, strict(body(self.identity))) is True
        )

    def request_stop(self, mode):
        try:
            with self.authorized(mode):
                return self._request_stop(mode)
        except (ValueError, OSError, KeyError, TypeError):
            # A post-effect lease/ownership failure cannot leave a clean-looking
            # FINISHED status. Preserve financial history in the native runtime;
            # this transport result is explicitly unverified, never replayed.
            self.progress = {"schema": "QD_CONTROL_STOP_V1", "phase": "REFUSED", "outcome": None}
            raise

    @contextmanager
    def authorized(self, mode):
        if mode not in ("SHUTDOWN_FLATTEN", "EMERGENCY") or not self.verify_session():
            raise ValueError("PAPER_STOP_SESSION_OR_MODE_UNVERIFIED")
        if self.runtime.enrollment.get('execution_domain') == 'PERSONAL_PAPER':
            from app.services.personal_paper_runtime import (
                PersonalEnrolledRuntime,
                PersonalOperatorInstallation,
                checked_personal_installation,
            )
            r = self.runtime
            if type(r) is not PersonalEnrolledRuntime or type(r.installation) is not PersonalOperatorInstallation:
                raise ValueError('PERSONAL_STOP_INSTALLATION_REQUIRED')
            request = {'schema': 'ATLAS_PERSONAL_CONTROL_CONTEXT_V1',
                       'action': 'EMERGENCY_STOP' if mode == 'EMERGENCY' else mode,
                       'session_digest': self.binding, 'process': self.identity}
            with r.installation.lease(request) as lease:
                proof = checked_personal_installation(lease, request)
                if not lease.check_components(r.installation_components()):
                    raise ValueError('PERSONAL_STOP_COMPONENTS_CHANGED')
                yield
                if not lease.check(proof) or not self.verify_session():
                    raise ValueError('PERSONAL_STOP_AUTHORIZATION_CHANGED')
        else:
            yield

    def _request_stop(self, mode):
        if mode not in ("SHUTDOWN_FLATTEN", "EMERGENCY") or self.verify_session() is not True:
            raise ValueError("PAPER_STOP_SESSION_OR_MODE_UNVERIFIED")
        # Close entries even when another bounded shutdown request is in flight.
        self.runtime.runtime.engine.entry_admission_closed = True
        if not self.lock.acquire(timeout=2):
            return {"schema": "QD_CONTROL_STOP_V1", "phase": "IN_PROGRESS", "outcome": None}
        try:
            self.progress = {"schema": "QD_CONTROL_STOP_V1", "phase": mode, "outcome": None}
            if mode == "SHUTDOWN_FLATTEN":
                outcome = self.runtime.stop(
                    mode=mode, evidence=self.evidence, owned_close=self.owned_close
                )
            else:
                outcome = {
                    "status": self.runtime.stop(mode="EMERGENCY"),
                    "position_state": "UNVERIFIED",
                }
            self.progress = {
                "schema": "QD_CONTROL_STOP_V1",
                "phase": "FINISHED",
                "outcome": outcome,
            }
            return strict(body(self.progress))
        except (ValueError, OSError, KeyError, TypeError):
            self.progress = {"schema": "QD_CONTROL_STOP_V1", "phase": "REFUSED", "outcome": None}
            raise
        finally:
            self.lock.release()

    def status(self):
        if not self.verify_session():
            raise ValueError("PAPER_STOP_OWNERSHIP_CHANGED")
        return strict(body(self.progress))


def register_stop_routes(app, *, bridge, origin, token):
    """Only an explicitly composed host registers this authenticated local route.

    Not registered in app.main or the read-only host by default. The injected
    token is transport CSRF protection, never financial or startup authority.
    """
    from fastapi import Request
    from fastapi.responses import JSONResponse

    if not origin.startswith("http://127.0.0.1:") or type(token) is not str or len(token) < 32:
        raise ValueError("CONTROL_LOOPBACK_TRANSPORT_REQUIRED")
    host = origin.removeprefix("http://")

    async def stop(request: Request):
        if (
            request.client.host != "127.0.0.1"
            or request.headers.get("host") != host
            or request.headers.get("origin") != origin
            or not compare_digest(request.headers.get("x-atlas-control", ''), token)
        ):
            return JSONResponse({"status": "REFUSED"}, status_code=403)
        try:
            raw = b''
            async for chunk in request.stream():
                if len(raw) + len(chunk) > 256:
                    raise ValueError('CONTROL_COMMAND_TOO_LARGE')
                raw += chunk
            payload = strict(raw.decode())
            if set(payload) != {"mode"}:
                raise ValueError("CONTROL_COMMAND_SCHEMA")
            # The existing bounded coordinator owns all financial decisions.
            from starlette.concurrency import run_in_threadpool

            result = await run_in_threadpool(bridge.request_stop, payload["mode"])
            return JSONResponse(result)
        except (ValueError, OSError, KeyError, TypeError):
            return JSONResponse({"status": "REFUSED"}, status_code=409)

    # Explicit Request annotation resolves without exposing globals or FastAPI startup.
    stop.__annotations__["request"] = Request
    app.add_api_route("/_atlas/control/stop", stop, methods=["POST"])
