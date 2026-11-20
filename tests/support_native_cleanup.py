"""Test-owned terminal evidence/cleanup; never a runtime or process starter."""


def collect_terminal(child, captured=None):
    if captured is not None:
        if type(captured) is not tuple or len(captured) != 2 or any(type(v) is not bytes for v in captured):
            raise ValueError("EXACT_CAPTURED_TERMINAL_BYTES_REQUIRED")
        return captured
    if child.poll() is None:
        if child.stdin is not None:
            child.stdin.close()
            child.stdin = None
        return child.communicate(timeout=120)
    if any(stream is None or stream.closed for stream in (child.stdout, child.stderr)):
        raise ValueError("TERMINAL_EVIDENCE_UNAVAILABLE_NO_EMPTY_FALLBACK")
    return child.stdout.read(), child.stderr.read()


def finish_controller(child, store, *, captured=None, record):
    """Always close owned resources, preserving diagnostics and real failures."""
    try:
        record(*collect_terminal(child, captured))
    finally:
        try:
            for stream in (child.stdin, child.stdout, child.stderr):
                if stream is not None:
                    stream.close()
        finally:
            try:
                child._handle.Close()
            finally:
                store.close()
