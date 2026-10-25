"""Reference discovery is research, never instrument/fill authority."""

import asyncio
import json
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest
from app.investment.alpaca_iex import Credentials, IEXFeed, IEXRefused
from app.investment.quality_dips_market_roster import (
    NasdaqDirectorySource,
    directory_snapshot,
    live_roster,
    research_batch,
    research_universe,
)


class TestAuthority:
    __test__ = False

    def verify_directory(self, source, raw):
        return True  # Explicit synthetic permission/authenticity, not production approval.

    def verify_ranking(self, row):
        return row["source"] == "synthetic-existing-ranker"


def directory():
    return (b"Symbol|Security Name|Market Category|Test Issue|Financial Status|Round Lot Size|ETF|NextShares\n"
            b"MSFT|Microsoft Common Stock|Q|N|N|100|N|N\n"
            b"QQQ|ETF Reference|G|N|N|100|Y|N\n"
            b"TEST|Test|G|Y|N|100|N|N\n"
            b"BAD|Deficient|G|N|D|100|N|N\n"
            b"File Creation Time: 1025202612:00|||||||\n")


def ranked():
    return [{"symbol": symbol, "score": score, "revision": 3, "at": 1000,
             "source": "synthetic-existing-ranker"} for symbol, score in (("QQQ", "90"), ("MSFT", "90"), ("SPY", "95"))]


def select(rows=None, **kwargs):
    return live_roster(ranked() if rows is None else rows, required_symbols=["MSFT"],
                       capacity=2, now=1000, max_age=10, ranking_authority=TestAuthority(), **kwargs)


def test_distinct_equity_etf_reference_and_source_cut_no_execution_claim():
    view = directory_snapshot(directory(), source="nasdaqlisted.txt", authority=TestAuthority())
    assert view["source_records"] == 4 and len(view["excluded"]) == 2
    assert {r["instrument_type"] for r in view["rows"]} == {"ETF", "EQUITY_REFERENCE"}
    assert all(not r["execution_eligible"] for r in view["rows"])
    assert view["source_cut_local"] == "1025202612:00"
    batch = research_batch(view, offset=0, budget=1)
    assert batch["rows"][0]["symbol"] == "MSFT" and batch["remaining"] == 1
    assert research_batch(view, offset=1, budget=1)["rows"][0]["symbol"] == "QQQ"


@pytest.mark.parametrize("raw", [
    directory()[:-1], directory().replace(b"File Creation Time:", b"Unknown cut:"),
    directory().replace(b"ETF|NextShares", b"ETF|ETF"),
    directory().replace(b"|100|Y|N", b"|0|Y|N"),
    directory().replace(b"|100|Y|N", b"|100|UNKNOWN|N"),
    directory().replace(b"QQQ|ETF Reference", b"MSFT|Duplicate"),
])
def test_truncated_unknown_duplicate_or_bad_directory_refused(raw):
    with pytest.raises(ValueError):
        directory_snapshot(raw, source="nasdaqlisted.txt", authority=TestAuthority())


def test_reference_path_never_relabels_tokens_or_unsupported_securities():
    with pytest.raises(ValueError):
        directory_snapshot(directory(), source="robinhood-tokens.json", authority=TestAuthority())
    with pytest.raises(ValueError):
        directory_snapshot(directory(), source="nasdaqlisted.txt", authority=None)


def test_other_exchange_symbols_preserved_without_punctuation_guessing():
    raw = (b"ACT Symbol|Security Name|Exchange|CQS Symbol|ETF|Round Lot Size|Test Issue|NASDAQ Symbol\n"
           b"SPY|ETF|P|SPY|Y|100|N|SPY\n"
           b"BRK.B|Class B|N|BRK.B|N|100|N|BRK.B\n"
           b"ODD$A|Unsupported|N|ODD$A|N|100|N|ODD$A\n"
           b"File Creation Time: 1025202612:00|||||||\n")
    result = directory_snapshot(raw, source="otherlisted.txt", authority=TestAuthority())
    assert result["rows"][0]["exchange"] == "ARCX"
    assert result["rows"][1]["source_symbols"]["CQS Symbol"] == "BRK.B"
    assert len(result["excluded"]) == 1


def test_deterministic_rank_rotation_preserves_open_position_quote_slot():
    assert select()["symbols"] == ["MSFT", "SPY"]
    rows = ranked()
    rows[0]["score"] = "100"
    assert select(rows)["symbols"] == ["MSFT", "QQQ"]
    assert select(list(reversed(rows)))["symbols"] == ["MSFT", "QQQ"]


@pytest.mark.parametrize("change", [{"at": 980}, {"at": 1001}, {"source": "forged"}, {"score": "NaN"}, {"revision": True}])
def test_stale_or_changed_rank_authority_refuses(change):
    rows = ranked()
    rows[0].update(change)
    with pytest.raises(ValueError):
        select(rows)


def test_duplicate_ranking_and_more_open_symbols_than_capacity_refuse():
    with pytest.raises(ValueError):
        select(ranked() + [ranked()[0]])
    with pytest.raises(ValueError):
        live_roster([], required_symbols=["MSFT", "SPY"], capacity=1, now=1000, max_age=10, ranking_authority=TestAuthority())


def test_live_reconfiguration_requires_independent_open_position_inventory():
    f = IEXFeed(["MSFT"])
    with pytest.raises(IEXRefused):
        f.request_roster(select())
    f = IEXFeed(["MSFT"], position_symbols=lambda: ["MSFT"])
    f.request_roster(select())
    assert f.symbols == ("MSFT", "SPY") and not f.subscribed
    forged = select() | {"symbols": ["SPY"], "required_symbols": []}
    with pytest.raises(IEXRefused):
        f.request_roster(forged)
    assert f.symbols == ("MSFT", "SPY")


def test_public_directory_download_is_bounded_fixed_source_and_no_implicit_io():
    calls = []
    class Response:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def geturl(self):
            return "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt"
        def read(self, limit):
            assert limit == 8_000_001
            return directory()
    def opener(request, timeout):
        calls.append(request.full_url)
        assert timeout == 8 and request.get_method() == "GET"
        return Response()
    source = NasdaqDirectorySource(opener=opener)
    assert calls == []
    assert len(source.download("nasdaqlisted.txt")["rows"]) == 2
    with pytest.raises(ValueError):
        source.download("https://foreign.invalid")
    assert len(calls) == 1


def test_actual_scanner_universe_interface_requires_metadata_without_file_loading(monkeypatch):
    from app.investment import universe
    monkeypatch.setattr(universe, "ensure_dirs", lambda: pytest.fail("directory initialization attempted"))
    view = directory_snapshot(directory(), source="nasdaqlisted.txt", authority=TestAuthority())
    batch = research_batch(view, offset=0, budget=10)
    metadata = {symbol: {"symbol": symbol, "instrument_id": "synthetic:" + symbol,
                        "asset_class": kind, "exchange": "XNAS", "currency": "USD", "status": "ACTIVE", "revision": 1}
                for symbol, kind in (("MSFT", "STOCK"), ("QQQ", "ETF"))}
    authority = SimpleNamespace(verify_instrument=lambda *args: True)
    result = research_universe(batch, metadata=metadata, instrument_authority=authority)
    assert [e.symbol for e in result["universe"].scan_order()] == ["MSFT", "QQQ"]
    assert result["execution_authorized"] is False
    metadata["MSFT"]["status"] = "HALTED"
    assert len(research_universe(batch, metadata=metadata, instrument_authority=authority)["universe"]) == 1


@pytest.mark.asyncio
async def test_rotations_are_bounded_without_dropping_open_position_pins():
    now = [1000]
    f = IEXFeed(["MSFT"], position_symbols=lambda: ["MSFT"], clock=lambda: now[0])
    rows = ranked()
    rows[0]["score"] = "100"
    async with f.run_lock:
        f.request_roster(select())
        with pytest.raises(IEXRefused, match="RATE_LIMIT"):
            f.request_roster(select(rows))
        now[0] += 30
        f.request_roster(select(rows))
    assert f.symbols == ("MSFT", "QQQ")


@pytest.mark.asyncio
async def test_socket_rotation_closes_original_before_reconnect_and_exact_ack():
    f = IEXFeed(["MSFT"], position_symbols=lambda: ["MSFT"])
    events, sent = [], []
    stop = asyncio.Event()

    class Wire:
        request = SimpleNamespace(headers={"Host": "stream.data.alpaca.markets"}, path="/v2/iex")

        def __init__(self):
            self.inbox = asyncio.Queue()
            self.inbox.put_nowait('[{"T":"success","msg":"authenticated"}]')

        async def send(self, raw):
            value = json.loads(raw)
            sent.append(value["action"])
            if value["action"] == "subscribe":
                self.inbox.put_nowait(json.dumps([{"T": "subscription", "quotes": value["quotes"]}]))
                if len(events) == 1:
                    asyncio.get_running_loop().call_later(.01, f.request_roster, select())
                else:
                    asyncio.get_running_loop().call_later(.01, stop.set)

        async def recv(self):
            return await self.inbox.get()

    @asynccontextmanager
    async def connect(url, **kwargs):
        assert not events or events[-1] == "closed"
        events.append("opened")
        try:
            yield Wire()
        finally:
            events.append("closed")

    result = await f.run(Credentials("test-key", "test-secret"), seconds=4, connect=connect, stop=stop)
    assert events == ["opened", "closed", "opened", "closed"]
    assert sent == ["auth", "subscribe", "auth", "subscribe"]
    assert result["subscribed"] and result["reconnects"] == 0
