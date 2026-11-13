"""R20 native IEX REST source-only validation; NO financial account or provider calls."""
from __future__ import annotations

import copy
import json
import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from email.message import Message
from pathlib import Path

import pytest
from app.investment.alpaca_iex import Credentials

from scripts.observation_runtime import atlas_r20_native_iex_latest_readonly as iex

NOW = 1_800_000_000
UTCSTAMP = datetime.fromtimestamp(NOW, UTC)


def quote(symbol="MSFT", age=2):
    return {
        "symbol": symbol,
        "quote": {
            "t": (UTCSTAMP - timedelta(seconds=age)).isoformat().replace("+00:00", "Z"),
            "bp": Decimal("100.01"),
            "ap": Decimal("100.03"),
            "bs": 10,
            "as": 15,
            "bx": "V",
            "ax": "V",
        },
    }


@pytest.mark.parametrize("age,fresh", [
    (-7, False), (-1, False), (0, True), (2, True), (3, True),
    (4, False), (5, False), (6, False), (10_000, False),
])
def test_bounded_independent_utc_never_grants_paper_quote(age, fresh):
    data = quote(age=age)
    freeze = copy.deepcopy(data)
    r = iex.inspect_quote(
        data, symbol="MSFT", observed_ns=NOW * 10**9,
        uncertainty_ms=139,
    )
    assert data == freeze
    assert r["provider_quote_fresh_at_sample"] is fresh
    assert r["executable_paper_quote_authorized"] is False
    assert "bp" not in str(r) and "100." not in str(r)
    assert r["share_sizes_valid"] is True
    assert r["provider_exchange"] == "IEX"


@pytest.mark.parametrize("bad", [
    "wrong_symbol", "extra_field", "naive_time", "foreign_zone", "bad_time",
    "missing_ask", "negative_bid", "crossed", "string_price", "nan",
    "wrong_exchange", "wrong_ask_exchange", "bad_max_shares", "no_shares",
    "negative_shares", "string_shares", "false_shares", "future_epoch",
])
def test_invalid_real_quote_wire_cannot_pass(bad):
    data = quote()
    stamp = NOW * 10**9
    symbol = "MSFT"
    if bad == "wrong_symbol":
        data["symbol"] = "AVGO"
    elif bad == "extra_field":
        data["paper_approved"] = True
    elif bad == "naive_time":
        data["quote"]["t"] = "2026-11-13T10:01:01"
    elif bad == "foreign_zone":
        data["quote"]["t"] = "2026-11-13T10:01:01-06:00"
    elif bad == "bad_time":
        data["quote"]["t"] = "2026-99-99T12:00:00Z"
    elif bad == "missing_ask":
        data["quote"].pop("ap")
    elif bad == "negative_bid":
        data["quote"]["bp"] = Decimal(-1)
    elif bad == "crossed":
        data["quote"]["bp"] = Decimal(102)
    elif bad == "string_price":
        data["quote"]["ap"] = "100.03"
    elif bad == "nan":
        data["quote"]["ap"] = Decimal("NaN")
    elif bad == "wrong_exchange":
        data["quote"]["bx"] = "N"
    elif bad == "wrong_ask_exchange":
        data["quote"]["ax"] = "P"
    elif bad == "bad_max_shares":
        data["quote"]["as"] = 10**9 + 1
    elif bad == "no_shares":
        data["quote"].pop("bs")
    elif bad == "negative_shares":
        data["quote"]["bs"] = -1
    elif bad == "string_shares":
        data["quote"]["bs"] = "10"
    elif bad == "false_shares":
        data["quote"]["bs"] = True
    else:
        stamp = 0
    with pytest.raises(ValueError):
        iex.inspect_quote(
            data, symbol=symbol, observed_ns=stamp, uncertainty_ms=139,
        )


class Response:
    status = 200
    def __init__(self, url, data, *, status=200, source_url=None,
                 content_type="application/json", raw=None):
        self.url, self.status = url, status
        self.source_url = source_url or url
        self.data = raw if raw is not None else json.dumps(data, default=float).encode()
        self.headers = Message()
        self.headers.add_header("Content-Type", content_type)
        self.read_count = 0
        self.closed = False

    def geturl(self):
        return self.source_url

    def read(self, amount):
        self.read_count += 1
        assert amount == iex.MAX_BYTES + 1
        return self.data[:amount]

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.closed = True


@pytest.mark.parametrize("failure", [
    "http_403", "redirect", "html", "large", "zero", "duplicate",
    "nonfinite", "bad_json",
])
def test_provider_http_evidence_refuses_on_boundary_break(failure):
    url = iex.BASE + "MSFT/quotes/latest?feed=iex"
    data = quote()
    response = Response(url, data)
    if failure == "http_403":
        response.status = 403
    elif failure == "redirect":
        response.source_url = "https://example.net/hijack"
    elif failure == "html":
        response.headers = Message()
        response.headers.add_header("Content-Type", "text/html")
    elif failure == "large":
        response.data = b" " * (iex.MAX_BYTES + 1)
    elif failure == "zero":
        response.data = b""
    elif failure == "duplicate":
        response.data = b'{"symbol":"MSFT","symbol":"MSFT","quote":{}}'
    elif failure == "nonfinite":
        response.data = b'{"symbol":"MSFT","quote":{"bp":NaN}}'
    elif failure == "bad_json":
        response.data = b"{broken"
    with pytest.raises(ValueError):
        iex._decode_response(response, url)


class FakeOwner:
    _phase = "PREINCEPTION"
    def __init__(self):
        self.valid = True
        self.checks = 0
    def verify_still_running(self):
        self.checks += 1
        return self.valid


class FakeClock:
    def __init__(self):
        self.accepted = True
    def require_operational(self, name):
        if name != "test-owned" or not self.accepted:
            raise ValueError("CLOCK_REFUSED")
        return self
    def sample(self):
        return {"utc": NOW, "uncertainty_ms": 139}
    def verify(self, sample):
        return sample == {"utc": NOW, "uncertainty_ms": 139}

    def sample_precise(self):
        return {
            "schema": "ATLAS_INDEPENDENT_PRECISE_UTC_V1",
            "utc_ns": NOW * 10**9 + 500_000_000,
            "monotonic_ns": 777,
            "uncertainty_ms": 139,
            "source": "TEST_ONLY",
        }

    def verify_precise(self, sample):
        return sample == type(self).sample_precise(self)


class Opener:
    def __init__(self, ages):
        self.ages = ages
        self.requests = []
        self.responses = []
    def open(self, request, timeout):
        assert timeout == 8
        assert request.get_method() == "GET"
        assert request.full_url.endswith("/quotes/latest?feed=iex")
        assert request.full_url.startswith(iex.BASE)
        assert request.headers["Apca-api-key-id"] == "DATA_ONLY_DUMMY"
        assert request.headers["Apca-api-secret-key"] == "DATA_ONLY_DUMMY"
        symbol = request.full_url[len(iex.BASE):].split("/")[0]
        response = Response(request.full_url, quote(symbol, self.ages[symbol]))
        self.requests.append(request)
        self.responses.append(response)
        return response


@pytest.fixture()
def test_ports(monkeypatch):
    monkeypatch.setattr(iex, "RetainedSelectedNativeOwnerPreflight", FakeOwner)
    monkeypatch.setattr(iex, "NativeVersionSafePaperOperatorClock", FakeClock)
    monkeypatch.setattr(iex, "_installed_ports", lambda **kw: None)
    monkeypatch.setattr(iex, "_required_data_only_config",
                        lambda: Path(r"D:\Work\Project Atlas\config\alpaca.env"))
    monkeypatch.setattr(iex, "require_version_safe_release_digest",
                        lambda **kw: True)
    return FakeOwner(), FakeClock()


def _run(ports, ages, symbols=("MSFT", "AVGO")):
    original, clock = ports
    opener = Opener(ages)
    report = iex.audit_owned_iex(
        owner=original, clock=clock, runtime_id="test-owned",
        release_digest="a" * 64, symbols=symbols, opener=opener,
        credential_reader=lambda _: Credentials(
            "DATA_ONLY_DUMMY", "DATA_ONLY_DUMMY"
        ),
    )
    return report, opener


def test_multi_symbol_stale_latest_data_does_not_become_paper_quote(test_ports):
    report, opener = _run(test_ports, {"MSFT": 1, "AVGO": 60})
    assert report["schema"] == iex.SCHEMA
    assert report["provider_rest_authentication_observed"] is True
    assert report["http_get_count"] == 2
    assert report["fresh_quote_count"] == 1
    assert report["stale_or_not_current_quote_count"] == 1
    assert report["both_sided_quote_count"] == 2
    assert report["missing_quote_side_count"] == 0
    assert report["fresh_and_both_sided_source_only_count"] == 1
    assert report["status"] == "PROVIDER_REACHABLE_BUT_NOT_ALL_QUOTES_CURRENT_DATA_ONLY"
    assert len(opener.requests) == 2
    assert all(resp.closed for resp in opener.responses)
    assert all(report[field] is False for field in (
        "provider_data_rights_independently_accepted",
        "authenticated_operational_research_issuer_accepted",
        "financial_quote_admission_accepted", "market_session_verified",
        "financial_inception_authorized", "paper_startup_authorized",
        "live_trading_authorized",
    ))
    assert "DATA_ONLY_DUMMY" not in str(report)
    assert "100." not in str(report)


def test_all_recent_still_no_financial_or_session_rights(test_ports):
    report, opener = _run(
        test_ports, dict.fromkeys(iex.WATCHLIST, 2), symbols=iex.WATCHLIST
    )
    assert report["fresh_quote_count"] == 4
    assert report["fresh_and_both_sided_source_only_count"] == 4
    assert report["status"] == "ALL_LATEST_QUOTES_RECENT_DATA_ONLY"
    assert len(opener.requests) == 4
    assert report["financial_quote_admission_accepted"] is False


@pytest.mark.parametrize("symbols", [
    (), ("MSFT", "MSFT"), ("FAKE",), ("msft",),
    ("MSFT", "AVGO", "SCHD", "VTI", "QQQ"), ["MSFT"], ("MSFT", True),
])
def test_invalid_roster_refuses_before_clock_credentials_and_http(test_ports, symbols):
    owner, clock = test_ports
    opener = Opener({})
    with pytest.raises(ValueError, match="BOUNDED_WATCHLIST"):
        iex.audit_owned_iex(
            owner=owner, clock=clock, runtime_id="test-owned",
            release_digest="a" * 64,
            symbols=symbols, opener=opener,
            credential_reader=lambda _: pytest.fail("credential access not allowed"),
        )
    assert not opener.requests and owner.checks == 0


@pytest.mark.parametrize("tamper", [
    "owner_type", "owner_phase", "owner_revoked",
    "clock_type", "clock_revoked", "wrong_runtime", "release_refused",
])
def test_owner_clock_and_native_release_refuse_before_credentials(
    monkeypatch, test_ports, tamper,
):
    owner, clock = test_ports
    rid = "test-owned"
    if tamper == "owner_type":
        owner = object()
    elif tamper == "owner_phase":
        owner._phase = "PREINCEPTION_COORDINATION_READY"
    elif tamper == "owner_revoked":
        owner.valid = False
    elif tamper == "clock_type":
        clock = object()
    elif tamper == "clock_revoked":
        clock.accepted = False
    elif tamper == "wrong_runtime":
        rid = "foreign"
    else:
        monkeypatch.setattr(iex, "require_version_safe_release_digest",
                            lambda **kw: False)
    with pytest.raises((ValueError, AttributeError)):
        iex.audit_owned_iex(
            owner=owner, clock=clock, runtime_id=rid,
            release_digest="a" * 64,
            symbols=("MSFT",),
            credential_reader=lambda _: pytest.fail("credential access not allowed"),
            opener=Opener({}),
        )


def test_selected_original_source_is_not_workspace_research_issuer():
    with pytest.raises(ValueError, match="INSTALLED_SELECTED_PORTS"):
        iex._installed_ports(
            release=Path(sys.executable).resolve().parent.parent,
        )



@pytest.mark.parametrize("bid,ask,bid_shares,ask_shares", [
    (0, 100, 0, 10), (100, 0, 10, 0), (0, 0, 0, 0),
    (0, 100, 10, 10), (100, 101, 0, 0),
])
def test_off_session_iex_zero_side_is_data_only_not_executable(
    bid, ask, bid_shares, ask_shares,
):
    # Alpaca IEX explicitly uses zero for an absent bid/ask. Preserve
    # source transport while forbidding a paper entry or presumed liquidity.
    data = quote(age=1)
    data["quote"].update(
        bp=Decimal(bid), ap=Decimal(ask), bs=bid_shares, **{"as": ask_shares},
    )
    row = iex.inspect_quote(
        data, symbol="MSFT", observed_ns=NOW * 10**9,
        uncertainty_ms=139,
    )
    assert row["provider_quote_fresh_at_sample"] is True
    assert row["bid_and_ask_present"] is False
    assert row["missing_one_or_both_sided_executable_quote"] is True
    assert row["executable_paper_quote_authorized"] is False


def test_partial_latest_quote_does_not_become_qualified_execution(test_ports):
    # One mock quote absent on the IEX single venue; still count the response.
    owner, clock = test_ports

    class ZeroOpener(Opener):
        def open(self, request, timeout):
            response = super().open(request, timeout)
            if "AVGO" in request.full_url:
                response.data = json.dumps(
                    {**quote("AVGO"), "quote": {
                        **quote("AVGO")["quote"], "bp": 0, "bs": 0
                    }},
                    default=float,
                ).encode()
            return response

    opener = ZeroOpener({"MSFT": 1, "AVGO": 1})
    result = iex.audit_owned_iex(
        owner=owner, clock=clock, runtime_id="test-owned",
        release_digest="a" * 64, symbols=("MSFT", "AVGO"),
        opener=opener, credential_reader=lambda _:
            Credentials("DATA_ONLY_DUMMY", "DATA_ONLY_DUMMY"),
    )
    assert result["both_sided_quote_count"] == 1
    assert result["missing_quote_side_count"] == 1
    assert result["fresh_and_both_sided_source_only_count"] == 1
    assert result["fresh_quote_count"] == 2
    assert result["status"] == "LATEST_QUOTES_HAVE_MISSING_IEX_SIDES_DATA_ONLY"
    assert result["financial_quote_admission_accepted"] is False
    assert all(row["executable_paper_quote_authorized"] is False
               for row in result["quotes"])



@pytest.mark.parametrize("side", ["missing_bid", "missing_ask"])
def test_zero_side_does_not_require_an_iex_exchange_for_absent_liquidity(side):
    data = quote(age=1)
    if side == "missing_bid":
        data["quote"].update(bp=Decimal(0), bs=0, bx="")
    else:
        data["quote"].update(ap=Decimal(0), **{"as": 0, "ax": None})
    row = iex.inspect_quote(
        data, symbol="MSFT", observed_ns=NOW * 10**9,
        uncertainty_ms=139,
    )
    assert row["bid_and_ask_present"] is False
    assert row["missing_one_or_both_sided_executable_quote"] is True
    assert row["executable_paper_quote_authorized"] is False



@pytest.mark.parametrize("age,uncertainty_ms,fresh", [
    (3.860, 139, True),
    (3.862, 139, False),
    (3.000, 1000, True),
    (3.001, 1000, False),
    (4.000, 0, True),
    (4.001, 0, False),
    (3.500, 1000, False),
])
def test_actual_ntp_bound_and_integer_second_quantization_are_both_counted(
    age, uncertainty_ms, fresh,
):
    data = quote(age=age)
    result = iex.inspect_quote(
        data, symbol="MSFT", observed_ns=NOW * 10**9,
        uncertainty_ms=uncertainty_ms,
    )
    assert result["provider_quote_fresh_at_sample"] is fresh
    assert result["verified_ntp_uncertainty_ms"] == uncertainty_ms
    assert result["utc_clock_sample_quantization_seconds"] == 1
    assert result["provider_quote_freshness_limit_seconds"] == 5
    assert result["executable_paper_quote_authorized"] is False
    # No source price/size, credential or generic claim of PAPER authorization.
    assert "DATA_ONLY_DUMMY" not in str(result)
    assert "100.0" not in str(result)


@pytest.mark.parametrize("invalid", [
    -1, 1001, None, True, False, 139.0, "139", [], {},
])
def test_fake_or_unbounded_ntp_uncertainty_never_treated_as_fresh(invalid):
    with pytest.raises(ValueError, match="EXACT_QUOTE_ENVELOPE"):
        iex.inspect_quote(
            quote(age=1), symbol="MSFT",
            observed_ns=NOW * 10**9, uncertainty_ms=invalid,
        )


def test_no_default_uncertainty_can_be_silently_inferred():
    with pytest.raises(TypeError):
        iex.inspect_quote(quote(age=2), symbol="MSFT", observed_ns=NOW * 10**9)


def test_real_after_inception_owner_phase_permits_only_data_observation(test_ports):
    owner, clock = test_ports
    owner._phase = "INITIAL_READBACK_ONLY"
    report, opener = _run(
        (owner, clock), dict.fromkeys(iex.WATCHLIST, 2),
        symbols=iex.WATCHLIST,
    )
    assert report["original_owner_data_only_phase"] == "INITIAL_READBACK_ONLY"
    assert report["postinception_diagnostic_never_issues_financial_grant"] is True
    assert report["fresh_quote_count"] == 4
    assert len(opener.requests) == 4
    assert report["authenticated_operational_research_issuer_accepted"] is False
    assert report["financial_quote_admission_accepted"] is False
    assert report["paper_startup_authorized"] is False
    assert report["live_trading_authorized"] is False


@pytest.mark.parametrize("phase", [
    "PREINCEPTION_COORDINATION_READY",
    "INITIAL_READBACK_PENDING",
    "LIVE_RUNNING",
    "PAPER_RUNNING",
    "CLOSED",
    None,
    True,
])
def test_intermediate_or_invented_original_owner_phase_refuses_before_credentials(
    test_ports, phase,
):
    owner, clock = test_ports
    owner._phase = phase
    with pytest.raises(ValueError, match="ORIGINAL_JOB_CLOCK_OR_SELECTED_RELEASE_REQUIRED"):
        iex.audit_owned_iex(
            owner=owner, clock=clock, runtime_id="test-owned",
            release_digest="a" * 64, symbols=("MSFT",),
            credential_reader=lambda _: pytest.fail("credentials may not be read"),
            opener=Opener({}),
        )



@pytest.mark.parametrize("event_ms,expected", (
    (0, True),     # original sample is 600ms later, fully > 139ms uncertainty
    (300, True),   # provider event is proven 300ms before central sample
    (470, False),  # 130ms < NTP uncertainty; event order is ambiguous
    (700, False),  # provider event is in the future relative to sample
    (-4_000, True),  # 4.6 seconds +139ms < 5s, no 1s floor tax
    (-4_500, False), # 5.1 seconds +139ms > 5s
))
def test_precise_original_ntp_conservatively_checks_event_arrival_order(
    event_ms, expected,
):
    data = quote(age=0)
    data["quote"]["t"] = (
        UTCSTAMP + timedelta(milliseconds=event_ms)
    ).isoformat().replace("+00:00", "Z")
    r = iex.inspect_quote(
        data, symbol="MSFT",
        observed_ns=NOW * 10**9 + 600_000_000,
        uncertainty_ms=139, observed_precision_ns=0,
    )
    assert r["provider_quote_fresh_at_sample"] is expected
    assert r["provider_event_proven_before_sample"] is (
        (600 - event_ms) >= 139
    )
    assert r["utc_clock_sample_quantization_seconds"] == 0
    assert r["verified_ntp_uncertainty_ms"] == 139
    assert r["executable_paper_quote_authorized"] is False
    assert "100." not in str(r)


@pytest.mark.parametrize("precision", (-1, 1, 300, 1_000_000_001, True, "0"))
def test_unverified_clock_precision_never_qualifies_a_quote(precision):
    with pytest.raises(ValueError, match="EXACT_QUOTE_ENVELOPE"):
        iex.inspect_quote(
            quote(age=0), symbol="MSFT",
            observed_ns=NOW*10**9 + 600_000_000,
            uncertainty_ms=139, observed_precision_ns=precision,
        )


def test_data_only_owned_rest_uses_verified_precise_clock_per_symbol(test_ports):
    r, _ = _run(test_ports, {"MSFT": 0, "AVGO": 2})
    assert r["http_get_count"] == 2
    assert r["fresh_quote_count"] == 2
    assert all(q["utc_clock_sample_quantization_seconds"] == 0
               for q in r["quotes"])
    assert all(q["provider_event_proven_before_sample"] is True
               for q in r["quotes"])
    assert r["provider_data_rights_independently_accepted"] is False
    assert r["financial_quote_admission_accepted"] is False
    assert r["paper_startup_authorized"] is False


@pytest.mark.parametrize("damage", ("forged", "missing", "future"))
def test_data_only_owned_rest_refuses_unissued_precise_clock_proof(
    monkeypatch, test_ports, damage,
):
    original, clock = test_ports
    if damage == "forged":
        monkeypatch.setattr(clock, "verify_precise", lambda sample: False)
    elif damage == "missing":
        monkeypatch.setattr(clock, "sample_precise",
                            lambda: {"utc": NOW, "uncertainty_ms": 139})
    else:
        def forged_future():
            data = clock.__class__.sample_precise(clock)
            data["utc_ns"] += 10_000_000_000
            return data
        monkeypatch.setattr(clock, "sample_precise", forged_future)
    opener = Opener({"MSFT": 2})
    with pytest.raises(ValueError, match="PRECISE_UTC_JOB_VERIFICATION_REFUSED"):
        iex.audit_owned_iex(
            owner=original, clock=clock, runtime_id="test-owned",
            release_digest="a"*64, symbols=("MSFT",),
            opener=opener,
            credential_reader=lambda _: Credentials(
                "DATA_ONLY_DUMMY", "DATA_ONLY_DUMMY"
            ),
        )
    assert len(opener.requests) == 1
