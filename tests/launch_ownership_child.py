"""Disposable stdin/EOF fixture. No Atlas imports, ports, provider or account."""

import argparse
import json
import os
import subprocess
import sys
import threading


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--nonce", required=True)
    p.add_argument("--role", required=True)
    p.add_argument("--unexpected-child", action="store_true")
    args = p.parse_args()
    watchdog = threading.Timer(45, lambda: os._exit(74))
    watchdog.daemon = True
    watchdog.start()
    child = None
    try:
        if args.unexpected_child:
            child = subprocess.Popen(
                [
                    sys._base_executable,
                    "-I",
                    "-B",
                    __file__,
                    "--nonce",
                    args.nonce,
                    "--role",
                    "unexpected_child",
                ],
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        print(
            json.dumps({"pid": os.getpid(), "nonce": args.nonce, "role": args.role}),
            flush=True,
        )
        # Only the retained parent's private pipe controls this fixture lifetime.
        if sys.stdin.buffer.read(1):
            raise RuntimeError("EOF_ONLY_DISPOSABLE_CONTROL")
    finally:
        if child is not None:
            child.stdin.close()
            child.wait(timeout=5)
        watchdog.cancel()


if __name__ == "__main__":
    main()
