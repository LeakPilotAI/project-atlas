"""In-memory cleanup regressions. No native copy, subprocess, port or fixture."""
import io
import unittest
from types import SimpleNamespace

from support_native_cleanup import finish_controller


class CleanupTests(unittest.TestCase):
    def fixture(self, *, closed=False, running=False):
        events = []
        out, err = io.BytesIO(b"terminal output"), io.BytesIO(b"failure evidence")
        if closed:
            out.close(); err.close()
        def communicate(*, timeout):
            self.assertEqual(timeout, 120)
            self.assertIsNone(child.stdin)
            events.append("communicate")
            return b"drained", b"retained error"
        child = SimpleNamespace(stdin=io.BytesIO(), stdout=out, stderr=err,
            poll=lambda: None if running else 0, communicate=communicate,
            _handle=SimpleNamespace(Close=lambda: events.append("handle closed")))
        store = SimpleNamespace(close=lambda: events.append("store closed"))
        return child, store, events

    def test_communicated_closed_streams_use_original_captured_bytes(self):
        child, store, events = self.fixture(closed=True)
        finish_controller(child, store, captured=(b"original", b"original error"),
                          record=lambda a, b: events.append((a, b)))
        self.assertEqual(events, [(b"original", b"original error"), "handle closed", "store closed"])

    def test_uncaptured_open_streams_are_preserved(self):
        child, store, events = self.fixture()
        finish_controller(child, store, record=lambda a, b: events.append((a, b)))
        self.assertEqual(events[0], (b"terminal output", b"failure evidence"))
        self.assertEqual(events[-2:], ["handle closed", "store closed"])

    def test_uncaptured_closed_streams_refuse_without_false_empty_success(self):
        child, store, events = self.fixture(closed=True)
        with self.assertRaisesRegex(ValueError, "EVIDENCE_UNAVAILABLE"):
            finish_controller(child, store, record=lambda a, b: self.fail("No invented evidence"))
        self.assertEqual(events, ["handle closed", "store closed"])

    def test_diagnostic_write_failure_still_closes_all_owned_resources(self):
        child, store, events = self.fixture()
        def failed_writer(*args):
            raise OSError("synthetic diagnostic failure")
        with self.assertRaisesRegex(OSError, "diagnostic failure"):
            finish_controller(child, store, record=failed_writer)
        self.assertEqual(events, ["handle closed", "store closed"])

    def test_running_child_receives_eof_and_terminal_errors_are_retained(self):
        child, store, events = self.fixture(running=True)
        finish_controller(child, store, record=lambda a, b: events.append((a, b)))
        self.assertEqual(events, ["communicate", (b"drained", b"retained error"), "handle closed", "store closed"])

    def test_invalid_capture_refuses_and_still_closes(self):
        child, store, events = self.fixture(closed=True)
        with self.assertRaisesRegex(ValueError, "CAPTURED_TERMINAL_BYTES"):
            finish_controller(child, store, captured=(None, b""), record=lambda *a: self.fail("No bad evidence"))
        self.assertEqual(events, ["handle closed", "store closed"])


if __name__ == "__main__":
    unittest.main()
