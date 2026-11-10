"""Selected R14 Hyperliquid public book probe: no implicit provider grant."""
import copy
import json
from pathlib import Path

import pytest

from scripts.observation_runtime import atlas_r14_hyperliquid_public_book_probe as probe


@pytest.fixture(scope="module")
def preview():
    return probe.inspect()


def fixture_book():
    return {
        "schema":"ATLAS_HYPERLIQUID_PUBLIC_BOOK_V1",
        "symbol":"BTC",
        "timestamp_basis":"PROVIDER_BOOK_MS",
        "market_book_validated":True,
        "financial_execution_authorized":False,
        "startup_authorized":False,
        "funding_settlement":None,
        "historical_settlement_oracle":None,
        "fee_schedule":None,
        "request_started_ms":123456000,
        "book_timestamp_ms":123456900,
        "observed_at_ms":123457200,
        "bid":"90000.5","ask":"90001.5",
        "bid_size":"1.25","ask_size":"2.5",
        "mark":"90001","oracle":"90000.9",
    }


def test_actual_r15_native_selected_scope_and_existing_readonly_budget(preview):
    assert preview["schema"]=="ATLAS_SELECTED_R15_HL_PUBLIC_BOOK_PREFLIGHT_V1"
    assert preview["decision"]=="REQUIRES_EXPLICIT_DATA_ONLY_SCOPE"
    assert preview["selected_code_revision"]==14
    assert preview["selected_code_verified"] is True
    assert preview["existing_request_budget"]["status"]=="EXISTING_UNAUTHORIZED_RESEARCH_BUDGET"
    # The one permitted BTC observation consumed two public info attempts; never reset it.
    assert preview["existing_request_budget"]["remaining"]==2
    assert preview["public_info_requests_per_probe"]==2
    assert preview["total_durable_budget"]==12
    for key in (
        "provider_connection_opened","private_account_accessed",
        "order_endpoint_used","market_book_observed",
        "provider_rights_independently_accepted",
        "continuous_executable_prices_verified",
        "financial_execution_authorized",
        "paper_startup_authorized","live_trading_authorized",
    ):
        assert preview[key] is False


@pytest.mark.parametrize("mode,scope,symbol",[
    (False,probe.SCOPE,"BTC"),
    (True,None,"BTC"),
    (True,"LIVE_PERPS_TRADING","BTC"),
    (True,probe.SCOPE,"DOGE"),
    (True,probe.SCOPE,"btc"),
    (True,probe.SCOPE,True),
])
def test_no_scope_or_unapproved_symbol_refused_before_gate(mode,scope,symbol):
    with pytest.raises(ValueError,match="EXPLICIT_TWO_REQUEST_PUBLIC_ONLY_SCOPE_REQUIRED"):
        probe.require_execute_scope(mode=mode,scope=scope,symbol=symbol)


def test_data_only_sample_from_strict_book_keeps_financial_permission_false():
    result=probe.admit_public_book(fixture_book(),"BTC")
    assert result["status"]=="BOUNDED_TWO_REQUEST_PUBLIC_BOOK_OBSERVED_NOT_FINANCIAL_AUTHORITY"
    assert result["bid"]=="90000.5"
    assert result["ask"]=="90001.5"
    assert result["provider_book_validated"] is True
    for name in (
        "provider_data_continuity_verified","provider_rights_independently_accepted",
        "actual_financial_writer_enrolled","paper_order_authorized",
        "live_order_authorized","automatic_startup_authorized",
    ):
        assert result[name] is False


@pytest.mark.parametrize("field,value",[
    ("schema","WRONG"),
    ("symbol","ETH"),
    ("market_book_validated",False),
    ("financial_execution_authorized",True),
    ("startup_authorized",True),
    ("funding_settlement","0"),
    ("historical_settlement_oracle","90000"),
    ("fee_schedule","claimed"),
    ("timestamp_basis","WINDOWS_TIME"),
])
def test_scope_expansion_refused(field,value):
    row=fixture_book()
    row[field]=value
    with pytest.raises(ValueError,match="SCOPE_OR_FRESHNESS_REFUSED"):
        probe.admit_public_book(row,"BTC")


@pytest.mark.parametrize("field,value",[
    ("request_started_ms",123458000),
    ("book_timestamp_ms",123458000),
    ("book_timestamp_ms",123456000-6000),
    ("observed_at_ms",123456000),
    ("observed_at_ms",123456000+11000),
    ("observed_at_ms",True),
])
def test_unusable_provider_or_clock_timestamps_refused(field,value):
    row=fixture_book()
    row[field]=value
    with pytest.raises(ValueError,match="TIMESTAMP_BOUNDS_REFUSED"):
        probe.admit_public_book(row,"BTC")


@pytest.mark.parametrize("field,value",[
    ("bid","NaN"),("ask","Infinity"),
    ("bid","0"),("ask","-2"),
    ("ask","90000.5"),("ask","90000.4"),
    ("bid",100.0),("bid_size","abc"),
    ("oracle",None),("mark","0"),
])
def test_malformed_crossed_or_nonfinite_book_refused(field,value):
    row=fixture_book()
    row[field]=value
    with pytest.raises(ValueError,match="DECIMALS_REQUIRED|POSITIVE_UNCROSSED_REQUIRED"):
        probe.admit_public_book(row,"BTC")


def test_unscoped_cli_never_constructs_real_clock_or_request_gate(monkeypatch,capsys):
    monkeypatch.setattr(probe,"IndependentNtpClock",
                        lambda **_:pytest.fail("NTP_OR_NETWORK_STARTED"))
    monkeypatch.setattr(probe,"HyperliquidRequestGate",
                        lambda *_args,**_kw:pytest.fail("BUDGET_OPENED"))
    assert probe.main(["--execute-data-only","--symbol","BTC"])==1
    result=json.loads(capsys.readouterr().out)
    assert result["status"]=="REFUSED"
    assert result["financial_execution_authorized"] is False


def test_offline_inspect_never_constructs_clock_or_provider_client(monkeypatch,capsys):
    monkeypatch.setattr(probe,"IndependentNtpClock",
                        lambda **_:pytest.fail("NTP_STARTED"))
    monkeypatch.setattr(probe,"HyperliquidAdapter",
                        lambda:pytest.fail("PROVIDER_CONNECTION_OPENED"))
    monkeypatch.setattr(probe,"HyperliquidRequestGate",
                        lambda *_args,**_kw:pytest.fail("WRITABLE_LEDGER_STARTED"))
    assert probe.main(["--inspect"])==0
    result=json.loads(capsys.readouterr().out)
    assert result["selected_code_revision"]==14
    assert result["provider_connection_opened"] is False
    assert result["financial_execution_authorized"] is False


def test_explicit_scope_refuses_if_two_attempts_are_not_available(monkeypatch):
    original=probe.inspect()
    original["existing_request_budget"]["remaining"]=1
    monkeypatch.setattr(probe,"inspect",lambda:original)
    monkeypatch.setattr(probe,"IndependentNtpClock",
                        lambda **_:pytest.fail("CLOCK_MUST_NOT_START"))
    monkeypatch.setattr(probe,"HyperliquidRequestGate",
                        lambda *_args,**_kw:pytest.fail("NO_LEDGER_OPEN"))
    with pytest.raises(ValueError,match="ENROLLED_BUDGET_NOT_AVAILABLE"):
        probe.execute_data_only(symbol="BTC",confirm_scope=probe.SCOPE)


def test_missing_direct_api_scope_refuses_before_operational_preflight():
    with pytest.raises(TypeError):
        probe.execute_data_only(symbol="BTC")
    with pytest.raises(ValueError,match="EXPLICIT_TWO_REQUEST_PUBLIC_ONLY_SCOPE_REQUIRED"):
        probe.execute_data_only(symbol="BTC",confirm_scope="NO")


def test_real_ntp_anchor_math_preserves_millisecond_precision_without_windows_clock(monkeypatch):
    class FakeExactNtp:
        def __init__(self):
            self._anchor={"mono_ns":10_000_000_000,
                          "utc_ns":1762800000123456789}
        def sample(self):
            return {"source":probe.CLOCK_SOURCE,
                    "utc":1762800001,
                    "monotonic_ns":11_500_000_000}
    monkeypatch.setattr(probe,"IndependentNtpClock",FakeExactNtp)
    assert probe.independent_utc_ms(FakeExactNtp())==1762800001623


def test_wrong_clock_anchor_or_foreign_source_refuses(monkeypatch):
    class FakeExactNtp:
        _anchor={"mono_ns":10_000_000_000,"utc_ns":1762800000123456789}
        def sample(self):
            return {"source":probe.CLOCK_SOURCE,
                    "utc":1762800000,
                    "monotonic_ns":11_500_000_000}
    monkeypatch.setattr(probe,"IndependentNtpClock",FakeExactNtp)
    with pytest.raises(ValueError,match="MILLISECOND_MISMATCH"):
        probe.independent_utc_ms(FakeExactNtp())


def test_foreign_injected_clock_is_not_natively_qualified():
    with pytest.raises(ValueError,match="REAL_INDEPENDENT_NTP_CLOCK_REQUIRED"):
        probe.independent_utc_ms(object())


def test_provider_refusal_categorization_is_sanitized_without_exception_details():
    import httpx
    from app.adapters.hyperliquid import HyperliquidPublicBookAdmissionRefused
    from app.adapters.hyperliquid_request_gate import RequestGateRefused
    secret = 'DO_NOT_PRINT_EXAMPLE_CREDENTIAL_MATERIAL'
    cases = [
        (RequestGateRefused(secret), "HL_REQUEST_BUDGET_OR_GATE_REFUSED"),
        (httpx.TimeoutException(secret), "HL_PUBLIC_HTTP_TIMEOUT"),
        (httpx.RequestError(secret), "HL_PUBLIC_TRANSPORT_REFUSED"),
        (HyperliquidPublicBookAdmissionRefused(secret), "HL_PUBLIC_BOOK_ADMISSION_REFUSED"),
        (ValueError("NTP_REFRESH_FAILED_CAPABILITY_REVOKED"), "HL_INDEPENDENT_NTP_REFUSED"),
        (ValueError(secret), "HL_SOURCE_OR_DATA_VALIDATION_REFUSED"),
    ]
    for error, code in cases:
        result=probe.safe_refusal_code(error)
        assert result==code
        assert secret not in result


def test_http_status_classification_does_not_echo_provider_body():
    import httpx
    request=httpx.Request("POST","https://api.hyperliquid.xyz/info")
    response=httpx.Response(429,request=request)
    error=httpx.HTTPStatusError("private response detail",request=request,response=response)
    assert probe.safe_refusal_code(error)=="HL_PUBLIC_HTTP_STATUS_REFUSED"


def test_current_r15_refused_promotion_stops_before_request_budget_and_ntp(
        monkeypatch,capsys):
    from scripts.observation_runtime import atlas_r15_paper_offline_commissioning as r15
    original=r15.inspect()
    for field,value in (
        ('decision','GO'),
        ('selected_native_revision',13),
        ('native_hyperliquid_forward_writer_enrolled',True),
        ('provider_connection_opened',True),
        ('financial_operating_gates_independently_accepted',1),
    ):
        monkeypatch.setattr(
            r15,'inspect',lambda f=field,v=value: {**original,f:v})
        monkeypatch.setattr(probe,'HyperliquidRequestGate',
                            lambda *_a,**_kw:pytest.fail('BUDGET_MUTATED'))
        monkeypatch.setattr(probe,'IndependentNtpClock',
                            lambda **_kw:pytest.fail('NTP_STARTED'))
        monkeypatch.setattr(probe,'HyperliquidAdapter',
                            lambda:pytest.fail('PUBLIC_INFO_REQUEST_STARTED'))
        rc=probe.main([
            '--execute-data-only','--confirm-scope',probe.SCOPE,
            '--symbol','BTC'])
        output=json.loads(capsys.readouterr().out)
        assert rc==1
        assert output['financial_execution_authorized'] is False
        assert output['live_order_authorized'] is False


def test_selected_r15_preview_refuses_provider_network_or_budget_writes(
        monkeypatch,capsys):
    monkeypatch.setattr(probe,'HyperliquidRequestGate',
                        lambda *_a,**_kw:pytest.fail('BUDGET_WRITTEN'))
    monkeypatch.setattr(probe,'HyperliquidAdapter',
                        lambda:pytest.fail('INFO_REQUEST_STARTED'))
    monkeypatch.setattr(probe,'IndependentNtpClock',
                        lambda **_kw:pytest.fail('NTP_STARTED'))
    assert probe.main(['--inspect'])==0
    data=json.loads(capsys.readouterr().out)
    assert data['schema']=='ATLAS_SELECTED_R15_HL_PUBLIC_BOOK_PREFLIGHT_V1'
    assert data['selected_code_revision']==14
    assert data['existing_request_budget']['remaining']==2
    assert data['provider_connection_opened'] is False
    assert data['financial_execution_authorized'] is False


def test_future_authorized_r15_sample_uses_current_release_label_with_stubbed_provider(
        monkeypatch):
    # No request-gate installation, durable budget spend, NTP or HTTP.
    current=probe.inspect()
    assert current["selected_code_revision"]==14
    monkeypatch.setattr(probe,"inspect",lambda:current)
    class FakeGate:
        def remaining(self):return 2
    monkeypatch.setattr(probe,"HyperliquidRequestGate",lambda *_a,**_kw:FakeGate())
    monkeypatch.setattr(probe.hyperliquid_gate_registry,"install_gate",
                        lambda gate:None)
    class FakeClock:
        def __init__(self,*,runtime_id):
            self.identity=runtime_id
        def require_operational(self,identity):
            assert identity==self.identity
            assert identity.startswith("atlas-r15-hl-public-book-btc-data-only")
        def revoke(self):pass
    monkeypatch.setattr(probe,"IndependentNtpClock",FakeClock)
    async def fake_two_requests(symbol,clock,identity,gate):
        assert symbol=="BTC"
        assert type(clock) is FakeClock
        return fixture_book()
    monkeypatch.setattr(probe,"_perform_two_requests",fake_two_requests)
    admitted=probe.execute_data_only(symbol="BTC",confirm_scope=probe.SCOPE)
    assert admitted["schema"]=="ATLAS_R15_HL_PUBLIC_BOOK_DATA_ONLY_SAMPLE_V1"
    assert admitted["selected_native_revision"]==14
    assert admitted["selected_native_release"]==current["selected_code_release"]
    assert admitted["provider_book_validated"] is True
    assert admitted["paper_order_authorized"] is False
    assert admitted["live_order_authorized"] is False
    assert admitted["automatic_startup_authorized"] is False
