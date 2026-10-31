"""Only a retained-child disposable test host; never an operational entry."""

import argparse
import hashlib
import json
import os
import socket
import sys
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [
    str(REPO / "backend"),
    str(REPO / "tests"),
    str(REPO / "scripts/observation_runtime"),
]

from app.services.paper_financial_replay import strict
from app.services.quality_dips_autonomous_integration import (
    AutonomousCoordinationRead,
    AutonomousSelectedRead,
)
from app.services.quality_dips_stop_bridge import PaperStopBridge
from disposable_host_owner import observe_pid
from qd_autonomous_binding_fixture import build
from selected_account_readonly_host import build_app, confined
from test_quality_dips_autonomous_binding import step
from test_quality_dips_shutdown_flatten import quotes


def main():
    import uvicorn

    p = argparse.ArgumentParser()
    p.add_argument("--fixture-root", required=True)
    p.add_argument("--fixture-sha256", required=True)
    args = p.parse_args()
    root = confined(args.fixture_root)
    raw = (root / "fixture.json").read_bytes()
    config = strict(raw.decode())
    if (
        hashlib.sha256(raw).hexdigest() != args.fixture_sha256
        or set(config) != {"schema", "damage", "partial"}
        or config["schema"] != "QD_CONTROL_DISPOSABLE_V1"
        or config["damage"] not in ("none", "stale", "closed", "disconnect", "unknown")
        or type(config["partial"]) is not bool
    ):
        raise ValueError("PINNED_CONTROL_FIXTURE_REQUIRED")
    (root / "account").mkdir()
    s = build(
        root / "account", root, stamp=1792418400
    )  # Explicit historical synthetic market clock.
    identity, host_id = observe_pid(os.getpid()), uuid.uuid4().hex
    s.runtime.start(s.grant)
    step(s, 1)
    if config["partial"]:
        step(s, 2, "partial")
    s.x.n.now[0] += 1
    if config["damage"] == "unknown":
        original = s.financial.delegate.publish

        def unknown(*args):
            original(*args)
            raise ValueError("SYNTHETIC_COMMIT_BEFORE_ACK")

        s.financial.delegate.publish = unknown
    ownership = SimpleNamespace(
        verify_session=lambda binding, ident: (
            observe_pid(os.getpid()) == identity and ident == identity
        )
    )
    bridge = PaperStopBridge(
        runtime=s.runtime, evidence=quotes(s, config["damage"]), ownership=ownership
    )

    class PresentationAuthority:
        @contextmanager
        def lease(self, enrollment, now):
            current = {**s.x.x.current(), "observed_at": now, "expires_at": now + 30}
            yield SimpleNamespace(snapshot=current, check=lambda p, t: True)

    def reader_factory(now):
        return AutonomousSelectedRead(
            enrollment=s.x.x.enrollment,
            authority=PresentationAuthority(),
            clock=lambda: now,
            port=s.x.x.port,
            coordination=AutonomousCoordinationRead(s.x.n.engine),
        )

    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(16)
    port, token = listener.getsockname()[1], uuid.uuid4().hex
    app, _, _ = build_app(
        root,
        {"phases": {"entry": {"enrollment": s.x.x.enrollment}}},
        port,
        host_id,
        root / (host_id + "-requests.jsonl"),
        reader_factory=reader_factory,
        control_bridge=bridge,
        control_token=token,
    )
    # Test harness controls are not Atlas assets/endpoints. The production UI
    # remains the original selected account page mounted below this test page.
    from fastapi import FastAPI, Request
    from fastapi.responses import HTMLResponse, Response

    wrapper = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    @wrapper.get("/control-test")
    def control_test(request: Request):
        if request.headers.get("host") != f"127.0.0.1:{port}":
            return Response(status_code=403)
        return HTMLResponse(
            """<!doctype html><title>Disposable Control Center action test</title>
            <h1>DISPOSABLE synthetic PAPER only</h1><p>Same injected Stop action as Atlas Control Center.</p>
            <button id="normal">Stop Atlas (SHUTDOWN_FLATTEN test)</button>
            <pre id="result" role="status">Awaiting Stop</pre>
            <a href="/quality_dips.html?mode=selected-paper">Original Atlas dashboard</a>
            <script>document.getElementById('normal').onclick=async()=>{
            document.getElementById('result').textContent='IN_PROGRESS';
            const r=await fetch('/_atlas/control/stop',{method:'POST',headers:{'Content-Type':'application/json',
            'X-Atlas-Control':"""
            + json.dumps(token)
            + """},body:JSON.stringify({mode:'SHUTDOWN_FLATTEN'})});
            document.getElementById('result').textContent=JSON.stringify(await r.json());};</script>"""
        )

    wrapper.mount("/", app)
    app = wrapper
    server = uvicorn.Server(
        uvicorn.Config(app, lifespan="off", access_log=False, log_level="error")
    )

    def control():
        while not server.started and not server.should_exit:
            time.sleep(0.02)
        print(
            json.dumps(
                {
                    "host_id": host_id,
                    "pid": os.getpid(),
                    "url": f"http://127.0.0.1:{port}",
                    "mode": "DISPOSABLE_SYNTHETIC_READ_ONLY",
                    "runtime_fixture": True,
                    "control_token": token,
                }
            ),
            flush=True,
        )
        try:
            for line in sys.stdin:
                command = strict(line)
                if observe_pid(os.getpid()) != identity:
                    raise ValueError("OWNED_CONTROL_IDENTITY_CHANGED")
                if command == {"action": "start"}:
                    print(
                        json.dumps(
                            {
                                "host_id": host_id,
                                "runtime": {"refused": "RESTART_REFUSED"},
                            }
                        ),
                        flush=True,
                    )
                else:
                    print(
                        json.dumps(
                            {
                                "host_id": host_id,
                                "runtime": {"state": s.x.n.engine.status()},
                            }
                        ),
                        flush=True,
                    )
        finally:
            s.runtime.stop(mode="EMERGENCY")
            server.should_exit = True

    threading.Thread(target=control, daemon=True).start()
    try:
        server.run(sockets=[listener])
    finally:
        listener.close()
        s.x.x.close()


if __name__ == "__main__":
    main()
