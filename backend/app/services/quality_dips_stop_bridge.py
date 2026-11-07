"""Injected Control Center action, shared by native GUI and confined HTTP tests.

No environment authorization, process discovery or force termination. The caller
must retain and independently verify the actual runtime/process ownership lease.
"""

from contextlib import contextmanager
from hmac import compare_digest
from threading import Lock

from app.services.paper_financial_replay import body, digest, strict


class PaperStopBridge:
    def __init__(self, *, runtime=None, evidence=None, ownership=None, owned_close=None, runner=None):
        if runtime is None or ownership is None:
            raise ValueError("PAPER_STOP_ACCEPTED_SESSION_REQUIRED")
        if runtime.enrollment.get('execution_domain') in ('OPERATIONAL_ACCEPTED', 'PERSONAL_PAPER') and owned_close is None:
            raise ValueError('PAPER_STOP_RETAINED_OWNED_CLOSE_REQUIRED')
        self.runtime, self.evidence = runtime, evidence
        self.ownership, self.owned_close = ownership, owned_close
        self.identity = strict(body(runtime.runtime.enrollment["process_identity"]))
        self.binding = digest(runtime.enrollment)
        self._ports = (runtime, evidence, ownership, owned_close)
        self.runner = self._runner = runner
        if runner is not None:
            from scripts.observation_runtime.personal_commissioning_runner import (
                PersonalCommissioningRunner,
            )
            if (type(runner) is not PersonalCommissioningRunner or runner.runtime is not runtime
                    or runner.evidence is not evidence):
                raise ValueError('PAPER_STOP_EXACT_DRIVER_REQUIRED')
            runner.bind_control(self)
        self.lock = Lock()
        self.progress = {"schema": "QD_CONTROL_STOP_V1", "phase": "IDLE", "outcome": None}

    def verify_session(self):
        return (
            all(a is b for a, b in zip((self.runtime, self.evidence, self.ownership, self.owned_close), self._ports, strict=True))
            and self.runner is self._runner
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
            if self.runner is not None:
                self.runner.refuse_control()
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
        if self.runner is not None:
            self.runner.request_stop(mode)
            return self.runner.control_status()
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
        return self.runner.control_status() if self.runner is not None else strict(body(self.progress))


def register_stop_routes(app, *, bridge, origin, token, require_session=False, require_durable_receipt=False):
    """Only an explicitly composed host registers this authenticated local route.

    Not registered in app.main or the read-only host by default. The injected
    token is transport CSRF protection, never financial or startup authority.
    """
    import sqlite3
    from fastapi import Request
    from fastapi.responses import JSONResponse

    if not origin.startswith("http://127.0.0.1:") or type(token) is not str or len(token) < 32:
        raise ValueError("CONTROL_LOOPBACK_TRANSPORT_REQUIRED")
    if type(require_session) is not bool:
        raise ValueError("CONTROL_SESSION_POLICY_INVALID")
    if type(require_durable_receipt) is not bool or (require_durable_receipt and not require_session):
        raise ValueError("CONTROL_RECEIPT_POLICY_INVALID")
    host = origin.removeprefix("http://")

    async def stop(request: Request):
        # In session-required installations the legacy mode-only endpoint
        # cannot bypass the session-bound identity check.
        if require_session:
            return JSONResponse({"status": "REFUSED"}, status_code=409)
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
    async def stop_session(request: Request):
        # Opt-in session-bound endpoint. The CSRF token authenticates the local
        # transport only; bridge.verify_session authenticates the installed
        # runtime. No discovery, startup, or self-asserted ownership flag.
        if (
            request.client.host != "127.0.0.1"
            or request.headers.get("host") != host
            or request.headers.get("origin") != origin
            or not compare_digest(request.headers.get("x-atlas-control", ""), token)
        ):
            return JSONResponse({"status": "REFUSED"}, status_code=403)
        try:
            raw = b""
            async for chunk in request.stream():
                if len(raw) + len(chunk) > 256:
                    raise ValueError("CONTROL_COMMAND_TOO_LARGE")
                raw += chunk
            payload = strict(raw.decode())
            if (type(payload) is not dict or set(payload) != {"session_id", "mode"}
                    or type(payload["session_id"]) is not str
                    or not 0 < len(payload["session_id"]) <= 128
                    or payload["mode"] not in ("SHUTDOWN_FLATTEN", "EMERGENCY")):
                raise ValueError("CONTROL_SESSION_COMMAND_SCHEMA")
            from starlette.concurrency import run_in_threadpool

            def verified_stop():
                # A route installed while RUNNING must not remain an active
                # financial-stop entry point after the runtime is stopped.
                # Restrict this to accepted unified installations; legacy
                # synthetic transport tests retain their explicit policy.
                if require_durable_receipt:
                    from app.services.unified_paper_runtime import UnifiedControlStopBridge
                    if (type(bridge) is UnifiedControlStopBridge
                            and bridge.runtime.state not in ("RUNNING", "PAUSED")):
                        raise ValueError("CONTROL_RUNTIME_NOT_ACTIVE")
                if (type(bridge.session_id) is not str
                        or bridge.session_id != payload["session_id"]
                        or bridge.verify_session() is not True):
                    raise ValueError("CONTROL_SESSION_IDENTITY_UNVERIFIED")
                result = bridge.request_stop(payload["mode"])
                if (bridge.session_id != payload["session_id"]
                        or bridge.verify_session() is not True):
                    raise ValueError("CONTROL_SESSION_IDENTITY_CHANGED")
                # An HTTP 200 is an affirmative shutdown receipt. Never
                # acknowledge a merely dispatched, incomplete, or unverifiable
                # financial stop as successfully flattened and exited.
                outcome = result.get("outcome") if type(result) is dict else None
                if (type(outcome) is not dict
                        or result.get("schema") != "QD_CONTROL_STOP_V1"
                        or result.get("phase") != "FINISHED"
                        or outcome.get("schema") != "QD_AUTO_SHUTDOWN_V1"
                        or outcome.get("mode") != payload["mode"]
                        or outcome.get("status") != "FLATTENED"
                        or outcome.get("position_state") != "FLAT"
                        or outcome.get("process_shutdown") != "VERIFIED_EXIT"
                        or type(outcome.get("lanes")) is not dict):
                    raise ValueError("CONTROL_SESSION_SHUTDOWN_UNVERIFIED")
                if require_durable_receipt:
                    # A finished in-memory response cannot certify a durable
                    # receipt. The accepted route must read back the exact
                    # session/mode receipt from SQLite before acknowledging.
                    persisted = bridge.stop_ledger.reserve_existing(
                        payload["session_id"], payload["mode"])
                    if (type(persisted) is not dict
                            or persisted.get("state") != "FINISHED"
                            or persisted.get("receipt") != result):
                        raise ValueError("CONTROL_DURABLE_STOP_RECEIPT_UNVERIFIED")
                return result

            return JSONResponse(await run_in_threadpool(verified_stop))
        except Exception:
            # Stop dispatch may have already affected financial state. An
            # unexpected bridge or storage error must never become HTTP 200,
            # and the transport must not retry the ambiguous command.
            return JSONResponse({"status": "REFUSED"}, status_code=409)

    stop_session.__annotations__["request"] = Request
    app.add_api_route("/_atlas/control/stop-session", stop_session, methods=["POST"])


def register_accepted_unified_paper_stop_routes(app, *, bridge, origin, token):
    """Opt-in composition gate: require actual installed unified runtime and
    durable stop receipts before exposing a session-bound control transport.

    Does not create or enroll a runtime, grant financial authority, or start
    any process. The caller must separately certify the installation.
    """
    from app.services.unified_paper_runtime import (
        UnifiedControlStopBridge, UnifiedPaperRuntime,
    )
    from app.services.paper_stop_receipt_ledger import PaperStopReceiptLedger

    if (type(bridge) is not UnifiedControlStopBridge
            or type(bridge.runtime) is not UnifiedPaperRuntime
            or type(bridge.stop_ledger) is not PaperStopReceiptLedger
            or bridge.owned_close is None
            or bridge.session_id is None
            or bridge.runtime.state not in ("RUNNING", "PAUSED")
            or bridge.verify_session() is not True):
        raise ValueError("ACCEPTED_UNIFIED_PAPER_STOP_INSTALLATION_REQUIRED")
    register_stop_routes(app, bridge=bridge, origin=origin, token=token,
                         require_session=True, require_durable_receipt=True)
