"""Offline synthetic regression of original IEX quote gate and count-only wrapper.

No Alpaca connection, credentials, raw real provider event or finance journal.
"""
import json
from datetime import UTC, datetime

import pytest
from app.investment.alpaca_iex import IEXFeed

from scripts.observation_runtime.atlas_iex_rejection_reasons_data_only import (
    REASON_CODES,
    CountOnlyIEXRejectionDiagnostic,
)

BASE_SECONDS = datetime(2026, 11, 18, 15, 1, 1, tzinfo=UTC).timestamp()
BASE_STAMP = "2026-11-18T15:01:01Z"


def quote(symbol="AVGO", **update):
    base = {
        "T": "q", "S": symbol, "bp": 100, "ap": 100.01,
        "bs": 10, "as": 12, "bx": "V", "ax": "V", "z": "C",
        "c": ["R"], "t": BASE_STAMP,
    }
    base.update(update)
    return base


def ready(*, clock=None):
    f = CountOnlyIEXRejectionDiagnostic(
        ["MSFT", "AVGO", "SPY"], clock=clock or (lambda: BASE_SECONDS + .5)
    )
    f.receive('[{"T":"success","msg":"authenticated"}]')
    f.receive('[{"T":"subscription","quotes":["AVGO","MSFT","SPY"]}]')
    return f


def send(f, frame):
    f.receive(json.dumps([frame]))


@pytest.mark.parametrize(
    ("frame", "reason"),
    [
        (quote(bp="100"), "PRICE_TYPE_OR_NONFINITE"),
        (quote(bp=0), "ZERO_OR_CROSSED_SIDE"),
        (quote(bp=101), "ZERO_OR_CROSSED_SIDE"),
        (quote(ap=102), "SPREAD_OVER_100_BASIS_POINTS"),
        (quote(bs=0), "INVALID_QUOTE_SIZE_SHARES"),
        (quote(**{"as": 0}), "INVALID_QUOTE_SIZE_SHARES"),
        (quote(c=["O"]), "NON_REGULAR_QUOTE_CONDITION"),
        (quote(c=["R", "O"]), "NON_REGULAR_QUOTE_CONDITION"),
        (quote(bx=""), "EXCHANGE_OR_TAPE_ABSENT"),
        (quote(t="bad"), "INVALID_SOURCE_TIMESTAMP"),
        (quote(t="2026-11-18T15:00:50Z"), "STALE_OR_FUTURE_QUOTE_TIMESTAMP"),
        (quote(t="2026-11-18T15:01:03Z"), "STALE_OR_FUTURE_QUOTE_TIMESTAMP"),
    ],
)
def test_diagnostic_labels_match_original_fail_closed_rejection(frame, reason):
    f = ready()
    send(f, frame)
    assert f.snapshot()["quotes"][1]["state"] == "UNAVAILABLE"
    assert f.quote_messages_rejected["AVGO"] == 1
    sample = f.count_only_snapshot()
    assert sample["reason_counts"]["AVGO"][reason] == 1
    assert sum(sample["reason_counts"]["AVGO"].values()) == 1
    assert sum(sample["reason_counts"]["MSFT"].values()) == 0
    assert f.reconcile_rejected_counts({
        "AVGO": {"rejected": 1},
        "MSFT": {"rejected": 0},
        "SPY": {"rejected": 0},
    }) == sample
    encoded = json.dumps(sample, sort_keys=True)
    assert '"bp"' not in encoded and '"ap"' not in encoded
    assert BASE_STAMP not in encoded and "100.01" not in encoded
    assert sample["paper_start_authorized"] is False


def test_accepted_quotes_unaffected_and_ordinary_feed_parity():
    f = ready()
    original = IEXFeed(["MSFT", "AVGO", "SPY"], clock=lambda:BASE_SECONDS + .5)
    original.receive('[{"T":"success","msg":"authenticated"}]')
    original.receive('[{"T":"subscription","quotes":["AVGO","MSFT","SPY"]}]')
    for frame in [quote(), quote("MSFT"), quote("SPY")]:
        send(f, frame)
        send(original, frame)
    assert f.snapshot() == original.snapshot()
    assert f.quote_messages_accepted == original.quote_messages_accepted
    assert all(sum(x.values()) == 0 for x in f.count_only_snapshot()["reason_counts"].values())


def test_rejection_does_not_resurrect_previous_valid_quote():
    f = ready()
    send(f, quote())
    assert f.snapshot()["quotes"][1]["state"] == "FRESH"
    send(f, quote(bp=0))
    assert f.snapshot()["quotes"][1]["state"] == "UNAVAILABLE"
    assert f.quote_messages_accepted["AVGO"] == 1
    assert f.quote_messages_rejected["AVGO"] == 1


def test_timestamp_regression_and_conflict_are_detected():
    f = ready()
    send(f, quote(t="2026-11-18T15:01:01.123456789Z"))
    send(f, quote(t="2026-11-18T15:01:01.1Z"))
    # The real parser removes a rejected quote from current executable state.
    # Restore an independently valid new event before testing a same-time conflict.
    send(f, quote(t="2026-11-18T15:01:01.123456789Z"))
    send(f, quote(t="2026-11-18T15:01:01.123456789Z", ap=100.02))
    assert f.quote_messages_rejected["AVGO"] == 2
    assert (f.count_only_snapshot()["reason_counts"]["AVGO"]
            ["TIMESTAMP_REVERSED_OR_CONFLICTED"] == 2)


def test_missing_timestamp_fails_closed_and_is_never_guessed():
    f = ready()
    frame = quote()
    del frame["t"]
    send(f, frame)
    assert f.quote_messages_rejected["AVGO"] == 1
    assert f.count_only_snapshot()["reason_counts"]["AVGO"][
        "UNCLASSIFIED_ORIGINAL_REFUSAL"] == 1


def test_reconciliation_refuses_inconsistent_original_totals():
    f = ready()
    send(f, quote(c=["H"]))
    with pytest.raises(ValueError, match="ORIGINAL_REJECTION_TOTAL_MISMATCH"):
        f.reconcile_rejected_counts({
            "AVGO": {"rejected": 0}, "MSFT": {"rejected": 0}, "SPY": {"rejected": 0}
        })
    with pytest.raises(ValueError, match="IDENTITY_REFUSED"):
        f.reconcile_rejected_counts({"AVGO": {"rejected": 1}})


def test_private_quote_values_never_in_count_only_summary():
    f = ready()
    send(f, quote(bp=99999, ap=100000))
    encoded = json.dumps(f.count_only_snapshot(), sort_keys=True)
    assert "99999" not in encoded and "100000" not in encoded
    assert "2026-11" not in encoded
    assert "ALPACA_API_KEY" not in encoded
    assert tuple(f.count_only_snapshot()["reason_counts"]["AVGO"]) == REASON_CODES


def test_unknown_kind_does_not_count_as_quote():
    f = ready()
    send(f, {"T": "b", "S": "AVGO", "bp": 0})
    assert f.quote_messages_seen["AVGO"] == 0
    assert all(sum(x.values()) == 0 for x in f.count_only_snapshot()["reason_counts"].values())

@pytest.mark.asyncio
async def test_original_source_only_probe_with_rejection_reason_adapter():
    """Original probe emits only admitted frames; sidecar labels refused ones."""
    import asyncio
    from contextlib import asynccontextmanager
    from types import SimpleNamespace

    from app.investment.alpaca_iex import URL, Credentials

    from scripts.observation_runtime import alpaca_iex_probe as original_probe

    frames = [
        '[{"T":"success","msg":"authenticated"}]',
        '[{"T":"subscription","quotes":["AVGO","SPY"]}]',
        json.dumps([
            quote("AVGO", c=["H"]),
            quote("AVGO", bs=0),
            quote("AVGO"),
            quote("SPY"),
        ]),
    ]

    class SyntheticSocket:
        def __init__(self):
            self.request=SimpleNamespace(
                headers={"Host":"stream.data.alpaca.markets"},path="/v2/iex"
            )
            self.sent=[]

        async def send(self,payload):
            self.sent.append(json.loads(payload))

        async def recv(self):
            if frames:
                return frames.pop(0)
            await asyncio.sleep(.01)
            raise TimeoutError

    socket=SyntheticSocket()

    @asynccontextmanager
    async def connect(url, **kwargs):
        assert url==URL and kwargs["logger"].disabled
        yield socket

    installed_adapters=[]

    class SyntheticCountOnlyFeed(CountOnlyIEXRejectionDiagnostic):
        def __init__(self,symbols):
            super().__init__(symbols,clock=lambda:BASE_SECONDS+.5)
            installed_adapters.append(self)

        async def run(self,credentials,*,seconds,max_reconnects,on_fresh_quote):
            return await super().run(
                credentials,seconds=seconds,max_reconnects=max_reconnects,
                on_fresh_quote=on_fresh_quote,connect=connect
            )

    observed=await original_probe.bounded_data_only_probe(
        seconds=1,symbols=["AVGO","SPY"],
        credentials=Credentials("SYNTHETIC-KEY","SYNTHETIC-SECRET"),
        feed_factory=SyntheticCountOnlyFeed,
    )
    assert observed["status"]=="BOUNDED_FRESH_IEX_OBSERVED_NOT_FINANCIAL_AUTHORITY"
    assert observed["observed_symbols"]==["AVGO","SPY"]
    assert observed["per_symbol_quote_diagnostics"]=={
        "AVGO":{"received":3,"accepted":1,"rejected":2,"fresh_callbacks":1},
        "SPY":{"received":1,"accepted":1,"rejected":0,"fresh_callbacks":1},
    }
    data=installed_adapters[0].reconcile_rejected_counts(
        observed["per_symbol_quote_diagnostics"]
    )
    counts=data["reason_counts"]["AVGO"]
    assert counts["NON_REGULAR_QUOTE_CONDITION"]==1
    assert counts["INVALID_QUOTE_SIZE_SHARES"]==1
    assert sum(counts.values())==2
    assert socket.sent[0]["action"]=="auth"
    assert socket.sent[1]=={"action":"subscribe","quotes":["AVGO","SPY"]}
    assert observed["provider_rights_independently_accepted"] is False
    assert observed["paper_fill_authorized"] is False
    assert data["live_order_authorized"] is False
    assert "100.01" not in json.dumps(data)

def test_refusal_snapshot_before_feed_exists_is_unknown_not_false_zero():
    from scripts.observation_runtime.atlas_iex_rejection_reasons_data_only import (
        preserve_original_probe_refusal,
    )

    result = preserve_original_probe_refusal(
        {"status": "REFUSED", "reason": "IEX_CONFIGURATION_OR_DATA_UNAVAILABLE"},
        None,
    )
    diagnostic = result["count_only_diagnostics"]
    assert diagnostic["feed_instantiated"] is False
    assert diagnostic["per_symbol_quote_diagnostics"] is None
    assert diagnostic["original_auth_ack_observed"] is None
    assert result["financial_paper_authorized"] is False


def test_refusal_snapshot_rejects_unsafe_original_success_or_untrusted_reason():
    from scripts.observation_runtime.atlas_iex_rejection_reasons_data_only import (
        preserve_original_probe_refusal,
    )

    for message in (
        {"status": "SUCCESS", "reason": "IEX_CONFIGURATION_OR_DATA_UNAVAILABLE"},
        {"status": "REFUSED", "reason": "secret data accidentally included"},
        {"status": "REFUSED", "reason": "IEX_CONFIGURATION_OR_DATA_UNAVAILABLE",
         "headers": "Authorization secret"},
    ):
        with pytest.raises(ValueError, match="UNRECOGNIZED_PROBE_RESPONSE"):
            preserve_original_probe_refusal(message, None)


def test_refusal_snapshot_redacts_arbitrary_native_error_text():
    from scripts.observation_runtime.atlas_iex_rejection_reasons_data_only import (
        refusal_safe_snapshot,
    )

    f = ready()
    f.disconnect("Authorization: private provider token")
    report = refusal_safe_snapshot(f)
    assert report["last_native_error_code"] == "REDACTED_OR_UNKNOWN_NATIVE_FEED_ERROR"
    assert "private" not in json.dumps(report).lower()
    assert report["per_symbol_quote_diagnostics"]["AVGO"]["received"] == 0


def test_refusal_snapshot_rejects_unsafe_nonreconciled_counts_and_running_feed():
    from scripts.observation_runtime.atlas_iex_rejection_reasons_data_only import (
        refusal_safe_snapshot,
    )

    f = ready()
    send(f, quote(c=["H"]))
    with f.lock:
        f._reason_counts["AVGO"]["NON_REGULAR_QUOTE_CONDITION"] = 0
    with pytest.raises(ValueError, match="NATIVE_COUNTS_MISMATCH"):
        refusal_safe_snapshot(f)


@pytest.mark.parametrize(
    ("frames", "expected_auth", "expected_sub", "native_code", "reasons"),
    [
        ([{"T":"error", "code":402}], False, False, "IEX_AUTH_FAILED", 0),
        ([{"T":"success", "msg":"authenticated"},
          {"T":"subscription", "quotes":["SPY"]}],
         True, False, "IEX_SUBSCRIPTION_MISMATCH", 0),
        ([{"T":"success", "msg":"authenticated"},
          {"T":"subscription", "quotes":["AVGO","SPY"]},
          quote("AVGO", c=["H"]),
          quote("AVGO", bs=0)],
         True, True, "IEX_BOUNDED_PROBE_COMPLETE", 2),
    ],
    ids=["auth-refused","subscription-mismatch","only-rejected-AVGO-frames"],
)
def test_real_original_selected_probe_refusal_retains_reason_counts_offline(
    monkeypatch, capsys, frames, expected_auth, expected_sub, native_code, reasons,
):
    """The *original* R24 main refuses; our added opt-in reporter saves counts."""
    import asyncio
    import io
    import types
    from contextlib import asynccontextmanager, redirect_stdout
    from types import SimpleNamespace

    from app.investment.alpaca_iex import URL, Credentials

    from scripts.observation_runtime import alpaca_iex_probe as original_probe
    from scripts.observation_runtime.atlas_iex_rejection_reasons_data_only import (
        preserve_original_probe_refusal,
    )

    class NoNetworkSocket:
        def __init__(self):
            self.request = SimpleNamespace(
                headers={"Host": "stream.data.alpaca.markets"}, path="/v2/iex",
            )
            self.sent = []
            self.frames = [json.dumps([f]) for f in frames]

        async def send(self, payload):
            data = json.loads(payload)
            self.sent.append({"action": data["action"]})  # no key ever stored

        async def recv(self):
            if self.frames:
                return self.frames.pop(0)
            await asyncio.sleep(.005)
            raise TimeoutError

    socket = NoNetworkSocket()

    @asynccontextmanager
    async def no_network_connect(url, **kwargs):
        assert url == URL and kwargs["logger"].disabled
        yield socket

    created = []

    def feed_factory(symbols):
        assert symbols == ["AVGO", "SPY"]
        assert not created
        feed = CountOnlyIEXRejectionDiagnostic(
            symbols, clock=lambda: BASE_SECONDS + .5,
        )
        async def run_with_no_network(self, credentials, **kwargs):
            return await IEXFeed.run(
                self, credentials, connect=no_network_connect, **kwargs,
            )
        feed.run = types.MethodType(run_with_no_network, feed)
        created.append(feed)
        return feed

    # This monkeypatch is TEST-ONLY and never changes installed original R24.
    monkeypatch.setattr(
        original_probe, "inspect_selected_data_only",
        lambda: {
            "selected_revision": 24,
            "future_selected_native_source_verified": True,
            "trading_authorized": False,
            "provider_rights_independently_accepted": False,
        },
    )
    capture = io.StringIO()
    with redirect_stdout(capture):
        exitcode = original_probe.main(
            ["--execute-data-only", "--confirm-scope", original_probe.SCOPE,
             "--seconds", "1", "--symbols", "AVGO", "SPY"],
            credentials_loader=lambda ignored: Credentials(
                "SYNTHETIC_LOCAL_KEY", "SYNTHETIC_LOCAL_SECRET",
            ),
            feed_factory=feed_factory,
        )
    assert exitcode == 1  # selected ORIGINAL R24 probe itself refused
    original_response = json.loads(capture.getvalue())
    assert len(created) == 1
    sanitized = preserve_original_probe_refusal(original_response, created[0])
    data = sanitized["count_only_diagnostics"]
    assert data["original_auth_ack_observed"] is expected_auth
    assert data["original_subscription_ack_observed"] is expected_sub
    assert data["last_native_error_code"] == native_code
    assert data["per_symbol_quote_diagnostics"]["AVGO"]["rejected"] == reasons
    assert sum(data["per_symbol_rejection_reason_counts"]["AVGO"].values()) == reasons
    assert data["per_symbol_quote_diagnostics"]["SPY"]["received"] == 0
    assert sanitized["original_probe_refused"] is True
    assert sanitized["financial_paper_authorized"] is False
    assert sanitized["live_money_authorized"] is False
    encoded = json.dumps(sanitized, sort_keys=True)
    assert "SYNTHETIC_LOCAL_KEY" not in encoded
    assert "SYNTHETIC_LOCAL_SECRET" not in encoded
    assert BASE_STAMP not in encoded
    assert "100.01" not in encoded
    assert "stream.data.alpaca.markets" not in encoded
    assert not capsys.readouterr().out
    if reasons:
        assert data["per_symbol_rejection_reason_counts"]["AVGO"][
            "NON_REGULAR_QUOTE_CONDITION"
        ] == 1
        assert data["per_symbol_rejection_reason_counts"]["AVGO"][
            "INVALID_QUOTE_SIZE_SHARES"
        ] == 1
