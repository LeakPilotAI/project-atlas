"""Funded rates are NOT historical oracle settlement or finance permissions."""
import json

import pytest

from scripts.observation_runtime.atlas_r20_real_hl_funding_readonly import (
    HOUR_MS,
    SCHEMA,
    SYMBOLS,
    URL,
    acquire,
    finished_hours,
    normalize,
)

NOW = 1_800_012_345_000


def rows(symbol, start, end):
    return [
        {"coin": symbol, "fundingRate": "0.0000123",
         "premium": "0.000040", "time": hour + 250}
        for hour in range(start, end, HOUR_MS)
    ]


def source_args(symbol="BTC"):
    start, end = finished_hours(now_ms=NOW, hours=3)
    return {
        "symbol": symbol, "rows": rows(symbol, start, end),
        "start_ms": start, "end_ms": end,
        "started_ms": NOW - 50, "observed_ms": NOW,
    }


def test_three_completed_hours_exclude_latest_incomplete_hour():
    a,b=finished_hours(now_ms=NOW,hours=3)
    assert (b-a)==3*HOUR_MS
    assert a%HOUR_MS == b%HOUR_MS == 0
    assert b<=NOW
    assert b == (NOW//HOUR_MS)*HOUR_MS


@pytest.mark.parametrize("hours", [0,-1,5,"3",None,True])
def test_reject_unbounded_requested_hours(hours):
    with pytest.raises(ValueError):
        finished_hours(now_ms=NOW,hours=hours)


@pytest.mark.parametrize("now_ms,hours", [(-1, 1), (0, 1), (HOUR_MS, 3), (True, 1)])
def test_reject_clock_values_without_full_completed_history(now_ms, hours):
    with pytest.raises(ValueError):
        finished_hours(now_ms=now_ms, hours=hours)


@pytest.mark.parametrize("symbol",SYMBOLS)
def test_complete_real_parser_never_grants_oracle(symbol):
    result=normalize(**source_args(symbol))
    assert result["schema"]==SCHEMA
    assert result["symbol"]==symbol
    assert result["hours"]==3
    assert result["rate_history_complete"] is True
    for key in ("historical_consensus_oracle_accepted",
                "historical_fee_schedule_accepted",
                "source_rights_accepted",
                "paper_funding_settlement_authorized",
                "paper_start_authorized",
                "live_trading_authorized"):
        assert result[key] is False


@pytest.mark.parametrize("mutation",[
    "missing_hour","duplicate_hour","wrong_coin","future_publication",
    "outside_hour","bad_rate","infinite_rate","late_provider",
    "extra_row_key"
])
def test_refuse_incomplete_conflicting_or_unbounded_original_funding(mutation):
    data=source_args()
    if mutation=="missing_hour":
        data["rows"].pop()
    elif mutation=="duplicate_hour":
        data["rows"][1]=dict(data["rows"][0])
    elif mutation=="wrong_coin":
        data["rows"][0]["coin"]="ETH"
    elif mutation=="future_publication":
        data["rows"][2]["time"]=NOW+10_000
    elif mutation=="outside_hour":
        data["rows"][1]["time"]+=HOUR_MS
    elif mutation=="bad_rate":
        data["rows"][1]["fundingRate"]="0.05"
    elif mutation=="infinite_rate":
        data["rows"][1]["fundingRate"]="NaN"
    elif mutation=="late_provider":
        data["rows"][1]["time"]+=31_000
    else:
        data["rows"][1]["settlementOracle"]="123"
    with pytest.raises((ValueError,KeyError,TypeError)):
        normalize(**data)


class FakeResponse:
    def __init__(self, symbol, start, end, *, fail=False):
        self.url=URL
        self.status_code=500 if fail else 200
        self._body=rows(symbol,start,end)
        self.content=json.dumps(self._body).encode()
    def json(self):
        return self._body


class FakeClient:
    def __init__(self, *,fail=False):
        self.calls=[]
        self.fail=fail
    def post(self, url, json):
        assert url==URL
        assert set(json)=={"type","coin","startTime","endTime"}
        assert json["type"]=="fundingHistory"
        self.calls.append(json)
        return FakeResponse(json["coin"],json["startTime"],
                            json["endTime"]+1,fail=self.fail)


def test_bounded_three_symbol_original_public_read_only_no_finance():
    client=FakeClient()
    audit=acquire(hours=3,client=client,clock_ms=lambda:NOW)
    assert audit["symbol_count"]==3
    assert audit["hours_per_symbol"]==3
    assert [r["symbol"] for r in audit["reports"]]==list(SYMBOLS)
    assert len(client.calls)==3
    assert all(c["endTime"]-c["startTime"]==3*HOUR_MS-1 for c in client.calls)
    for key in ("historical_consensus_oracle_accepted",
                "historical_fee_schedule_accepted","source_rights_accepted",
                "paper_funding_settlement_authorized","paper_start_authorized",
                "live_trading_authorized"):
        assert audit[key] is False


def test_bad_http_status_never_claims_funding():
    with pytest.raises(ValueError,match="PUBLIC_FUNDING_RECEIPT_REFUSED"):
        acquire(client=FakeClient(fail=True),clock_ms=lambda:NOW)
