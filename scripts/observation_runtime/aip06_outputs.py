"""Guarded native evidence and legacy-output adapters; no transport or authority."""

import hashlib
import ntpath
import threading

from app.services.paper_financial_replay import body, digest, strict

from scripts.observation_runtime.aip06_harness import ROOTS, SCOPE_HASH, need, path_for


class EvidenceOutput:
    """Create-new records with native readback; never overwrite failure evidence."""

    def __init__(self, guard, *, directory, producer):
        guard.locate(directory)
        need(
            type(producer) is dict
            and set(producer) == {"session", "owner", "role", "source_pins"}
            and producer["owner"] in guard.resources.state["owners"]
            and type(producer["source_pins"]) is dict
            and producer["source_pins"]
            and producer["session"],
            "OUTPUT_PRODUCER_IDENTITY",
        )
        self.guard, self.directory, self.producer = (
            guard,
            directory,
            strict(body(producer)),
        )
        self.sequence, self.head = 0, digest(self.producer)
        self.lock = threading.RLock()
        self.failed = False

    def append(self, value):
        with self.lock:
            need(not self.failed, "OUTPUT_WRITER_UNKNOWN")
            self.guard.check()
            record = {
                "schema": "AIP06_EVIDENCE_RECORD_V1",
                "scope": SCOPE_HASH,
                "producer": self.producer,
                "sequence": self.sequence + 1,
                "parent": self.head,
                "payload": value,
            }
            raw = body(record).encode()
            need(len(raw) <= 1024**2, "EVIDENCE_OUTPUT_CAPACITY")
            path = ntpath.join(self.directory, f"{self.sequence + 1:08d}.json")
            self.failed = True
            self.guard.write(path, raw)
            need(
                self.guard.io.read_bytes(path) == raw, "EVIDENCE_OUTPUT_NATIVE_READBACK"
            )
            self.sequence += 1
            self.head = digest(record)
            self.failed = False
            return {
                "path": path,
                "sha256": hashlib.sha256(raw).hexdigest(),
                "head": self.head,
                "sequence": self.sequence,
            }

    def recover(self, *, expected_head):
        need(self.sequence == 0, "COLD_OUTPUT_RECOVERY_ONLY")
        names = self.guard.io.names(self.directory, maximum=8192)
        need(
            names == [f"{i:08d}.json" for i in range(1, len(names) + 1)],
            "OUTPUT_NAMESPACE_CONFLICT",
        )
        records = []
        head = digest(self.producer)
        for index, name in enumerate(names, 1):
            raw = self.guard.io.read_bytes(ntpath.join(self.directory, name))
            record = strict(raw.decode())
            need(
                body(record).encode() == raw
                and set(record)
                == {"schema", "scope", "producer", "sequence", "parent", "payload"}
                and record["schema"] == "AIP06_EVIDENCE_RECORD_V1"
                and record["scope"] == SCOPE_HASH
                and record["producer"] == self.producer
                and record["sequence"] == index
                and record["parent"] == head,
                "OUTPUT_PROVENANCE_OR_REVISION_CONFLICT",
            )
            head = digest(record)
            records.append(record)
        need(head == expected_head, "OUTPUT_RESTART_HEAD_MISMATCH")
        return records  # Never adopts an old output directory as a fresh writer.


class BoundedOutput:
    """File-like pytest/stdout sink. Buffering is bounded and flush is guarded.

    Every chunk is a fresh immutable record. There is no raw file descriptor,
    unlink, cache, implicit directory creation, or outside-path fallback.
    """

    encoding = "utf-8"
    errors = "strict"

    def __init__(self, output, *, stream, maximum_bytes=1024**2, chunk_bytes=32768):
        need(
            stream in ("stdout", "stderr", "junit", "diagnostic")
            and type(maximum_bytes) is int
            and 0 < chunk_bytes <= 65536
            and chunk_bytes <= maximum_bytes <= 1024**2,
            "BOUNDED_OUTPUT_CONFIGURATION",
        )
        self.output, self.stream, self.maximum, self.chunk = (
            output,
            stream,
            maximum_bytes,
            chunk_bytes,
        )
        self.buffer = bytearray()
        self.total = 0
        self.closed = False
        self.lock = threading.RLock()

    def write(self, value):
        need(type(value) is str and not self.closed, "OPEN_TEXT_OUTPUT_REQUIRED")
        raw = value.encode("utf8")
        with self.lock:
            need(self.total + len(raw) <= self.maximum, "OUTPUT_STREAM_CAPACITY")
            self.total += len(raw)
            self.buffer.extend(raw)
            while len(self.buffer) >= self.chunk:
                self._emit(self.chunk)
        return len(value)

    def _emit(self, count):
        raw = bytes(self.buffer[:count])
        # UTF8 bytes are losslessly encoded rather than splitting Unicode text.
        import base64

        self.output.append(
            {
                "schema": "AIP06_STREAM_CHUNK_V1",
                "stream": self.stream,
                "bytes": len(raw),
                "base64": base64.b64encode(raw).decode("ascii"),
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
        )
        del self.buffer[:count]

    def flush(self):
        with self.lock:
            need(not self.closed, "OUTPUT_ALREADY_CLOSED")
            if self.buffer:
                self._emit(len(self.buffer))

    def close(self):
        if not self.closed:
            self.flush()
            self.closed = True

    def isatty(self):
        return False

    def writable(self):
        return not self.closed

    def fileno(self):
        raise ValueError("NO_UNGUARDED_OUTPUT_DESCRIPTOR")


class FixtureDirectories:
    """Create-new tmp_path replacement for the exact approved root map."""

    def __init__(self, guard):
        self.guard = guard
        self.counts = {}

    def create(self, alias, label):
        need(
            alias in ROOTS and type(label) is str and label and len(label) <= 64,
            "DECLARED_FIXTURE_DIRECTORY",
        )
        number = self.counts.get(alias, 0) + 1
        path = path_for(alias, label + "-" + str(number))
        self.guard.mkdir(path)
        self.counts[alias] = number
        return path

    def remove(self, *args, **kwargs):
        raise ValueError("PRESERVE_NATIVE_FIXTURE_EVIDENCE_NO_DELETE")


class LegacyProbeAdapter:
    """Retain legacy field names only after independently verified native cuts."""

    CASES = ("direct-supervisor", "direct-worker", "direct-unexpected")

    def __init__(self, controller, output):
        self.controller, self.output = controller, output

    def run(self, root, cases):
        need(
            root == ROOTS["L"]
            and type(cases) in (list, tuple)
            and cases
            and len(cases) == len(set(cases))
            and set(cases) <= set(self.CASES),
            "LEGACY_PROBE_SCOPE_OR_UNSUPPORTED_CASE",
        )
        results = []
        for name in cases:
            before = self.controller.clock()
            result = self.controller.probe_case(name)
            need(
                type(result) is dict
                and set(result)
                == {"case", "ready", "claims", "exit", "cleanup", "refusal", "source"}
                and result["case"] == name
                and result["source"]["scope"] == SCOPE_HASH
                and result["source"]["session"] == self.output.producer["session"],
                "LEGACY_PROBE_SOURCE_IDENTITY",
            )
            self.controller.verify_probe_result(result)
            need(
                self.controller.clock() - before <= 180 * 10**9, "LEGACY_PROBE_DEADLINE"
            )
            legacy = {
                "case": name,
                "passed": True,
                "seconds": (self.controller.clock() - before) / 10**9,
                "ready": result["ready"],
                "launch_pid": result["ready"]["pid"],
                "handles_closed": result["cleanup"]["handles_closed"],
                "final_job_pids": result["cleanup"]["job_members"],
                "forced_cleanup": False,
                "observations": result["source"],
                "exit": result["exit"],
            }
            self.output.append(
                {
                    "schema": "AIP06_LEGACY_PROBE_V1",
                    "original": legacy,
                    "verified_source": result,
                }
            )
            results.append(legacy)
        summary = {
            "passed": True,
            "cases": results,
            "installed_launches": 0,
            "selection_mutations": 0,
            "native_acceptance": False,
            "startup_authorized": False,
        }
        self.output.append(
            {"schema": "AIP06_LEGACY_PROBE_SUMMARY_V1", "original": summary}
        )
        return summary
