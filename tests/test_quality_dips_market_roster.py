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


def test_merge_two_reference_sources_deduplicates_and_excludes_ambiguous_symbols():
    from app.investment.quality_dips_market_roster import merge_reference_directories
    first = {"schema": "QD_REFERENCE_DIRECTORY_V1", "source": "nasdaqlisted.txt", "source_digest": "a" * 64,
             "rows": [{"symbol": "MSFT"}, {"symbol": "DUP"}]}
    second = {"schema": "QD_REFERENCE_DIRECTORY_V1", "source": "otherlisted.txt", "source_digest": "b" * 64,
              "rows": [{"symbol": "SPY"}, {"symbol": "DUP"}]}
    merged = merge_reference_directories([first, second])
    assert [r["symbol"] for r in merged["rows"]] == ["MSFT", "SPY"]
    assert merged["conflicted_symbols"] == ["DUP"]
    assert merged["broker_eligibility_verified"] is False
    assert merged["execution_authorized"] is False


def test_merge_refuses_partial_or_untrusted_source_snapshots():
    from app.investment.quality_dips_market_roster import merge_reference_directories
    with pytest.raises(ValueError, match="TWO_SOURCE"):
        merge_reference_directories([])
    with pytest.raises(ValueError, match="TWO_SOURCE"):
        merge_reference_directories([{"source": "nasdaqlisted.txt"}, {"source": "nasdaqlisted.txt"}])


def test_merged_reference_pages_connect_to_existing_scanner_universe_interface():
    from app.investment.quality_dips_market_roster import merged_research_batch, merge_reference_directories
    from types import SimpleNamespace
    first = {"schema": "QD_REFERENCE_DIRECTORY_V1", "source": "nasdaqlisted.txt", "source_digest": "a" * 64,
             "rows": [{"symbol": "MSFT", "name": "Microsoft", "exchange": "XNAS", "instrument_type": "EQUITY_REFERENCE"}]}
    second = {"schema": "QD_REFERENCE_DIRECTORY_V1", "source": "otherlisted.txt", "source_digest": "b" * 64,
              "rows": [{"symbol": "SPY", "name": "SPY ETF", "exchange": "ARCX", "instrument_type": "ETF"}]}
    merged = merge_reference_directories([first, second])
    page1 = merged_research_batch(merged, offset=0, budget=1)
    page2 = merged_research_batch(merged, offset=1, budget=1)
    assert page1["source_digest"] == page2["source_digest"]
    assert page1["remaining"] == 1 and page2["remaining"] == 0
    metadata = {"MSFT": {"symbol": "MSFT", "instrument_id": "broker:MSFT", "asset_class": "STOCK",
                         "exchange": "XNAS", "currency": "USD", "status": "ACTIVE", "revision": 1}}
    authority = SimpleNamespace(verify_instrument=lambda item, ref, digest: digest == page1["source_digest"])
    admitted = research_universe(page1, metadata=metadata, instrument_authority=authority)
    assert admitted["universe"].symbols() == ["MSFT"]
    assert admitted["execution_authorized"] is False
    excluded = research_universe(page2, metadata=metadata, instrument_authority=authority)
    assert excluded["universe"].symbols() == [] and len(excluded["excluded"]) == 1


def test_merged_pagination_refuses_missing_source_provenance_and_unbounded_budget():
    from app.investment.quality_dips_market_roster import merged_research_batch
    valid = {"schema": "QD_MERGED_REFERENCE_RESEARCH_V1", "source_digests": {
        "nasdaqlisted.txt": "a" * 64, "otherlisted.txt": "b" * 64}, "rows": [], "reference_count": 0}
    with pytest.raises(ValueError, match="MERGED_BOUNDED"):
        merged_research_batch(valid, offset=0, budget=101)
    with pytest.raises(ValueError, match="MERGED_BOUNDED"):
        merged_research_batch(valid | {"source_digests": {}}, offset=0, budget=1)


def test_alpaca_asset_identity_normalization_is_not_broker_authority():
    from app.investment.quality_dips_market_roster import alpaca_asset_reference_metadata
    reference = {"symbol": "MSFT", "exchange": "XNAS", "instrument_type": "EQUITY_REFERENCE"}
    asset = {"symbol": "MSFT", "class": "us_equity", "status": "active", "tradable": True,
             "fractionable": True, "id": "provider-id", "exchange": "NASDAQ"}
    assert alpaca_asset_reference_metadata(asset, reference) == {
        "symbol": "MSFT", "instrument_id": "provider-id", "asset_class": "STOCK",
        "exchange": "XNAS", "currency": "USD", "status": "ACTIVE", "revision": 1}
    assert alpaca_asset_reference_metadata(asset | {"exchange": "NYSE"}, reference) is None
    assert alpaca_asset_reference_metadata(asset | {"tradable": False}, reference) is None
    assert alpaca_asset_reference_metadata(asset | {"id": ""}, reference) is None
    assert alpaca_asset_reference_metadata(asset | {"symbol": "AAPL"}, reference) is None


def test_real_transport_cohort_bridge_rejects_mismatch_and_never_grants_authority():
    from app.investment.quality_dips_market_roster import acquire_reference_asset_cohort
    class Provider:
        domain = "TLS_PUBLIC_PROVIDER"
        def get(self, url, ttl):
            symbol = url.rsplit("/", 1)[-1]
            return ({"symbol": symbol, "class": "us_equity", "status": "active", "tradable": True,
                     "fractionable": True, "id": "asset:" + symbol,
                     "exchange": "NASDAQ" if symbol == "MSFT" else "NYSE"}, {"url": url, "status": 200})
    batch = {"source_digest": "a" * 64, "rows": [
        {"symbol": "MSFT", "exchange": "XNAS", "instrument_type": "EQUITY_REFERENCE"},
        {"symbol": "SPY", "exchange": "ARCX", "instrument_type": "ETF"}]}
    result = acquire_reference_asset_cohort(batch, client=Provider(), budget=2)
    assert list(result["metadata"]) == ["MSFT"]
    assert result["excluded"] == [{"symbol": "SPY", "reason": "PROVIDER_ASSET_IDENTITY_UNVERIFIED"}]
    assert result["independent_instrument_authority_verified"] is False
    assert result["execution_authorized"] is False
    with pytest.raises(ValueError, match="BOUNDED_REAL"):
        acquire_reference_asset_cohort(batch, client=Provider(), budget=1)
    Provider.domain = "SYNTHETIC"
    with pytest.raises(ValueError, match="BOUNDED_REAL"):
        acquire_reference_asset_cohort(batch, client=Provider(), budget=2)


def test_reviewed_cohort_requires_exact_source_receipts_and_independent_verifier():
    from app.investment.quality_dips_market_roster import reviewed_asset_research_universe
    from types import SimpleNamespace
    batch = {"source_digest": "a" * 64, "rows": [{"symbol": "MSFT", "name": "Microsoft",
             "exchange": "XNAS", "instrument_type": "EQUITY_REFERENCE"}]}
    item = {"symbol": "MSFT", "instrument_id": "alpaca-id", "asset_class": "STOCK",
            "exchange": "XNAS", "currency": "USD", "status": "ACTIVE", "revision": 1}
    cohort = {"schema": "QD_PROVIDER_ASSET_RESEARCH_COHORT_V1", "source_digest": "a" * 64,
              "metadata": {"MSFT": item}, "receipt_digests": [{"symbol": "MSFT", "receipt_digest": "b" * 64}],
              "excluded": [], "execution_authorized": False,
              "independent_instrument_authority_verified": False, "robinhood_eligibility_verified": False}
    denied = reviewed_asset_research_universe(batch, cohort, instrument_authority=SimpleNamespace(
        verify_instrument=lambda *args: False))
    assert denied["universe"].symbols() == [] and not denied["execution_authorized"]
    accepted = reviewed_asset_research_universe(batch, cohort, instrument_authority=SimpleNamespace(
        verify_instrument=lambda item, reference, source: source == "a" * 64))
    assert accepted["universe"].symbols() == ["MSFT"] and not accepted["execution_authorized"]
    for corrupt in (cohort | {"source_digest": "c" * 64},
                    cohort | {"receipt_digests": []},
                    cohort | {"execution_authorized": True}):
        with pytest.raises(ValueError):
            reviewed_asset_research_universe(batch, corrupt, instrument_authority=SimpleNamespace(
                verify_instrument=lambda *args: True))
