import json

import pytest
from app.backtest.io import load_historical_contexts


@pytest.mark.parametrize("field,value",[(f,v) for f in ("open_interest_usd","volume_24h_usd") for v in ("nan","inf","-inf",True)]+[("close",True),("funding_rate",True),("volume","nan"),("high",99)])
def test_invalid_numeric_context_is_refused(tmp_path,field,value):
    row={"timestamp":"2026-01-01T00:00:00Z","symbol":"BTC","timeframe":"5m","open":100,"high":101,"low":99,"close":100,"volume":1,"open_interest_usd":1000,"volume_24h_usd":2000,"htf_trend":"UP"}
    row[field]=value
    path=tmp_path/"fixture.jsonl";path.write_text(json.dumps(row)+"\n",encoding="utf-8")
    with pytest.raises(ValueError):load_historical_contexts(path)
