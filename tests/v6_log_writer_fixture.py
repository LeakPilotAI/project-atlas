"""Confined source-Python fixture. No installed application or providers."""

import ctypes as C
import json
import os
import sys
import time
from pathlib import Path

if len(sys.argv) != 4 or sys.argv[1] != "--disposable-log-writer":
    raise SystemExit("DISPOSABLE_ONLY")
root = Path(sys.argv[2]).absolute()
repo = Path(__file__).resolve().parents[1]
relative = root.relative_to(repo / "logs/diagnostics")
if len(relative.parts) != 2 or not relative.parts[0].startswith(
    "qd-v6-worker-log-native-"
):
    raise SystemExit("CONFINED_FRESH_FIXTURE_REQUIRED")
if any(p.is_symlink() or p.is_junction() for p in (root, *root.parents)):
    raise SystemExit("FIXTURE_REPARSE_REFUSED")
sys.path.insert(0, str(repo))
from scripts.acceptance_harness_v6.worker_log import publish_worker_logs
from scripts.observation_runtime.launch_ownership_windows import NativeQueries

mode = sys.argv[3]
streams = []
try:
    if mode != "missing":
        path = root / "worker-stdout.log"
        if mode == "exclusive":
            import msvcrt

            native = NativeQueries()
            h = native.k.CreateFileW(str(path), 0x40000000, 0, None, 1, 0x80, None)
            if h in (None, C.c_void_p(-1).value):
                raise C.WinError(C.get_last_error())
            stdout = os.fdopen(
                msvcrt.open_osfhandle(h, os.O_WRONLY),
                "w",
                buffering=1,
                encoding="utf-8",
            )
        else:
            stdout = path.open("x", buffering=1, encoding="utf-8")
        stderr = (root / "worker-stderr.log").open("x", buffering=1, encoding="utf-8")
        streams = [stdout, stderr]
        if mode == "exclusive":
            # fdopen exposes an integer .name. Give the strict publisher the
            # actual pathname while retaining the same exclusive native FD.
            from types import SimpleNamespace

            named = SimpleNamespace(name=str(path), fileno=stdout.fileno)
            publish_worker_logs(root, named, stderr)
        else:
            publish_worker_logs(root, stdout, stderr)
    (root / "fixture-ready.json").write_text(
        json.dumps({"ready": True, "pid": os.getpid()})
    )
    deadline = time.monotonic() + 20
    for index in range(1, 21):
        command_path = root / f"cmd-{index:03d}.json"
        while not command_path.with_suffix(".ready").exists():
            if time.monotonic() > deadline:
                raise TimeoutError("FIXTURE_COMMAND_DEADLINE")
            time.sleep(0.003)
        command = json.loads(command_path.read_bytes())
        action = command["action"]
        if action == "append":
            stdout.write(command["text"])
            if command.get("flush", True):
                stdout.flush()
        elif action == "many":
            for line in range(command["count"]):
                stdout.write(f"line-{line}\n")
                stdout.flush()
                time.sleep(0.002)
        elif action == "flush":
            stdout.flush()
        elif action == "truncate":
            stdout.flush()
            stdout.seek(0)
            stdout.truncate()
            stdout.flush()
        elif action == "overwrite":
            stdout.seek(0)
            stdout.write(command["text"])
            stdout.flush()
        elif action in ("replace", "remove"):
            stdout.close()
            if action == "replace":
                path.rename(root / "replaced-original.log")
                stdout = path.open("x", encoding="utf-8")
                streams.append(stdout)
                stdout.write("replacement\n")
                stdout.flush()
            else:
                path.unlink()
        elif action == "abrupt":
            os._exit(7)
        elif action != "exit":
            raise ValueError("UNKNOWN_FIXTURE_ACTION")
        (root / f"done-{index:03d}.json").write_text(
            json.dumps({"action": action, "pid": os.getpid()})
        )
        if action == "exit":
            break
    else:
        raise ValueError("FIXTURE_COMMAND_CAPACITY")
except Exception:
    import traceback

    (root / "fixture-error.txt").write_text(traceback.format_exc(), encoding="utf-8")
    raise
finally:
    for stream in streams:
        stream.close()
