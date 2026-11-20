"""Disposable FS2/FS3 protocol harness, NOT native Windows/authority acceptance.

Executes the actual unmodified protocol classes with the module's native-loader
assignments replaced by injected ordinary-file primitives. No protected directory,
ACL, registry, issuer or Windows handle is created. Native security is not tested.
"""
import ast
import copy
import hashlib
import importlib.machinery
import importlib.util
import json
import os
import threading
import types
from contextlib import contextmanager
from pathlib import Path

from app.services.paper_financial_replay import body, digest, strict

ROOT = Path(__file__).parents[1]


def identity(path):
    stat = Path(path).stat()
    return [stat.st_dev, stat.st_ino, 0]


class Output:
    def __init__(self, root):
        self.root = Path(root)
        self.root_handle = self.root

    def write_bound(self, leaf, raw):
        with (self.root / leaf).open("xb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        return {"id": identity(self.root / leaf), "sha256": hashlib.sha256(raw).hexdigest()}

    def _verify(self):
        assert self.root.is_dir()

    def close(self):
        pass


def read_bound(output, leaf, binding):
    path = output.root / leaf
    if identity(path) != binding["id"]:
        raise ValueError("SUBSTITUTION")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != binding["sha256"]:
        raise ValueError("CORRUPTION")
    return raw, binding


def protocol_module(name, path, namespace):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    # Only module-scope dynamic native-loader statements are replaced. All class
    # and function AST nodes are retained exactly, including refusals and audits.
    retained = []
    for node in tree.body:
        targets = {n.id for n in ast.walk(node) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)} if isinstance(node, ast.Assign) else set()
        if targets & {"_spec", "s", "f", "w", "native", "Refused"}:
            continue
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Attribute) and node.value.func.attr == "exec_module":
            continue
        retained.append(node)
    tree.body = retained
    class InjectedLoader(importlib.machinery.SourceFileLoader):
        def get_code(self, fullname):
            return compile(tree, str(path), "exec")

    loader = InjectedLoader(name, str(path))
    module = importlib.util.module_from_spec(importlib.util.spec_from_loader(name, loader))
    module.__dict__.update(namespace)
    module.__file__ = str(path)
    loader.exec_module(module)
    return module


class DurablePins:
    def __init__(self, path, now):
        self.path, self.now = path, now

    def current(self):
        return strict(self.path.read_text(encoding="utf-8"))

    def advance(self, old, new):
        assert body(old) == body(self.current())
        self.save(new)

    def save(self, value):
        temp = self.path.with_suffix(".tmp")
        with temp.open("w", encoding="utf-8") as stream:
            stream.write(body(value))
            stream.flush()
            os.fsync(stream.fileno())
        temp.replace(self.path)

    def check_clock(self, timestamp):
        if timestamp != self.now():
            raise ValueError("CLOCK")


def fs_bundle(root, manifest, now, *, provision=True):
    roots = [root / name for name in ("financial", "projection", "pins")]
    for path in roots:
        if provision:
            path.mkdir()
    s = types.SimpleNamespace(read_bound=read_bound)
    native = types.SimpleNamespace(file_identity=identity)
    w = types.SimpleNamespace(WindowsOutput=Output)
    f = protocol_module("injected_fs2", ROOT / "scripts/volume_inspector/financial_record_store.py",
                        {"s": s, "native": native, "w": w, "Refused": ValueError})
    fs3 = protocol_module("injected_fs3", ROOT / "scripts/volume_inspector/financial_reporting.py", {"f": f})
    projection = fs3.ProjectionTarget(str(roots[1]), identity(roots[1]))
    projection._read = lambda leaf, binding: f.FinancialRecordStore._read(projection, leaf, binding)
    pins = DurablePins(roots[2] / "pin.json", now)
    output = Output(roots[0])
    if provision:
        inception = output.write_bound("inception.json", f.encoded(manifest))
        pins.save({"schema": "FS2_TEST_PIN_V1", "root": identity(roots[0]), "inception": inception,
                   "epoch": manifest["epoch"], "entries": []})
    lock = threading.RLock()

    def reopen():
        store = f.FinancialRecordStore.__new__(f.FinancialRecordStore)
        store.trust, store.output, store.projection, store.poisoned = pins, Output(roots[0]), projection, False

        @contextmanager
        def guard():
            with lock:
                if store.poisoned:
                    raise ValueError("UNKNOWN")
                yield
        store.guard = guard
        return store

    return reopen(), projection, reopen


class Admission:
    """Durable ordinary-file test journal; not protected authority or C1 proof."""
    def __init__(self, path):
        self.path, self.lock = path, threading.RLock()
        if not path.exists():
            self.save({"closed": False, "operations": {}})

    def load(self):
        return json.loads(self.path.read_text(encoding="utf-8"))

    def save(self, value):
        temp = self.path.with_suffix(".tmp")
        with temp.open("w", encoding="utf-8") as stream:
            stream.write(body(value))
            stream.flush()
            os.fsync(stream.fileno())
        temp.replace(self.path)

    @contextmanager
    def lease(self, account, epoch):
        with self.lock:
            if self.load()["closed"]:
                raise ValueError("ADMISSION_CLOSED")
            yield

    def verify_owner(self, owner, account, epoch):
        return {"verified": True, "binding": digest({"owner": owner, "account_id": account, "epoch": epoch})}

    def lookup(self, operation, request_digest):
        return self.load()["operations"].get(operation)

    def has_unresolved(self):
        return any(row["status"] != "ACKNOWLEDGED" for row in self.load()["operations"].values())

    def prepare(self, operation, request_digest, context):
        self.finish(operation, {"status": "PENDING", "request_digest": request_digest, "context": context})

    def finish(self, operation, result):
        value = self.load()
        value["operations"][operation] = result
        self.save(value)

    def mark_unknown(self, operation, request_digest, reason):
        previous = self.lookup(operation, request_digest)
        self.finish(operation, {"status": "UNKNOWN", "request_digest": request_digest, "reason": reason, "previous": previous})


class RankingAuthority:
    def __init__(self, admission, bundle):
        self.admission, self.current = admission, digest(bundle)

    def replace(self, bundle):
        with self.admission.lock:
            self.current = digest(bundle)

    def verify_current(self, bundle, *, now):
        if digest(bundle) != self.current:
            raise ValueError("RANKING_REPLACED")
        return {"schema": "QD_RANKING_VERIFIED_V1", "verified": True, "binding": digest(bundle), "receipt_id": "FIXTURE_AUTHORITY"}


class ExecutionAuthority:
    def __init__(self, instrument, quote):
        self.allowed = {digest({"instrument": instrument, "quote": quote})}

    def verify(self, evidence, *, now):
        if digest(evidence) not in self.allowed:
            raise ValueError("EXECUTION_UNVERIFIED")
        return {"schema": "QD_EXECUTION_VERIFIED_V1", "verified": True, "binding": digest(evidence),
                "receipt_id": "FIXTURE_EXECUTION_" + digest(evidence)}


class Manual:
    def __init__(self):
        self.approvals, self.used = {}, set()

    def grant(self, context):
        ident = "fixture-approval-" + str(len(self.approvals))
        self.approvals[ident] = copy.deepcopy(context)
        return ident

    def verify_and_reserve(self, approval, context, *, now):
        if approval in self.used or self.approvals.get(approval) != context:
            raise ValueError("APPROVAL_REFUSED")
        self.used.add(approval)
        return {"approved": True, "binding": digest(context), "receipt_id": approval, "expires_at": now + 15}
