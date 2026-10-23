"""Synthetic persistence faults; never instantiate production journal singletons."""
from __future__ import annotations

import ast
import asyncio
import builtins
import errno
import json
from pathlib import Path
from types import ModuleType

import app
import pytest

ROOT = Path(__file__).resolve().parents[1]


def source_module(relative, singleton):
    path = Path(app.__file__).resolve().parents[2] / relative
    tree = ast.parse(path.read_text(encoding="utf-8"))
    tree.body = [node for node in tree.body if not (
        isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == singleton for target in node.targets)
    )]
    module = ModuleType("synthetic_persistence")
    module.__file__ = str(path)
    # Execute only reviewed repository source, omitting the production singleton.
    exec(compile(tree, str(path), "exec"), module.__dict__)  # noqa: S102
    return module


@pytest.fixture
def journal(tmp_path):
    module = source_module("backend/app/services/paper_journal.py", "paper_journal")
    module.JOURNAL_PATH = tmp_path / "paper.jsonl"
    module.CANDIDATE_PATH = tmp_path / "candidates.jsonl"
    return module, module.PaperJournal()


def open_trade(journal):
    return asyncio.run(journal.open_trade(
        symbol="BTC", side="LONG", entry=100, stop=99, tp1=102, tp2=103,
    ))


def test_paper_fsync_failure_never_acknowledges_or_commits_memory(journal, monkeypatch):
    module, owner = journal
    original = OSError(errno.ENOSPC, "synthetic disk full")

    def fail(_fd):
        raise original

    monkeypatch.setattr(module.os, "fsync", fail)
    with pytest.raises(OSError) as failure:
        open_trade(owner)
    assert failure.value is original
    assert owner.list_open() == []
    before = module.JOURNAL_PATH.read_bytes()
    with pytest.raises(OSError) as replay:
        open_trade(owner)
    assert replay.value is original
    assert module.JOURNAL_PATH.read_bytes() == before
    with pytest.raises(OSError):
        owner.flush()


@pytest.mark.parametrize("operation", ["update", "be", "adaptive", "close", "interrupt"])
def test_paper_failed_write_keeps_confirmed_state(journal, monkeypatch, operation):
    _module, owner = journal
    identity = open_trade(owner)
    before = json.loads(json.dumps(owner._open))
    original = OSError("synthetic flush failure")

    def fail(*_args):
        raise original

    monkeypatch.setattr(owner, "_append", fail)
    with pytest.raises(OSError):
        if operation == "update":
            owner.update_excursion(identity, 102, force=True)
        elif operation == "be":
            owner.note_be_armed(identity, 100)
        elif operation == "adaptive":
            owner.note_adaptive_exit(identity, working_stop=100, working_target=104,
                                     stage="TRAIL", policy_version="synthetic", reason="test")
        elif operation == "close":
            asyncio.run(owner.close_trade(identity, exit_price=102, result="WIN"))
        else:
            owner.interrupt_open_for_shutdown()
    assert owner._open == before


def test_manual_fsync_failure_preserves_original_and_old_snapshot(tmp_path, monkeypatch):
    from app.trading_core import perp_manual_state_store as module

    path = tmp_path / "state.json"
    owner = module.ManualPerpStateStore(path)
    owner.save(plans=[{"status": "OLD"}], setup_history=[])
    before = path.read_bytes()
    original = OSError("synthetic fsync failure")

    def fail(_fd):
        raise original

    monkeypatch.setattr(module.os, "fsync", fail)
    with pytest.raises(OSError) as failure:
        owner.save(plans=[{"status": "NEW"}], setup_history=[])
    assert failure.value is original
    assert path.read_bytes() == before
    assert owner.pending_path.exists(), "Failed publication evidence must be retained"


def test_manual_service_does_not_return_failed_plan(tmp_path, monkeypatch):
    module = source_module("backend/app/services/perp_manual_service.py", "perp_manual_service")
    owner = module.PerpManualService(state_path=tmp_path / "state.json")
    owner.last_snapshot["markets"] = [{"symbol": "BTC", "price": 100}]
    before = json.loads(json.dumps(owner.last_snapshot))
    owner._confirmed_snapshot = before
    original = OSError("synthetic required-state failure")

    def fail(**_kwargs):
        raise original

    monkeypatch.setattr(owner._state_store, "save", fail)
    with pytest.raises(OSError) as failure:
        owner.create_plan(symbol="BTC", side="LONG", reference_price=100)
    assert failure.value is original
    assert owner.last_snapshot == before
    assert owner.last_refresh_at is None
    with pytest.raises(OSError):
        owner.create_plan(symbol="BTC", side="LONG", reference_price=100)
    with pytest.raises(OSError):
        asyncio.run(owner.stop())


def test_manual_pending_intent_excludes_concurrent_publication(tmp_path, monkeypatch):
    from app.trading_core import perp_manual_state_store as module

    path = tmp_path / "state.json"
    first, second = module.ManualPerpStateStore(path), module.ManualPerpStateStore(path)
    real_write = module.write_flushed
    refused = []

    def interleave(handle, value):
        if Path(handle.name) == first.pending_path:
            with pytest.raises(module.ManualPerpStateError):
                second.save(plans=[{"status": "SECOND"}], setup_history=[])
            with pytest.raises(module.ManualPerpStateError):
                second.load()
            refused.append(True)
        return real_write(handle, value)

    monkeypatch.setattr(module, "write_flushed", interleave)
    first.save(plans=[{"status": "FIRST"}], setup_history=[])
    assert refused == [True]
    assert first.load()["plans"] == [{"status": "FIRST"}]


def test_manual_corrupt_recovery_cannot_be_overwritten(tmp_path):
    module = source_module("backend/app/services/perp_manual_service.py", "perp_manual_service")
    path = tmp_path / "state.json"
    path.write_text("{broken", encoding="utf-8")
    owner = module.PerpManualService(state_path=path)
    owner.last_snapshot["markets"] = [{"symbol": "BTC", "price": 100}]
    with pytest.raises(Exception, match="unreadable"):
        owner.create_plan(symbol="BTC", side="LONG", reference_price=100)
    assert path.read_text() == "{broken"


def test_successful_paper_replay_stays_single_open_and_close(journal):
    module, owner = journal
    identity = open_trade(owner)
    assert open_trade(owner) == identity
    first = asyncio.run(owner.close_trade(identity, exit_price=102, result="WIN"))
    assert asyncio.run(owner.close_trade(identity, exit_price=103, result="WIN")) == first
    rows = [json.loads(line) for line in module.JOURNAL_PATH.read_text().splitlines()]
    assert sum(row["event"] == "open" for row in rows) == 1
    assert sum(row["event"] == "close" for row in rows) == 1


class FaultFile:
    def __init__(self, wrapped, fault, error):
        self.wrapped, self.fault, self.error = wrapped, fault, error

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return self.wrapped.__exit__(*args)

    def write(self, value):
        if self.fault == "partial":
            self.wrapped.write(value[:len(value) // 2])
            return len(value) // 2
        if self.fault in ("write", "disk_full", "interrupted"):
            raise self.error
        return self.wrapped.write(value)

    def flush(self):
        if self.fault == "flush":
            raise self.error
        return self.wrapped.flush()

    def fileno(self):
        return self.wrapped.fileno()


@pytest.mark.parametrize("store_kind", ["paper", "manual"])
@pytest.mark.parametrize("fault", ["write", "partial", "flush", "disk_full", "interrupted"])
def test_fault_boundaries_never_return_success(journal, tmp_path, monkeypatch, store_kind, fault):
    from app.trading_core.perp_manual_state_store import ManualPerpStateStore

    module, paper = journal
    manual = ManualPerpStateStore(tmp_path / "state.json")
    path = module.JOURNAL_PATH if store_kind == "paper" else manual.path
    original = KeyboardInterrupt("synthetic crash") if fault == "interrupted" else OSError(
        errno.ENOSPC if fault == "disk_full" else errno.EIO, "synthetic " + fault,
    )
    real_open = Path.open

    def faulty_open(target, mode="r", *args, **kwargs):
        handle = real_open(target, mode, *args, **kwargs)
        if (target == path and mode == "a") or (store_kind == "manual" and mode == "x"):
            return FaultFile(handle, fault, original)
        return handle

    monkeypatch.setattr(Path, "open", faulty_open)
    invoke = (lambda: open_trade(paper)) if store_kind == "paper" else (
        lambda: manual.save(plans=[{"status": "ENTERED"}], setup_history=[])
    )
    with pytest.raises((OSError, KeyboardInterrupt)) as failure:
        invoke()
    if fault != "partial":
        assert failure.value is original
    else:
        assert "Incomplete persistence write" in str(failure.value)
    sizes = {p.name: p.stat().st_size for p in tmp_path.iterdir() if p.is_file()}
    with pytest.raises((OSError, KeyboardInterrupt)) as replay:
        invoke()
    assert replay.value is failure.value
    assert sizes == {p.name: p.stat().st_size for p in tmp_path.iterdir() if p.is_file()}
    if store_kind == "paper":
        assert paper.list_open() == []
    else:
        assert not path.exists()
        assert manual.pending_path.exists()


@pytest.mark.parametrize("boundary", ["replace", "directory_sync"])
def test_manual_publication_failure_is_not_acknowledged(tmp_path, monkeypatch, boundary):
    from app.trading_core import perp_manual_state_store as module

    path = tmp_path / "state.json"
    owner = module.ManualPerpStateStore(path)
    owner.save(plans=[{"status": "OLD"}], setup_history=[])
    original = OSError("synthetic " + boundary)
    calls = []

    def fail(*_args):
        calls.append(_args)
        if boundary == "directory_sync" and len(calls) == 1:
            return
        raise original

    monkeypatch.setattr(module.os if boundary == "replace" else module,
                        "replace" if boundary == "replace" else "sync_parent", fail)
    with pytest.raises(OSError) as failure:
        owner.save(plans=[{"status": "NEW"}], setup_history=[])
    assert failure.value is original
    # A failure after replace is an UNKNOWN commit, not evidence the old file survived.
    assert json.loads(path.read_text())["plans"][0]["status"] == (
        "OLD" if boundary == "replace" else "NEW"
    )
    with pytest.raises(OSError):
        owner.save(plans=[], setup_history=[])
    with pytest.raises(module.ManualPerpStateError):
        module.ManualPerpStateStore(path).load()
    assert owner.pending_path.exists()


def test_restart_refuses_partial_paper_tail(journal):
    module, _owner = journal
    module.JOURNAL_PATH.write_text('{"event":"open"', encoding="utf-8")
    restarted = module.PaperJournal()
    before = module.JOURNAL_PATH.read_bytes()
    with pytest.raises(OSError):
        open_trade(restarted)
    assert module.JOURNAL_PATH.read_bytes() == before


@pytest.mark.parametrize("filename", ["state.json.tmp", "state.json.synthetic.tmp"])
def test_manual_restart_retains_unresolved_temporary_evidence(tmp_path, filename):
    from app.trading_core.perp_manual_state_store import (
        ManualPerpStateError,
        ManualPerpStateStore,
    )

    evidence = tmp_path / filename
    evidence.write_text("interrupted", encoding="utf-8")
    owner = ManualPerpStateStore(tmp_path / "state.json")
    with pytest.raises(ManualPerpStateError):
        owner.load()
    with pytest.raises(ManualPerpStateError):
        owner.save(plans=[], setup_history=[])
    assert evidence.read_text() == "interrupted"


def test_manual_identical_snapshot_replay_is_format_compatible(tmp_path):
    from app.trading_core.perp_manual_state_store import ManualPerpStateStore

    path = tmp_path / "state.json"
    owner = ManualPerpStateStore(path)
    owner.save(plans=[{"status": "ENTERED"}], setup_history=[])
    before = path.read_bytes()
    owner.save(plans=[{"status": "ENTERED"}], setup_history=[])
    assert path.read_bytes() == before
    assert owner.load()["version"] == 1
    assert not list(tmp_path.glob("*.tmp"))


def test_shutdown_outcome_receives_original_persistence_failure(journal, monkeypatch):
    from types import SimpleNamespace

    from app.core.shutdown import ShutdownReport

    module, owner = journal
    original = OSError("synthetic shutdown fsync")

    def fail(_fd):
        raise original

    monkeypatch.setattr(module.os, "fsync", fail)
    with pytest.raises(OSError):
        open_trade(owner)

    async def scenario():
        report = ShutdownReport(timeout=0.2)

        async def cleanup():
            owner.flush()

        with pytest.raises(OSError) as failure:
            await report.run("paper", cleanup)
        assert failure.value is original

        async def independent_cleanup():
            return None

        await report.run("independent", independent_cleanup)
        logger = SimpleNamespace(info=lambda *_a, **_k: None, error=lambda *_a, **_k: None)
        with pytest.raises(builtins.BaseExceptionGroup) as outcome:
            report.finish(logger)
        assert report.outcome == "INCOMPLETE"
        assert outcome.value.exceptions == (original,)

    asyncio.run(scenario())


def test_uncertain_close_retry_is_refused_then_restart_reconfirms_without_duplicate(journal, monkeypatch):
    module, owner = journal
    identity = open_trade(owner)
    real_write = module.write_flushed
    original = OSError("synthetic lost close acknowledgement")

    def fail_after_close(handle, value):
        real_write(handle, value)
        if json.loads(value)["event"] == "close":
            raise original

    monkeypatch.setattr(module, "write_flushed", fail_after_close)
    with pytest.raises(OSError) as failure:
        asyncio.run(owner.close_trade(identity, exit_price=102, result="WIN"))
    assert failure.value is original
    before = module.JOURNAL_PATH.read_bytes()
    owner.reload()
    with pytest.raises(OSError):
        asyncio.run(owner.close_trade(identity, exit_price=102, result="WIN"))
    assert module.JOURNAL_PATH.read_bytes() == before
    restarted = module.PaperJournal()
    recovered = asyncio.run(restarted.close_trade(identity, exit_price=103, result="WIN"))
    assert recovered["actual_exit_price"] == 102
    assert module.JOURNAL_PATH.read_bytes() == before


def test_native_directory_sync_policy_and_posix_failure(monkeypatch, tmp_path):
    from types import SimpleNamespace

    from app.core import durable_io

    real_name = durable_io.os.name
    # Windows has no implemented directory-fsync guarantee; do not call it native PASS.
    durable_io.sync_parent(tmp_path / "fixture")
    calls = []
    original = OSError("synthetic directory fsync")

    def fail(fd):
        calls.append(("fsync", fd))
        raise original

    fake = SimpleNamespace(name="posix", O_RDONLY=0, O_DIRECTORY=1,
                           open=lambda *_a: 42, fsync=fail,
                           close=lambda fd: calls.append(("close", fd)))
    monkeypatch.setattr(durable_io, "os", fake)
    with pytest.raises(OSError) as failure:
        durable_io.sync_parent(tmp_path / "fixture")
    assert failure.value is original
    assert calls == [("fsync", 42), ("close", 42)]
    assert real_name in ("nt", "posix")


@pytest.mark.parametrize("method", ["acknowledge", "enter", "close"])
def test_manual_action_failure_rolls_back_and_refuses_replay(tmp_path, monkeypatch, method):
    module = source_module("backend/app/services/perp_manual_service.py", "perp_manual_service")
    owner = module.PerpManualService(state_path=tmp_path / "state.json")
    setup = {"setup_key": "BTC:LONG", "symbol": "BTC", "side": "LONG", "entry_price": 100,
             "status": "ENTERED", "alert_eligible": True}
    owner.last_snapshot["setups"] = [dict(setup)]
    owner.last_snapshot["plans"] = [dict(setup)] if method == "close" else []
    owner._persist_state()
    before = json.loads(json.dumps(owner.last_snapshot))
    original = OSError("synthetic manual action persistence failure")

    def fail(**_kwargs):
        raise original

    monkeypatch.setattr(owner._state_store, "save", fail)
    monkeypatch.setattr(module, "enter_setup", lambda *_a, **_k: {
        **setup, "entered_at": "synthetic", "entry_price": 100,
    })
    monkeypatch.setattr(module, "close_plan", lambda *_a, **_k: {**setup, "status": "CLOSED"})
    invoke = {"acknowledge": lambda: owner.acknowledge_alert("BTC:LONG"),
              "enter": lambda: owner.enter_discovered_setup("BTC:LONG"),
              "close": lambda: owner.close_entered_plan("BTC:LONG", exit_price=101)}[method]
    for _attempt in range(2):
        with pytest.raises(OSError) as failure:
            invoke()
        assert failure.value is original
        assert owner.last_snapshot == before


def test_manual_snapshot_file_fsync_failure_retains_intent_and_temporary(tmp_path, monkeypatch):
    from app.trading_core import perp_manual_state_store as module

    owner = module.ManualPerpStateStore(tmp_path / "state.json")
    original = OSError("synthetic snapshot fsync failure after intent")
    real_fsync = module.os.fsync
    calls = []

    def fail_second(fd):
        calls.append(fd)
        if len(calls) == 2:
            raise original
        return real_fsync(fd)

    # On Windows these are the intent and snapshot file flushes, with no dir fsync.
    monkeypatch.setattr(module, "sync_parent", lambda _path: None)
    monkeypatch.setattr(module.os, "fsync", fail_second)
    with pytest.raises(OSError) as failure:
        owner.save(plans=[{"status": "ENTERED"}], setup_history=[])
    assert failure.value is original
    assert owner.pending_path.exists()
    assert len(list(tmp_path.glob("*.tmp"))) == 1
    assert not owner.path.exists()


def test_successful_manual_service_replay_after_restart_does_not_duplicate(tmp_path, monkeypatch):
    module = source_module("backend/app/services/perp_manual_service.py", "perp_manual_service")
    path = tmp_path / "state.json"
    owner = module.PerpManualService(state_path=path)
    owner.last_snapshot["setups"] = [{"setup_key": "BTC:LONG", "symbol": "BTC", "side": "LONG"}]
    plan = {"setup_key": "BTC:LONG", "symbol": "BTC", "side": "LONG",
            "status": "ENTERED", "entry_price": 100, "entered_at": "synthetic"}
    monkeypatch.setattr(module, "enter_setup", lambda *_a, **_k: dict(plan))
    owner.enter_discovered_setup("BTC:LONG")
    before = path.read_bytes()
    assert owner.enter_discovered_setup("BTC:LONG") == plan
    restarted = module.PerpManualService(state_path=path)
    restarted.last_snapshot["setups"] = [{"setup_key": "BTC:LONG"}]
    replay = restarted.enter_discovered_setup("BTC:LONG")
    assert replay["status"] == "ENTERED"
    assert len(restarted.last_snapshot["plans"]) == 1
    assert path.read_bytes() == before


def test_manual_refresh_failure_does_not_acknowledge_new_snapshot(tmp_path, monkeypatch):
    from datetime import datetime, timezone
    from types import SimpleNamespace

    module = source_module("backend/app/services/perp_manual_service.py", "perp_manual_service")
    owner = module.PerpManualService(state_path=tmp_path / "state.json")
    original = OSError("synthetic refresh persistence failure")
    before = json.loads(json.dumps(owner.last_snapshot))

    async def tickers():
        return [SimpleNamespace(symbol="BTC", price=100, timestamp=datetime.now(timezone.utc).isoformat(),
                                volume_24h=1000, open_interest=100, funding_rate=0)]

    async def setups(*_args, **_kwargs):
        return []

    def fail(**_kwargs):
        raise original

    monkeypatch.setattr(owner, "_adapter", lambda: SimpleNamespace(
        get_all_tickers=tickers, universe_names=lambda: ["BTC"],
    ))
    monkeypatch.setattr(owner, "_discover_setups", setups)
    monkeypatch.setattr(owner._state_store, "save", fail)
    with pytest.raises(OSError) as failure:
        asyncio.run(owner.refresh())
    assert failure.value is original
    assert owner.last_snapshot == before
    assert owner.last_refresh_at is None
