"""R17 selected native Alpaca one-GET diagnostic: no real network in tests."""
from __future__ import annotations

import copy
import json
from datetime import UTC, datetime
from email.message import Message

import pytest
from app.investment.alpaca_iex import Credentials

from scripts.observation_runtime import atlas_r17_alpaca_iex_rest_probe as r17

NOW = 1794420000


def payload(*, age=0):
    return {"symbol": "MSFT", "quote": {
        "t": datetime.fromtimestamp(NOW-age, UTC).isoformat().replace("+00:00", "Z"),
    }}


class Response:
    def __init__(self, row, endpoint, status=200, ctype="application/json"):
        self.status = status
        self.endpoint = endpoint
        self.raw = json.dumps(row).encode("utf-8")
        self.headers = Message()
        self.headers["Content-Type"] = ctype

    def geturl(self):
        return self.endpoint

    def read(self, length):
        assert length == r17.LIMIT + 1
        return self.raw

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


def trial(*, row=None, status=200, ctype="application/json"):
    observed = []

    def fake_credential(path):
        assert path == r17.CONFIG
        observed.append("DATA_ONLY_CREDENTIAL")
        return Credentials(key="DISPOSABLE-TEST-KEY", secret="DISPOSABLE-TEST-SECRET")

    class FakeHttps:
        def open(self, request, timeout):
            assert timeout == 8
            assert request.get_method() == "GET"
            assert request.full_url == (
                "https://data.alpaca.markets/v2/stocks/MSFT/quotes/latest?feed=iex")
            observed.append("ONE_DATA_GET")
            return Response(row or payload(), request.full_url, status, ctype)

    return r17.probe(
        confirmed_scope=r17.SCOPE, symbol="MSFT",
        credential_reader=fake_credential, opener=FakeHttps(),
        observed_at=NOW,
    ), observed


def test_real_native_r17_selector_current_16_and_no_network():
    actual = r17.require_selected_r17_nonfinancial()
    assert actual["release"] == r17.SOURCE
    assert actual["artifact_digest"] == r17.ARTIFACT
    report = r17.inspect()
    assert report["selected_native_revision"] == 16
    assert report["network_requests"] == 0
    assert report["credential_read"] is False
    assert report["paper_start_authorized"] is False
    assert report["live_trading_authorized"] is False
    assert report["financial_operating_gates_accepted"] == 0


def test_fake_https_single_get_is_sanitized_and_not_financial_authority():
    report, observed = trial()
    assert observed == ["DATA_ONLY_CREDENTIAL", "ONE_DATA_GET"]
    assert report["network_requests"] == 1
    assert report["observed_symbol"] == "MSFT"
    assert report["quote_timestamp_within_five_seconds_of_unqualified_host_clock"]
    assert report["raw_bid_ask_prices_exposed"] is False
    assert report["licensed_execution_entitlement_independently_accepted"] is False
    assert report["continuous_quote_source_and_freshness_verified"] is False
    assert report["paper_start_authorized"] is False
    assert report["real_money_orders_created"] == 0
    assert "DISPOSABLE-TEST-SECRET" not in str(report)


def test_stale_quote_cannot_become_execution_authority():
    report, observed = trial(row=payload(age=120))
    assert len(observed) == 2
    assert report["quote_timestamp_within_five_seconds_of_unqualified_host_clock"] is False
    assert report["financial_operating_gates_accepted"] == 0
    assert report["paper_start_authorized"] is False


@pytest.mark.parametrize("scope,symbol", [
    (None, "MSFT"), ("UNSCOPED", "MSFT"), (r17.SCOPE, "msft"),
    (r17.SCOPE, "BTC/USD"), (r17.SCOPE, "MSFT;DROP"),
])
def test_bad_scope_or_symbol_refuses_before_credentials(monkeypatch, scope, symbol):
    monkeypatch.setattr(r17, "require_selected_r17_nonfinancial",
                        lambda: pytest.fail("BAD_SCOPE_REACHED_NATIVE"))
    with pytest.raises(ValueError, match="R17_IEX_EXACT_DATA_ONLY_SCOPE_REQUIRED"):
        r17.probe(confirmed_scope=scope, symbol=symbol)


@pytest.mark.parametrize("mode", ["bad_status", "wrong_mime", "wrong_symbol", "oversize"])
def test_malformed_http_response_refuses_not_authorizes(mode):
    row = payload()
    status, ctype = 200, "application/json"
    if mode == "bad_status":
        status = 302
    elif mode == "wrong_mime":
        ctype = "text/plain"
    elif mode == "wrong_symbol":
        row["symbol"] = "AAPL"
    else:
        row["oversized"] = "X" * (r17.LIMIT+1)
    with pytest.raises(ValueError):
        trial(row=row, status=status, ctype=ctype)


def test_modified_native_account_roots_refuse_before_credentials(monkeypatch):
    old = r17.inspect_two_lane_native_roots()
    new = copy.deepcopy(old)
    new["all_twelve_distinct_and_empty"] = False
    monkeypatch.setattr(r17, "inspect_two_lane_native_roots", lambda: new)
    with pytest.raises(ValueError, match="R17_IEX_NATIVE_PAPER_ROOTS_CHANGED"):
        trial()


def test_data_only_inspect_does_not_open_secret_file(monkeypatch):
    monkeypatch.setattr(r17.Credentials, "load",
                        lambda *_: pytest.fail("NO_SECRET_READ_FOR_INSPECT"))
    assert r17.inspect()["credential_read"] is False


def test_live_mode_cli_refuses_without_exact_scope(capsys):
    assert r17.main(["--execute-data-only", "--confirm-scope", "WRONG"]) == 2
    raw = capsys.readouterr().out
    assert '"paper_start_authorized": false' in raw
    assert '"http_data_endpoint_responded": false' in raw
