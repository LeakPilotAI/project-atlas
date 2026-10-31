"""Actual teardown AST with fake services: no application startup or live I/O."""

import ast
import asyncio
import builtins
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from app.core.shutdown import ShutdownReport

ROOT = Path(__file__).resolve().parents[1]
SERVICES = (
    "micro_heartbeat", "prediction_paper_automation", "daily_paper_recap",
    "perp_alert_delivery_service", "perp_manual_service", "perp_micro_coach",
    "command_center", "robinhood_universe_research_service", "robinhood_brief_service",
    "quality_dip_scanner", "weekly_summary_service", "paper_trade_tracker",
    "opportunity_tracker", "scanner",
)


def scenario(monkeypatch, failures=(), *, logger_fails=False):
    calls = []

    def action(name):
        async def stop(**_kwargs):
            calls.append(name)
            if name in failures:
                raise OSError(name)
        return stop

    def emit(message, **_fields):
        if logger_fails:
            raise OSError("synthetic logging unavailable")
        calls.append(message)

    log = SimpleNamespace(info=emit, error=emit, warning=emit)
    app = SimpleNamespace(state=SimpleNamespace())
    boot = asyncio.get_running_loop().create_future()
    boot.set_result(None)
    namespace = {"app": app, "asyncio": asyncio, "log": log, "boot_task": boot,
                 "runtime_watchdog": SimpleNamespace(stop=action("watchdog")),
                 "stop_discord_bot": action("discord"), "close_redis": action("redis"),
                 "engine": SimpleNamespace(dispose=action("database")),
                 "registry": SimpleNamespace(close_all=action("adapters")),
                 "desktop_control": SimpleNamespace(stop=action("desktop")),
                 "accumulation_ladder": None, "btc_accumulation": None}
    namespace.update({name: SimpleNamespace(stop=action(name)) for name in SERVICES})

    async def research_stop(**_kwargs):
        await action("research")()

    async def providers_stop(**_kwargs):
        await action("providers")()

    def journal_call(name, value):
        calls.append(name)
        if name in failures:
            raise OSError(name)
        return value

    fixtures = {
        "app.investment.scan": SimpleNamespace(stop_investment_scanner=action("investment")),
        "app.services.extended_hours_research": SimpleNamespace(
            extended_hours_research_service=SimpleNamespace(stop=research_stop)),
        "app.investment.quality_dip_quotes": SimpleNamespace(
            quality_dip_quote_service=SimpleNamespace(shutdown=providers_stop)),
        "app.services.perp_setup_paper_mirror": SimpleNamespace(perp_setup_paper_mirror=
            SimpleNamespace(cancel_all_pending=lambda **_kw: journal_call("pending", 0))),
        "app.services.paper_journal": SimpleNamespace(paper_journal=SimpleNamespace(
            persist_open_marks=lambda: journal_call("marks", 0),
            interrupt_open_for_shutdown=lambda: journal_call("interrupt", []),
            first_fsync_error=OSError("fsync") if "fsync" in failures else None)),
    }
    for name, value in fixtures.items():
        monkeypatch.setitem(sys.modules, name, value)
    source = ast.parse((ROOT / "backend/app/main.py").read_text(encoding="utf-8"))
    lifespan = next(n for n in source.body if isinstance(n, ast.AsyncFunctionDef)
                    and n.name == "lifespan")
    body = next(n.finalbody for n in lifespan.body if isinstance(n, ast.Try) and n.finalbody)
    wrapper = ast.parse("async def teardown(): pass")
    wrapper.body[0].body = body
    exec(compile(ast.fix_missing_locations(wrapper), "isolated-lifespan", "exec"), namespace)  # noqa: S102 - actual AST, inert dependencies
    return namespace["teardown"], app, calls


@pytest.mark.asyncio
@pytest.mark.parametrize("failures", [(), ("redis",), ("database",), ("redis", "database"),
                                    ("watchdog",), ("desktop",), ("pending",), ("marks",),
                                    ("providers",), ("research",), ("adapters",), ("fsync",)])
async def test_actual_teardown_outcome_and_independent_cleanup(monkeypatch, failures):
    teardown, app, calls = scenario(monkeypatch, failures)
    if failures:
        with pytest.raises(builtins.ExceptionGroup):
            await teardown()
        assert app.state.shutdown_report.outcome == (
            "UNKNOWN" if set(failures) & {"watchdog", "research", "providers", "adapters"}
            else "INCOMPLETE")
        assert "Project Atlas shutdown complete" not in calls
        assert all(any(str(error) == name for _, error in app.state.shutdown_report.errors)
                   for name in failures)
    else:
        await teardown()
        assert app.state.shutdown_report.outcome == "COMPLETE"
        assert "Project Atlas shutdown complete" in calls
    assert "desktop" in calls
    assert ("database" in calls) is not bool(
        set(failures) & {"watchdog", "research", "providers", "adapters"})


@pytest.mark.asyncio
async def test_logging_failure_cannot_become_success(monkeypatch):
    teardown, app, calls = scenario(monkeypatch, logger_fails=True)
    with pytest.raises(builtins.ExceptionGroup):
        await teardown()
    assert app.state.shutdown_report.outcome == "UNKNOWN"
    assert "desktop" in calls
    assert "Project Atlas shutdown complete" not in calls


@pytest.mark.asyncio
async def test_stuck_supervisor_retained_and_late_success_not_reclassified():
    release = asyncio.Event()
    report = ShutdownReport(timeout=0.01)
    with pytest.raises(TimeoutError):
        await report.run("stuck", release.wait)
    assert not report.tasks["stuck"].done()
    with pytest.raises(builtins.ExceptionGroup):
        report.finish(SimpleNamespace(error=lambda *_a, **_k: None))
    release.set()
    await report.tasks["stuck"]
    assert report.outcome == "TIMED_OUT"
    with pytest.raises(builtins.ExceptionGroup):
        report.finish(None)


@pytest.mark.asyncio
async def test_exhausted_budget_never_starts_new_work():
    report = ShutdownReport(timeout=0)
    with pytest.raises(TimeoutError):
        await report.run("queue", lambda: pytest.fail("must not start"))
    assert not report.tasks
    assert report.outcome == "TIMED_OUT"


@pytest.mark.asyncio
async def test_caller_interruption_retains_owned_work():
    entered, release = asyncio.Event(), asyncio.Event()

    async def work():
        entered.set()
        await release.wait()

    report = ShutdownReport()
    caller = asyncio.create_task(report.run("owned", work))
    await entered.wait()
    caller.cancel()
    with pytest.raises(asyncio.CancelledError):
        await caller
    assert not report.tasks["owned"].done()
    assert report.outcome == "UNKNOWN"
    release.set()
    await report.tasks["owned"]
    with pytest.raises(builtins.BaseExceptionGroup):
        report.finish(SimpleNamespace(error=lambda *_a, **_k: None))


@pytest.mark.asyncio
async def test_successful_step_and_finish_are_idempotent():
    calls = []

    async def close():
        calls.append("closed")

    report = ShutdownReport()
    await report.run("client", close)
    await report.run("client", close)
    logger = SimpleNamespace(info=lambda *_a, **_k: None)
    report.finish(logger)
    report.finish(logger)
    assert report.outcome == "COMPLETE"
    assert calls == ["closed"]


@pytest.mark.asyncio
async def test_single_shared_budget_is_not_renewed():
    now = [0.0]
    report = ShutdownReport(clock=lambda: now[0])

    async def research():
        now[0] = 19.0

    await report.run("research", research)
    assert report.remaining() == 1
    now[0] = 20
    with pytest.raises(TimeoutError):
        await report.run("providers", lambda: pytest.fail("expired"))


def source_method(path, name, namespace, *, owner=None):
    tree = ast.parse((ROOT / path).read_text(encoding="utf-8"))
    nodes = tree.body if owner is None else next(
        n.body for n in tree.body if isinstance(n, ast.ClassDef) and n.name == owner)
    method = next(n for n in nodes if isinstance(n, (ast.AsyncFunctionDef, ast.FunctionDef)) and n.name == name)
    module = ast.Module(body=[method], type_ignores=[])
    exec(compile(ast.fix_missing_locations(module), "isolated-stop", "exec"), namespace)  # noqa: S102 - actual method with inert globals
    return namespace[name]


@pytest.mark.asyncio
async def test_prediction_preserves_multiple_failed_tasks():
    tasks = [asyncio.get_running_loop().create_future() for _ in range(2)]
    for task in tasks:
        task.set_exception(OSError("synthetic task failure"))
    import threading
    owner = SimpleNamespace(_scanner_task=tasks[0], _flat_task=tasks[1],
                            _state_lock=threading.RLock(), _persistence_failures={},
                            _known_persistence_failure=lambda _lane: None)
    stop = source_method("backend/app/prediction/prediction_paper_automation.py", "stop",
                         {"asyncio": asyncio}, owner="PredictionPaperAutomation")
    with pytest.raises(builtins.ExceptionGroup) as error:
        await stop(owner)
    assert len(error.value.exceptions) == 2
    assert tuple(error.value.exceptions) == tuple(task.exception() for task in tasks)
    assert owner._scanner_task is tasks[0]


@pytest.mark.asyncio
async def test_investment_stop_propagates_failed_owned_task():
    task = asyncio.get_running_loop().create_future()
    original = OSError("synthetic scanner failure")
    task.set_exception(original)
    owner = SimpleNamespace(_task=task)
    stop = source_method("backend/app/investment/scan.py", "stop",
                         {"asyncio": asyncio}, owner="InvestmentScanner")
    with pytest.raises(OSError) as error:
        await stop(owner)
    assert error.value is original
    assert owner._task is task


@pytest.mark.asyncio
async def test_discord_close_and_completed_task_failures_preserved():
    async def close():
        raise OSError("synthetic close failure")

    task = asyncio.get_running_loop().create_future()
    task.set_exception(RuntimeError("synthetic bot task failure"))
    namespace = {"asyncio": asyncio, "_bot_task": task,
                 "bot": SimpleNamespace(is_ready=lambda: True, close=close)}
    stop = source_method("backend/app/alerts/discord.py", "stop_discord_bot", namespace)
    with pytest.raises(builtins.ExceptionGroup) as error:
        await stop()
    assert len(error.value.exceptions) == 2
    assert namespace["_bot_task"] is task


@pytest.mark.asyncio
async def test_registry_attempts_independent_adapter_after_failure():
    calls = []

    async def fail():
        raise OSError("synthetic adapter failure")

    async def close():
        calls.append("second")

    owner = SimpleNamespace(_adapters={"a": SimpleNamespace(close=fail),
                                     "b": SimpleNamespace(close=close)})
    stop = source_method("backend/app/adapters/registry.py", "close_all", {},
                         owner="AdapterRegistry")
    with pytest.raises(builtins.ExceptionGroup):
        await stop(owner)
    assert calls == ["second"]


@pytest.mark.asyncio
async def test_coach_retains_http_failure_and_attempts_journal_flush(monkeypatch):
    calls = []

    async def close():
        raise OSError("synthetic HTTP cleanup failure")

    def flush():
        calls.append("flush")
        raise RuntimeError("synthetic journal flush failure")

    monkeypatch.setitem(sys.modules, "app.services.paper_journal", SimpleNamespace(
        paper_journal=SimpleNamespace(flush=flush)))
    owner = SimpleNamespace(_task=None, _manage_task=None,
                            _http=SimpleNamespace(aclose=close), _open={})
    stop = source_method("backend/app/services/perp_micro_coach.py", "stop",
                         {"asyncio": asyncio}, owner="PerpMicroCoach")
    with pytest.raises(builtins.ExceptionGroup) as error:
        await stop(owner)
    assert len(error.value.exceptions) == 2
    assert owner._http is not None
    assert calls == ["flush"]


@pytest.mark.asyncio
async def test_desktop_corrupt_synthetic_manifest_is_not_success(tmp_path):
    import json

    manifest = tmp_path / "runtime.json"
    manifest.write_text("synthetic invalid JSON", encoding="utf-8")
    owner = SimpleNamespace(task=None, directory=tmp_path, run_id="synthetic")
    stop = source_method("backend/app/services/desktop_control.py", "stop",
                         {"asyncio": asyncio, "json": json}, owner="DesktopControl")
    with pytest.raises(ValueError):
        await stop(owner)
    assert manifest.read_text(encoding="utf-8") == "synthetic invalid JSON"


@pytest.mark.asyncio
async def test_worker_ignoring_cancellation_remains_owned():
    entered, release = asyncio.Event(), asyncio.Event()

    async def stubborn():
        entered.set()
        try:
            await release.wait()
        except asyncio.CancelledError:
            await release.wait()

    report = ShutdownReport(timeout=0.02)
    caller = asyncio.create_task(report.run("stubborn", stubborn))
    await entered.wait()
    report.tasks["stubborn"].cancel()
    with pytest.raises(TimeoutError):
        await caller
    assert not report.tasks["stubborn"].done()
    release.set()
    await report.tasks["stubborn"]
    assert report.outcome == "TIMED_OUT"


@pytest.mark.asyncio
async def test_actual_finally_executes_on_context_interruption(monkeypatch):
    from contextlib import asynccontextmanager

    teardown, app, calls = scenario(monkeypatch)
    source = ast.parse((ROOT / "backend/app/main.py").read_text(encoding="utf-8"))
    lifespan = next(n for n in source.body if isinstance(n, ast.AsyncFunctionDef)
                    and n.name == "lifespan")
    final = next(n for n in lifespan.body if isinstance(n, ast.Try) and n.finalbody)
    wrapper = ast.parse("async def flow(): pass")
    wrapper.body[0].body = [final]
    namespace = teardown.__globals__
    exec(compile(ast.fix_missing_locations(wrapper), "isolated-finally", "exec"), namespace)  # noqa: S102 - same actual teardown with fake services
    context = asynccontextmanager(namespace["flow"])
    original = OSError("synthetic context interruption")
    with pytest.raises(OSError) as failure:
        async with context():
            raise original
    assert failure.value is original
    assert app.state.shutdown_report.outcome == "COMPLETE"
    assert "desktop" in calls


@pytest.mark.asyncio
async def test_interrupted_boot_cannot_claim_complete(monkeypatch):
    teardown, app, _calls = scenario(monkeypatch)
    teardown.__globals__["boot_task"] = asyncio.get_running_loop().create_future()
    with pytest.raises(builtins.ExceptionGroup):
        await teardown()
    assert app.state.shutdown_report.outcome == "UNKNOWN"


@pytest.mark.asyncio
async def test_untracked_legacy_task_is_observed_without_termination(monkeypatch):
    release = asyncio.Event()
    task = asyncio.create_task(release.wait(), name="paper_session_announce")
    try:
        teardown, app, _calls = scenario(monkeypatch)
        with pytest.raises(builtins.ExceptionGroup):
            await teardown()
        assert app.state.shutdown_report.outcome == "UNKNOWN"
        assert not task.done()
    finally:
        release.set()
        await task


@pytest.mark.asyncio
async def test_watchdog_cannot_confirm_while_thread_is_alive():
    alive = [True]
    owner = SimpleNamespace(_stop=SimpleNamespace(set=lambda: None), _task=None,
                            _thread=SimpleNamespace(is_alive=lambda: alive[0]))
    stop = source_method("backend/app/services/runtime_watchdog.py", "stop",
                         {"asyncio": asyncio}, owner="RuntimeWatchdog")
    report = ShutdownReport(timeout=0.02)
    with pytest.raises(TimeoutError):
        await report.run("watchdog", lambda: stop(owner))
    assert not report.tasks["watchdog"].done()
    alive[0] = False
    await report.tasks["watchdog"]
    assert report.outcome == "TIMED_OUT"


def test_manual_state_required_persistence_is_strict_for_all_callers(tmp_path):
    from test_r7e47r_durable_acknowledgements import source_module

    original = OSError("synthetic state persistence failure")

    def save(**_kwargs):
        raise original

    module = source_module("backend/app/services/perp_manual_service.py", "perp_manual_service")
    owner = module.PerpManualService(state_path=tmp_path / "state.json")
    owner._state_store = SimpleNamespace(save=save)
    for strict in (False, True):
        with pytest.raises(OSError) as failure:
            owner._persist_state(strict=strict)
        assert failure.value is original
    assert owner.recovery_error


def test_marks_attempt_all_and_preserve_failures():
    calls = []

    def update(identity, *_args, **_kwargs):
        calls.append(identity)
        raise OSError(identity)

    owner = SimpleNamespace(_open={"a": {"mark": 1}, "b": {"mark": 2}},
                            update_excursion=update, _require_persistence=lambda: None)
    persist = source_method("backend/app/services/paper_journal.py", "persist_open_marks",
                            {}, owner="PaperJournal")
    with pytest.raises(builtins.ExceptionGroup) as failure:
        persist(owner)
    assert calls == ["a", "b"]
    assert len(failure.value.exceptions) == 2


def test_fsync_failure_preserves_first_exception_without_rewriting(tmp_path, monkeypatch):
    import json

    from test_r7e47r_durable_acknowledgements import source_module

    original = OSError("synthetic fsync failure")

    def fsync(_descriptor):
        raise original

    module = source_module("backend/app/services/paper_journal.py", "paper_journal")
    module.JOURNAL_PATH = tmp_path / "synthetic.jsonl"
    module.CANDIDATE_PATH = tmp_path / "candidates.jsonl"
    owner = module.PaperJournal()
    monkeypatch.setattr(module.os, "fsync", fsync)
    for _attempt in range(2):
        with pytest.raises(OSError) as failure:
            owner._append(module.JOURNAL_PATH, {"event": "synthetic"})
        assert failure.value is original
    assert owner.first_fsync_error is original
    assert json.loads(module.JOURNAL_PATH.read_text(encoding="utf-8")) == {"event": "synthetic"}


@pytest.mark.asyncio
@pytest.mark.parametrize("preserve", [True, False])
async def test_desktop_retains_evidence_on_failure_or_identity_change(tmp_path, preserve):
    import json

    manifest = tmp_path / "runtime.json"
    manifest.write_text(json.dumps({"run_id": "foreign"}), encoding="utf-8")
    owner = SimpleNamespace(task=None, directory=tmp_path, run_id="synthetic")
    stop = source_method("backend/app/services/desktop_control.py", "stop",
                         {"asyncio": asyncio, "json": json}, owner="DesktopControl")
    if preserve:
        await stop(owner, preserve_manifest=True)
    else:
        with pytest.raises(RuntimeError):
            await stop(owner)
    assert json.loads(manifest.read_text(encoding="utf-8")) == {"run_id": "foreign"}


@pytest.mark.asyncio
async def test_prediction_preserves_persistence_and_task_errors_without_duplicates():
    import threading
    tasks = [asyncio.get_running_loop().create_future() for _ in range(2)]
    for task in tasks:
        task.set_exception(OSError("synthetic owned task failure"))
    persistence = OSError("synthetic required persistence failure")
    owner = SimpleNamespace(_scanner_task=tasks[0], _flat_task=tasks[1],
                            _state_lock=threading.RLock(),
                            _persistence_failures={"scanner": persistence, "auto_flat": persistence},
                            _known_persistence_failure=lambda _lane: persistence)
    stop = source_method("backend/app/prediction/prediction_paper_automation.py", "stop",
                         {"asyncio": asyncio}, owner="PredictionPaperAutomation")
    with pytest.raises(builtins.ExceptionGroup) as actual:
        await stop(owner)
    assert actual.value.exceptions == (tasks[0].exception(), tasks[1].exception(), persistence)
    assert owner._scanner_task is tasks[0]
