"""Deterministic data protocol, provider refusals and existing PAPER interfaces."""

import asyncio
import json
from contextlib import asynccontextmanager, contextmanager
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest
from app.investment.alpaca_iex import FEED, URL, Credentials, IEXFeed, IEXRefused
from app.services.quality_dips_iex_input import IEXPaperQuotes

STAMP = int(datetime(2026, 10, 26, 14, tzinfo=UTC).timestamp())


def message(**changes):
    return (
        dict(
            T="q",
            S="MSFT",
            bp=100,
            ap=100.1,
            bs=2,
            **{"as": 3},
            bx="V",
            ax="V",
            c=["R"],
            z="C",
            t="2026-10-26T14:00:00.123456789Z",
        )
        | changes
    )


def feed():
    now = [STAMP + 0.5]
    f = IEXFeed(["MSFT"], clock=lambda: now[0])
    f.receive('[{"T":"success","msg":"authenticated"}]')
    f.receive('[{"T":"subscription","quotes":["MSFT"]}]')
    return f, now


def test_valid_quote_preserves_precision_sizes_scope_and_latency():
    f, now = feed()
    f.receive(json.dumps([message()]))
    v = f.snapshot()
    q = v["quotes"][0]
    assert q["state"] == "FRESH" and q["ask"] == "100.1" and q["bid_lots"] == 2
    assert q["source_ns"] == STAMP * 10**9 + 123456789
    assert (
        v["scope"] == "SINGLE_EXCHANGE_NOT_NBBO" and not v["paper_startup_authorized"]
    )
    assert 376 < q["latency_ms"] < 377
    now[0] += 6
    assert f.snapshot()["quotes"][0]["state"] == "STALE"
    f.disconnect()
    assert f.snapshot()["connection"] == "DISCONNECTED"


@pytest.mark.parametrize(
    "changes",
    [
        {"bp": 0},
        {"bp": 101},
        {"ap": "100.1"},
        {"bs": 0},
        {"as": 0},
        {"bs": True},
        {"c": ["H"]},
        {"t": "bad"},
        {"t": "2026-10-26T13:00:00Z"},
        {"t": "2026-10-27T14:00:00Z"},
        {"bp": float("nan")},
        {"bx": ""},
    ],
)
def test_malformed_quote_not_executable(changes):
    f, _ = feed()
    try:
        f.receive(json.dumps([message(**changes)]))
    except IEXRefused:
        pass
    assert f.snapshot()["quotes"][0]["state"] == "UNAVAILABLE"


@pytest.mark.parametrize(
    "raw", ["{}", "[]", '[{"T":"q","T":"error"}]', "secret-broken-json"]
)
def test_malformed_frames_are_redacted(raw):
    f, _ = feed()
    with pytest.raises(IEXRefused) as e:
        f.receive(raw)
    assert "secret" not in str(e.value)


@pytest.mark.parametrize(
    "code,reason",
    [
        (402, "AUTH_FAILED"),
        (409, "ENTITLEMENT_FAILED"),
        (405, "SYMBOL_LIMIT"),
        (406, "CONNECTION_LIMIT"),
    ],
)
def test_provider_error_messages_never_escape(code, reason):
    f, _ = feed()
    with pytest.raises(IEXRefused, match=reason):
        f.receive(json.dumps([{"T": "error", "code": code, "msg": "private-secret"}]))
    assert "private-secret" not in str(f.snapshot()) and not f.authenticated


def test_config_bom_and_credential_repr(tmp_path):
    p = tmp_path / "private.env"
    p.write_text(
        "\ufeffALPACA_API_KEY=key-for-tests\nALPACA_API_SECRET=secret-for-tests\nALPACA_TRADING_ENABLED=false\n",
        encoding="utf-8",
    )
    c = Credentials.load(p)
    assert c.key == "key-for-tests" and "secret-for-tests" not in repr(c)
    p.write_text(
        p.read_text(encoding="utf-8").replace("false", "true"), encoding="utf-8"
    )
    with pytest.raises(IEXRefused, match="TRADING_MUST_BE_DISABLED"):
        Credentials.load(p)


@pytest.mark.parametrize(
    "content",
    [
        "ALPACA_TRADING_ENABLED=false\n",
        "invalid-secret-line",
        "ALPACA_API_KEY=a\nALPACA_API_KEY=b\n",
        "ALPACA_TRADING_ENABLED=false\nALPACA_DATA_FEED=sip",
    ],
)
def test_config_refuses_missing_malformed_duplicate_and_paid_feed(tmp_path, content):
    p = tmp_path / "private.env"
    p.write_text(content)
    with pytest.raises(IEXRefused) as e:
        Credentials.load(p)
    assert "invalid-secret" not in str(e.value)


class Wire:
    def __init__(self, frames):
        self.frames, self.sent = list(frames), []
        self.request = SimpleNamespace(
            headers={"Host": "stream.data.alpaca.markets"}, path="/v2/iex"
        )

    async def send(self, message):
        self.sent.append(json.loads(message))

    async def recv(self):
        if self.frames:
            return self.frames.pop(0)
        await asyncio.sleep(0.01)
        raise TimeoutError


@pytest.mark.asyncio
async def test_authenticated_subscription_and_idle_closed_market_transport():
    w = Wire(
        [
            '[{"T":"success","msg":"connected"}]',
            '[{"T":"success","msg":"authenticated"}]',
            '[{"T":"subscription","quotes":["MSFT"]}]',
        ]
    )

    @asynccontextmanager
    async def connect(url, **kw):
        assert url == URL and kw["ping_interval"] == 10 and kw["logger"].disabled
        yield w

    f = IEXFeed(["MSFT"])
    result = await f.run(
        Credentials("test-key", "test-secret"), seconds=1, connect=connect
    )
    assert (
        result["authenticated"] and result["subscribed"] and result["quote_count"] == 0
    )
    assert [x["action"] for x in w.sent] == ["auth", "subscribe"]
    assert w.sent[-1] == {"action": "subscribe", "quotes": ["MSFT"]}
    assert f.snapshot()["connection"] == "DISCONNECTED" and "test-secret" not in str(
        result
    )


@pytest.mark.asyncio
async def test_disconnect_reconnect_invalidates_prior_quotes_and_redacts_transport():
    calls = []

    @asynccontextmanager
    async def connect(url, **kw):
        calls.append(url)
        if len(calls) == 1:
            raise OSError("private-secret-from-transport")
        yield Wire(
            [
                '[{"T":"success","msg":"authenticated"}]',
                '[{"T":"subscription","quotes":["MSFT"]}]',
            ]
        )

    f = IEXFeed(["MSFT"])
    r = await f.run(
        Credentials("test-key", "test-secret"),
        seconds=2,
        max_reconnects=1,
        connect=connect,
    )
    assert len(calls) == 2 and r["reconnects"] == 1 and r["authenticated"]
    assert "private-secret" not in str(r)


@pytest.mark.asyncio
async def test_auth_failure_has_no_retry_or_subscription():
    w = Wire(['[{"T":"error","code":402,"msg":"test-secret"}]'])

    @asynccontextmanager
    async def connect(url, **kw):
        yield w

    r = await IEXFeed(["MSFT"]).run(
        Credentials("test-key", "test-secret"), seconds=1, connect=connect
    )
    assert not r["authenticated"] and r["reconnects"] == 0 and len(w.sent) == 1


@pytest.mark.asyncio
async def test_redirected_host_refused_before_credentials_leave_client():
    w = Wire([])
    w.request.headers["Host"] = "foreign.invalid"

    @asynccontextmanager
    async def connect(url, **kw):
        yield w

    r = await IEXFeed(["MSFT"]).run(
        Credentials("test-key", "test-secret"), seconds=1, connect=connect
    )
    assert not w.sent and not r["authenticated"]
    assert r["result"]["error"] == "IEX_WEBSOCKET_IDENTITY_REFUSED"


def authority(instrument, calendar, *, valid=True):
    @contextmanager
    def lease(request, now):
        data = {
            "verified": valid,
            "instrument": instrument,
            "feed_id": FEED,
            "round_lot_shares": 100,
            "market_status": "TRADING",
            "entitlement_id": "SYNTHETIC_TEST_ONLY",
            "calendar": calendar,
            "clock_uncertainty_seconds": "0",
        }
        yield SimpleNamespace(snapshot=data, check=lambda p, t: valid)

    return SimpleNamespace(lease=lease)


def test_existing_autonomous_engine_entry_exit_using_iex_contract(tmp_path):
    from app.services.paper_epoch_fixture import create_epoch_fixture
    from app.services.quality_dips_autonomous_paper import AutonomousPaper
    from test_quality_dips_autonomous_paper import candidate, quote, setup

    n = setup(tmp_path)
    b = candidate(n)
    instrument = b["instrument"]
    ledger = create_epoch_fixture(tmp_path / "iex-account.sqlite", n.m)
    engine = AutonomousPaper(
        ledger=ledger,
        candidates=n.engine.candidates,
        session_authority=n.engine.session_authority,
        source_authority=n.engine.source_authority,
        clock=lambda: n.now[0],
    )
    engine.start({**n.grant, "feed_id": FEED})
    f, _ = feed()
    f.clock = lambda: n.now[0]
    f.receive(json.dumps([message(bp=99.9, ap=100, t="2026-10-26T14:00:00Z")]))
    port = IEXPaperQuotes(
        feed=f, execution_authority=authority(instrument, quote(n, b)["calendar"])
    )
    frame = port.frame(
        session_id=n.grant["session_id"], sequence=1, bundles=[b], instrument=instrument
    )
    result = engine.step("iex-entry", **frame["request"])
    assert result["filled"]
    assert Decimal(ledger.snapshot()["cash"]) == Decimal("899.96")
    n.now[0] += 1
    f.receive(json.dumps([message(bp=110, ap=110.1, t="2026-10-26T14:00:01Z")]))
    position = next(iter(ledger.snapshot()["positions"].values()))
    result = engine.step(
        "iex-shutdown",
        bundles=[],
        **port.observe(position, timeout=2),
        shutdown_mode="SHUTDOWN_FLATTEN",
    )
    assert result["filled"] and Decimal(ledger.snapshot()["cash"]) == Decimal(
        "1009.916"
    )
    assert (
        engine.step(
            "iex-shutdown",
            bundles=[],
            **port.observe(position, timeout=2),
            shutdown_mode="SHUTDOWN_FLATTEN",
        )
        == result
    )
    f.disconnect()
    with pytest.raises(IEXRefused):
        port.quote(instrument)


def test_no_invented_round_lot_or_calendar_authority():
    f, _ = feed()
    f.receive(json.dumps([message()]))
    with pytest.raises(IEXRefused, match="AUTHORITY_REQUIRED"):
        IEXPaperQuotes(feed=f).quote({"symbol": "MSFT"})


def test_existing_runtime_next_protocol_uses_explicit_decisions_and_no_duplicate_tick(
    tmp_path,
):
    from test_quality_dips_autonomous_paper import candidate, quote, setup

    n = setup(tmp_path)
    b = candidate(n)
    f, _ = feed()
    f.receive(json.dumps([message()]))
    reader = SimpleNamespace(
        read_request=lambda timeout: {
            "instrument": b["instrument"],
            "bundles": [b],
            "observation": None,
        }
    )
    port = IEXPaperQuotes(
        feed=f,
        execution_authority=authority(b["instrument"], quote(n, b)["calendar"]),
        session_id="explicit-test-session",
        decision_reader=reader,
    )
    frame = port.next(0.01)
    assert frame["schema"] == "QD_AUTO_OBSERVATION_V3" and frame["sequence"] == 1
    assert frame["request"]["quotes"][0]["clock_uncertainty_seconds"] == "1"
    assert port.verify_observation(frame, now=int(f.clock()))
    altered = json.loads(json.dumps(frame))
    altered['request']['quotes'][0]['bid'] = '999'
    with pytest.raises(IEXRefused): port.verify_observation(altered, now=int(f.clock()))
    assert port.next(0.01) is None
    f.disconnect()
    with pytest.raises(IEXRefused): port.verify_observation(frame, now=int(f.clock()))
    with pytest.raises(IEXRefused):
        port.next(0.01)


@pytest.mark.asyncio
async def test_existing_quote_service_cache_read_has_no_provider_fallback():
    from app.investment.quality_dip_quotes import QualityDipQuoteService

    f, _ = feed()
    f.receive(json.dumps([message()]))
    s = QualityDipQuoteService(alpaca_feed=f)
    result = await s.get_many(["MSFT", "SPY"])
    assert result["MSFT"]["source"] == "ALPACA_IEX_SINGLE_EXCHANGE_NOT_NBBO"
    assert result["SPY"]["trigger_price"] is None
    f.disconnect()
    assert (await s.get_many(["MSFT"]))["MSFT"]["trigger_price"] is None


def test_malformed_protocol_clears_live_admission_and_reconnect_needs_new_quote():
    f, _ = feed()
    f.receive(json.dumps([message()]))
    with pytest.raises(IEXRefused):
        f.receive("private-malformed")
    assert f.snapshot()["quotes"][0]["state"] == "STALE" and not f.authenticated
    f.generation += 1
    f.receive('[{"T":"success","msg":"authenticated"}]')
    f.receive('[{"T":"subscription","quotes":["MSFT"]}]')
    assert f.snapshot()["quotes"][0]["state"] == "STALE"
    f.receive(json.dumps([message()]))
    assert f.snapshot()["quotes"][0]["state"] == "FRESH"


def test_nanosecond_order_duplicate_and_conflicting_quote_refusal():
    f, _ = feed()
    f.receive(json.dumps([message(t="2026-10-26T14:00:00Z")]))
    f.receive(json.dumps([message()]))
    assert f.snapshot()["quotes"][0]["source_ns"] == STAMP * 10**9 + 123456789
    f.receive(json.dumps([message(bp=100.05)]))
    assert f.snapshot()["quotes"][0]["state"] == "UNAVAILABLE"


def test_market_closed_never_triggers_research_ladder():
    f, now = feed()
    now[0] = int(datetime(2026, 10, 25, 14, tzinfo=UTC).timestamp())
    f.receive(json.dumps([message(t="2026-10-25T14:00:00Z")]))
    q = f.research_snapshot("MSFT")
    assert (
        q["session"] == "CLOSED"
        and q["trigger_price"] is None
        and not q["tradable_for_ladder"]
    )


def test_credential_file_is_ignored_and_untracked():
    import subprocess
    from pathlib import Path

    repo = Path(__file__).resolve().parents[1]
    tracked = subprocess.run(
        ["git", "ls-files", "--", "config/alpaca.env"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    )
    ignored = subprocess.run(
        ["git", "check-ignore", "config/alpaca.env"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    assert not tracked.stdout and ignored.returncode == 0


@pytest.mark.asyncio
async def test_readonly_router_shows_data_even_when_financial_source_unavailable():
    import httpx
    from app.api.quality_dips_selected_paper import create_router
    from fastapi import FastAPI

    f, _ = feed()
    f.receive(json.dumps([message()]))

    def refused(*a, **k):
        raise ValueError("NO_OPERATIONAL_FINANCIAL_ENROLLMENT")

    reader = SimpleNamespace(read_committed=refused, verify=refused)
    app = FastAPI()
    app.include_router(
        create_router(
            reader=reader,
            verifier=reader,
            clock=lambda: STAMP,
            account_id="uninitialized-test",
            epoch="uninitialized-test",
            market_reader=f,
        )
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://localhost"
    ) as client:
        r = await client.get("/api/investments/quality-dips/selected-paper")
        assert r.json()["status"] == "UNAVAILABLE" and r.json()["cash"] is None
        assert r.json()["market_data"]["quotes"][0]["bid"] == "100"
        assert (
            await client.post(
                "/api/investments/quality-dips/selected-paper/commands", json={}
            )
        ).status_code == 403
    assert f.observations == 1
