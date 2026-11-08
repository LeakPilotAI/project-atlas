import json
from datetime import datetime, timedelta, timezone

import pytest
from app.investment.research_contract import public_research

from scripts.observation_runtime.r7e47cp_market_signals import analyze_market

NOW=datetime(2026,10,19,12,tzinfo=timezone.utc)


def signal():
    return analyze_market("AAPL", [{"timestamp": NOW, "Close": 102, "Volume": 10}],100,now=NOW)


def test_public_contract_preserves_unknown_baseline_and_authority():
    result=public_research(signal(),now=NOW)
    assert result["relative_volume"] is None
    assert result["relative_volume_status"] == "BASELINE_REQUIRED"
    assert result["wire_request_count"] is None
    assert result["provider_rights_status"] == "NOT_VERIFIED"
    assert not any(v for k,v in result["capabilities"].items() if k != "research_only")
    assert json.loads(json.dumps(result,allow_nan=False)) == result


@pytest.mark.parametrize("field,value", [("research_only",False),("trading_enabled",True),("network_authorized",True),("execution_authority",True),("relative_volume",2),("relative_volume_status","COMPARABLE_HISTORY"),("session","REGULAR"),("price",float("nan")),("source",None),("previous_close_status","VERIFIED")])
def test_public_contract_refuses_malformed_or_authorizing_data(field,value):
    with pytest.raises(ValueError): public_research({**signal(),field:value},now=NOW)


@pytest.mark.parametrize("delta", [-1,181])
def test_public_freshness_uses_data_time(delta):
    with pytest.raises(ValueError): public_research(signal(),now=NOW+timedelta(seconds=delta))


def test_backend_contract_not_registered_in_production_routes():
    from pathlib import Path
    root=Path(__file__).resolve().parents[1]
    assert "research_contract" not in (root/"backend/app/main.py").read_text()
    assert "offline_research" not in (root/"backend/app/api/investment_board.py").read_text()
