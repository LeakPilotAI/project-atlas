"""Hyperliquid R14 OFFLINE official-shaped L2 metadata and refusal diagnosis.

These cases are fixtures, NOT a retrieved BTC quote. No network, NTP,
provider budget writes, financial ledger, or service startup.
"""
import copy

import pytest

from app.adapters.hyperliquid import (
    HyperliquidPublicBookAdmissionRefused,
    _paper_book_admission_reason,
    _paper_execution_observation,
)
from scripts.observation_runtime.atlas_r14_hyperliquid_public_book_probe import (
    admit_public_book, safe_refusal_code,
)


def documented_sample():
    """L2 field layout and strings from Hyperliquid's official API reference."""
    started = 1754450974000
    observed = 1754450974800
    meta = [{
        "universe":[{
            "name":"BTC","szDecimals":5,
            "maxLeverage":40,"marginTableId":56,
        }],
        "marginTables":[],
    }, [{
        "markPx":"113382.0",
        "oraclePx":"113381.0",
        "funding":"0.0000125",
    }]]
    book = {
        "coin":"BTC",
        "time":1754450974231,
        "levels":[
            [{"px":"113377.0","sz":"7.6699","n":17},
             {"px":"113376.0","sz":"4.13714","n":8}],
            [{"px":"113397.0","sz":"0.11543","n":3}],
        ],
    }
    return started, observed, meta, book


def test_documented_l2_shape_parses_as_nonfinancial_data():
    started,observed,meta,book=documented_sample()
    assert _paper_book_admission_reason("BTC",meta,book,started,observed) is None
    parsed=_paper_execution_observation("BTC",meta,book,started,observed)
    report=admit_public_book(parsed,"BTC")
    assert report["schema"]=="ATLAS_R14_HL_PUBLIC_BOOK_DATA_ONLY_SAMPLE_V1"
    assert report["bid"]=="113377.0"
    assert report["ask"]=="113397.0"
    assert report["mark"]=="113382.0"
    assert report["provider_book_timestamp_ms"]==1754450974231
    assert report["paper_order_authorized"] is False
    assert report["live_order_authorized"] is False
    assert report["actual_financial_writer_enrolled"] is False
    assert report["provider_data_continuity_verified"] is False


@pytest.mark.parametrize("mode,expected",[
    ("late","HL_PUBLIC_BOOK_BOOK_TIMESTAMP_STALE"),
    ("future","HL_PUBLIC_BOOK_BOOK_TIMESTAMP_FUTURE"),
    ("missing","HL_PUBLIC_BOOK_BOOK_ENVELOPE"),
    ("clock_slip","HL_PUBLIC_BOOK_OBSERVATION_DURATION_EXCEEDED"),
    ("wrong_coin","HL_PUBLIC_BOOK_BOOK_COIN_MISMATCH"),
])
def test_offline_first_gate_reason_tokens_identify_exact_safe_failure(mode,expected):
    started,observed,meta,book=documented_sample()
    if mode=="late":
        book["time"]=observed-5001
    elif mode=="future":
        book["time"]=observed+1
    elif mode=="missing":
        book.pop("time")
    elif mode=="clock_slip":
        observed=started+10001
    else:
        book["coin"]="ETH"
    code=_paper_book_admission_reason("BTC",meta,book,started,observed)
    assert code is not None
    with pytest.raises(HyperliquidPublicBookAdmissionRefused) as exc:
        _paper_execution_observation("BTC",meta,book,started,observed)
    assert exc.value.reason_code==code
    assert safe_refusal_code(exc.value)==expected


def test_foreign_or_unreviewed_book_reason_never_echoes_user_data():
    secret="BAD_LEVEL_KEYS_PRIVATE_PROXY_CONTENT"
    assert safe_refusal_code(HyperliquidPublicBookAdmissionRefused(secret))==(
        "HL_PUBLIC_BOOK_ADMISSION_REFUSED")
    assert secret not in safe_refusal_code(
        HyperliquidPublicBookAdmissionRefused(secret))


def test_sample_documentation_fixtures_never_grant_live_trading():
    _,_,meta,book=documented_sample()
    mutated=copy.deepcopy(book)
    mutated["levels"][0][0]["sz"]="NaN"
    with pytest.raises(ValueError):
        _paper_execution_observation("BTC",meta,mutated,1754450974000,1754450974800)


def test_book_parsing_requires_unmodified_decimal_provider_values():
    started,observed,meta,book=documented_sample()
    mutated=copy.deepcopy(book)
    mutated["levels"][1][0]["px"]="0"
    with pytest.raises(ValueError):
        _paper_execution_observation("BTC",meta,mutated,started,observed)
