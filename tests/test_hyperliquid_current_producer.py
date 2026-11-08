"""Offline HL source assembly. Actual parser/protocol, in-memory native I/O only."""

import copy
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from app.adapters.hyperliquid import HyperliquidAdapter, _paper_execution_observation
from app.services.hyperliquid_current_producer import HyperliquidCurrentProducer
from app.services.paper_financial_replay import body, digest
from test_hyperliquid_public_book import inputs
from test_perp_financial_v2 import manifest
from test_personal_native_coordination_memory import (
    installation_authority,
    native_double,
)
from test_personal_research_archive import SyntheticSourceAuthority
from test_quality_dips_current_producer import STAMP, proof

from scripts.observation_runtime.personal_perp_research_archive import (
    NativePersonalPerpResearchArchive,
    initial_image,
)


def fixture(monkeypatch, symbols=("BTC", "ETH", "SOL"), shared_clock=None):
    io = native_double(monkeypatch)
    io.owner.root, io.owner.root_id = "D:\\SYNTHETIC-HL-NOT-REAL", [2, 3, 4]
    io.owner.native.native.file_identity = lambda _: io.owner.root_id
    parameters = manifest()
    parameters.update(opened_at=STAMP - 10, release="b" * 64)
    parameters["perp_policy"]["symbols"] = list(symbols)
    e = {
        "schema": "PERSONAL_PERP_SOURCE_ARCHIVE_V1",
        "account_id": "SYNTHETIC-HL-ACCOUNT",
        "epoch": parameters["epoch"],
        "source_id": "SYNTHETIC-HL-CURRENT",
        "release_digest": "b" * 64,
        "source_commit": "c" * 40,
        "root_id": io.owner.root_id,
        "lane": "HYPERLIQUID",
        "currency": "USDC",
        "parameters_digest": digest(parameters),
    }
    io.owner.enrollment = digest(e)
    io.owner._binding = (
        io.owner.output,
        io.owner.root,
        tuple(io.owner.root_id),
        digest(e),
    )
    io.owner.initialize(
        initial_image(e), authorization=SimpleNamespace(lease=installation_authority)
    )
    now = [STAMP]
    clock = shared_clock if shared_clock is not None else lambda: now[0]
    auth = SyntheticSourceAuthority()
    archive = NativePersonalPerpResearchArchive(
        enrollment=e, images=io.owner, authority=auth, clock=clock
    )
    adapter = HyperliquidAdapter()

    async def no_provider(*args, **kwargs):
        raise AssertionError("Provider access forbidden in source assembly fixtures")

    monkeypatch.setattr(adapter, "_post", no_provider)
    monkeypatch.setattr(adapter, "connect", no_provider)
    adapter._connected = True  # Explicit synthetic state, never an actual connection.
    markets = []
    for symbol in symbols:
        metadata, book = inputs()
        metadata[0]["universe"][0]["name"] = symbol
        book.update(coin=symbol, time=STAMP * 1000)
        parsed = _paper_execution_observation(
            symbol, metadata, book, STAMP * 1000, STAMP * 1000
        )
        adapter._cache_paper(
            "books", symbol, {"parsed": parsed, "metadata": metadata, "book": book}
        )
        adapter._cache_paper(
            "candles",
            symbol,
            {
                "interval": "5m",
                "observed_at_ms": STAMP * 1000,
                "rows": [
                    {
                        "close": 100 - (47 - i) * 0.04,
                        "time": (STAMP - (47 - i) * 300) * 1000,
                    }
                    for i in range(48)
                ],
            },
        )
        markets.append(
            {
                "symbol": symbol,
                "price": 100.5,
                "volume_24h": 20000000,
                "open_interest": 8000000,
                "funding_rate": -0.001,
                "timestamp": datetime.fromtimestamp(STAMP, UTC).isoformat(),
            }
        )
    adapter._cache_paper("markets", None, markets)
    control = {
        "execution_domain": "DISPOSABLE_TEST",
        "head": "SYNTHETIC-ORDER-HEAD",
        "state": {"orders": {}, "revision": 0, "last_clock": STAMP - 10},
    }
    orders = SimpleNamespace(
        manifest=parameters,
        execution_domain="DISPOSABLE_TEST",
        snapshot=lambda: copy.deepcopy(control),
        remaining_slots=lambda: 128,
    )
    cut = {
        "schema": "HL_CURRENT_RESEARCH_INPUT_V1",
        "execution_domain": "DISPOSABLE",
        "source_id": e["source_id"],
        "input_revision": 1,
        "observed_at": STAMP,
        "cache": adapter.paper_source_snapshot(),
        "orders": copy.deepcopy(control),
        "maker_windows": {},
        "settlements": {},
        "setups": [],
        "provenance": {
            "SYNTHETIC_ONLY": [
                "original-book",
                "original-candles",
                "original-trade-transport",
            ]
        },
    }
    source = SimpleNamespace(read_current=lambda: copy.deepcopy(cut))
    flags = SimpleNamespace(valid=True, window=True, mutate=False, domain="DISPOSABLE")

    def accept(context, *, now):
        if not flags.valid or context != {
            "input": cut,
            "enrollment": e,
            "execution_domain": "DISPOSABLE",
        }:
            return False
        result = proof(
            "HL_CURRENT_RESEARCH_VERIFIED_V1", context, execution_domain=flags.domain
        )
        if flags.mutate:
            context["input"]["provenance"]["MUTATED"] = True
        return result

    def window(context, *, now):
        if not flags.window or context["execution_domain"] != "DISPOSABLE":
            return False
        order = context["order"]
        key = order["order_id"]
        assert context["window"] == cut["maker_windows"][key]
        assert context["trades"] == cut["cache"]["facts"]["trades"][order["symbol"]]
        return proof(
            "HL_MAKER_WINDOW_VERIFIED_V1", context, execution_domain="DISPOSABLE"
        )

    input_auth = SimpleNamespace(verify_current=accept, verify_maker_window=window)
    enrolled = []

    def components(c):
        if not enrolled:
            assert (
                c["archive"] is archive
                and c["adapter"] is adapter
                and c["orders"] is orders
            )
            assert (
                c["clock"] is clock
                and c["source_id"] == e["source_id"]
                and c["lane"] == "HYPERLIQUID"
            )
            enrolled.append(dict(c))
        return auth.valid and c == enrolled[0]

    auth.verify_components = components
    auth.verify_head = lambda c, h, at: components(c) and h == archive.current()
    auth.verify_current = lambda c, h, p, at: (
        components(c) and p == archive.read(h) and h == archive.current()
    )
    auth.verify_cache = lambda c, cache, at: (
        components(c) and cache == adapter.paper_source_snapshot() == cut["cache"]
    )
    auth.verify_settlement = lambda history, oracle, at: (
        oracle in cut["settlements"].values()
    )
    auth.verify_maker = lambda order, value, trades, at: (
        flags.window
        and order == control["state"]["orders"][order["order_id"]]["order"]
        and trades == cut["cache"]["facts"]["trades"][order["symbol"]]
    )
    auth.verify_publication = lambda c, h, p, sources, at: (
        components(c) and sources["current_input"]["input"] == cut
    )

    def reopen(domain="DISPOSABLE"):
        enrolled.clear()
        return HyperliquidCurrentProducer(
            source=source,
            input_authority=input_auth,
            publication_authority=auth,
            adapter=adapter,
            orders=orders,
            archive=archive,
            parameters=parameters,
            enrollment=e,
            clock=clock,
            execution_domain=domain,
        )

    owner = reopen()

    def sync():
        cut["cache"] = adapter.paper_source_snapshot()
        cut["orders"] = copy.deepcopy(control)

    return SimpleNamespace(**locals())


def resting(f):
    order = {
        "schema": "PERP_RESTING_ORDER_V1",
        "epoch": f.parameters["epoch"],
        "order_id": "SYNTHETIC-ORDER",
        "session_id": "SYNTHETIC-SESSION",
        "symbol": "BTC",
        "side": "LONG",
        "quantity": ".5",
        "limit_price": "100",
        "stop_price": "99",
        "risk_price": "1",
        "leverage": "1",
        "created_at": STAMP - 2,
        "expires_at": STAMP + 100,
        "source_id": f.e["source_id"],
        "source_revision": 1,
        "source_digest": "SYNTHETIC-ORIGINAL-CUT",
        "plan": {"quantity_step": ".001", "execution_policy": "STATIC_SETUP_TP1_V1"},
    }
    f.control["state"]["orders"][order["order_id"]] = {
        "state": "RESERVED",
        "order": order,
    }
    f.sync()
    return order


def maker(f, size="5"):
    order = resting(f)
    metadata, book = inputs()
    book["time"] = (STAMP - 2) * 1000
    queue = {
        "book": book,
        "metadata": metadata,
        "source_digest": order["source_digest"],
        "source_revision": 1,
        "receipt": "SYNTHETIC-INDEPENDENT-QUEUE",
    }
    frame = {
        "channel": "trades",
        "data": [
            {
                "coin": "BTC",
                "side": "A",
                "px": "100",
                "sz": size,
                "time": (STAMP - 1) * 1000,
                "tid": 9,
                "hash": "SYNTHETIC-TRADE",
            }
        ],
    }
    f.adapter.ingest_paper_trades(
        frame, received_ms=STAMP * 1000, continuity_receipt="SYNTHETIC-WINDOW"
    )
    f.cut["maker_windows"][order["order_id"]] = {
        "queue": queue,
        "trade_ids": [[(STAMP - 1) * 1000, 9]],
        "queue_ahead": "1.25",
    }
    f.sync()
    return order


def test_btc_eth_sol_actual_normalization_publication_ack_and_cold_replay(monkeypatch):
    f = fixture(monkeypatch)
    before = copy.deepcopy(f.cut)
    packet = f.owner.publish_current()
    assert set(packet["books"]) == {"BTC", "ETH", "SOL"}
    assert packet["books"]["BTC"]["bid"] == "100"
    assert f.owner.read_cut() == packet and f.cut == before
    assert f.archive.current()["native_revision"] == 2
    frozen = copy.deepcopy(f.io.files)
    assert f.owner.publish_current() == packet
    other = f.reopen()
    assert other.read_cut() == packet and other.publish_current() == packet
    assert f.io.files == frozen


def test_discovery_and_research_reuse_original_strategy(monkeypatch):
    from app.services.perp_source_planner import source_research_plans
    from app.trading_core.perp_board import build_perp_board

    f = fixture(monkeypatch)
    p = f.owner.publish_current()
    expected = build_perp_board(
        source_research_plans(p, {}, f.parameters["perp_policy"]["symbols"], now=STAMP)
    )
    assert f.owner.research() == expected
    assert expected and {r["symbol"] for r in expected} == {"BTC", "ETH", "SOL"}


@pytest.mark.parametrize(
    "damage",
    [
        "source",
        "domain",
        "receipt",
        "provenance",
        "stale",
        "future",
        "revision",
        "cache",
        "symbols",
        "book",
        "candle",
        "nonfinite",
        "foreign-order",
        "window",
        "source-mutation",
    ],
)
def test_invalid_current_inputs_refuse_before_effect(monkeypatch, damage):
    f = fixture(monkeypatch)
    if damage == "source":
        f.cut["source_id"] = "OTHER"
    elif damage == "domain":
        f.cut["execution_domain"] = "OPERATIONAL"
    elif damage == "receipt":
        f.flags.valid = False
    elif damage == "provenance":
        f.cut["provenance"] = {}
    elif damage == "stale":
        f.cut["observed_at"] -= 6
    elif damage == "future":
        f.cut["observed_at"] += 1
    elif damage == "revision":
        f.cut["input_revision"] = True
    elif damage == "cache":
        f.adapter._connected = False
    elif damage == "symbols":
        f.adapter._paper_cache["markets"].pop()
        f.sync()
    elif damage == "book":
        f.adapter._paper_cache["books"]["BTC"]["parsed"]["bid"] = "1"
        f.sync()
    elif damage == "candle":
        f.adapter._paper_cache["candles"]["BTC"]["rows"][-1]["time"] += 1000
        f.sync()
    elif damage == "nonfinite":
        f.adapter._paper_cache["markets"][0]["funding_rate"] = "NaN"
        f.sync()
    elif damage == "foreign-order":
        resting(f)
        f.control["state"]["orders"]["SYNTHETIC-ORDER"]["order"]["epoch"] = "FOREIGN"
        f.sync()
    elif damage == "window":
        maker(f)
        f.flags.window = False
    else:
        f.flags.mutate = True
    frozen = copy.deepcopy(f.io.files)
    with pytest.raises((ValueError, KeyError)):
        f.owner.publish_current()
    assert f.io.files == frozen


def test_maker_fill_is_derived_from_original_queue_trades_and_existing_participation(
    monkeypatch,
):
    f = fixture(monkeypatch)
    order = maker(f)
    p = f.owner.publish_current()
    proof = p["maker_fills"][order["order_id"]]
    assert (
        proof["filled_quantity"] == "0.375" and proof["cancelled_quantity"] == "0.125"
    )
    assert proof["queue_ahead"] == "1.25" and proof["traded_quantity"] == "5"
    assert f.owner.read_cut() == p and f.owner.publish_current() == p
    r = f.archive.read_evidence(f.archive.current())
    assert (
        r["sources"]["current_input"]["input"]["maker_windows"]
        == f.cut["maker_windows"]
    )


@pytest.mark.parametrize("size", ["1", "1.25"])
def test_no_fill_before_queue_capacity_and_no_touch_substitution(monkeypatch, size):
    f = fixture(monkeypatch)
    maker(f, size)
    assert f.owner.publish_current()["maker_fills"] == {}


def test_resting_without_trade_window_remains_unfilled(monkeypatch):
    f = fixture(monkeypatch)
    resting(f)
    assert f.owner.publish_current()["maker_fills"] == {}


@pytest.mark.parametrize("advance,passes", [(5, True), (6, False)])
def test_five_second_freshness_and_restart(monkeypatch, advance, passes):
    f = fixture(monkeypatch)
    p = f.owner.publish_current()
    f.now[0] += advance
    frozen = copy.deepcopy(f.io.files)
    if passes:
        assert f.reopen().read_cut() == p
    else:
        with pytest.raises(ValueError):
            f.reopen().read_cut()
    assert f.io.files == frozen


@pytest.mark.parametrize("damage", ["conflict", "rollback"])
def test_input_revision_conflict_and_rollback_survive_restart(monkeypatch, damage):
    f = fixture(monkeypatch)
    f.cut["input_revision"] = 9
    f.owner.publish_current()
    if damage == "conflict":
        f.cut["provenance"]["OTHER"] = True
    else:
        f.cut["input_revision"] = 8
    frozen = copy.deepcopy(f.io.files)
    with pytest.raises(ValueError, match="CONFLICT|ROLLBACK"):
        f.reopen().publish_current()
    assert f.io.files == frozen


def test_interrupted_commit_never_retries_or_adopts_uncertain_state(monkeypatch):
    f = fixture(monkeypatch)
    f.io.owner.fail_leaf = "0002-commit.json"
    with pytest.raises(OSError):
        f.owner.publish_current()
    frozen = copy.deepcopy(f.io.files)
    with pytest.raises(ValueError):
        f.owner.publish_current()
    with pytest.raises(ValueError):
        f.reopen().read_cut()
    assert f.io.files == frozen and f.io.owner.poisoned


def test_synthetic_cannot_be_operational_and_bool_does_not_authenticate(monkeypatch):
    f = fixture(monkeypatch)
    f.owner.input_authority.verify_current = lambda *a, **k: True
    frozen = copy.deepcopy(f.io.files)
    with pytest.raises(ValueError):
        f.owner.publish_current()
    with pytest.raises(ValueError):
        f.reopen("OPERATIONAL")
    assert f.io.files == frozen


def test_independent_store_deterministic_replay(monkeypatch):
    first = fixture(monkeypatch).owner.publish_current()
    second = fixture(monkeypatch).owner.publish_current()
    assert body(first) == body(second)


@pytest.mark.parametrize(
    "damage",
    [
        "ids",
        "duplicate",
        "side",
        "price",
        "queue",
        "queue-receipt",
        "source-cut",
        "negative-price",
        "negative-size",
    ],
)
def test_maker_source_disagreement_is_not_a_fill(monkeypatch, damage):
    f = fixture(monkeypatch)
    order = maker(f)
    window = f.cut["maker_windows"][order["order_id"]]
    if damage == "ids":
        window["trade_ids"][0][1] = 100
    elif damage == "duplicate":
        window["trade_ids"] *= 2
    elif damage == "side":
        f.adapter._paper_cache["trades"]["BTC"]["rows"][0]["side"] = "B"
        f.sync()
    elif damage == "price":
        f.adapter._paper_cache["trades"]["BTC"]["rows"][0]["px"] = "101"
        f.sync()
    elif damage == "queue":
        window["queue_ahead"] = "1"
    elif damage == "queue-receipt":
        window["queue"]["receipt"] = None
    elif damage == "negative-price":
        f.adapter._paper_cache["trades"]["BTC"]["rows"][0]["px"] = "-1"
        f.sync()
    elif damage == "negative-size":
        f.adapter._paper_cache["trades"]["BTC"]["rows"][0]["sz"] = "-1"
        f.sync()
    else:
        window["queue"]["source_digest"] = "FOREIGN"
    frozen = copy.deepcopy(f.io.files)
    with pytest.raises(ValueError):
        f.owner.publish_current()
    assert f.io.files == frozen


def test_maker_math_is_independent_of_ambient_decimal_rounding(monkeypatch):
    from decimal import ROUND_UP, localcontext

    f = fixture(monkeypatch)
    order = maker(f)
    with localcontext() as context:
        context.prec = 5
        context.rounding = ROUND_UP
        p = f.owner.publish_current()
    assert p["maker_fills"][order["order_id"]]["filled_quantity"] == "0.375"


@pytest.mark.parametrize("oracle", ["missing", "original", "unaccepted"])
def test_due_funding_keeps_historical_oracle_distinct_from_current_mark(
    monkeypatch, oracle
):
    from app.adapters.hyperliquid import _paper_funding_observation

    f = fixture(monkeypatch)
    rows = [
        {"coin": "BTC", "time": STAMP * 1000, "fundingRate": "-.001", "premium": "0"}
    ]
    parsed = _paper_funding_observation(
        "BTC", rows, STAMP * 1000, (STAMP + 3600) * 1000, STAMP * 1000, STAMP * 1000
    )
    f.adapter._cache_paper(
        "funding", "BTC", {"parsed": parsed, "rows": rows, "started_ms": STAMP * 1000}
    )
    if oracle != "missing":
        f.cut["settlements"][f"BTC:{STAMP}"] = {
            "symbol": "BTC",
            "settlement_at": STAMP,
            "price": "87",
            "source_id": "SYNTHETIC-HISTORICAL-ORACLE",
            "revision": 1,
        }
    if oracle == "unaccepted":
        f.auth.verify_settlement = lambda *a: False
    f.sync()
    frozen = copy.deepcopy(f.io.files)
    if oracle == "unaccepted":
        with pytest.raises(ValueError):
            f.owner.publish_current()
        assert f.io.files == frozen
    else:
        packet = f.owner.publish_current()
        if oracle == "missing":
            assert packet["oracles"] == {}
        else:
            assert packet["oracles"][f"BTC:{STAMP}"]["price"] == "87"
            assert packet["books"]["BTC"]["oracle"] != "87"


def read_only_planner(f):
    from app.services.paper_financial_replay import initial_state
    from app.services.perp_resting_writer import RestingPerpWriter
    from app.services.perp_source_planner import PerpSourcePlanner
    from app.services.unified_native_writer import NativeFinancialWriter

    state = {
        "pin_schema": "FS2_TEST_PIN_V1",
        "manifest": f.parameters,
        "state": initial_state(f.parameters),
        "head": "SYNTHETIC-UNMUTATED-HEAD",
        "root": [8, 8, 8],
        "acknowledged_operations": {},
    }
    store = SimpleNamespace(verified_cut=lambda: copy.deepcopy(state))
    a = SimpleNamespace(
        verify_components=lambda b: b["store"] is store,
        verify_cut=lambda b, c: c == state,
    )
    financial = NativeFinancialWriter(
        store=store,
        authority=a,
        manifest=f.parameters,
        execution_domain="DISPOSABLE_TEST",
    )
    a.verify_order_components = lambda b, p: (
        p == {"financial": financial, "orders": f.orders}
    )
    writer = RestingPerpWriter(financial=financial, orders=f.orders)
    a.verify_planner_components = lambda b, p: (
        p["writer"] is writer and p["source"] is f.owner
    )
    a.verify_strategy_source = lambda b, p, o, c, control: (
        p == f.owner.read_cut() and c == state and control == f.control
    )
    planner = PerpSourcePlanner(
        writer=writer, source=f.owner, clock=f.clock, session_id="SYNTHETIC-SESSION"
    )
    return SimpleNamespace(**locals())


@pytest.mark.asyncio
async def test_actual_planner_refuses_due_funding_without_history_instead_of_current_oracle(
    monkeypatch,
):
    f = fixture(monkeypatch)
    f.owner.publish_current()
    r = read_only_planner(f)
    from app.services.paper_financial_replay import apply_event
    from test_perp_financial_v2 import entry

    command = entry()
    command["timestamp"] = STAMP - 1
    command["evidence"]["observed_at"] = STAMP - 1
    r.state["state"], _ = apply_event(f.parameters, r.state["state"], command)
    assert next(iter(r.state["state"]["positions"].values()))["next_funding"] == STAMP
    frozen = copy.deepcopy(r.state)
    with pytest.raises(ValueError, match="SETTLEMENT_RATE_AND_HISTORICAL_ORACLE"):
        await r.planner.next_proposal(None, r.writer._cut())
    assert r.state == frozen


@pytest.mark.asyncio
async def test_actual_planner_leaves_resting_touch_unfilled_without_window(monkeypatch):
    f = fixture(monkeypatch)
    resting(f)
    f.owner.publish_current()
    r = read_only_planner(f)
    before = copy.deepcopy(f.control)
    assert await r.planner.next_proposal(None, r.writer._cut()) is None
    assert r.planner.last == "RESTING_NO_EXECUTION_EVIDENCE" and f.control == before


@pytest.mark.parametrize(
    "damage", ["release", "commit", "root", "parameters", "archive", "adapter"]
)
def test_source_component_and_enrollment_substitution_refuses(monkeypatch, damage):
    f = fixture(monkeypatch)
    if damage == "release":
        f.owner.enrollment["release_digest"] = "0" * 64
    elif damage == "commit":
        f.owner.enrollment["source_commit"] = "0" * 40
    elif damage == "root":
        f.owner.enrollment["root_id"] = [9, 9, 9]
    elif damage == "parameters":
        f.owner.parameters["perp_policy"]["risk_limit"] = ".9"
    elif damage == "archive":
        f.owner.publication.archive = object()
    else:
        f.owner.adapter = HyperliquidAdapter()
    frozen = copy.deepcopy(f.io.files)
    with pytest.raises(ValueError):
        f.owner.publish_current()
    assert f.io.files == frozen


def test_qd_images_cannot_be_read_as_perp_or_perp_as_qd(monkeypatch):
    from scripts.observation_runtime.personal_research_archive import (
        initial_image as qd_initial,
    )

    f = fixture(monkeypatch)
    qscope = {
        k: v
        for k, v in f.e.items()
        if k not in ("lane", "currency", "parameters_digest")
    }
    qscope["schema"] = "PERSONAL_QD_SOURCE_ARCHIVE_V1"
    with f.io.owner.transaction(readonly=False) as tx:
        tx.publish(tx.read(), qd_initial(qscope))
    frozen = copy.deepcopy(f.io.files)
    with pytest.raises(ValueError):
        f.archive.current()
    assert f.io.files == frozen


def test_current_cache_change_requires_new_accepted_input_not_reuse(monkeypatch):
    f = fixture(monkeypatch)
    first = f.owner.publish_current()
    old = copy.deepcopy(f.io.files)
    f.adapter._cache_paper(
        "markets", None, copy.deepcopy(f.cut["cache"]["facts"]["markets"])
    )
    with pytest.raises(ValueError):
        f.owner.read_cut()
    f.cut["input_revision"] += 1
    f.sync()
    second = f.owner.publish_current()
    assert first["revision"] == 1 and second["revision"] == 2
    assert all(f.io.files[k] == v for k, v in old.items())


@pytest.mark.asyncio
async def test_original_market_observer_accepts_only_verified_current_wrapper(
    monkeypatch,
):
    from app.services.paper_market_observers import HyperliquidMarketObserver

    f = fixture(monkeypatch)
    packet = f.owner.publish_current()
    observer = HyperliquidMarketObserver(f.adapter, clock=f.clock, source=f.owner)
    observation = await observer.observe()
    assert observation["source"]["cut"] == digest(
        packet
    ) and observer.verify_observation(observation)
    f.now[0] += 6
    with pytest.raises(ValueError):
        observer.verify_observation(observation)


def test_source_authority_cannot_mutate_bound_parameters_before_publication(
    monkeypatch,
):
    f = fixture(monkeypatch)
    original = f.input_auth.verify_current

    def changed(*args, **kwargs):
        receipt = original(*args, **kwargs)
        f.owner.parameters["perp_policy"]["risk_limit"] = ".9"
        return receipt

    f.input_auth.verify_current = changed
    frozen = copy.deepcopy(f.io.files)
    with pytest.raises(ValueError, match="BINDING_CHANGED"):
        f.owner.publish_current()
    assert f.io.files == frozen
