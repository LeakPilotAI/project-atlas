"""Isolated writer ownership, failure reporting and restart deduplication."""

import ast
import asyncio
import builtins
import threading
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from app.investment.extended_hours_collector import ExtendedHoursCollector
from app.services.extended_hours_research import ExtendedHoursResearchService

NOW = datetime(2026, 10, 16, 8, tzinfo=ZoneInfo("America/New_York"))


class Quotes:
    async def get_many(self, symbols):
        return {s: {"price": 250, "effective_timestamp": NOW.isoformat(),
                    "quality": "LIVE", "source": "fixture"} for s in symbols}


@pytest.mark.asyncio
async def test_commit_drain_timeout_never_confirms_shutdown_and_retains_evidence(tmp_path):
    path = tmp_path / "research.jsonl"
    collector = ExtendedHoursCollector(Quotes(), path)
    entered, release = threading.Event(), threading.Event()
    original = collector._commit_with_lock

    def blocked(*args):
        entered.set()
        assert release.wait(5)
        return original(*args)

    collector._commit_with_lock = blocked
    task = asyncio.create_task(collector.collect_once(["TEST"], now=NOW))
    try:
        for _ in range(200):
            if entered.is_set():
                break
            await asyncio.sleep(0.001)
        assert entered.is_set()
        with pytest.raises(TimeoutError):
            await collector.shutdown(0.01)
        with pytest.raises(RuntimeError):
            await collector.collect_once(["OTHER"], now=NOW)
        assert not task.done()
    finally:
        release.set()
        await collector.shutdown(2)
        await asyncio.gather(task, return_exceptions=True)
    committed = path.read_bytes()
    await asyncio.sleep(0.02)
    assert path.read_bytes() == committed
    assert not collector._collections
    # New collector uses the independent witness and existing identities.
    restarted = ExtendedHoursCollector(Quotes(), path)
    assert await restarted.collect_once(["TEST"], now=NOW) == []
    assert path.read_bytes() == committed
    await restarted.shutdown()


@pytest.mark.asyncio
async def test_shutdown_cancels_queued_collection_without_journal_write(tmp_path):
    entered = asyncio.Event()

    class BlockedQuotes:
        async def get_many(self, symbols):
            entered.set()
            await asyncio.Event().wait()

    path = tmp_path / "research.jsonl"
    collector = ExtendedHoursCollector(BlockedQuotes(), path)
    task = asyncio.create_task(collector.collect_once(["TEST"], now=NOW))
    await asyncio.wait_for(entered.wait(), 2)
    await collector.shutdown(1)
    assert task.cancelled()
    assert not path.exists()
    with pytest.raises(RuntimeError):
        await collector.collect_once(["TEST"], now=NOW)


@pytest.mark.asyncio
async def test_service_reports_drain_failure_and_keeps_owned_task_reference():
    class Collector:
        async def shutdown(self, timeout):
            raise TimeoutError("synthetic commit blocked")

    service = ExtendedHoursResearchService(collector=Collector(), universe_loader=lambda: None)
    with pytest.raises(TimeoutError):
        await service.stop(0.01)
    assert service.last_error == "SHUTDOWN_DRAIN_TIMEOUT"
    with pytest.raises(RuntimeError):
        await service.collect_once(now=NOW)


@pytest.mark.asyncio
@pytest.mark.parametrize("prior_stopped,drain_fails", [(True, False), (True, True), (False, False)])
async def test_actual_lifespan_drain_and_completion_reporting(monkeypatch, prior_stopped, drain_fails):
    from app.investment import quality_dip_quotes

    calls = []

    class Quotes:
        async def shutdown(self, timeout):
            calls.append(timeout)
            if drain_fails:
                raise TimeoutError("synthetic owned worker blocked")

    class Log:
        def info(self, message, **kwargs):
            calls.append(message)

        def error(self, message, **kwargs):
            calls.append(message)

    monkeypatch.setattr(quality_dip_quotes, "quality_dip_quote_service", Quotes())
    path = Path(__file__).resolve().parents[1] / "backend/app/main.py"
    lifespan = next(node for node in ast.parse(path.read_text(encoding="utf-8")).body
                    if isinstance(node, ast.AsyncFunctionDef) and node.name == "lifespan")
    body = next(node.finalbody for node in lifespan.body if isinstance(node, ast.Try) and node.finalbody)
    index = next(i for i, node in enumerate(body)
                 if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)
                 and node.targets[0].id == "provider_drain_confirmed")
    wrapper = ast.parse("async def scenario():\n    return provider_drain_confirmed, shutdown_services_stopped\n")
    wrapper.body[0].body[0:0] = body[index:index + 2]
    from app.core.shutdown import ShutdownReport

    report = ShutdownReport(clock=lambda: 0.0)
    namespace = {"log": Log(), "shutdown_services_stopped": prior_stopped, "shutdown_report": report, "asyncio": asyncio}
    # Assignment makes this local; explicitly initialize the prior service state.
    wrapper.body[0].body.insert(0, ast.parse(f"shutdown_services_stopped = {prior_stopped}").body[0])
    exec(compile(ast.fix_missing_locations(wrapper), str(path), "exec"), namespace)  # noqa: S102 - isolated actual-source AST with fake services
    drained, services_stopped = await namespace["scenario"]()
    assert calls[0] == 20.0
    if prior_stopped and not drain_fails:
        report.finish(namespace["log"])
    else:
        report.record("prior", RuntimeError("synthetic prior stop failure"))
        with pytest.raises(builtins.ExceptionGroup):
            report.finish(namespace["log"])
    assert drained is not drain_fails
    assert services_stopped is (prior_stopped and not drain_fails)
    assert ("Project Atlas shutdown complete" in calls) is (prior_stopped and not drain_fails)
    assert ("Project Atlas shutdown incomplete; operator recovery required" in calls) is not (
        prior_stopped and not drain_fails)
