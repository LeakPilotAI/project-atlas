"""Offline contract tests for R16 account identity GET and redaction."""
from __future__ import annotations

import copy
import json
from types import SimpleNamespace

import pytest
from app.investment.alpaca_iex import Credentials

from scripts.observation_runtime import (
    atlas_r16_alpaca_paper_identity_readonly as probe,
)

PAPER = {
    "id": "123e4567-e89b-42d3-a456-426614174000",
    "account_number": "VERY_PRIVATE_PAPER_ACCOUNT_NUMBER",
    "cash": "9000000",
    "buying_power": "10000000",
    "equity": "9000000",
    "status": "ACTIVE",
    "currency": "USD",
    "account_blocked": False,
}


class Response:
    def __init__(self, payload=None, *, status=200, url=probe.ACCOUNT_URL,
                 content_type="application/json"):
        self.status = status
        self.url = url
        self.headers = SimpleNamespace(get_content_type=lambda: content_type)
        self.payload = json.dumps(PAPER if payload is None else payload).encode()

    def geturl(self):
        return self.url

    def read(self, limit):
        return self.payload[:limit]

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


class FixedOpener:
    def __init__(self, response=None):
        self.response = response or Response()
        self.calls = []

    def open(self, request, timeout):
        self.calls.append({
            "url": request.full_url,
            "method": request.get_method(),
            "timeout": timeout,
            "request": request,
        })
        return self.response


@pytest.fixture
def confined(monkeypatch, tmp_path):
    path = tmp_path / "alpaca-data-only.env"
    path.write_text(
        "ALPACA_API_KEY=synthetic-alpaca-key\n"
        "ALPACA_API_SECRET=synthetic-alpaca-secret\n"
        "ALPACA_TRADING_ENABLED=false\n"
        "ALPACA_DATA_FEED=iex\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(probe, "CONFIG", path)
    selection = {"code_selection_accepted": True, "selected": "SYNTHETIC_R16"}
    roots = {
        "native_root_total": 12,
        "all_twelve_distinct_and_empty": True,
        "synthetic_only": True,
    }
    monkeypatch.setattr(probe, "require_selected_r16_data_only", lambda: copy.deepcopy(selection))
    monkeypatch.setattr(probe, "inspect_two_lane_native_roots", lambda: copy.deepcopy(roots))
    return path, selection, roots


def test_public_docs_allow_paper_algo_iex_but_never_grant_local_financial_start():
    packet = probe.no_grant()
    assert packet["public_documentation_paper_iex_algo_support"] is True
    assert "paper-trading" in packet["documentation"][0]
    assert packet["provider_market_data_entitlement_independently_verified"] is False
    assert packet["account_specific_terms_and_redistribution_rights_independently_verified"] is False
    assert not packet["paper_start_authorized"]
    assert not packet["live_trading_authorized"]


def test_paper_account_identity_redacts_all_private_values():
    report = probe.interpret_paper_account(copy.deepcopy(PAPER))
    assert report["paper_trading_api_authenticated"] is True
    assert report["paper_account_status_suitable_for_data_research"]
    assert "VERY_PRIVATE" not in repr(report)
    assert PAPER["id"] not in repr(report)
    assert "9000000" not in repr(report)


@pytest.mark.parametrize("status", ["INACTIVE", "ONBOARDING", "ACCOUNT_CLOSED", "REJECTED"])
def test_non_active_paper_api_does_not_qualify_data_readiness(status):
    account = dict(PAPER, status=status)
    report = probe.interpret_paper_account(account)
    assert report["paper_trading_api_authenticated"]
    assert report["paper_account_status_suitable_for_data_research"] is False


@pytest.mark.parametrize("damage", [
    None, [], {}, {"status": "ACTIVE"}, dict(PAPER, id="INVALID"),
    dict(PAPER, status="BUY_SELL_ON_LIVE"), dict(PAPER, currency="EUR"),
    dict(PAPER, status=True), dict(PAPER, id=123),
])
def test_malformed_account_identity_never_accepted(damage):
    with pytest.raises(ValueError):
        probe.interpret_paper_account(damage)


def test_bounded_single_get_confirms_paper_api_without_orders(confined):
    opener = FixedOpener()
    result = probe.probe(
        confirmed_scope=probe.SCOPE, opener=opener)
    assert len(opener.calls) == 1
    call = opener.calls[0]
    assert call["url"] == "https://paper-api.alpaca.markets/v2/account"
    assert call["method"] == "GET" and call["timeout"] == 8
    assert result["paper_trading_api_authenticated"]
    assert result["paper_account_status_suitable_for_data_research"]
    assert not result["provider_market_data_entitlement_independently_verified"]
    assert not result["continuous_source_accepted"]
    assert result["orders_sent"] == 0
    assert result["account_modifications"] == 0
    assert result["native_financial_roots_unmodified"]
    assert PAPER["account_number"] not in str(result)
    assert PAPER["id"] not in str(result)
    assert "9000000" not in str(result)


def test_readonly_inspect_does_not_read_credentials_or_send_network(confined, monkeypatch):
    seen = []
    monkeypatch.setattr(Credentials, "load", lambda path: seen.append(path))
    result = probe.inspect()
    assert result["network_requests"] == 0
    assert result["credentials_file_present_unread"]
    assert seen == []
    assert result["paper_trading_api_authenticated"] is False


@pytest.mark.parametrize("damage", [
    "missing_scope", "wrong_scope", "root_modified", "changed_selection",
    "redirect", "bad_status", "wrong_mime", "oversize", "wrong_json",
    "trading_enabled",
])
def test_invalid_scope_or_provider_response_refuses_before_grant(
        confined, monkeypatch, damage):
    path, selected, roots = confined
    opener = FixedOpener()
    scope = probe.SCOPE
    if damage == "missing_scope":
        scope = None
    elif damage == "wrong_scope":
        scope = "TRADE_LIVE"
    elif damage == "root_modified":
        roots["all_twelve_distinct_and_empty"] = False
        monkeypatch.setattr(probe, "inspect_two_lane_native_roots", lambda: roots)
    elif damage == "changed_selection":
        observed = [0]
        def selection():
            observed[0] += 1
            return {**selected, "selected": f"R16_{observed[0]}"}
        monkeypatch.setattr(probe, "require_selected_r16_data_only", selection)
    elif damage == "redirect":
        opener = FixedOpener(Response(url="https://api.alpaca.markets/v2/account"))
    elif damage == "bad_status":
        opener = FixedOpener(Response(status=403))
    elif damage == "wrong_mime":
        opener = FixedOpener(Response(content_type="text/html"))
    elif damage == "oversize":
        opener = FixedOpener(Response(payload={"blob": "z" * 33000}))
    elif damage == "wrong_json":
        opener = FixedOpener(Response(payload={"schema": "OTHER"}))
    elif damage == "trading_enabled":
        path.write_text(path.read_text().replace("false", "true"), encoding="utf-8")
    with pytest.raises(ValueError):
        probe.probe(confirmed_scope=scope, opener=opener)
    assert len(opener.calls) <= 1
    assert all(call["url"] == probe.ACCOUNT_URL and call["method"] == "GET"
               for call in opener.calls)


def test_forged_credential_reader_rejected_before_network(confined):
    opened = FixedOpener()
    with pytest.raises(ValueError, match="DATA_ONLY_CREDENTIALS_REQUIRED"):
        probe.probe(
            confirmed_scope=probe.SCOPE,
            credentials_reader=lambda path: object(),
            opener=opened)
    assert opened.calls == []


def test_no_live_host_literal_or_financial_order_endpoint_in_any_request(confined):
    opened = FixedOpener()
    result = probe.probe(confirmed_scope=probe.SCOPE, opener=opened)
    assert not result["live_api_host_contacted"]
    assert "/v2/orders" not in str(opened.calls)
    assert "https://api.alpaca.markets" not in opened.calls[0]["url"]
    assert result["financial_operating_gates_accepted"] == 0
