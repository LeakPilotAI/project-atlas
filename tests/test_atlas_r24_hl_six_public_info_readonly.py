"""Disposable raw Hyperliquid six-frame review; no HTTP, broker or PAPER."""
import copy
import hashlib
import json

import pytest

from scripts.observation_runtime import atlas_r24_hl_six_public_info_readonly as hl

T = 1_800_000_000_000
HOUR = (T // hl.HOUR_MS + 1) * hl.HOUR_MS


def frame(kind, coin, t, observed, value):
    raw = json.dumps(value, separators=(",", ":"), sort_keys=True)
    return {"type":kind, "coin":coin, "started_ms":t,
            "observed_ms":observed,
            "raw_json":raw,"raw_sha256":hashlib.sha256(raw.encode()).hexdigest()}


def data():
    symbols=hl.SYMBOLS
    metadata=[
       {"universe":[{"name":x, "maxLeverage":20,
                      "szDecimals":4} for x in symbols],
        "marginTables":[]},
       [{"markPx":"300", "oraclePx":"300", "funding":"0.0001"}
        for _ in symbols],
    ]
    def forecasts(rate="0.00001",nexttime=HOUR):
        return [[coin,[["HlPerp",{"fundingRate":rate,
                                "nextFundingTime":nexttime}],
                       ["BinPerp",{"fundingRate":"0.0003",
                                  "nextFundingTime":nexttime}]]]
                for coin in symbols]
    frames=[frame("metaAndAssetCtxs",None,T,T+100,metadata),
            frame("predictedFundings",None,T+200,T+300,forecasts())]
    for i,coin in enumerate(symbols):
        start=T+400+i*200
        book={"coin":coin,"time":start+20,"levels":[
            [{"px":"299.9","sz":"3","n":1}],
            [{"px":"300.1","sz":"2","n":2}]]}
        frames.append(frame("l2Book",coin,start,start+100,book))
    frames.append(frame("predictedFundings",None,T+11_000,T+11_100,
                        forecasts(rate="0.000011")))
    return frames


def replace_raw(record,value):
    raw=json.dumps(value,sort_keys=True,separators=(",",":"))
    record["raw_json"]=raw
    record["raw_sha256"]=hashlib.sha256(raw.encode()).hexdigest()


def test_original_six_public_bytes_and_two_forecasts_stay_nonfinancial():
    result=hl.inspect_exact_six(frames=data(),ntp_uncertainty_ms=139)
    assert result["schema"]==hl.SCHEMA
    assert result["real_public_info_requests"]==6
    assert result["reserved_max_info_weight"]==66
    assert set(result["books"])==set(hl.SYMBOLS)
    assert all(result["first_funding"][s]["next_funding_ms"]==HOUR
               for s in hl.SYMBOLS)
    assert result["second_funding"]["BTC"]["rate"]=="0.000011"
    assert result["historical_settlement_oracle_accepted"] is False
    assert result["account_fee_tier_accepted"] is False
    assert result["provider_data_rights_accepted"] is False
    assert result["original_source_issuer_commissioned"] is False
    assert result["paper_start_authorized"] is False
    assert result["live_trading_authorized"] is False


@pytest.mark.parametrize("damage", [
    "short_list","long_list","changed_kind","wrong_coin",
    "changed_hash","too_big","duplicate_json","early_forecast",
    "late_forecast","new_hour_beyond_75sec","clock_reversed",
    "clock_excess","clock_forged_type","wrong_utc_bound",
])
def test_malformed_transport_and_clock_are_all_refused(damage):
    rows=data()
    ntp=139
    if damage=="short_list":
        rows.pop()
    elif damage=="long_list":
        rows.append(copy.deepcopy(rows[-1]))
    elif damage=="changed_kind":
        rows[2]["type"]="fundingHistory"
    elif damage=="wrong_coin":
        rows[2]["coin"]="ETH"
    elif damage=="changed_hash":
        rows[3]["raw_json"]+=" "
    elif damage=="too_big":
        rows[1]["raw_json"]=" "*hl.MAX_BYTES+"x"
    elif damage=="duplicate_json":
        rows[1]["raw_json"]='{"dup":1,"dup":2}'
        rows[1]["raw_sha256"]=hashlib.sha256(rows[1]["raw_json"].encode()).hexdigest()
    elif damage=="early_forecast":
        rows[5]["started_ms"]=T+1000
        rows[5]["observed_ms"]=T+1100
    elif damage=="late_forecast":
        rows[5]["started_ms"]=T+100_000
        rows[5]["observed_ms"]=T+100_100
    elif damage=="new_hour_beyond_75sec":
        rows[5]["started_ms"]=T+75_001
        rows[5]["observed_ms"]=T+75_010
    elif damage=="clock_reversed":
        rows[4]["observed_ms"]=rows[4]["started_ms"]-1
    elif damage=="clock_excess":
        rows[4]["observed_ms"]=rows[4]["started_ms"]+5001
    elif damage=="clock_forged_type":
        rows[2]["started_ms"]=True
    else:
        ntp=1001
    with pytest.raises((ValueError,TypeError)):
        hl.inspect_exact_six(frames=rows,ntp_uncertainty_ms=ntp)


@pytest.mark.parametrize("damage", [
    "past_hour","future_hour_plus_one","unequal_btc",
    "missing_coin","duplicate_coin","missing_hl_venue",
    "duplicate_hl_venue","rate_infinite","rate_bad",
    "stamp_float","wrong_next_field","rate_number",
    "second_stale","second_hour_changed","rates_differ_ok",
])
def test_actual_hl_forecast_hours_no_stale_or_fake_funding(damage):
    rows=data()
    j=1 if damage not in ("second_stale","second_hour_changed") else 5
    payload=json.loads(rows[j]["raw_json"])
    if damage=="past_hour" or damage=="second_stale":
        payload[0][1][0][1]["nextFundingTime"]=HOUR-hl.HOUR_MS
    elif damage=="future_hour_plus_one" or damage=="second_hour_changed":
        payload[0][1][0][1]["nextFundingTime"]=HOUR+hl.HOUR_MS
    elif damage=="unequal_btc":
        payload[0][1][0][1]["nextFundingTime"]=HOUR-500
    elif damage=="missing_coin":
        payload.pop()
    elif damage=="duplicate_coin":
        payload.append(copy.deepcopy(payload[0]))
    elif damage=="missing_hl_venue":
        payload[0][1].pop(0)
    elif damage=="duplicate_hl_venue":
        payload[0][1].append(copy.deepcopy(payload[0][1][0]))
    elif damage=="rate_infinite":
        payload[0][1][0][1]["fundingRate"]="NaN"
    elif damage=="rate_bad":
        payload[0][1][0][1]["fundingRate"]="0.05"
    elif damage=="stamp_float":
        payload[0][1][0][1]["nextFundingTime"]=float(HOUR)
    elif damage=="wrong_next_field":
        payload[0][1][0][1]["another"]="ignored"
    elif damage=="rate_number":
        payload[0][1][0][1]["fundingRate"]=0.001
    elif damage=="rates_differ_ok":
        payload[0][1][0][1]["fundingRate"]="0.000012"
    replace_raw(rows[j],payload)
    if damage=="rates_differ_ok":
        assert hl.inspect_exact_six(frames=rows,ntp_uncertainty_ms=139)[
            "paper_start_authorized"] is False
    else:
        with pytest.raises(ValueError):
            hl.inspect_exact_six(frames=rows,ntp_uncertainty_ms=139)


@pytest.mark.parametrize("damage", [
    "book_stale","book_future","book_one_side","book_crossed",
    "book_wrong_coin","meta_duplicate","meta_missing","market_delisted",
])
def test_original_book_parser_cannot_be_bypassed(damage):
    rows=data()
    payload=json.loads(rows[2]["raw_json"])
    meta=json.loads(rows[0]["raw_json"])
    if damage=="book_stale":
        payload["time"]=rows[2]["observed_ms"]-6000
    elif damage=="book_future":
        payload["time"]=rows[2]["observed_ms"]+1
    elif damage=="book_one_side":
        payload["levels"][1]=[]
    elif damage=="book_crossed":
        payload["levels"][0][0]["px"]="310"
    elif damage=="book_wrong_coin":
        payload["coin"]="ETH"
    elif damage=="meta_duplicate":
        meta[0]["universe"][1]["name"]="BTC"
    elif damage=="meta_missing":
        meta[0]["universe"].pop()
    elif damage=="market_delisted":
        meta[0]["universe"][0]["isDelisted"]=True
    if damage.startswith("meta_") or damage=="market_delisted":
        replace_raw(rows[0],meta)
    else:
        replace_raw(rows[2],payload)
    with pytest.raises(ValueError):
        hl.inspect_exact_six(frames=rows,ntp_uncertainty_ms=139)


def test_injected_synthetic_funding_time_no_rights_grant():
    # A fake all-green bundle can never grant real E1 or trading permissions.
    sample=hl.inspect_exact_six(frames=data(),ntp_uncertainty_ms=0)
    assert sample["provider_data_rights_accepted"] is False
    assert sample["ongoing_source_continuity_proven"] is False
    assert sample["historical_settlement_oracle_accepted"] is False
    assert sample["financial_accounts_initialized"] is False
    assert sample["paper_start_authorized"] is False
