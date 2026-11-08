"""Explicit disposable continuous runtime fixture, NOT an operational launcher.

Only this test module supplies synthetic local authorities and a virtual market
clock. HTTP is read-only; observations arrive from a bounded in-process fixture
source, never from HTTP or a live provider. Parent ownership authorizes stdin EOF.
"""
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
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO / "backend"), str(REPO / "tests"), str(REPO / "scripts/observation_runtime")]

from app.services.paper_financial_replay import strict
from app.services.quality_dips_autonomous_integration import (
    AutonomousCoordinationRead,
    AutonomousSelectedRead,
)
from disposable_host_owner import observe_pid
from qd_autonomous_runtime_fixture import compose
from selected_account_readonly_host import build_app, confined


def main():
    import uvicorn
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture-root", required=True)
    parser.add_argument("--fixture-sha256", required=True)
    args = parser.parse_args()
    root = confined(args.fixture_root)
    if not root.name.startswith("qd-http-browser-runtime-"):
        raise ValueError("CONTINUOUS_DISPOSABLE_ROOT_REQUIRED")
    raw = (root / "fixture.json").read_bytes()
    config = strict(raw.decode())
    if (hashlib.sha256(raw).hexdigest() != args.fixture_sha256
            or set(config) != {"schema", "interval_seconds"}
            or config["schema"] != "QD_AUTO_CONTINUOUS_FIXTURE_V3"
            or type(config["interval_seconds"]) not in (float, int)
            or not 0.05 <= config["interval_seconds"] <= 60):
        raise ValueError("PINNED_SYNTHETIC_CONFIGURATION_REQUIRED")
    account = root / "account"
    account.mkdir()  # Exclusive test initialization; never adopt or repair.
    stamp = int(datetime(2026, 10, 19, 14, tzinfo=UTC).timestamp())
    s = compose(account, root, stamp=stamp, identity_observer=lambda: observe_pid(os.getpid()))
    runtime = s.runtime
    identity = observe_pid(os.getpid())
    host_id, worker = uuid.uuid4().hex, None
    source_state = {"sequence": 0, "next_at": 0, "disconnect": False, "error": None, "closed_tick": False}

    class Source:
        def next(self, timeout):
            if runtime.stopped.wait(timeout):
                return None
            if source_state["sequence"] >= 3:
                if not source_state["closed_tick"]:
                    with runtime.gate:
                        s.n.now[0] += 1  # Explicit virtual-clock tick, not a fabricated fill.
                        source_state["closed_tick"] = True
                return None
            if time.monotonic() < source_state["next_at"]:
                return None
            with runtime.gate:
                s.n.now[0] += 1
                source_state["sequence"] += 1
                sequence = source_state["sequence"]
                source_state["next_at"] = time.monotonic() + config["interval_seconds"]
                result = s.frame(sequence, ("entry", "partial", "final")[sequence - 1])
                if source_state["disconnect"]:
                    result["connected"] = False
                return result

    class PresentationAuthority:
        @contextmanager
        def lease(self, enrollment, now):
            if enrollment != s.x.enrollment:
                raise ValueError("FOREIGN_TEST_ENROLLMENT")
            def current():
                return {**s.x.current(), "observed_at": now, "expires_at": now + 30}
            pin = current()
            yield SimpleNamespace(snapshot=pin, check=lambda p, t: p == current())

    def reader_factory(now):
        class Coordination:
            def read_status(self):
                result = AutonomousCoordinationRead(s.n.engine).read_status()
                packet = result["activity"]["l1"]
                # Market time is deliberately historical. Never claim live L1.
                result["activity"]["l1_state"] = "STALE" if packet else "UNAVAILABLE"
                result["activity"]["candidate"] = None
                return result
        cap = AutonomousSelectedRead(enrollment=s.x.enrollment, authority=PresentationAuthority(),
                                    clock=lambda: now, port=s.x.port, coordination=Coordination())
        class Reader:
            def read_committed(self, *args):
                with runtime.gate:
                    return cap.read_committed(*args)
            def verify(self, *args, **kwargs):
                with runtime.gate:
                    return cap.verify(*args, **kwargs)
        return Reader()

    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(16)
    port = listener.getsockname()[1]
    app, _, _ = build_app(root, {"phases": {"entry": {"enrollment": s.x.enrollment}}}, port,
                         host_id, root / (host_id + "-requests.jsonl"), reader_factory=reader_factory)
    server = uvicorn.Server(uvicorn.Config(app, lifespan="off", access_log=False, log_level="error"))

    def dispatch():
        try:
            runtime.run(Source())
        except (ValueError, OSError) as error:
            source_state["error"] = str(error)

    def control():
        nonlocal worker
        while not server.started and not server.should_exit:
            time.sleep(0.02)
        print(json.dumps({"host_id": host_id, "pid": os.getpid(), "url": f"http://127.0.0.1:{port}",
                          "mode": "DISPOSABLE_SYNTHETIC_READ_ONLY", "runtime_fixture": True}), flush=True)
        try:
            for line in sys.stdin:
                try:
                    command = strict(line)
                    if set(command) != {"action"} or observe_pid(os.getpid()) != identity:
                        raise ValueError("OWNED_FIXTURE_CONTROL_REQUIRED")
                    action = command["action"]
                    if action == "start":
                        if worker is not None:
                            raise ValueError("NO_RESTART_OR_RECOVERY_THROUGH_FIXTURE_CONTROL")
                        runtime.start(s.grant)
                        source_state["next_at"] = time.monotonic() + config["interval_seconds"]
                        worker = threading.Thread(target=dispatch, daemon=True)
                        worker.start()
                    elif action == "pause": runtime.pause()
                    elif action == "stop": runtime.stop()
                    elif action == "disconnect": source_state["disconnect"] = True
                    elif action != "status": raise ValueError("INVALID_FIXTURE_ACTION")
                    print(json.dumps({"host_id": host_id, "runtime": {"state": s.n.engine.status(),
                        "sequence": source_state["sequence"], "error": source_state["error"]}}), flush=True)
                except (ValueError, OSError) as error:
                    print(json.dumps({"host_id": host_id, "runtime": {"refused": str(error)}}), flush=True)
        finally:
            if runtime.grant is not None:
                runtime.stop()
            runtime.stopped.set()
            if worker is not None:
                worker.join(2)
                if worker.is_alive():
                    print(json.dumps({"error": "FIXTURE_WRITER_NOT_DRAINED"}), flush=True)
            server.should_exit = True

    threading.Thread(target=control, daemon=True).start()
    try:
        server.run(sockets=[listener])
    finally:
        listener.close()
        s.x.close()


if __name__ == "__main__":
    main()
